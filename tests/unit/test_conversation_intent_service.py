from app.schemas.conversation_intent import ConversationIntent
from app.services.conversation_intent_service import classify_conversation_intent


def test_classify_greeting_intent():
    assert classify_conversation_intent("hello") == ConversationIntent.GREETING
    assert classify_conversation_intent("hi") == ConversationIntent.GREETING
    assert classify_conversation_intent("გამარჯობა") == ConversationIntent.GREETING


def test_classify_gratitude_intent():
    assert classify_conversation_intent("thanks") == ConversationIntent.GRATITUDE
    assert classify_conversation_intent("thank you") == ConversationIntent.GRATITUDE
    assert classify_conversation_intent("მადლობა") == ConversationIntent.GRATITUDE


def test_classify_farewell_intent():
    assert classify_conversation_intent("bye") == ConversationIntent.FAREWELL
    assert classify_conversation_intent("good bye") == ConversationIntent.FAREWELL
    assert classify_conversation_intent("ნახვამდის") == ConversationIntent.FAREWELL


def test_classify_unknown_intent():
    assert classify_conversation_intent("nike") == ConversationIntent.UNKNOWN
    assert classify_conversation_intent("nike air max") == ConversationIntent.UNKNOWN
    assert classify_conversation_intent("40") == ConversationIntent.UNKNOWN


def test_classify_small_talk_intent():
    assert classify_conversation_intent("ok") == ConversationIntent.SMALL_TALK
    assert classify_conversation_intent("okay") == ConversationIntent.SMALL_TALK
    assert classify_conversation_intent("cool") == ConversationIntent.SMALL_TALK
    assert classify_conversation_intent("how are you") == ConversationIntent.SMALL_TALK
    assert classify_conversation_intent("კარგი") == ConversationIntent.SMALL_TALK