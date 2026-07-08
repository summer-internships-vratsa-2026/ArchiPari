"""
scrape_domestico.py
---------------------
Скрапер за Domestico (domestico.bg).

ВАЖНО — защо продуктите тук са РАЗЛИЧНИ от тези при другите магазини:

Проверих на живо (юли 2026) какво реално продава Domestico. За разлика от
Praktiker/HomeMax/Inex/GStroy, при тях НЕ намерих цимент, замазка,
хидроизолация или акумулаторни винтоверти — навигацията им е Баня / Кухня /
Отопление / За майстора / Боядисване, и реалният им фокус в "строителство"
е бои, грундове и мазилки (марка DEKO на Оргахим). Затова PRODUCTS по-долу
НЕ съвпада по id с общите продукти при другите 4 магазина — вместо това
въвежда 2 нови продукта в категория "Бои и лакове", които съществуват само
при Domestico (както вече OSB съществува само при 3 от 4-те магазина,
теракотът само при Praktiker и т.н. — сайтът поддържа това нормално).

Ако по-късно намериш при Domestico истински еквивалент на някой от общите
продукти (cement-42-5-25kg, zamazka-samorazlivna-25kg,
hidroizolacia-kristalizirashta-25kg, vintovertka-akum-18v), просто добави
запис с ТОЧНО същото id тук и той автоматично ще се появи като нова
оферта към съществуващия продукт, вместо да създава нов.

Технически Domestico е по-лесен от GStroy: цената идва статично в HTML
(Magento сайт), не е нужен Playwright. Открих на живо два надеждни
източника, по приоритет:
  1. Schema.org JSON-LD блок (както при Praktiker) — ако е наличен.
  2. Meta таговете <meta property="product:price:amount" content="..."> и
     <meta property="product:price:currency" content="BGN"> — потвърдени
     на живо в реалния HTML на продуктовите страници. Цената в тях е в
     лева, затова я конвертираме в евро (курс 1.95583) — вижте другите
     скрапери за същата конвенция.

ЗАБЕЛЕЖКА за цената на грунда (grund-fasaden-ps112-18kg): на сайта пише
271,99 лв. за 18 кг, което е необичайно скъпо спрямо подобни продукти на
пазара (~3-6 лв/кг при други марки). Възможно е да е грешка/остаряла цена
в самия магазин, а не в скрапера — провери test.html при първо пускане,
преди да се довериш на резултата сляпо.

Стартиране самостоятелно (за тест):
    python scrape_domestico.py
"""

import re
import json
import time
import requests
from bs4 import BeautifulSoup

STORE_ID = "domestico"
STORE_NAME = "Domestico"
BASE_URL = "https://www.domestico.bg"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

BGN_PER_EUR = 1.95583

# Съпоставяне: вътрешен id на продукт -> данни за него в Domestico.
# Проверени на живо реални продуктови страници (юли 2026, виж бележката
# по-горе защо тези 2, а не общите 4 продукта).
PRODUCTS = {
    "mazilka-silikonova-b3-25kg": {
        "url": f"{BASE_URL}/silikonova-mazilka-deko-professional-b3-vlachena-product",
        "name": "Силиконова фасадна мазилка, влачена структура, 25 кг",
        "category": "Бои и лакове",
        "unit": "кофа",
        "label": "Силиконова мазилка DEKO Professional, B3, влачена структура",
    },
    "grund-fasaden-ps112-18kg": {
        "url": f"{BASE_URL}/bojadisvane/za-stroitelstvo/grundove-za-steni/grund-deko-fcd112-product",
        "name": "Фасаден грунд за мазилки, 18 кг",
        "category": "Бои и лакове",
        "unit": "кофа",
        "label": "Грунд Deko Professional, фасаден, ПС-112",
    },
    # ... добави останалите продукти тук, по същия модел.
}


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    with open("test.html", "w", encoding="utf-8") as f:
        f.write(resp.text)

    return resp.text


def _price_from_jsonld(soup: BeautifulSoup) -> float | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue

        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            offers = entry.get("offers")
            if not offers:
                continue
            offer_list = offers if isinstance(offers, list) else [offers]
            for offer in offer_list:
                if not isinstance(offer, dict) or offer.get("price") is None:
                    continue
                try:
                    price = float(str(offer["price"]).replace(",", "."))
                except ValueError:
                    continue
                currency = offer.get("priceCurrency", "BGN")
                return price / BGN_PER_EUR if currency == "BGN" else price
    return None


def _price_from_meta(soup: BeautifulSoup) -> float | None:
    """Потвърдено на живо: Domestico слага
    <meta property="product:price:amount" content="93.99">
    <meta property="product:price:currency" content="BGN">
    в <head> на всяка продуктова страница."""
    amount_el = soup.select_one('meta[property="product:price:amount"]')
    currency_el = soup.select_one('meta[property="product:price:currency"]')
    if not amount_el or not amount_el.get("content"):
        return None
    try:
        price = float(amount_el["content"].replace(",", "."))
    except ValueError:
        return None
    currency = currency_el["content"] if currency_el and currency_el.get("content") else "BGN"
    return price / BGN_PER_EUR if currency == "BGN" else price


def parse_price(html: str) -> float | None:
    soup = BeautifulSoup(html, "lxml")

    price = _price_from_jsonld(soup)
    if price is not None:
        return price

    price = _price_from_meta(soup)
    if price is not None:
        return price

    # Резервен вариант — regex по видимия текст на страницата.
    text = soup.get_text(" ", strip=True)
    match = re.search(r"(\d+[.,]\d{2})\s*лв", text, re.IGNORECASE)
    if match:
        return round(float(match.group(1).replace(",", ".")) / BGN_PER_EUR, 2)

    return None


def parse_image(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")

    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        return og_image["content"]

    return None


def scrape_all(delay_seconds: float = 1.5) -> dict:
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
                print(f"[{STORE_ID}] Не намерих цена за {product_id} ({url}) — провери test.html")
        except requests.RequestException as e:
            print(f"[{STORE_ID}] Грешка при {url}: {e}")

        time.sleep(delay_seconds)

    return results


if __name__ == "__main__":
    found = scrape_all()
    print(f"{STORE_ID}: намерени {len(found)} цени")
    for pid, info in found.items():
        print(f"  {pid}: {info['price']:.2f} € ({info.get('label') or info['name']})")
