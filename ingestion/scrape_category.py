import requests
from bs4 import BeautifulSoup
import re
import json

from app.db.session import SessionLocal
from app.db.models import Product
from app.services.product_intent_service import extract_product_intent

BASE_URL = "https://topsport.ge"


def fetch_page(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    return response.text


def parse_products(html: str):
    soup = BeautifulSoup(html, "html.parser")

    products = []
    seen_urls = set()

    cards = soup.find_all("a", href=True)

    for card in cards:
        href = card.get("href")

        if not href or "/product/" not in href:
            continue

        onclick = card.get("onclick")
        img = card.find("img")

        # ვიღებთ მოხლოდ საჭირო ბმულებს:
        # ან თუ არის  onclick  dataLayer,
        # ან თუ არის img  დასახელება/სურათი
        if not onclick and not img:
            continue

        full_url = href

        # დუბლირების დაცვა
        if full_url in seen_urls:
            continue

        brand = None
        price = None

        if onclick:
            brand_match = re.search(r"item_brand:'(.*?)'", onclick)
            if brand_match:
                brand = brand_match.group(1)

            if brand and brand.lower() != "nike":
                continue

            price_match = re.search(r"price:(\d+)", onclick)
            if price_match:
                price = float(price_match.group(1))

        image_url = img.get("src") if img else None
        name = img.get("alt") if img else None

        # თუ არაფერი სასარგებლო ვტოვებთ
        if not name and not brand and not price:
            continue

        size = None

        # სკუდან გამოგვაქვს ზომა (მაგალითად: HJ9198-402-44)
        sku_match = re.search(r"-(\d+(?:\.\d+)?)$", full_url)
        if sku_match:
            size = sku_match.group(1)

        products.append({
            "name": name,
            "brand": brand,
            "price": price,
            "url": full_url,
            "image_url": image_url,
            "size": size
        })
        seen_urls.add(full_url)

    return products


def extract_category_slug(category_url: str) -> str:
    return category_url.rstrip("/").split("/")[-1]


def save_products(products, category_slug: str):
    db = SessionLocal()

    for p in products:
        product_html = fetch_page(p["url"])

        sizes = extract_sizes_from_html(product_html)
        raw_sku = extract_sku_from_html(product_html)
        base_sku, fallback_size = split_sku_and_size(raw_sku)

        if not sizes and fallback_size:
            sizes = [fallback_size]

        if not base_sku:
            continue

        classification_text = " ".join(
            part for part in [p["name"], p["brand"], base_sku, category_slug] if part
        )

        product_intent = extract_product_intent(classification_text)

        print("RAW SKU:", raw_sku, "=>", "BASE SKU:", base_sku, "SIZES:", sizes)

        for parsed_size in sizes:
            variant_sku = f"{base_sku}-{parsed_size}"

            existing = db.query(Product).filter(
                Product.sku == variant_sku
            ).first()

            if existing:
                continue

            product = Product(
                sku=variant_sku,
                name=p["name"],
                brand=p["brand"],
                price=p["price"],
                category_slug=category_slug,
                style_group=product_intent.style_group.value if product_intent else None,
                sport_type=product_intent.sport_type.value if product_intent else None,
                usage_type=product_intent.usage_type.value if product_intent else None,
                size=parsed_size,
                product_url=f'{p["url"]}?size={parsed_size}',
                image_url=p["image_url"],
            )

            db.add(product)

    db.commit()
    db.close()


CATEGORY_URLS = [
    "https://topsport.ge/ka/products/mamakatsis-sportuli-fekhsatsmeli",
    "https://topsport.ge/ka/products/qalis-fekhsatsmeli",
    "https://topsport.ge/ka/products/bavshvis-fekhsatsmeli",
    "https://topsport.ge/ka/products/fekhsatsmeli",
]

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
    text = soup.get_text(" ", strip=True)

    sizes = re.findall(r"\b\d{2}(?:\.\d)?\b", text)

    valid_sizes = []
    for size in sizes:
        value = float(size)
        if 20 <= value <= 50 and size not in valid_sizes:
            valid_sizes.append(size)

    return valid_sizes


def main():
    for url in CATEGORY_URLS:
        print(f"\nPROCESSING: {url}")

        category_slug = extract_category_slug(url)

        html = fetch_page(url)
        products = parse_products(html)

        print(f"FOUND: {len(products)} products")
        print(f"CATEGORY: {category_slug}")


        save_products(products, category_slug)

    print("\nAll categories processed")



if __name__ == "__main__":
    main()