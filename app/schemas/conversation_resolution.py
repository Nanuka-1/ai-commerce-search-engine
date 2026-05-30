from pydantic import BaseModel


class ConversationResolution(BaseModel):
    query: str
    should_search: bool = True
    reason: str | None = None