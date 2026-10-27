import pytest

from app.db.models import Product
from app.repositories.product_repository import get_products_by_query


def make_candidate_product(index: int) -> Product:
    return Product(
        sku=f"TEST-CANDPROBE-{index}",
        name=f"CandidateProbe Runner {index}",
        brand="candidateprobe",
        price=100.0,
        category_slug="shoes",
        size="42",
        product_url=f"https://topsport.ge/test-candidateprobe-{index}",
        image_url=None,
    )


@pytest.fixture
def seeded_candidate_products(db):
    products = [make_candidate_product(i) for i in range(60)]
    db.add_all(products)
    db.commit()

    yield products

    for product in products:
        db.delete(product)
    db.commit()


def test_get_products_by_query_does_not_truncate_candidates_before_ranking(
    db, seeded_candidate_products
):
    items, total_count = get_products_by_query(
        db,
        "candidateprobe",
        limit=50,
        offset=0,
    )

    assert total_count == 60
    assert len(items) == 60