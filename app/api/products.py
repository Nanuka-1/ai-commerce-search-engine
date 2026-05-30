from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.services.search_analytics_service import get_top_queries, get_zero_queries

from app.db.session import get_db
from app.schemas.product import ProductSearchResponse, ProductCreate, Product
from app.services.product_service import create_new_product
from app.use_cases.search_products import SearchProductsUseCase

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/search", response_model=ProductSearchResponse)
def search_products_endpoint(q: str, db: Session = Depends(get_db)):
    use_case = SearchProductsUseCase()
    return use_case.execute(db, q)


@router.post("", response_model=Product)
def create_product_endpoint(product_data: ProductCreate, db: Session = Depends(get_db)):
    return create_new_product(db, product_data)


@router.get("/top-queries")
def top_queries_endpoint(limit: int = 10, db: Session = Depends(get_db)):
    return {
        "items": get_top_queries(db=db, limit=limit)
    }

@router.get("/zero-queries")
def zero_queries_endpoint(limit: int = 10, db: Session = Depends(get_db)):
    return {
        "items": get_zero_queries(db=db, limit=limit)
    }