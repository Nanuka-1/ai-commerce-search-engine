"""29.10 (поиск по фото, шаг 1): какие картинки каталога отправлять в Gemini."""
from types import SimpleNamespace

from ingestion.build_image_embeddings import IMAGE_EMBEDDING_MODEL, first_by_word, plan_images

SHOE = "ბავშვი, ბავშვის ფეხსაცმელი, ბავშვის სპორტული ფეხსაცმელი"
JACKET = "ქალი, ქალის ტანსაცმელი, ქალის ქურთუკი"


def card(image, category=SHOE):
    return SimpleNamespace(image_url=image, category_slug=category)


def test_new_pages_are_planned_and_same_image_counted_once():
    cards = {"p1": card("img/a.jpg"), "p2": card("img/a.jpg"), "p3": card("img/b.jpg")}
    plan = dict(plan_images(cards, saved={}, model=IMAGE_EMBEDDING_MODEL))
    assert plan == {"img/a.jpg": ["p1", "p2"], "img/b.jpg": ["p3"]}     # a.jpg — один вызов Gemini на 2 модели


def test_unchanged_image_is_skipped_changed_is_recounted():
    cards = {"p1": card("img/a.jpg"), "p2": card("img/new.jpg")}
    saved = {"p1": ("img/a.jpg", IMAGE_EMBEDDING_MODEL), "p2": ("img/old.jpg", IMAGE_EMBEDDING_MODEL)}
    assert plan_images(cards, saved, IMAGE_EMBEDDING_MODEL) == [("img/new.jpg", ["p2"])]


def test_other_gemini_model_is_recounted():
    cards = {"p1": card("img/a.jpg")}
    saved = {"p1": ("img/a.jpg", "old-model")}
    assert plan_images(cards, saved, IMAGE_EMBEDDING_MODEL) == [("img/a.jpg", ["p1"])]


def test_footwear_first_and_no_image_skipped():
    cards = {"jacket": card("img/j.jpg", JACKET), "shoe": card("img/s.jpg"), "empty": card("", SHOE)}
    plan = plan_images(cards, saved={}, model=IMAGE_EMBEDDING_MODEL)
    assert [pages for _, pages in plan] == [["shoe"], ["jacket"]]


def test_word_first_moves_matching_models_to_the_front():
    plan = [("a.jpg", ["…/nike-air-1"]), ("b.jpg", ["…/adidas-samba-og-w-1"]), ("c.jpg", ["…/puma-1"])]
    assert [image for image, _ in first_by_word(plan, "SAMBA")] == ["b.jpg", "a.jpg", "c.jpg"]
    assert first_by_word(plan, None) == plan