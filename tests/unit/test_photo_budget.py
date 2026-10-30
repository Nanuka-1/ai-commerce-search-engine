"""30.10: общий лимит времени на фото — описание ждём только ОСТАТОК после метки (живьём кофе ждал 17.6 с)."""
import threading
import time

import app.services.photo_search_service as photo


def test_slow_description_does_not_add_second_full_budget(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(photo, "PHOTO_BUDGET_SECONDS", 0.6)
    monkeypatch.setattr(photo, "embed_photo", lambda data, mime: time.sleep(0.4) or [1.0, 0.0])
    monkeypatch.setattr(photo, "describe_photo", lambda data, mime: release.wait(5) and None)
    monkeypatch.setattr(photo, "nearest_pages", lambda db, vector, understanding: [])

    started = time.monotonic()
    result = photo.search_by_photo(None, b"jpeg", "image/jpeg")
    elapsed = time.monotonic() - started
    release.set()

    assert elapsed < 0.9                      # было бы ~1.0 (0.4 метка + 0.6 ещё раз на описание)
    assert result.errors == ["understanding: timeout"]
    assert result.verdict == photo.NOT_FOUND