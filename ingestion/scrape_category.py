import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time
from urllib.parse import quote

from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from datetime import datetime, UTC

from app.db.models import Product, ProductChange, ScrapeRun
from app.services.product_intent_service import extract_product_intent, classify_product_type
from app.services.product_enrichment_service import (
    extract_model_family,
    extract_color,
    infer_category_from_name,
)
from app.services import cache_service
from concurrent.futures import ThreadPoolExecutor

MAX_WORKERS = 8
REQUEST_TIMEOUT = 30
FETCH_RETRIES = 2
RETRY_BACKOFF_SECONDS = 3
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

SESSION = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
SESSION.mount("https://", _adapter)
SESSION.mount("http://", _adapter)

def get_product_sitemap_urls() -> list[str]:
    sitemap_index_url = "https://topsport.ge/sitemap_ka.xml"
    response = requests.get(sitemap_index_url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "xml")
    all_locs = [loc.get_text(strip=True) for loc in soup.find_all("loc")]

    product_sitemap_urls = [
        url for url in all_locs if "sitemap-products-" in url
    ]

    return product_sitemap_urls

def get_all_product_urls() -> list[str]:
    sitemap_urls = get_product_sitemap_urls()
    product_urls = []

    for sitemap_url in sitemap_urls:
        response = requests.get(sitemap_url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "xml")
        locs = [loc.get_text(strip=True) for loc in soup.find_all("loc")]

        product_urls.extend(locs)

    return product_urls

def _parse_price(tag) -> float | None:
    text = tag.get_text(strip=True).replace("\xa0", "").replace(",", ".")
    match = re.search(r"[\d.]+", text)
    return float(match.group()) if match else None


def extract_product_details_from_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    name_tag = soup.find("h1", class_="title-detail")
    name = name_tag.get_text(strip=True) if name_tag else None

    price = None
    regular_price = None
    price_tag = soup.find("span", class_="current-price")
    if price_tag:
        price = _parse_price(price_tag)
        # Зачёркнутая обычная цена (есть только у товаров со скидкой): 177,00 ₾ при current 124,00 ₾.
        # Ищем в том же блоке цены, что и текущую, — не в "похожих товарах" ниже на странице.
        price_block = price_tag.find_parent("div")
        old_price_tag = price_block.find("span", class_="old-price") if price_block else None
        if old_price_tag:
            regular_price = _parse_price(old_price_tag)

    brand = None
    categories = []

    for item in soup.find_all("div", class_="item"):
        title_tag = item.find("div", class_="title")
        info_tag = item.find("div", class_="info")
        if not title_tag or not info_tag:
            continue

        label = title_tag.get_text(strip=True)

        if label == "ბრენდი":
            brand = info_tag.get_text(strip=True)
        elif label == "კატეგორია":
            categories = [a.get_text(strip=True) for a in info_tag.find_all("a")]

    image_url = None
    slider_div = soup.find("div", class_="product-image-slider")
    if slider_div:
        first_image_tag = slider_div.find("img")
        if first_image_tag:
            image_url = first_image_tag.get("src")

    return {
        "name": name,
        "brand": brand,
        "price": price,
        "regular_price": regular_price,
        "categories": categories,
        "image_url": image_url,
    }

def get_base_sku(raw_sku: str, sizes: list[str]) -> str:
    raw_sku = raw_sku.strip()
    if sizes:
        suffix = f"-{sizes[0]}"
        if raw_sku.endswith(suffix) and len(raw_sku) > len(suffix):
            return raw_sku[: -len(suffix)]
    return raw_sku

def build_product_variants(url: str) -> list[dict]:
    html = fetch_page(url)

    raw_sku = extract_sku_from_html(html)
    if not raw_sku:
        return []

    sizes = extract_sizes_from_html(html)
    if sizes:
        base_sku = get_base_sku(raw_sku, sizes)
    else:
        base_sku, fallback_size = split_sku_and_size(raw_sku)
        sizes = [fallback_size] if fallback_size else []

    if not base_sku or not sizes:
        return []

    details = extract_product_details_from_html(html)
    if details["categories"]:
        category_slug = ", ".join(details["categories"])
    else:
        category_slug = infer_category_from_name(details["name"])

    classification_text = " ".join(
        part for part in [details["name"], details["brand"], base_sku] if part
    )
    product_intent = extract_product_intent(classification_text, category_slug)
    product_type = classify_product_type(category_slug)

    variants = []
    for raw_size in sizes:
        size = raw_size.replace(",", ".").rstrip(".")  # "40,5" -> "40.5", "5," -> "5"
        variants.append({
            "sku": f"{base_sku}-{size}",
            "name": details["name"],
            "brand": details["brand"],
            "price": details["price"],
            "regular_price": details.get("regular_price"),
            "category_slug": category_slug,
            "product_type": product_type.value,
            "style_group": product_intent.style_group.value if product_intent and product_intent.style_group else None,
            "sport_type": product_intent.sport_type.value if product_intent and product_intent.sport_type else None,
            "usage_type": product_intent.usage_type.value if product_intent else None,
            "model_family": extract_model_family(details["name"] or ""),
            "color": extract_color(details["name"] or ""),
            "size": size,
            "product_url": f"{url}?size={quote(size)}",
            "image_url": details["image_url"],
        })

    return variants

def get_product_changes(existing: Product, variant: dict) -> dict:
    fields_to_compare = [
        "name", "brand", "price", "regular_price", "category_slug", "product_type",
        "style_group", "sport_type", "usage_type",
        "model_family", "color", "image_url", "product_url",
    ]

    changes = {}
    for field in fields_to_compare:
        old_value = getattr(existing, field, None)
        new_value = variant.get(field)
        if old_value != new_value:
            changes[field] = (old_value, new_value)

    return changes

class ProductIndex:
    def __init__(self, products):
        self.by_sku = {}
        self.by_url = {}
        for product in products:
            self.add(product)

    def add(self, product):
        if product.sku:
            self.by_sku[product.sku] = product
        self.by_url[product.product_url] = product

    def rename_sku(self, product, new_sku):
        if product.sku and self.by_sku.get(product.sku) is product:
            del self.by_sku[product.sku]
        product.sku = new_sku
        self.by_sku[new_sku] = product

    def move_url(self, product, old_url, new_url):
        if self.by_url.get(old_url) is product:
            del self.by_url[old_url]
        self.by_url[new_url] = product

    def forget(self, variant: dict):
        product = self.by_sku.get(variant["sku"])
        if product is not None and product.id is None:
            del self.by_sku[variant["sku"]]
            if self.by_url.get(product.product_url) is product:
                del self.by_url[product.product_url]


def load_product_index(db) -> ProductIndex:
    return ProductIndex(db.query(Product).all())


def _log_change(change_log, **entry) -> None:
    if change_log is not None:
        change_log.append(entry)


def _as_text(value):
    return None if value is None else str(value)


def save_product_variant(db, variant: dict, index: ProductIndex | None = None,
                         change_log: list | None = None) -> str:
    if index is None:
        index = load_product_index(db)

    existing = index.by_sku.get(variant["sku"])
    sku_changed = False

    if existing is None:
        existing = index.by_url.get(variant["product_url"])
        if existing is not None:
            print(
                f"⚠ Смена SKU для {variant['product_url']}: "
                f"было {existing.sku}, стало {variant['sku']}"
            )
            old_sku = existing.sku
            index.rename_sku(existing, variant["sku"])
            sku_changed = True
            _log_change(change_log, sku=variant["sku"], change_type="sku_changed",
                        field="sku", old_value=old_sku, new_value=variant["sku"])

    if existing is not None:
        changes = get_product_changes(existing, variant)

        if "product_url" in changes:
            holder = index.by_url.get(variant["product_url"])
            if holder is not None and holder is not existing:
                print(
                    f"⚠ Конфликт: {variant['product_url']} уже принадлежит sku={holder.sku}, "
                    f"пропускаю sku={variant['sku']}"
                )
                return "conflict"

        if not changes and not sku_changed:
            if not existing.is_active:
                existing.is_active = True
                _log_change(change_log, sku=variant["sku"], change_type="reactivated")
                return "reactivated"
            return "unchanged"

        for field, (old_value, new_value) in changes.items():
            setattr(existing, field, new_value)
            entry = {"sku": variant["sku"], "change_type": "updated", "field": field,
                     "old_value": _as_text(old_value), "new_value": _as_text(new_value)}
            if field == "price":
                entry["old_price"] = old_value
                entry["new_price"] = new_value
            _log_change(change_log, **entry)

        if not existing.is_active:
            _log_change(change_log, sku=variant["sku"], change_type="reactivated")
        if "product_url" in changes:
            index.move_url(existing, changes["product_url"][0], changes["product_url"][1])

        existing.is_active = True
        return "updated"

    product = Product(
        sku=variant["sku"],
        name=variant["name"],
        brand=variant["brand"],
        price=variant["price"],
        regular_price=variant.get("regular_price"),
        category_slug=variant["category_slug"],
        product_type=variant["product_type"],
        style_group=variant["style_group"],
        sport_type=variant["sport_type"],
        usage_type=variant["usage_type"],
        model_family=variant["model_family"],
        color=variant["color"],
        size=variant["size"],
        product_url=variant["product_url"],
        image_url=variant["image_url"],
        is_active=True,
    )
    db.add(product)
    index.add(product)
    _log_change(change_log, sku=variant["sku"], change_type="created",
                new_value=_as_text(variant["price"]), new_price=variant["price"])

    return "created"


BASE_URL = "https://topsport.ge"


def fetch_page(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    for attempt in range(FETCH_RETRIES + 1):
        is_last_attempt = attempt == FETCH_RETRIES
        try:
            response = SESSION.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except (requests.Timeout, requests.ConnectionError):
            if is_last_attempt:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
            continue

        if response.status_code in RETRYABLE_STATUS_CODES and not is_last_attempt:
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
            continue

        response.raise_for_status()
        return response.text


def extract_sku_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            data = json.loads(script.string)

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "sku" in item:
                        return item["sku"]
            elif isinstance(data, dict):
                if "sku" in data:
                    return data["sku"]

        except json.JSONDecodeError:
            continue

    return None

def split_sku_and_size(raw_sku: str | None) -> tuple[str | None, str | None]:
    if not raw_sku:
        return None, None

    parts = raw_sku.strip().split("-")

    if len(parts) < 2:
        return raw_sku, None

    last_part = parts[-1]

    try:
        float(last_part)
        base_sku = "-".join(parts[:-1])
        return base_sku, last_part
    except ValueError:
        return raw_sku, None

def extract_sizes_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    size_list = soup.select_one("div.attr-size ul.size-filter")
    if not size_list:
        return []

    sizes = []
    for link in size_list.select("li a"):
        size = link.get_text(strip=True)
        if size and size not in sizes:
            sizes.append(size)

    return sizes


MIN_SCRAPE_COVERAGE_RATIO = 0.5
COMMIT_BATCH_SIZE = 200
RESUME_OVERLAP = 200

CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), "scrape_checkpoint.txt")


def read_checkpoint() -> int:
    if os.path.exists(CHECKPOINT_FILE):
        content = open(CHECKPOINT_FILE).read().strip()
        if content.isdigit():
            return int(content)
    return 0


def write_checkpoint(index: int):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(index))


def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)


SCRAPED_SKUS_FILE = os.path.join(os.path.dirname(__file__), "scraped_skus.txt")


def append_scraped_skus(skus) -> None:
    with open(SCRAPED_SKUS_FILE, "a", encoding="utf-8") as f:
        for sku in skus:
            f.write(f"{sku}\n")


def read_scraped_skus() -> set:
    if not os.path.exists(SCRAPED_SKUS_FILE):
        return set()
    with open(SCRAPED_SKUS_FILE, encoding="utf-8") as f:
        return {line.rstrip("\n") for line in f if line.rstrip("\n")}


def clear_scraped_skus() -> None:
    if os.path.exists(SCRAPED_SKUS_FILE):
        os.remove(SCRAPED_SKUS_FILE)


DEACTIVATION_CHUNK_SIZE = 1000


def deactivate_missing_products(db, scraped_skus: set) -> dict:
    currently_active_count = db.query(Product).filter(Product.is_active == True).count()

    if currently_active_count > 0 and len(scraped_skus) < currently_active_count * MIN_SCRAPE_COVERAGE_RATIO:
        print(
            f"🚨 ВНИМАНИЕ: скрапинг вернул только {len(scraped_skus)} SKU, "
            f"а в базе сейчас {currently_active_count} активных товаров. "
            f"Деактивация ОТМЕНЕНА — похоже, скрапинг прошёл не полностью."
        )
        return {"deactivated_count": 0, "skipped": True}

    active_rows = db.query(Product.id, Product.sku).filter(Product.is_active == True).all()
    missing = [(product_id, sku) for product_id, sku in active_rows if sku not in scraped_skus]
    missing_ids = [product_id for product_id, _ in missing]

    for start in range(0, len(missing_ids), DEACTIVATION_CHUNK_SIZE):
        chunk = missing_ids[start:start + DEACTIVATION_CHUNK_SIZE]
        db.query(Product).filter(Product.id.in_(chunk)).update({Product.is_active: False})

    return {
        "deactivated_count": len(missing_ids),
        "skipped": False,
        "deactivated_skus": [sku for _, sku in missing if sku],
    }

def save_variant_safely(db, variant: dict, url: str, failed_urls: list,
                        index: ProductIndex | None = None) -> str | None:
    try:
        with db.begin_nested():
            status = save_product_variant(db, variant, index)
        return status
    except IntegrityError as error:
        if index is not None:
            index.forget(variant)
        failed_urls.append(url)
        print(f"⚠ Конфликт при сохранении sku={variant['sku']} ({url}): {error}")
        return None


def build_change_rows(change_log: list, run_id: int | None) -> list:
    return [ProductChange(run_id=run_id, **entry) for entry in change_log]


def commit_batch(db, batch: list, index: ProductIndex, failed_urls: list) -> ProductIndex:
    try:
        db.commit()
        return index
    except IntegrityError as error:
        db.rollback()
        print(
            f"⚠ Пакетное сохранение упало ({len(batch)} вариантов), "
            f"повторяю по одному: {error.orig}"
        )
        index = load_product_index(db)
        for variant, url in batch:
            save_variant_safely(db, variant, url, failed_urls, index)
        db.commit()
        return index

def _fetch_variants_safe(url: str):
    try:
        return build_product_variants(url), None
    except Exception as error:
        return None, error


def main(limit: int | None = None):
    urls = get_all_product_urls()

    start_index = 0
    resumed = False
    has_full_sku_history = False
    previous_scraped_skus = set()

    if limit is None:
        checkpoint_index = read_checkpoint()
        if checkpoint_index > 0:
            start_index = max(0, checkpoint_index - RESUME_OVERLAP)
            resumed = True
            has_full_sku_history = os.path.exists(SCRAPED_SKUS_FILE)
            previous_scraped_skus = read_scraped_skus()
            print(
                f"Найден чекпоинт на {checkpoint_index}. "
                f"Возобновляем с {start_index} (перепроверяем последние {RESUME_OVERLAP}). "
                f"SKU из прошлых частей прогона: {len(previous_scraped_skus)}."
            )
        else:
            clear_scraped_skus()
            has_full_sku_history = True
        urls_to_process = urls[start_index:]
    else:
        urls_to_process = urls[:limit]

    print(f"Найдено ссылок на товары: {len(urls)}. К обработке: {len(urls_to_process)}")

    db = SessionLocal()

    db.expire_on_commit = False

    scrape_run = ScrapeRun(resumed=resumed, urls_total=len(urls_to_process))
    db.add(scrape_run)
    db.commit()
    change_log = []
    index = load_product_index(db)
    print(f"Загружено товаров в память: {len(index.by_url)}")

    scraped_skus = set(previous_scraped_skus)
    created_count = 0
    updated_count = 0
    reactivated_count = 0
    unchanged_count = 0
    conflict_count = 0
    batch = []
    failed_urls = []
    processed_count = 0
    absolute_index = start_index - 1

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(_fetch_variants_safe, urls_to_process)

        for url, (variants, error) in zip(urls_to_process, results):
            absolute_index += 1

            if error is not None:
                failed_urls.append(url)
                print(f"⚠ Не удалось обработать {url}: {error}")
                continue

            for variant in variants:
                status = save_product_variant(db, variant, index, change_log)
                scraped_skus.add(variant["sku"])
                batch.append((variant, url))

                if status == "created":
                    created_count += 1
                elif status == "updated":
                    updated_count += 1
                elif status == "reactivated":
                    reactivated_count += 1
                elif status == "unchanged":
                    unchanged_count += 1
                elif status == "conflict":
                    conflict_count += 1

            processed_count += 1
            if limit is None and processed_count % COMMIT_BATCH_SIZE == 0:
                db.add_all(build_change_rows(change_log, scrape_run.id))
                change_log.clear()
                index = commit_batch(db, batch, index, failed_urls)
                append_scraped_skus({variant["sku"] for variant, _ in batch})
                batch = []
                write_checkpoint(absolute_index + 1)
                print(
                    f"…сохранено {processed_count} из {len(urls_to_process)} (глобальный индекс {absolute_index + 1})")

    db.add_all(build_change_rows(change_log, scrape_run.id))
    change_log.clear()
    index = commit_batch(db, batch, index, failed_urls)

    if failed_urls:
        print(f"⚠ Не удалось обработать {len(failed_urls)} ссылок из {len(urls_to_process)}")

    if limit is None and has_full_sku_history:
        deactivation_result = deactivate_missing_products(db, scraped_skus)
        db.add_all(build_change_rows(
            [{"sku": sku, "change_type": "deactivated"}
             for sku in deactivation_result.get("deactivated_skus", [])],
            scrape_run.id,
        ))
        db.commit()
        clear_checkpoint()
        clear_scraped_skus()
    elif limit is None:
        print("⚠ Возобновлённый прогон без файла SKU прошлых частей — деактивация пропущена.")
        clear_checkpoint()
        clear_scraped_skus()
        deactivation_result = {"deactivated_count": 0, "skipped": True}
    else:
        deactivation_result = {"deactivated_count": 0, "skipped": True}

    scrape_run.finished_at = datetime.now(UTC)
    scrape_run.urls_failed = len(failed_urls)
    scrape_run.created_count = created_count
    scrape_run.updated_count = updated_count
    scrape_run.reactivated_count = reactivated_count
    scrape_run.unchanged_count = unchanged_count
    scrape_run.conflict_count = conflict_count
    scrape_run.deactivated_count = deactivation_result["deactivated_count"]
    db.commit()

    total_changes = (
        created_count + updated_count + reactivated_count + deactivation_result["deactivated_count"]
    )

    if total_changes > 0:
        cache_service.clear()
        print("Кеш общения очищен (были изменения).")

    print("\n=== ИТОГИ СКРАПИНГА ===")
    print(f"Обработано ссылок: {len(urls_to_process) - len(failed_urls)} из {len(urls_to_process)}")
    print(f"Создано новых вариантов: {created_count}")
    print(f"Обновлено: {updated_count}")
    print(f"Реактивировано: {reactivated_count}")
    print(f"Без изменений: {unchanged_count}")
    print(f"Конфликтов (пропущено): {conflict_count}")
    print(f"Деактивировано: {deactivation_result['deactivated_count']}")
    if deactivation_result["skipped"]:
        print("⚠ Деактивация не выполнялась (см. причину выше).")

    db.close()


if __name__ == "__main__":
    main()