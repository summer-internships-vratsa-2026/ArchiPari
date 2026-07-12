"""
scrape_praktiker.py
--------------------
Скрапер за Praktiker.
 
Стартиране самостоятелно (за тест):
    python scrape_praktiker.py
"""
 
import json
import time
import requests
from bs4 import BeautifulSoup
 
STORE_ID = "praktiker"
STORE_NAME = "Praktiker"
BASE_URL = "https://www.praktiker.bg"
 
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}
 
# Съпоставяне: вътрешен id на продукт -> данни за него в Praktiker.
# "name", "category" и "unit" се ползват само за автоматично създаване
# на нов продукт в data/products.json, ако той още го няма там.
PRODUCTS = {
    "lepilo-plochki-ceresit-cm11-25kg": {
        "url": f"{BASE_URL}/bg/Lepila-za-plochki/LEPILO-ZA-PLOChKI-CERESIT-CM-11-SIV/p/432837",
        "name": "Лепило за плочки Ceresit CM 11, 25 кг",
        "category": "Плочки и настилки",
        "unit": "чувал",
        "label": "ЛЕПИЛО ЗА ПЛОЧКИ CERESIT CM 11 СИВ, клас C1T, 25 кг",
    },
    "gipsokarton-sonicboard-12-5-1200x2000": {
        "url": f"{BASE_URL}/bg/Gipskarton/GIPSKARTON-SONICBOARD-1200-2000-12-5MM-KNAUF-A13/p/238154",
        "name": "Гипсокартон 12.5 мм, 1200/2000 мм",
        "category": "Гипсокартон и мазилки",
        "unit": "бр.",
        "label": "ГИПСКАРТОН SONICBOARD 1200/2000/12,5ММ KNAUF A13",
        # ВАЖНО: продуктът НЕ се продава онлайн при Praktiker (само в
        # магазин) - при скрейпване с requests може да върне грешна/липсваща
        # цена, ако страницата показва "Продуктът не се продава онлайн"
        # вместо реална цена. Провери test.html при първо пускане.
    },
    "mazilka-silikonova-d15-draskana-25kg": {
        "url": f"{BASE_URL}/Mazilki/SILIKONOVA-MAZILKA-DRASKANA-D1-5-DEKO-Professional/p/471751",
        "name": "Силиконова мазилка D1,5, драскана, 25kg",
        "category": "Бои и лакове",
        "unit": "кофа",
        "label": "СИЛИКОНОВА МАЗИЛКА ДРАСКАНА Д1.5 DEKO Professional, 25 кг",
    },
    "pvc-lamperiya-wood": {
        # ЗАБЕЛЕЖКА: продуктовото "name" тук е material-неутрално нарочно —
        # реалният продукт е 3D MDF ламперия (не PVC!), докато при HomeMax
        # е истинска PVC ламперия. Виж matchNote в data/products.json.
        # run_all.py презаписва "name" САМО ако продуктът тепърва се
        # създава — за съществуващ продукт стойността в products.json има
        # превес, затова смени я и тук, за да останат в синхрон.
        "url": f"{BASE_URL}/Lamperiya/3D-MDF-LAMPERIYa-KRONO-ORIGINAL-KRONOWALL-DAB-SANDANS/p/142328",
        "name": "Стенна ламперия за интериор (цена за м²)",
        "category": "Дърво и ОСБ",
        "unit": "м²",
        "label": "3D MDF ламперия Krono Original Kronowall, дъб Сандан",
    },
    # ЗАБЕЛЕЖКА: beton-suha-smes-25kg, zamazka-samorazlivna-25kg и
    # hidroizolacia-kristalizirashta-25kg бяха премахнати оттук — категория
    # "Цимент и бетон" се преизгражда само с 3 нови вида продукта (Портланд
    # цимент CEM II 42.5R, Сух бетон B20, Саморазливна подова замазка).
    # Саморазливната замазка ще се добави отново, когато е готова с новите
    # изисквания (Weberfloor 4010 25 kg) — засега умишлено я няма.
    "cement-42-5-25kg": {
        "url": f"{BASE_URL}/Tziment-i-preobrazuvateli/TzIMENT-HOLCIM-TzIMENT-CEM-II-B-LL-42-5R/p/496669",
        "name": "Цимент 42.5, 25 кг",
        "category": "Цимент и бетон",
        "unit": "чувал",
        "label": "ЦИМЕНТ HOLCIM ЦИМЕНТ CEM II/B-LL 42.5R",
    },
    "vintovertka-akum-18v": {
        # ПОПРАВЕНО: старият URL сочеше към "АКУМУЛАТОРНА УДАРНА БОРМАШИНА"
        # (Black&Decker BDCHD18BAFC-QW) — това е УДАРЕН инструмент, различна
        # категория от "винтоверт" (при HomeMax/Inex/GStroy офертите за
        # този продукт са всички от типа "бормашина-винтоверт" БЕЗ ударна
        # функция: Bosch UniversalDrill, Metabo BS18L, Bosch GSR 18V-50).
        # Заменено с реален, наличен продукт от същия клас: Bosch
        # Professional GSR 185-LI — самата страница на Praktiker го описва
        # изрично като "Акумулаторният винтоверт GSR 185-LI Professional",
        # без ударна функция. Проверено на живо (юли 2026): в наличност,
        # 168.70 € / 329.95 лв.
        "url": f"{BASE_URL}/Akumulatorni-bormashini-i-vintoverti/AKUMULATORNA-BEZChETKOVA-BORMAShINA-BOSCH-PROFESSIONAL-GSR-185-Li/p/144086",
        "name": "Акумулаторен винтоверт 18V, 2 батерии",
        "category": "Инструменти",
        "unit": "брой",
        "label": "АКУМУЛАТОРЕН ВИНТОВЕРТ BOSCH PROFESSIONAL GSR 185 Li 18V, 50Nm, 2х2.0Ah",
    },
    # ... добави останалите продукти тук, по същия модел
}
 
 
def fetch_page(url: str, attempts: int = 3) -> str:
    """Praktiker понякога отговаря бавно на отделни продуктови страници
    (видяно на живо: "Read timed out" при SAMORAZLIVNA-ZAMAZKA-CN-68,
    докато всички други продукти минават нормално) — най-вероятно моментно
    претоварване на техния сървър, не постоянен проблем с конкретния URL.
    Затова: до `attempts` опита с нарастващ timeout, вместо целият продукт
    да отпадне заради една бавна секунда."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15 + attempt * 10)
            resp.raise_for_status()

            # Оставено за debug — презаписва се на всяка заявка, така че пази
            # само последната изтеглена страница. Полезно е при настройване на
            # селектора в parse_price(), но не е нужно за нормална работа.
            with open("test.html", "w", encoding="utf-8") as f:
                f.write(resp.text)

            return resp.text
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < attempts:
                time.sleep(2 * attempt)  # кратка пауза преди следващия опит
    raise last_error
 
 
# Ключови думи, по които разпознаваме, че даден ценови ред е за ОПАКОВКА
# (пакет, стек, к-т и т.н.), а не за базовата мерна единица (м², кг, г...).
# Такива редове НЕ трябва да се вземат — искаме само цената за базовата
# единица, както се показва при "Цена М2:", "Цена КГ:" и т.н.
_PACKAGE_KEYWORDS = ("пакет", "к-т", "комплект", "стек", "опаковка", "кутия", "палет")


def _is_package_label(label: str) -> bool:
    if not label:
        return False
    low = label.lower()
    return any(kw in low for kw in _PACKAGE_KEYWORDS)


def _extract_eur_price(item) -> float | None:
    """От елемент .product-store-prices__item взема САМО стойността в
    евро (не в лева) от вложените .product-price подредове."""
    for price_el in item.select(".product-price"):
        text = price_el.get_text(" ", strip=True)
        if "€" not in text:
            continue
        raw = text.replace("€", "").replace(",", ".").strip()
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _extract_price_from_jsonld(soup: BeautifulSoup) -> float | None:
    """Извлича цената от вградения schema.org JSON-LD блок
    (<script type="application/ld+json">, "@type": "Product").

    Това е по-надежден източник от CSS селекторите по-долу: при част от
    продуктите (напр. цимента) секцията ".product-store-prices__item"
    изобщо не се рендира в статичния HTML на страницата на продукта (тя
    се появява само за "подобни продукти"/аксесоари по-надолу), докато
    JSON-LD блокът с offers.price винаги е наличен и е в EUR."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue

        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("@type") != "Product":
                continue

            offers = entry.get("offers")
            if not offers:
                continue
            offer_list = offers if isinstance(offers, list) else [offers]

            for offer in offer_list:
                if not isinstance(offer, dict):
                    continue
                price = offer.get("price")
                if price is None:
                    continue
                currency = offer.get("priceCurrency")
                if currency and currency != "EUR":
                    continue  # искаме цената само в евро
                try:
                    return float(str(price).replace(",", "."))
                except ValueError:
                    continue

    return None


def parse_price(html: str) -> float | None:
    """Извлича цената в ЕВРО за БАЗОВАТА мерна единица (м², кг, г...).

    1) Основен метод: JSON-LD блокът на Praktiker (виж
       _extract_price_from_jsonld) — най-стабилен, винаги присъства.
    2) Резервен метод: CSS селекторите за редовете "Цена М2:" / "Цена КГ:"
       вътре в контейнера .pdp, като изрично прескачаме редовете за
       опаковка/пакет (напр. "Цена за ПАКЕТ (1 ПАКЕТ - 1.62 M2):").
       Ползва се само ако JSON-LD не даде резултат."""
    soup = BeautifulSoup(html, "lxml")

    jsonld_price = _extract_price_from_jsonld(soup)
    if jsonld_price is not None:
        return jsonld_price

    scope = soup.select_one(".pdp") or soup
    items = scope.select(".product-store-prices__item")

    for item in items:
        title_el = item.select_one(".product-store-prices__title")
        label = title_el.get_text(" ", strip=True) if title_el else ""
        if _is_package_label(label):
            continue  # пропускаме "Цена за ПАКЕТ / К-Т / ..."

        price = _extract_eur_price(item)
        if price is not None:
            return price

    return None
 
 
def parse_image(html: str, page_url: str) -> str | None:
    """Извлича URL на главната снимка на продукта.
    TODO: провери в test.html (генерира се от fetch_page) какъв точно
    е маркъпът при Praktiker и коригирай селектора при нужда — og:image
    е разумна първа стъпка, защото почти винаги е коректно попълнен."""
    soup = BeautifulSoup(html, "lxml")
 
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        return og_image["content"]
 
    # Резервен вариант — селекторът по-долу е примерен, провери в test.html:
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
    """Обхожда всички продукти на Praktiker от PRODUCTS и връща:
    {
      product_id: {
        "price": 12.49,
        "image": "https://.../snimka.jpg",  # или None
        "url": "https://.../produkt",
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
            price = parse_price(html)
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
        has_img = "да" if info.get("image") else "не"
        print(f"  {pid}: {info['price']:.2f} лв. (снимка: {has_img})")