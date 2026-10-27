import time

from bs4 import BeautifulSoup

from app.db.session import SessionLocal
from app.db.models import Product
from scrape_category import (
    get_all_product_urls,
    fetch_page,
    extract_sku_from_html,
    extract_sizes_from_html,
    extract_product_details_from_html,
    get_base_sku,
)

SAMPLE = 20
WORKERS = 20


def main():
    t0 = time.perf_counter()
    all_urls = get_all_product_urls()
    sitemap_time = time.perf_counter() - t0
    step = max(1, len(all_urls) // SAMPLE)
    urls = all_urls[::step][:SAMPLE]

    db = SessionLocal()
    totals = {"fetch": 0.0, "parse": 0.0, "lxml_once": 0.0, "db_per_variant": 0.0}
    total_variants = 0

    for url in urls:
        t0 = time.perf_counter()
        html = fetch_page(url)
        t1 = time.perf_counter()

        raw_sku = extract_sku_from_html(html)
        sizes = extract_sizes_from_html(html)
        extract_product_details_from_html(html)
        t2 = time.perf_counter()

        BeautifulSoup(html, "lxml")
        t3 = time.perf_counter()

        db_time = 0.0
        if raw_sku and sizes:
            base_sku = get_base_sku(raw_sku, sizes)
            for size in sizes:
                d0 = time.perf_counter()
                with db.begin_nested():
                    db.query(Product).filter(Product.sku == f"{base_sku}-{size}").first()
                db_time += time.perf_counter() - d0
            total_variants += len(sizes)

        totals["fetch"] += t1 - t0
        totals["parse"] += t2 - t1
        totals["lxml_once"] += t3 - t2
        totals["db_per_variant"] += db_time
        print(f"fetch={t1 - t0:5.2f}s  parse={t2 - t1:5.2f}s  lxml_once={t3 - t2:5.2f}s  "
              f"db={db_time:5.2f}s  variants={len(sizes)}  html={len(html) // 1024}KB")

    db.rollback()
    db.close()

    n = len(urls)
    fetch = totals["fetch"] / n
    parse = totals["parse"] / n
    lxml_once = totals["lxml_once"] / n
    db_per_url = totals["db_per_variant"] / n
    variants_per_url = total_variants / n

    print(f"\nSitemap (48 файлов): {sitemap_time:.1f}s, ссылок: {len(all_urls)}")
    print(f"Среднее на URL: fetch={fetch:.2f}s  parse(3x html.parser)={parse:.2f}s  "
          f"lxml один раз={lxml_once:.2f}s  db={db_per_url:.2f}s  вариантов={variants_per_url:.1f}")
    print("\nОценка узкого места (сек на URL в боевом прогоне):")
    print(f"  сеть при {WORKERS} потоках : {fetch / WORKERS:.2f}")
    print(f"  парсинг (GIL, по очереди): {parse:.2f}")
    print(f"  БД (главный поток)       : {db_per_url:.2f}")


if __name__ == "__main__":
    main()