from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services.photo_search_service import MAX_PHOTO_BYTES
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


@router.post("/photo", response_model=ChatMessageResponse)
def chat_photo(
        user_id: str = Form(...),
        locale: str = Form("ka"),
        photo: UploadFile = File(...),
        db: Session = Depends(get_db),
):
    """29.10: фото клиента → похожие модели. Фото не сохраняется: читаем в память (не больше лимита + 1 байт,
    чтобы честно сказать «слишком большое»), ищем и забываем."""
    data = photo.file.read(MAX_PHOTO_BYTES + 1)
    return ChatUseCase().process_photo(db, user_id, data, photo.content_type or "", locale)