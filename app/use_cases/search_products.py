from sqlalchemy.orm import Session
from app.services.product_service import search_products


class SearchProductsUseCase:
    def execute(self, db: Session, query: str):
        if not query or not query.strip():
            return {"items": [], "total": 0}

        return search_products(db, query.strip())





