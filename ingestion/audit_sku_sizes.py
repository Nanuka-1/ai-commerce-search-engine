import csv
import random
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from app.db.session import SessionLocal
from app.db.models import Product
from scrape_category import (
    fetch_page,
    extract_sku_from_html,
    extract_sizes_from_html,
    extract_product_details_from_html,
)

PER_BRAND = 15
WORKERS = 10
OUTPUT_FILE = "audit_sku_sizes.csv"

random.seed(42)


def load_sample() -> list[tuple[str, str]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Product.brand, Product.product_url)
            .filter(Product.is_active == True, Product.product_url.isnot(None))
            .all()
        )
    finally:
        db.close()

    pages_by_brand = defaultdict(set)
    for brand, url in rows:
        pages_by_brand[brand or "UNKNOWN"].add(url.split("?")[0])

    sample = []
    for brand, pages in sorted(pages_by_brand.items()):
        pages = sorted(pages)
        for page in random.sample(pages, min(PER_BRAND, len(pages))):
            sample.append((brand, page))
    return sample


def audit_page(item: tuple[str, str]) -> dict:
    brand, url = item
    row = {"db_brand": brand, "url": url, "page_brand": "", "name": "",
           "raw_sku": "", "sizes": "", "size_count": 0,
           "sku_ends_with_size": False, "error": ""}
    try:
        html = fetch_page(url)
    except Exception as error:
        row["error"] = str(error)[:100]
        return row

    raw_sku = extract_sku_from_html(html) or ""
    sizes = extract_sizes_from_html(html)
    details = extract_product_details_from_html(html)

    row.update({
        "page_brand": details["brand"] or "",
        "name": details["name"] or "",
        "raw_sku": raw_sku,
        "sizes": "|".join(sizes),
        "size_count": len(sizes),
        "sku_ends_with_size": bool(raw_sku and sizes and raw_sku.endswith(f"-{sizes[0]}")),
    })
    return row


def print_summary(rows: list[dict]):
    by_brand = defaultdict(list)
    for row in rows:
        by_brand[row["db_brand"]].append(row)

    print(f"\n{'brand':<14}{'pages':>6}{'no_sku':>8}{'no_size':>9}{'multi':>7}{'sku+size':>10}{'errors':>8}  size examples")
    for brand, items in sorted(by_brand.items()):
        size_examples = Counter(s for r in items for s in r["sizes"].split("|") if s)
        print(
            f"{brand:<14}{len(items):>6}"
            f"{sum(1 for r in items if not r['raw_sku'] and not r['error']):>8}"
            f"{sum(1 for r in items if r['size_count'] == 0 and not r['error']):>9}"
            f"{sum(1 for r in items if r['size_count'] > 1):>7}"
            f"{sum(1 for r in items if r['sku_ends_with_size']):>10}"
            f"{sum(1 for r in items if r['error']):>8}"
            f"  {', '.join(s for s, _ in size_examples.most_common(8))}"
        )

    variant_urls = defaultdict(set)
    for row in rows:
        for size in row["sizes"].split("|"):
            if row["raw_sku"] and size:
                variant_urls[(row["raw_sku"], size)].add(row["url"])
    collisions = {key: urls for key, urls in variant_urls.items() if len(urls) > 1}
    print(f"\nКоллизии (одинаковые SKU+размер на разных страницах): {len(collisions)}")
    for (sku, size), urls in list(collisions.items())[:10]:
        print(f"  {sku} / {size}: {sorted(urls)}")


def main():
    sample = load_sample()
    print(f"Страниц в выборке: {len(sample)}")

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        rows = list(executor.map(audit_page, sample))

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Сохранено в {OUTPUT_FILE}")
    print_summary(rows)


if __name__ == "__main__":
    main()