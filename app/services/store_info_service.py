"""
Вопросы о магазине (шаг U1): доставка, возврат, оплата, магазины, контакты.

Ответы — ТОЛЬКО из правил магазина: app/config/store_info.json (topsport.ge/terms-conditions, /stores).
Тему узнаём по корням слов, без LLM: надёжно и бесплатно. Тексты и ссылки правятся в файле, не в коде.
"""
import json
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "store_info.json"

# Порядок важен: "დაბრუნების მიწოდება" — это возврат; "მაღაზიის ტელეფონი" — контакт.
TOPIC_KEYWORDS = [
    ("returns", ["დაბრუნ", "გაცვლ", "გადაცვლ", "return", "exchange", "refund"]),
    ("delivery", ["მიწოდ", "მიტან", "კურიერ", "delivery", "deliver", "shipping", "courier"]),
    ("payment", ["გადახდ", "ბარათით", "payment", "pay by", "card payment"]),
    ("contact", ["ტელეფონ", "საკონტაქტო", "კონტაქტ", "მეილ", "phone", "contact", "e-mail", "email", "call you"]),
    ("stores", ["მაღაზი", "ფილიალ", "მისამართ", "სად ხართ", "სად მდებარეობ", "სამუშაო საათ", "გახსნილ",
                "store", "shop", "branch", "address", "where are you", "opening hours", "open"]),
]


def load_store_info(path: Path = CONFIG_PATH) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def detect_store_topic(message: str) -> str | None:
    text = (message or "").lower()
    for topic, keywords in TOPIC_KEYWORDS:
        if any(re.search(rf"(?<![\w]){re.escape(word)}", text) for word in keywords):
            return topic
    return None


def build_store_answer(topic: str, language: str, info: dict) -> str | None:
    language = language if language in ("ka", "en") else "ka"
    template = info.get("answers", {}).get(topic, {}).get(language)
    if not template:
        return None
    links = info.get("links", {})
    return template.format(
        terms=links.get("terms", {}).get(language, ""),
        stores=links.get("stores", {}).get(language, ""),
        contact=links.get("contact", {}).get(language, ""),
        phone=info.get("phone", ""),
        email=info.get("email", ""),
    )


def build_store_info_response(message: str, user_id: str, language: str, info: dict | None = None) -> dict | None:
    """Ответ чата или None (тема не распознана / файл недоступен → обычный поиск)."""
    topic = detect_store_topic(message)
    if not topic:
        return None
    info = info if info is not None else load_store_info()
    if not info:
        return None
    text = build_store_answer(topic, language, info)
    if not text:
        return None
    return {
        "type": "store_info",
        "message": text,
        "data": {"user_id": user_id, "topic": topic, "links": info.get("links", {})},
    }