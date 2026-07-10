"""
scrape_gstroy.py
-----------------
Скрапер за GStroy (gstroy.bg).

ВАЖНО - защо цената и снимката се вземат по РАЗЛИЧЕН начин:

Проверих на живо (юли 2026) реални продуктови страници на gstroy.bg
(напр. https://gstroy.bg/product/13381-ciment-25kg-varovik-holsim-n42-5):

- Снимката (meta таг og:image) Я ИМА в статичния HTML, който сървърът
  връща - затова я вземаме с обикновена `requests.get()` заявка, точно
  както при Praktiker/Inex.
- Цената ГО НЯМА в статичния HTML - зарежда се допълнително през
  JavaScript (клиентски рендиран компонент/AJAX извикване). Затова само
  за цената ползваме Playwright (истински headless браузър), който
  изчаква JS-а да се изпълни и чак тогава чете рендирания текст.

(По-ранна версия на този файл четеше og:image през Playwright, СЛЕД
JS рендирането - но фронтенд фреймуъркът на GStroy пренаписва <head>
при hydration и на моменти маха/сменя тага, затова снимките излизаха
празни. Разделянето на двата метода го оправя.)

Инсталация:
    pip install -r requirements.txt
    playwright install chromium

Стартиране самостоятелно (за тест):
    python scrape_gstroy.py
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

STORE_ID = "gstroy"
STORE_NAME = "GStroy"
BASE_URL = "https://gstroy.bg"

# Съпоставяне: вътрешен id на продукт -> данни за него в GStroy.
# Проверени на живо реални продуктови страници (юли 2026). Само продукти,
# при които намерих разумен еквивалент - виж бележката в README.md за
# принципа "по-малко, но коректни съпоставки".
PRODUCTS = {
    "mazilka-silikonova-d15-draskana-25kg": {
        # ЗАБЕЛЕЖКА: GStroy продава DEKO T8500 (не "DEKO Professional D1.5"
        # като повечето други магазини) — виж matchNote в data/products.json.
        "url": f"{BASE_URL}/product/14835-mazilka-silikonova-orgahim-d1-5-25kg",
        "name": "Силиконова мазилка D1,5, драскана, 25kg",
        "category": "Бои и лакове",
        "unit": "кофа",
        "label": "МАЗИЛКА СИЛИКОНОВА DEKO T 8500 Д1.5 25кг",
    },
    "cement-42-5-25kg": {
        "url": f"{BASE_URL}/product/13381-ciment-25kg-varovik-holsim-n42-5",
        "name": "Цимент 42.5, 25 кг",
        "category": "Цимент и бетон",
        "unit": "чувал",
        "label": "ЦИМЕНТ 25кг ВАРОВИК ХОЛСИМ Н42.5 (CEM II/A-LL 42.5N)",
    },
    # ЗАБЕЛЕЖКА: zamazka-samorazlivna-25kg и hidroizolacia-kristalizirashta-25kg
    # бяха премахнати оттук — категория "Цимент и бетон" се преизгражда само
    # с 3 нови вида продукта. Замазката (Ceresit CN68, url:
    # 13303-samorazlivna-zamazka-cn68-25kg) ще се добави отново при новите
    # изисквания (Ceresit DA 25 kg) — засега умишлено я няма.
    "vintovertka-akum-18v": {
        "url": f"{BASE_URL}/product/69363-vintovert-akumulatoren-sbosh-gsr-185-li-2h20ah-21-50nm",
        "name": "Акумулаторен винтоверт 18V, 2 батерии",
        "category": "Инструменти",
        "unit": "брой",
        "label": "ВИНТОВЕРТ АКУМУЛАТОРЕН с.БОШ GSR 185-LI 2х2.0Ah 21-50Nm",
    },
    "osb-plocha-15mm": {
        "url": f"{BASE_URL}/product/13013-osb-2-15mm-2440h1220",
        "name": "OSB плоскост 15 мм (цена за м²)",
        "category": "Дърво и ОСБ",
        "unit": "м²",
        "label": "ОСБ 2 15мм 2440х1220мм (не влагоустойчив)",
        # Тази оферта досега стоеше ръчно вкарана в data/products.json,
        # без снимка (image: null) — защото изобщо не беше в PRODUCTS тук,
        # затова run_all.py никога не я презаписваше. Сега влиза в
        # автоматичното обхождане и ще си получи og:image като другите.
    },
    # ... добави останалите продукти тук, по същия модел, след като
    # провериш в браузъра реалната продуктова страница на gstroy.bg.
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

# Цената на страницата се показва като "46.80 лв." някъде в основния
# продуктов панел. Търсим низ във вида "ЦИФРИ.ЦИФРИ лв."
_PRICE_BGN_RE = re.compile(r"(\d[\d\s]*[.,]\d{2})\s*лв", re.IGNORECASE)


def fetch_static_html(url: str, attempts: int = 3) -> str:
    """Обикновена HTTP заявка - достатъчна за снимката (og:image), която
    Е налична в статичния HTML (за разлика от цената).

    Забелязано на живо: GStroy понякога отговаря бавно на отделни
    продуктови страници в рамките на един run (напр. hidroizolacia и
    vintovertka-akum-18v гръмнаха с "Read timed out" при timeout=15,
    докато другите 3 продукта минаха нормално) — вероятно моментно
    натоварване от сървъра им при последователни заявки, не постоянен
    проблем с конкретния URL. Затова: до `attempts` опита с нарастващ
    timeout, вместо целият продукт (вкл. снимката му) да отпадне заради
    една бавна заявка."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15 + attempt * 10)
            resp.raise_for_status()

            # Debug: пази последната изтеглена страница за проверка на маркъпа.
            with open("test.html", "w", encoding="utf-8") as f:
                f.write(resp.text)

            return resp.text
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < attempts:
                time.sleep(2 * attempt)  # кратка пауза преди следващия опит
    raise last_error


def parse_image(html: str) -> str | None:
    """Извлича URL на главната снимка на продукта от статичния HTML
    (meta таг og:image - проверено на живо, че присъства).

    ВАЖНО: GStroy не спазват стандарта на Open Graph буквално - вместо
    стандартния атрибут `property="og:image"`, те слагат тага като
    `name="og:image"` (проверено на живо в реален HTML отговор на
    сървъра, виж scraper/test.html). Затова търсим и по двата атрибута,
    за да проработи независимо кой от двата варианта ползва сайтът."""
    soup = BeautifulSoup(html, "lxml")

    og_image = soup.select_one(
        'meta[property="og:image"], meta[name="og:image"]'
    )
    if og_image and og_image.get("content"):
        return og_image["content"]

    return None


def _extract_price_bgn(text: str) -> float | None:
    """Извлича цена в лева от рендирания (след JS) текст на страницата и
    я връща конвертирана в евро (фиксиран курс BGN/EUR = 1.95583,
    официалният валутен борд на България)."""
    matches = _PRICE_BGN_RE.findall(text)
    if not matches:
        return None
    # Взимаме първото съвпадение - обикновено е основната цена на продукта,
    # изведена най-горе в продуктовия панел (преди "подобни продукти").
    raw = matches[0].replace(" ", "").replace(",", ".")
    try:
        bgn = float(raw)
    except ValueError:
        return None
    return round(bgn / 1.95583, 2)


def fetch_rendered_price(playwright, url: str) -> float | None:
    """Отваря страницата с headless Chromium, изчаква JS рендирането на
    цената и я връща в евро.

    GStroy понякога държи фонови мрежови заявки отворени за постоянно
    (chat widget, tracking пиксели и т.н.), заради което "networkidle"
    никога не се задейства и page.goto() гърми с Timeout — виж грешката
    при zamazka-samorazlivna-25kg. Затова: първи опит с networkidle
    (по-сигурен, когато проработи), а при timeout — втори опит само с
    domcontentloaded + ръчно изчакване, вместо целият продукт да пропадне."""
    browser = playwright.chromium.launch(headless=True)
    try:
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        try:
            page.goto(url, wait_until="networkidle", timeout=20000)
        except Exception:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # Без networkidle като сигнал, изчакваме ръчно JS-ът да успее
            # да вкара цената в DOM-а.
            page.wait_for_timeout(4000)
        else:
            page.wait_for_timeout(1500)
        text = page.inner_text("body")
        return _extract_price_bgn(text)
    finally:
        browser.close()


def scrape_all(delay_seconds: float = 1.5) -> dict:
    """Обхожда всички продукти на GStroy от PRODUCTS и връща:
    {
      product_id: {
        "price": 23.93,               # в евро
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
    with sync_playwright() as playwright:
        for product_id, info in PRODUCTS.items():
            url = info["url"]
            try:
                html = fetch_static_html(url)
                image = parse_image(html)
                price = fetch_rendered_price(playwright, url)

                if price is not None:
                    results[product_id] = {
                        "price": price,
                        "image": image,
                        "url": url,
                        "label": info.get("label"),
                        "name": info.get("name", product_id),
                        "category": info.get("category", "Некатегоризирани"),
                        "unit": info.get("unit", "брой"),
                    }
                    if not image:
                        print(f"[{STORE_ID}] ПРЕДУПРЕЖДЕНИЕ: намерих цена, но не и снимка за {product_id} ({url})")
                else:
                    print(f"[{STORE_ID}] Не намерих цена за {product_id} ({url})")
            except requests.RequestException as e:
                print(f"[{STORE_ID}] Грешка (HTTP) при {url}: {e}")
            except Exception as e:  # грешки от Playwright/браузъра
                print(f"[{STORE_ID}] Грешка (браузър) при {url}: {e}")

            time.sleep(delay_seconds)  # учтива пауза между заявките

    return results


if __name__ == "__main__":
    found = scrape_all()
    print(f"{STORE_ID}: намерени {len(found)} цени")
    for pid, info in found.items():
        has_img = "да" if info.get("image") else "не"
        print(f"  {pid}: {info['price']:.2f} € (снимка: {has_img})")
