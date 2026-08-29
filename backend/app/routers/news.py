from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..services.news import get_market_news, get_symbol_news

router = APIRouter(prefix="/api/news", tags=["news"],
                   dependencies=[Depends(get_current_user)])


@router.get("/market")
def market():
    try:
        return get_market_news()
    except Exception as exc:
        raise HTTPException(502, f"News fetch failed: {exc}")


@router.get("/{symbol}")
def symbol(symbol: str):
    try:
        return get_symbol_news(symbol)
    except Exception as exc:
        raise HTTPException(502, f"News fetch failed: {exc}")
