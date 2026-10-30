"""29.10 (поиск по фото, шаг 3): чат отвечает на фото честно — без Gemini и базы (поиск подменён)."""
import app.use_cases.chat_use_case as chat_module
from app.services import cache_service
from app.services.photo_search_service import EXACT, JUNK, NOT_FOUND, SIMILAR, UNAVAILABLE, PhotoResult
from app.services.translations import translate
from app.use_cases.chat_use_case import ChatUseCase

PAGE = "https://topsport.ge/ka/product/adidas-qalis-sportuli-fekhsatsmeli-samba-og-w-{}"
PAGES = [(PAGE.format(n), 0.87 - n / 100) for n in range(1, 8)]
CARD = {"name": "Adidas ქალის სპორტული ფეხსაცმელი SAMBA OG W", "brand": "Adidas", "sizes": ["37", "38"]}


def _photo(monkeypatch, result, cards_by_page=None):
    cache_service.clear()
    searched = []
    monkeypatch.setattr(chat_module, "search_by_photo",
                        lambda db, data, mime: searched.append(mime) or result)
    monkeypatch.setattr(chat_module, "get_model_cards_by_page", lambda db, page: (
        cards_by_page.get(page, []) if cards_by_page is not None else [{**CARD, "product_url": page}]))
    response = ChatUseCase().process_photo(None, "u-photo", b"jpeg-bytes", "image/jpeg", "ka")
    return response, searched


def test_exact_photo_shows_this_model_first_and_remembers_it(monkeypatch):
    response, _ = _photo(monkeypatch, PhotoResult(EXACT, PAGES, {"is_product": True}))
    items = response["data"]["results"]["items"]
    assert response["message"] == translate("photo_exact", "ka")
    assert items[0]["product_url"] == PAGES[0][0] and len(items) == ChatUseCase.PHOTO_CARDS
    assert "ფეხსაცმელი" in response["meta"]["dialog_state"]            # дальше «а 38?» — об этой модели
    assert response["meta"]["photo_top"][0] == 0.86


def test_similar_photo_says_honestly_not_exact(monkeypatch):
    response, _ = _photo(monkeypatch, PhotoResult(SIMILAR, PAGES, {"is_product": True}))
    assert response["message"] == translate("photo_similar", "ka")
    assert len(response["data"]["results"]["items"]) == ChatUseCase.PHOTO_CARDS
    assert "dialog_state" not in response["meta"]                     # «похожие» — не утверждаем модель


def test_junk_unavailable_not_found_without_cards(monkeypatch):
    for verdict in (JUNK, UNAVAILABLE, NOT_FOUND):
        response, _ = _photo(monkeypatch, PhotoResult(verdict, [], None))
        assert response["message"] == translate(f"photo_{verdict}", "ka")
        assert response["data"]["results"]["items"] == []


def test_exact_but_models_gone_from_sale_is_not_found(monkeypatch):
    response, _ = _photo(monkeypatch, PhotoResult(EXACT, PAGES, {"is_product": True}), cards_by_page={})
    assert response["message"] == translate("photo_not_found", "ka")


def test_bad_photo_is_rejected_before_search(monkeypatch):
    cache_service.clear()
    called = []
    monkeypatch.setattr(chat_module, "search_by_photo", lambda *args: called.append(1))
    response = ChatUseCase().process_photo(None, "u-photo", b"gif", "image/gif", "ka")
    assert response["message"] == translate("photo_bad_format", "ka")
    assert called == []