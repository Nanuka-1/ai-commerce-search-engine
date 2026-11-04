"""04.11: предел фото 4 МБ — запрос с фото должен пройти в Vercel (≤ 4.5 МБ вместе с остальной формой)."""
from app.services.photo_search_service import MAX_PHOTO_BYTES, check_photo
from app.services.translations import translate

MB = 1024 * 1024


def test_limit_fits_vercel_request_size():
    assert MAX_PHOTO_BYTES == 4 * MB
    assert MAX_PHOTO_BYTES < 4.5 * MB


def test_four_mb_ok_bigger_rejected():
    assert check_photo(b"x" * (4 * MB), "image/jpeg") is None
    assert check_photo(b"x" * (4 * MB + 1), "image/jpeg") == "photo_too_big"


def test_message_tells_the_real_limit():
    assert "4 MB" in translate("photo_too_big", "ka")
    assert "4 MB" in translate("photo_too_big", "en")