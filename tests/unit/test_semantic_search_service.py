from app.services.semantic_search_service import build_semantic_sql


def test_no_rules_understood_only_active_filter():
    sql, params = build_semantic_sql(None, None, None, limit=10)
    assert "p.is_active" in sql
    assert ":sizes" not in sql and ":brand" not in sql and ":category_like" not in sql
    assert params == {"limit": 10}


def test_size_and_brand_become_hard_filters():
    sql, params = build_semantic_sql(["42", "41-42", "42-43"], "Nike", None, limit=5)
    assert "p.size = ANY(:sizes)" in sql
    assert "lower(p.brand) = :brand" in sql
    assert params["sizes"] == ["42", "41-42", "42-43"]
    assert params["brand"] == "nike"


def test_adult_category_includes_unisex():
    sql, params = build_semantic_sql(None, None, "მამაკაც", limit=10)
    assert "Unisex%" in sql
    assert params["category_like"] == "%მამაკაც%"


def test_kids_category_without_unisex():
    sql, params = build_semantic_sql(None, None, "ბავშვ", limit=10)
    assert "Unisex%" not in sql
    assert params["category_like"] == "%ბავშვ%"


def test_results_ordered_by_distance_and_limited():
    sql, _ = build_semantic_sql(None, None, None, limit=10)
    assert "ORDER BY e.embedding <=> CAST(:query_vector AS vector)" in sql
    assert "LIMIT :limit" in sql