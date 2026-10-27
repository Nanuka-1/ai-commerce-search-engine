from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.use_cases.chat_use_case import ChatUseCase

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def chat_message(request: ChatMessageRequest, db: Session = Depends(get_db)):
    use_case = ChatUseCase()
    return use_case.process_text(
        db,
        request.user_id,
        request.message,
        request.locale,
        request.limit,
        request.offset,
        action=request.action,      # 26.10: кнопка виджета «more» / «new_search» (None — обычное сообщение)
    )