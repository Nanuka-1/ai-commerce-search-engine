from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    user_id: str
    message: str
    locale: str = "ka"
    limit: int = 5
    offset: int = 0


class ChatMessageResponse(BaseModel):
    type: str
    data: dict | None = None
    message: str | None = None