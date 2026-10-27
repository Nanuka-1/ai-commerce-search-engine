from app.repositories.product_repository import clean_query_tokens


def test_punctuation_is_not_a_search_word():
    assert clean_query_tokens("როგორ ხარ ?") == ["როგორ", "ხარ"]
    assert clean_query_tokens("nike 42!") == ["nike", "42"]
    assert clean_query_tokens("? !") == []
    assert clean_query_tokens("(adidas), samba") == ["adidas", "samba"]
    # знаки ВНУТРИ слова сохраняются: артикул, полуразмер, буквенный размер
    assert clean_query_tokens("CW2288-111 42.5 XS/S") == ["CW2288-111", "42.5", "XS/S"]
    assert clean_query_tokens(None) == []