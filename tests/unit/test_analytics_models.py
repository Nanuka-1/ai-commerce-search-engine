from app.db.models import ProductChange, ScrapeRun


def test_scrape_run_and_product_change_are_persisted(db):
    run = ScrapeRun(urls_total=10, created_count=2, updated_count=1)
    db.add(run)
    db.commit()

    db.add_all([
        ProductChange(run_id=run.id, sku="ANALYTICS-SKU-1", change_type="created"),
        ProductChange(run_id=run.id, sku="ANALYTICS-SKU-2", change_type="updated",
                      field="price", old_value="390.0", new_value="156.0"),
    ])
    db.commit()

    changes = db.query(ProductChange).filter(ProductChange.run_id == run.id).all()

    assert run.started_at is not None
    assert run.finished_at is None
    assert {c.change_type for c in changes} == {"created", "updated"}
    price_change = next(c for c in changes if c.field == "price")
    assert (price_change.old_value, price_change.new_value) == ("390.0", "156.0")

def test_price_change_direction_can_be_queried(db):
    run = ScrapeRun()
    db.add(run)
    db.commit()

    db.add_all([
        ProductChange(run_id=run.id, sku="PRICE-DOWN", change_type="updated", field="price",
                      old_value="390.0", new_value="156.0", old_price=390.0, new_price=156.0),
        ProductChange(run_id=run.id, sku="PRICE-UP", change_type="updated", field="price",
                      old_value="100.0", new_value="120.0", old_price=100.0, new_price=120.0),
    ])
    db.commit()

    decreased = db.query(ProductChange).filter(
        ProductChange.run_id == run.id, ProductChange.new_price < ProductChange.old_price
    ).all()
    increased = db.query(ProductChange).filter(
        ProductChange.run_id == run.id, ProductChange.new_price > ProductChange.old_price
    ).all()

    assert [c.sku for c in decreased] == ["PRICE-DOWN"]
    assert [c.sku for c in increased] == ["PRICE-UP"]