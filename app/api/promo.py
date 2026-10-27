from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.promo_service import build_deals_response, get_ticker

router = APIRouter(prefix="/promo", tags=["promo"])


@router.get("/ticker")
def promo_ticker(lang: str = "ka", db: Session = Depends(get_db)):
    """Бегущая строка для виджета: заголовок + модели (что именно — app/config/promo.json)."""
    return get_ticker(db, lang)


@router.get("/deals")
def promo_deals(lang: str = "ka", offset: int = 0, limit: int = 5, user_id: str = "web",
                max_price: float | None = None, db: Session = Depends(get_db)):
    """Кнопка виджета «📉 დღის ფასდაკლებები» и «კიდევ 5»: подборка скидок пачками, без LLM."""
    limit = max(1, min(limit, 20))
    # max_price — «კიდევ 5» после «скидки до 100 лари» продолжает с тем же бюджетом
    return build_deals_response(db, user_id, lang, limit=limit, offset=max(0, offset), max_price=max_price)