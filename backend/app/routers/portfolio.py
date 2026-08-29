from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Holding, Trade, User
from ..services.portfolio import (
    behavior_profile, fetch_live_prices, fifo_round_trips, holdings_summary,
    parse_broker_file, portfolio_source,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

MAX_FILE_BYTES = 5 * 1024 * 1024


@router.post("/import")
async def import_file(
    file: UploadFile = File(...),
    broker: str = Form("unknown"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File too large (5 MB max).")
    try:
        parsed = parse_broker_file(data, file.filename or "upload.csv")
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    broker = broker[:24]
    if parsed["kind"] == "holdings":
        db.query(Holding).filter(Holding.user_id == user.id, Holding.broker == broker).delete()
        for r in parsed["rows"]:
            db.add(Holding(user_id=user.id, broker=broker, symbol_raw=r["symbol_raw"],
                           symbol=r["symbol"], name=r["name"], quantity=r["quantity"],
                           avg_price=r["price"], ltp_imported=r.get("ltp")))
    else:
        db.query(Trade).filter(Trade.user_id == user.id, Trade.broker == broker).delete()
        for r in parsed["rows"]:
            db.add(Trade(user_id=user.id, broker=broker, symbol_raw=r["symbol_raw"],
                         symbol=r["symbol"], name=r["name"], side=r["side"],
                         quantity=r["quantity"], price=r["price"],
                         trade_date=r.get("trade_date")))
    db.commit()
    return {"kind": parsed["kind"], "broker": broker, **parsed["report"],
            "note": "Re-importing the same broker replaces its previous rows."}


@router.get("/summary")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Holding).filter(Holding.user_id == user.id).all()
    if not rows:
        return {"empty": True, "positions": []}
    holdings = [{"symbol_raw": h.symbol_raw, "symbol": h.symbol, "name": h.name,
                 "quantity": h.quantity, "avg_price": h.avg_price,
                 "ltp_imported": h.ltp_imported} for h in rows]
    live = fetch_live_prices(sorted({h["symbol"] for h in holdings if h["symbol"]}))
    out = holdings_summary(holdings, live)
    note = None
    if out["live_quotes_missing"]:
        note = (f"{out['live_quotes_missing']} position(s) had no live quote "
                "(unresolved symbol or provider miss) — shown at file/avg price.")
    return {"empty": False, **out, "source": portfolio_source(note)}


@router.get("/behavior")
def behavior(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Trade).filter(Trade.user_id == user.id).all()
    if not rows:
        return {"empty": True}
    trades = [{"id": t.id, "symbol_raw": t.symbol_raw, "symbol": t.symbol,
               "name": t.name, "side": t.side, "quantity": t.quantity,
               "price": t.price, "trade_date": t.trade_date} for t in rows]
    trips, realized = fifo_round_trips(trades)
    profile = behavior_profile(trips, trades)
    return {"empty": False, "trade_count": len(trades),
            "realized_pnl": realized, "recent_trips": trips[-8:][::-1],
            "profile": profile,
            "source": portfolio_source("FIFO matching on your imported tradebook; math only, no AI.")}


@router.delete("")
def clear(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    h = db.query(Holding).filter(Holding.user_id == user.id).delete()
    t = db.query(Trade).filter(Trade.user_id == user.id).delete()
    db.commit()
    return {"deleted_holdings": h, "deleted_trades": t}
