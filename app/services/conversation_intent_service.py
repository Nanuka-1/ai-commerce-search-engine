from app.schemas.conversation_intent import ConversationIntent


GREETING_WORDS = {
    "hello",
    "hi",
    "hey",
    "გამარჯობა",
}

GRATITUDE_WORDS = {
    "thanks",
    "thank you",
    "madloba",
    "მადლობა",
}

FAREWELL_WORDS = {
    "bye",
    "goodbye",
    "good bye",
    "see you",
    "ნახვამდის",
}

SMALL_TALK_WORDS = {
    "ok",
    "okay",
    "cool",
    "great",
    "nice",
    "good",
    "how are you",
    "thanks ok",
    "კარგი",
}

def classify_conversation_intent(message: str) -> ConversationIntent:
    normalized = message.strip().lower()

    if normalized in GREETING_WORDS:
        return ConversationIntent.GREETING

    if normalized in GRATITUDE_WORDS:
        return ConversationIntent.GRATITUDE

    if normalized in FAREWELL_WORDS:
        return ConversationIntent.FAREWELL

    if normalized in SMALL_TALK_WORDS:
        return ConversationIntent.SMALL_TALK

    return ConversationIntent.UNKNOWN