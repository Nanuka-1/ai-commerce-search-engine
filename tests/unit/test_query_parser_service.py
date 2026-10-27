from app.services.query_parser_service import extract_usage_type_from_query


def test_extract_usage_type_from_query():
    assert extract_usage_type_from_query("nike running 44") == "running"
    assert extract_usage_type_from_query("adidas casual shoes") == "casual"
    assert extract_usage_type_from_query("nike air max") is None

def test_extract_usage_type_from_query_detects_georgian_basketball():
    assert extract_usage_type_from_query("კალათბურთის ფეხსაცმელი") == "basketball"

def test_extract_usage_type_from_query_detects_georgian_running():
    assert extract_usage_type_from_query("სარბენი ფეხსაცმელი") == "running"
    assert extract_usage_type_from_query("სირბილისთვის ფეხსაცმელი") == "running"