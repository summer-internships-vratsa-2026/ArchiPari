"""
scrape_template.py
-------------------
Скелет за скрапер на ЕДИН магазин. Копирай този файл (напр. като
scrape_praktiker.py) и адаптирай маркираните с TODO места според
реалната структура на сайта на магазина.
 
Стартиране самостоятелно (за тест):
    python scrape_template.py
"""
 
import time
import requests
from bs4 import BeautifulSoup
 
STORE_ID = "example_store"          # TODO: id, съвпадащ с data/products.json -> stores[].id
STORE_NAME = "Example Store"        # TODO: показвано име
BASE_URL = "https://www.example.bg" # TODO: домейн на магазина
 
HEADERS = {
    # Реалистичен User-Agent намалява шанса заявката да бъде отхвърлена.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}
 
# Съпоставяне: вътрешен id на продукт -> данни за него в този магазин.
# TODO: попълни с реалните продуктови страници на магазина.
#
# "name", "category" и "unit" се използват САМО ако продуктът с това id
# още го няма в data/products.json — run_all.py ще го създаде автоматично
# при първо пускане. Ако продуктът вече съществува (защото друг магазин
# вече го е добавил), тези три полета се игнорират и просто се добавя
# цена за твоя магазин — затова е важно да ползваш ЕДНО И СЪЩО id между
# скраперите на различните магазини за един и същ материал.
PRODUCTS = {
    "cement-42-5-25kg": {
        "url": f"{BASE_URL}/produkt/cement-42-5r-25kg",
        "name": "Цимент CEM I 42.5R, 25 кг",
        "category": "Цимент и бетон",
        "unit": "чувал",
        # По избор: точното име на продукта в ТОЗИ магазин, ако се различава
        # от общото "name" (полезно е, защото продуктите между магазините
        # рядко са напълно идентични — различни марки/класове/размери).
        "label": "Точното заглавие на продукта в този магазин (по избор)",
    },
    "gipsokarton-12-5-standart": {
        "url": f"{BASE_URL}/produkt/gipsokarton-standarten-12-5mm",
        "name": "Гипсокартон стандартен 12.5 мм, 1.2x2 м",
        "category": "Гипсокартон и мазилки",
        "unit": "брой",
    },
    # ... добави останалите продукти тук
}
 
 
def fetch_page(url: str) -> str:
    """Изтегля HTML на страницата. При Cloudflare/JS защита може да се
    наложи playwright/selenium вместо requests."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text
 
 
def parse_price(html: str) -> float | None:
    """Извлича цената от HTML. TODO: адаптирай CSS селектора според
    реалния маркъп на страницата (Инспектирай елемента в браузъра,
    Дясен клик -> Inspect, намери елемента с цената)."""
    soup = BeautifulSoup(html, "lxml")
 
    # Пример за възможен селектор — ПОЧТИ СИГУРНО ще трябва да го смениш:
    price_el = soup.select_one(".product-price, .price, [itemprop='price']")
    if not price_el:
        return None
 
    raw = price_el.get_text(strip=True)
    # Пример за почистване на текст от типа "12,49 лв." -> 12.49
    raw = raw.replace("лв.", "").replace("лв", "").replace(",", ".").strip()
    try:
        return float(raw)
    except ValueError:
        return None
 
 
def parse_image(html: str, page_url: str) -> str | None:
    """Извлича URL на главната снимка на продукта. TODO: адаптирай
    селектора — обикновено е <img> в основната галерия/зона на продукта,
    или meta таг og:image (по-стабилен избор, ако е наличен).
 
    Ползваме og:image като първи опит, защото почти всички сайтове го
    попълват коректно за социално споделяне и рядко се променя структурата му."""
    soup = BeautifulSoup(html, "lxml")
 
    # 1) Най-стабилният вариант — Open Graph мета тагът:
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        return og_image["content"]
 
    # 2) Резервен вариант — директно <img> в галерията на продукта.
    # ПОЧТИ СИГУРНО ще трябва да смениш този селектор според реалния сайт:
    img_el = soup.select_one(".product-gallery img, .product-image img, [itemprop='image']")
    if img_el:
        src = img_el.get("src") or img_el.get("data-src")
        if src:
            # Някои сайтове ползват относителни пътища -> направи ги пълни.
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("/"):
                base = "/".join(page_url.split("/")[:3])  # https://domain.bg
                return base + src
            return src
 
    return None
 
 
def scrape_all(delay_seconds: float = 1.5) -> dict:
    """Обхожда всички продукти на този магазин и връща речник:
    {
      product_id: {
        "price": 12.49,
        "image": "https://.../snimka.jpg",  # или None, ако не е намерена
        "url": "https://.../produkt",        # линк към продукта в магазина
        "name": "...",       # само за информация/автоматично създаване
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
                    "label": info.get("label"),  # точното име в ТОЗИ магазин, ако е зададено
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