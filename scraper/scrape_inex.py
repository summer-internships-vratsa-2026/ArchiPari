"""
scrape_inex.py
--------------
Скрапер за Inex (inex-bg.com) — строителен магазин, основно за
електроинструменти и железария (виж бележката в README.md за домейна:
inex-bg.com, не inex.bg!).

Структура на сайта (проверена на живо, юли 2026):
  - URL на продукт: https://inex-bg.com/p/<slug>  (или .../p/<числов id>)
  - Цената е в мета таг в <head>:
        <meta property="product:price:amount" content="138.99">
        <meta property="product:price:currency" content="EUR">
    Проверено на 2 различни продукта — стойността Е крайната цена с ДДС
    (след промоционална отстъпка, ако има такава), точно както се
    показва на страницата в блока "Крайна цена с ДДС".
  - Снимка: стандартен <meta property="og:image" content="...">

Стартиране самостоятелно (за тест):
    python scrape_inex.py
"""

import re
import time
import requests
from bs4 import BeautifulSoup

STORE_ID = "inex"
STORE_NAME = "Inex"
BASE_URL = "https://inex-bg.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

# ВАЖНО: id-тата тук трябва да СЪВПАДАТ с id-тата в scrape_praktiker.py /
# scrape_homemax.py за същия материал — иначе run_all.py ще създаде НОВ,
# отделен продукт вместо да добави офертата на Inex към съществуващия.
#
# Inex е основно магазин за инструменти/железария — затова засега само
# двата продукта от категория "Инструменти" (вече дефинирани в
# data/products.json) имат реален, проверен на живо еквивалент тук. За
# цимент/гипсокартон/плочки и т.н. провери какво предлага inex-bg.com,
# преди да добавяш нови редове — може изобщо да няма съответствие.
PRODUCTS = {
    "perforator-sds-plus": {
        "url": f"{BASE_URL}/p/190996",
        "name": "Перфоратор SDS-Plus, 800 W",
        "category": "Инструменти",
        "unit": "брой",
        "label": "Електрически перфоратор Makita HR2670, SDS-Plus, 800 W, 3 J",
    },
    "vintovertka-akum-18v": {
        "url": f"{BASE_URL}/p/akum-vintovert-metabo-bs18l18v-zaryadnokufar-602321500",
        "name": "Акумулаторна винтоверта 18V, 2 батерии",
        "category": "Инструменти",
        "unit": "брой",
        "label": "Акумулаторен винтоверт Metabo BS18L, 18V, 2 батерии, зарядно и куфар",
    },
    "cement-42-5-25kg": {
        "url": f"{BASE_URL}/p/premium-tsiment-devnya-42-5r-25kg-64br-pale-0000070011",
        "name": "Цимент 42.5, 25 кг",
        "category": "Цимент и бетон",
        "unit": "чувал",
        "label": "Цимент Premium Devnya 42.5R 25 кг.",
    },
    "zamazka-samorazlivna-25kg": {
        "url": f"{BASE_URL}/p/baumit-alfa-2000-25kg-zamazka-samorazlivna-48-br-p-0000056327",
        "name": "Саморазливна замазка, 25 кг",
        "category": "Цимент и бетон",
        "unit": "чувал",
        "label": "Саморазливна замазка Алфа 2000, Baumit, 25 кг",
    },
    "hidroizolacia-kristalizirashta-25kg": {
        # ЗАБЕЛЕЖКА: Inex не продава директно Ceresit CR90 (25кг) — най-близкият
        # реален еквивалент е хидроизолационна мазилка на циментова основа,
        # но в по-малка опаковка (7 кг вместо 25 кг). Виж matchNote в
        # products.json за този продукт.
        "url": f"{BASE_URL}/p/tkk-tekadom-hidroblokers-7-kg-superel-hidr-24644-sm22467",
        "name": "Хидроизолация кристализираща, 25 кг",
        "category": "Цимент и бетон",
        "unit": "чувал",
        "label": "Хидроизолационна мазилка TKK HydroBlocker Hidroizol S, 7 кг",
    },
    # ... добави останалите продукти тук, по същия модел, след като
    # провериш в браузъра, че inex-bg.com има разумен еквивалент.
}


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    # Debug: пази последната изтеглена страница, за да провериш реалния
    # HTML, ако цената/снимката не се хванат правилно.
    with open("test.html", "w", encoding="utf-8") as f:
        f.write(resp.text)

    return resp.text


def parse_price(html: str) -> float | None:
    """Извлича крайната цена с ДДС в ЕВРО.

    Основен метод: Inex (платформа Omnilinx) винаги попълва в <head> на
    страницата стандартните Open Graph "product" мета тагове:
        <meta property="product:price:amount" content="138.99">
        <meta property="product:price:currency" content="EUR">
    Проверено на живо на два различни продукта — стойността съвпада
    точно с показаната на страницата "Крайна цена с ДДС" (т.е. вече е
    отчетена евентуална промоционална отстъпка). Това е далеч по-стабилен
    избор от парсване на видимия ценови блок, чиито CSS класове/оформление
    е по-вероятно да се сменят с редизайн на сайта.
    """
    soup = BeautifulSoup(html, "lxml")

    amount_el = soup.select_one('meta[property="product:price:amount"]')
    if amount_el and amount_el.get("content"):
        currency_el = soup.select_one('meta[property="product:price:currency"]')
        currency = currency_el.get("content") if currency_el else None
        if not currency or currency == "EUR":
            try:
                return float(amount_el["content"].replace(",", "."))
            except ValueError:
                pass

    # Резервен метод — ако мета таговете липсват, вземи видимата цена
    # директно от текста преди етикета "Крайна цена с ДДС" (напр.
    # "187.13 € (365.99 лв.) 138.99 € (271.84 лв.) Крайна цена с ДДС").
    # Взимаме ПОСЛЕДНОТО съвпадение с "€" преди този етикет, защото при
    # промоция страницата показва първо старата, зачертана цена.
    text = soup.get_text(" ", strip=True)
    marker = "Крайна цена с ДДС"
    idx = text.find(marker)
    if idx != -1:
        preceding = text[:idx]
        matches = re.findall(r"([\d]+[.,]\d{2})\s*€", preceding)
        if matches:
            try:
                return float(matches[-1].replace(",", "."))
            except ValueError:
                return None

    return None


def parse_image(html: str, page_url: str) -> str | None:
    """Извлича URL на главната снимка — og:image е надежден избор тук,
    Inex го попълва коректно за всеки продукт (проверено на живо)."""
    soup = BeautifulSoup(html, "lxml")

    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        return og_image["content"]

    # Резервен вариант, ако og:image липсва по някаква причина:
    img_el = soup.select_one(".product-gallery img, [itemprop='image']")
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
    """Обхожда всички продукти на Inex от PRODUCTS и връща:
    {
      product_id: {
        "price": 138.99,
        "image": "https://.../snimka.jpg",  # или None
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
        print(f"  {pid}: {info['price']:.2f} € (снимка: {has_img})")
