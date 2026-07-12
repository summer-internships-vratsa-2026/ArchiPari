"""
scrape_bauhaus.py
-------------------
Скрапер за Bauhaus (bauhaus.bg).

Bauhaus е статичен, сървърно рендиран сайт (Rails-базиран) — НЕ е нужен
Playwright. Цената обаче е показана по необичаен начин: разбита е по
цифри в отделни HTML таблични клетки (за стилизиране), напр. визуално
"5,75 €" реално е три отделни клетки "5," / "75" / "€". BeautifulSoup's
.get_text() ги слепва с интервали, затова regex-ът по-долу допуска
whitespace между цифрите (виж _extract_price_eur).

По-надежден и по-прост първичен източник обаче е <meta name="description">
в <head> — Bauhaus слага текущата цена в евро в самия край на описанието,
напр.: "...Гарантирано качество, 5.75 €" — потвърдено на живо (юли 2026).

Двата продукта тук са избрани да съвпаднат с id-та, които ВЕЧЕ
съществуват в data/products.json (виж съответно scrape_praktiker.py /
scrape_homemax.py / scrape_gstroy.py за същите id-та):
  - cement-42-5-25kg        (нова оферта — вече има praktiker/homemax/inex/gstroy)
  - vintovertka-akum-18v    (нова оферта — вече има praktiker/homemax/inex/gstroy)

И двата са проверени на живо и НЕ са "ударни" инструменти / различен клас
цимент, за да не повторят проблема, поправен по-рано в scrape_praktiker.py
(виж git история / чат бележките за "УДАРНА БОРМАШИНА" грешката).

Стартиране самостоятелно (за тест):
    python scrape_bauhaus.py
"""

import re
import time
import requests
from bs4 import BeautifulSoup

STORE_ID = "bauhaus"
STORE_NAME = "Bauhaus"
BASE_URL = "https://bauhaus.bg"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

PRODUCTS = {
    "gipsokarton-sonicboard-12-5-1200x2000": {
        "url": f"{BASE_URL}/gipsokarton-knauf-sonicboard-tip-d-gkb/p/155209",
        "name": "Гипсокартон 12.5 мм, 1200/2000 мм",
        "category": "Гипсокартон и мазилки",
        "unit": "бр.",
        "label": "Гипсокартон Knauf Sonicboard тип D GKB, 2000х1200х12,5 мм",
    },
    "mazilka-silikonova-d15-draskana-25kg": {
        "url": f"{BASE_URL}/silikonova-mazilka-deko-professional-d15/p/23650",
        "name": "Силиконова мазилка D1,5, драскана, 25kg",
        "category": "Бои и лакове",
        "unit": "кофа",
        "label": "Силиконова мазилка Deko Professional D1,5, 25 кг, бяла, драскана",
    },
    "cement-42-5-25kg": {  # <- същото id във всички скрапери за този продукт!
        # ЗАМЕНЕНО: старата оферта (Bravo CEM II/B-M 42,5N) не отговаряше
        # на изисквания клас 42.5R. Devnya Premium CEM II/A-LL 42,5R е
        # истински R-клас, проверено на живо (юли 2026).
        "url": f"{BASE_URL}/ciment-devnya-premium-cem-ii-a-ll-425-r/p/9971",
        "name": "Портланд цимент CEM II 42.5R, 25 кг",
        "category": "Цимент и бетон",
        "unit": "чувал",
        "label": "Цимент Devnya Premium CEM II/A-LL 42,5 R, 25 кг",
    },
    "vintovertka-akum-18v": {
        # Нарочно избран БЕЗ "ударен"/SB (Schlagbohrschrauber) в името —
        # HiKOKI DS18DF е чист drill-driver (DS = Driver Screwdriver),
        # както винтовертите при другите 4 магазина.
        "url": f"{BASE_URL}/akumulatoren-vintovert-hikoki-ds18df/p/135182",
        "name": "Акумулаторен винтоверт 18V, 2 батерии",
        "category": "Инструменти",
        "unit": "брой",
        "label": "Акумулаторен винтоверт HiKOKI DS18DF, 18V, 2 батерии 2Ah, зарядно и куфар",
    },
    # ... добави останалите продукти тук, по същия модел.
}


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    with open("test.html", "w", encoding="utf-8") as f:
        f.write(resp.text)

    return resp.text


def _price_from_meta_description(soup: BeautifulSoup) -> float | None:
    """Първичен източник: Bauhaus слага текущата цена в евро в самия край
    на <meta name="description">, напр. "...Гарантирано качество, 5.75 €"."""
    meta = soup.select_one('meta[name="description"]')
    if not meta or not meta.get("content"):
        return None
    match = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*€\s*$", meta["content"].strip())
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def _price_from_page_text(soup: BeautifulSoup) -> float | None:
    """Резервен вариант: цената на Bauhaus е разбита по цифри в отделни
    таблични клетки (напр. "5," / "75" / "€"). get_text(" ") ги слепва с
    интервали, затова regex-ът допуска whitespace между групите цифри.
    Взимаме ПЪРВОТО съвпадение преди "Свързани продукти" — секцията с
    препоръчани продукти по-надолу на страницата има собствени цени,
    които не бива да бъркаме с цената на търсения продукт."""
    text = soup.get_text(" ", strip=True)
    cutoff = text.find("Свързани продукти")
    if cutoff != -1:
        text = text[:cutoff]

    match = re.search(r"(\d+)\s*,\s*(\d{2})\s*€", text)
    if match:
        return float(f"{match.group(1)}.{match.group(2)}")

    return None


def parse_price(html: str) -> float | None:
    soup = BeautifulSoup(html, "lxml")

    price = _price_from_meta_description(soup)
    if price is not None:
        return price

    return _price_from_page_text(soup)


def parse_image(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")

    # Проверено на живо: og:image ГО ИМА в статичния HTML на Bauhaus,
    # затова обикновен requests.get() е достатъчен (не е нужен Playwright).
    # За по-голяма сигурност приемаме и двата варианта на атрибута
    # (property/name — различни сайтове от нашия списък ги смесват, виж
    # аналогичната бележка в scrape_gstroy.py), плюс twitter:image като
    # резервен източник, ако og:image липсва по някаква причина.
    og_image = soup.select_one(
        'meta[property="og:image"], meta[name="og:image"]'
    )
    if og_image and og_image.get("content"):
        return og_image["content"]

    twitter_image = soup.select_one(
        'meta[property="twitter:image"], meta[name="twitter:image"]'
    )
    if twitter_image and twitter_image.get("content"):
        return twitter_image["content"]

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
