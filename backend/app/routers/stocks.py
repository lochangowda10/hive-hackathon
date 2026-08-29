from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..services.market_data import MarketDataError, get_candles, search_symbols

router = APIRouter(prefix="/api/stocks", tags=["stocks"], dependencies=[Depends(get_current_user)])


@router.get("/search")
def search(q: str = Query(min_length=1, max_length=40)):
    return search_symbols(q)


@router.get("/{symbol}/candles")
def candles(symbol: str, range: str = "1Y", interval: str = "1D"):
    try:
        return get_candles(symbol, range_label=range, interval_label=interval)
    except MarketDataError as exc:
        raise HTTPException(exc.status_code, exc.message)
