"""
run_all.py
----------
Пуска скрапера на всеки регистриран магазин, обединява резултатите
с текущия ../data/products.json (запазвайки имена/категории/единици)
и записва обновен файл с нови цени + нов lastUpdated timestamp.
 
Регистрирай тук всеки готов скрапер (виж scrape_template.py) след
като си го адаптирал за конкретния магазин.
"""
 
import json
import importlib
from datetime import datetime, timezone, timedelta
 
DATA_PATH = "../data/products.json"
 
# TODO: добавяй по един запис на всеки готов скрапер, например:
import scrape_praktiker
import scrape_homemax
import scrape_inex
import scrape_gstroy
import scrape_domestico
import scrape_bauhaus
SCRAPER_MODULES = [
    "scrape_praktiker",
    "scrape_homemax",
    "scrape_inex",
    "scrape_gstroy",
    "scrape_domestico",
    "scrape_bauhaus",
]
 
BG_TZ = timezone(timedelta(hours=3))  # лятно часово време; смени на +2 през зимата или ползвай zoneinfo
 
 
def load_current_data() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return migrate_schema(data)
 
 
def migrate_schema(data: dict) -> dict:
    """Ако products.json е от преди добавянето на снимки, продуктите
    имат "prices": {store_id: 12.49} вместо новия "offers":
    {store_id: {"price":..., "image":..., "url":...}}. Тази функция
    преобразува старите записи автоматично, за да не се налага ръчно
    редактиране на файла."""
    for product in data["products"]:
        if "prices" in product and "offers" not in product:
            product["offers"] = {
                store_id: {"price": price, "image": None, "url": None}
                for store_id, price in product.pop("prices").items()
            }
    return data
 
 
def save_data(data: dict) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
 
 
def run_all_scrapers() -> dict:
    """Връща {store_id: {product_id: price}}"""
    all_results = {}
    for module_name in SCRAPER_MODULES:
        module = importlib.import_module(module_name)
        store_prices = module.scrape_all()
        all_results[module.STORE_ID] = store_prices
        print(f"OK: {module.STORE_ID} -> {len(store_prices)} цени")
    return all_results
 
 
def _extract_offer_and_meta(entry):
    """Скрапер може да върне:
    - чисто число (най-стар формат: само цена, без снимка/линк/метаданни)
    - речник {"price":..., "name":..., "category":..., "unit":...}
      (междинен формат, без снимка)
    - речник {"price":..., "image":..., "url":..., "name":..., ...}
      (пълен, текущ формат)
    Връща (offer, meta) където offer е {"price","image","url"} и meta е
    {"name","category","unit"} или None ако липсват метаданни."""
    if isinstance(entry, dict):
        offer = {
            "price": entry.get("price"),
            "image": entry.get("image"),
            "url": entry.get("url"),
        }
        if entry.get("label"):
            offer["label"] = entry["label"]
        if entry.get("warning"):
            offer["warning"] = entry["warning"]
        meta = None
        if entry.get("name"):
            meta = {
                "name": entry.get("name"),
                "category": entry.get("category", "Некатегоризирани"),
                "unit": entry.get("unit", "брой"),
            }
        return offer, meta
    return {"price": entry, "image": None, "url": None}, None
 
 
def merge_into_data(data: dict, scraped: dict) -> dict:
    by_id = {p["id"]: p for p in data["products"]}
    created, updated = 0, 0
 
    for store_id, store_results in scraped.items():
        for product_id, entry in store_results.items():
            offer, meta = _extract_offer_and_meta(entry)
            if offer.get("price") is None:
                continue
 
            if product_id in by_id:
                # Продуктът вече съществува -> обновяваме офертата.
                # Ако новите данни НЕ включват label/warning, пазим
                # съществуващите (ръчно зададени бележки не изчезват
                # тихомълком при следващо автоматично обновяване).
                existing_offer = by_id[product_id]["offers"].get(store_id, {})
                if "label" not in offer and "label" in existing_offer:
                    offer["label"] = existing_offer["label"]
                if "warning" not in offer and "warning" in existing_offer:
                    offer["warning"] = existing_offer["warning"]
                by_id[product_id]["offers"][store_id] = offer
                updated += 1
            else:
                # Нов продукт -> създаваме запис, ако имаме метаданни.
                if meta and meta.get("name"):
                    new_product = {
                        "id": product_id,
                        "name": meta["name"],
                        "category": meta["category"],
                        "unit": meta["unit"],
                        "offers": {store_id: offer},
                    }
                    data["products"].append(new_product)
                    by_id[product_id] = new_product
                    if meta["category"] not in data["categories"]:
                        data["categories"].append(meta["category"])
                    created += 1
                    print(f"НОВ ПРОДУКТ: '{meta['name']}' (id={product_id}) от {store_id}")
                else:
                    print(
                        f"ПРЕДУПРЕЖДЕНИЕ: {store_id} върна цена за непознат "
                        f"продукт '{product_id}', но без name/category/unit — "
                        f"пропуснат. Добави метаданни в PRODUCTS в скрапера "
                        f"или ръчно добави продукта в data/products.json."
                    )
 
    data["lastUpdated"] = datetime.now(BG_TZ).isoformat()
    print(f"Обобщение: {updated} обновени оферти, {created} нови продукта.")
    return data
 
 
if __name__ == "__main__":
    if not SCRAPER_MODULES:
        print(
            "Няма регистрирани скрапери в SCRAPER_MODULES. "
            "Адаптирай scrape_template.py за поне един магазин и го добави "
            "в списъка, преди да пуснеш този скрипт."
        )
    else:
        data = load_current_data()
        scraped = run_all_scrapers()
        data = merge_into_data(data, scraped)
        save_data(data)
        print(f"Готово. Обновен {DATA_PATH} в {data['lastUpdated']}.")