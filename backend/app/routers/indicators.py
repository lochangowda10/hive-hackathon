from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..services.indicators import compute, registry_meta
from ..services.market_data import MarketDataError, get_candles

router = APIRouter(prefix="/api/indicators", tags=["indicators"],
                   dependencies=[Depends(get_current_user)])


@router.get("")
def catalog():
    """The full indicator catalog with educational metadata for the dialog."""
    return {"indicators": registry_meta()}


class IndicatorReq(BaseModel):
    uid: str = Field(max_length=40)
    id: str = Field(max_length=40)
    params: dict = {}


class BatchIn(BaseModel):
    range: str = "1Y"
    interval: str = "1D"
    indicators: list[IndicatorReq] = Field(max_length=20)


@router.post("/{symbol}")
def compute_batch(symbol: str, body: BatchIn):
    """Compute a batch of indicator instances against one candle fetch."""
    try:
        data = get_candles(symbol, range_label=body.range, interval_label=body.interval)
    except MarketDataError as exc:
        raise HTTPException(exc.status_code, exc.message)

    results, errors = [], []
    for req in body.indicators:
        try:
            out = compute(req.id, data["candles"], req.params)
            out["uid"] = req.uid
            results.append(out)
        except KeyError as exc:
            errors.append({"uid": req.uid, "error": str(exc)})
    return {"symbol": data["symbol"], "results": results, "errors": errors,
            "source": data["source"]}
