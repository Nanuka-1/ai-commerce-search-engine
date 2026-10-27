from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    user_id: str
    message: str
    locale: str = "ka"
    limit: int = 5
    offset: int = 0
    action: str | None = None  # 26.10: кнопка виджета «more» / «new_search»

class ChatMessageResponse(BaseModel):
    type: str
    data: dict | None = None
    message: str | None = None
    meta: dict | None = None      # ответ LLM или шаблон, модель, время — для демо-страницы
