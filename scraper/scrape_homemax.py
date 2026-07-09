"""
scrape_homemax.py
------------------
Скрапер за HomeMax (home-max.bg).

Стартиране самостоятелно (за тест):
    python scrape_homemax.py
"""

import json
import time
import requests
from bs4 import BeautifulSoup

STORE_ID = "homemax"
STORE_NAME = "Homemax"
BASE_URL = "https://www.home-max.bg"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

# ВАЖНО: id-тата тук трябва да СЪВПАДАТ с id-тата, които вече ползваш в
# scrape_praktiker.py за същия материал — иначе run_all.py ще създаде
# ДВА отделни продукта, вместо да ги съпостави в едно и също сравнение.
#
# "unit_size": ако продуктът се продава в опаковка, покриваща повече от
# 1 базова единица (напр. пакет ламперия = 2.65 м²), посочи тук колко
# базови единици има в опаковката. Скрапера първо се опитва да намери
# директно показаната от HomeMax цена за базовата единица (напр. "Цена
# за кв.м.") някъде на страницата; ако не успее, изчислява цена за
# базовата единица като раздели цената на опаковката на "unit_size".
# Ако продуктът се продава на брой/чувал като цяло (напр. чувал цимент),
# просто НЕ задавай "unit_size" — цената на опаковката си Е базовата.
PRODUCTS = {
    "cement-42-5-25kg": {  # <- същото id като в scrape_praktiker.py!
        "url": f"{BASE_URL}/ciment-bravo-42-5-n-torbi-po-25-kg-devnya/",
        "name": "Цимент 42.5, 25 кг",
        "category": "Цимент и бетон",
        "unit": "чувал",
        "label": "Цимент Bravo 42,5 N торби по 25 кг Девня",
    },
    # ЗАБЕЛЕЖКА: beton-suha-smes-25kg, zamazka-samorazlivna-25kg и
    # hidroizolacia-kristalizirashta-25kg бяха премахнати оттук — категория
    # "Цимент и бетон" се преизгражда само с 3 нови вида продукта. Замазката
    # (Ceresit CN68, url: samorazlivna-zamazka-ceresit-cn68-25-kg) ще се
    # добави отново при новите изисквания — засега умишлено я няма.
    "vintovertka-akum-18v": {  # <- същото id като в scrape_praktiker.py!
        "url": f"{BASE_URL}/akumulatoren-vintovert-bosch-universaldrill-18v-2-1-5-ah/",
        "name": "Акумулаторна винтоверта 18V, 2 батерии",
        "category": "Инструменти",
        "unit": "брой",
        "label": "Акумулаторен винтоверт BOSCH UniversalDrill 18V 2x1.5 Ah",
    },
    # ... добави останалите продукти тук
}


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    # Debug: пази последната изтеглена страница, за да провериш реалния
    # HTML, ако цената/снимката не се хванат правилно.
    with open("test.html", "w", encoding="utf-8") as f:
        f.write(resp.text)

    return resp.text


# Ключови думи, показващи, че даден "Цена за ..." етикет се отнася за
# ОПАКОВКА (пакет, к-т и т.н.), а не за базова мерна единица. Такива
# редове ги прескачаме — искаме само м², кг, г, л и т.н.
_PACKAGE_KEYWORDS = ("пакет", "к-т", "комплект", "стек", "опаковка", "кутия", "палет")

# Ключови думи, показващи, че етикетът Е за базова мерна единица.
_BASE_UNIT_KEYWORDS = ("кв.м", "м2", "м²", "кг", "гр.", "грам", "литър", " л.")


def _is_package_label(label: str) -> bool:
    low = (label or "").lower()
    return any(kw in low for kw in _PACKAGE_KEYWORDS)


def _is_base_unit_label(label: str) -> bool:
    low = (label or "").lower()
    return any(kw in low for kw in _BASE_UNIT_KEYWORDS)


def _eur_price_from_price_box(container) -> float | None:
    """От контейнер с .price-item-wrapper (маркъп на HomeMax) взема САМО
    стойността, чиято валута е '€' (не 'ЛВ.')."""
    for wrapper in container.select(".price-item-wrapper"):
        currency_el = wrapper.select_one(".currency")
        holder_el = wrapper.select_one(".price-holder")
        if not currency_el or not holder_el:
            continue
        if currency_el.get_text(strip=True) != "€":
            continue
        raw = holder_el.get_text(strip=True)
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _price_from_jsonld_eur(soup: BeautifulSoup):
    """schema.org JSON-LD — взема цената, САМО ако валутата е изрично EUR.
    Това Е цената на опаковката/бройката, не непременно на базовата
    мерна единица."""
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if isinstance(offers, dict) and offers.get("price"):
                if offers.get("priceCurrency") != "EUR":
                    continue
                try:
                    return float(str(offers["price"]).replace(",", "."))
                except ValueError:
                    continue
    return None


def _package_price_eur(soup: BeautifulSoup):
    """Цената на цялата опаковка/бройка в евро (НЕ на базовата единица)."""
    # 1) Директен елемент с data-price от кутията "Крайна цена с ДДС".
    eur_el = soup.select_one(".total-price-value-eur")
    if eur_el and eur_el.get("data-price"):
        try:
            return float(eur_el["data-price"])
        except ValueError:
            pass

    # 2) JSON-LD (schema.org), само ако валутата е EUR.
    price = _price_from_jsonld_eur(soup)
    if price is not None:
        return price

    # 3) Последна опора: generic price box, само стойността до "€".
    for box in soup.select(".price-box, .final-prices-box"):
        price = _eur_price_from_price_box(box)
        if price is not None:
            return price

    return None


def _find_own_base_unit_price(soup: BeautifulSoup, page_url: str):
    """HomeMax понякога показва навсякъде по страницата (напр. в блокове
    "подобни продукти") картичка за СЪЩИЯ продукт, с етикет "Цена за
    кв.м." (или др. базова единица) точно до цената в евро — тази
    стойност е точната цена за базовата единица, директно от магазина,
    без да се налага ние да делим ръчно."""
    from urllib.parse import urlparse

    target_path = urlparse(page_url).path.rstrip("/")

    for box in soup.select(".product-box-item"):
        link = box.select_one("a[href]")
        if not link:
            continue
        href = link.get("href", "")
        href_path = urlparse(href).path.rstrip("/") if href.startswith("http") else href.rstrip("/")
        if href_path != target_path:
            continue  # различен продукт, пропускаме

        info_el = box.select_one(".price-info-text")
        label = info_el.get_text(" ", strip=True) if info_el else ""
        if not label or _is_package_label(label) or not _is_base_unit_label(label):
            continue

        price_box = box.select_one(".price-box")
        if not price_box:
            continue
        price = _eur_price_from_price_box(price_box)
        if price is not None:
            return price

    return None


def parse_price(html: str, page_url: str, unit_size: float | None = None):
    """Извлича цената в ЕВРО за БАЗОВАТА мерна единица (м², кг, г...),
    НЕ за опаковка/пакет.

    Логика:
    1) Опитваме се да намерим директно показана от HomeMax цена за
       базовата единица (напр. "Цена за кв.м.") за същия продукт.
    2) Ако не успеем, вземаме цената на цялата опаковка/бройка в евро и,
       ако е зададен "unit_size" за продукта, я разделяме на него.
    3) Ако продуктът няма unit_size (значи опаковката Е базовата
       единица, напр. чувал цимент), връщаме цената на опаковката.
    """
    soup = BeautifulSoup(html, "lxml")

    base_price = _find_own_base_unit_price(soup, page_url)
    if base_price is not None:
        return base_price

    package_price = _package_price_eur(soup)
    if package_price is None:
        return None

    if unit_size:
        return round(package_price / unit_size, 2)

    return package_price


def parse_image(html: str, page_url: str):
    soup = BeautifulSoup(html, "lxml")

    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        return og_image["content"]

    img_el = soup.select_one(".product-gallery img, .product-image img, [itemprop='image']")
    if img_el:
        src = img_el.get("src") or img_el.get("data-src")
        if src:
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("/"):
                return BASE_URL + src
            return src

    return None


def scrape_all(delay_seconds: float = 1.5) -> dict:
    """Обхожда всички продукти на HomeMax от PRODUCTS и връща:
    {
      product_id: {
        "price": 12.77,            # ВИНАГИ в евро, за базовата мерна единица
        "image": "https://.../snimka.jpg",
        "url": "https://.../produkt",
        "label": "...",
        "name": "...",
        "category": "...",
        "unit": "..."
      }
    }
    """
    results = {}
    for product_id, info in PRODUCTS.items():
        url = info["url"]
        try:
            html = fetch_page(url)
            price = parse_price(html, url, unit_size=info.get("unit_size"))
            if price is not None:
                results[product_id] = {
                    "price": price,
                    "image": parse_image(html, url),
                    "url": url,
                    "label": info.get("label"),
                    "name": info.get("name", product_id),
                    "category": info.get("category", "Некатегоризирани"),
                    "unit": info.get("unit", "брой"),
                }
            else:
                print(f"[{STORE_ID}] Не намерих цена за {product_id} ({url})")
        except requests.RequestException as e:
            print(f"[{STORE_ID}] Грешка при {url}: {e}")

        time.sleep(delay_seconds)  # учтива пауза между заявките

    return results


if __name__ == "__main__":
    found = scrape_all()
    print(f"{STORE_ID}: намерени {len(found)} цени")
    for pid, info in found.items():
        print(f"  {pid}: {info['price']:.2f} € ({info.get('label') or info['name']})")
