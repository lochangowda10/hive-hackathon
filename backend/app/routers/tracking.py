from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Alert, TradePlan, User, WatchItem
from ..services.grading import aggregate, grade_plan
from ..services.market_data import MarketDataError, batch_quotes, get_candles

router = APIRouter(prefix="/api", tags=["tracking"])


# ----------------------------------------------------------------- watchlist

@router.get("/watchlist")
def watchlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(WatchItem).filter(WatchItem.user_id == user.id)
            .order_by(WatchItem.added_at.asc()).all())
    quotes = batch_quotes(sorted({r.symbol for r in rows}))
    return {"items": [{"id": r.id, "symbol": r.symbol, "name": r.name,
                       **quotes.get(r.symbol, {})} for r in rows]}


@router.post("/watchlist/{symbol}")
def watch(symbol: str, name: str = "", user: User = Depends(get_current_user),
          db: Session = Depends(get_db)):
    symbol = symbol.upper()
    existing = (db.query(WatchItem)
                .filter(WatchItem.user_id == user.id, WatchItem.symbol == symbol).first())
    if existing:
        db.delete(existing)
        db.commit()
        return {"watched": False, "symbol": symbol}
    db.add(WatchItem(user_id=user.id, symbol=symbol, name=name[:120] or symbol))
    db.commit()
    return {"watched": True, "symbol": symbol}


# -------------------------------------------------------------------- alerts

@router.get("/alerts")
def alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(Alert).filter(Alert.user_id == user.id)
            .order_by(Alert.created_at.desc()).limit(50).all())
    return {"alerts": [
        {"id": a.id, "symbol": a.symbol, "price": a.price, "direction": a.direction,
         "status": a.status, "triggered_price": a.triggered_price,
         "created_at": a.created_at.isoformat()} for a in rows]}


@router.post("/alerts")
def create_alert(symbol: str, price: float, direction: str,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    direction = "above" if direction != "below" else "below"
    a = Alert(user_id=user.id, symbol=symbol.upper(), price=round(price, 2),
              direction=direction)
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "symbol": a.symbol, "price": a.price, "direction": a.direction}


@router.delete("/alerts/{alert_id}")
def delete_alert(alert_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a and a.user_id == user.id:
        db.delete(a)
        db.commit()
    return {"deleted": alert_id}


@router.post("/alerts/check")
def check_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Called by the app while open (and on load): marks crossed alerts."""
    from datetime import datetime, timezone
    active = (db.query(Alert)
              .filter(Alert.user_id == user.id, Alert.status == "active").all())
    if not active:
        return {"triggered": [], "active": 0}
    quotes = batch_quotes(sorted({a.symbol for a in active}))
    fired = []
    for a in active:
        q = quotes.get(a.symbol)
        if not q:
            continue
        crossed = q["price"] >= a.price if a.direction == "above" else q["price"] <= a.price
        if crossed:
            a.status = "triggered"
            a.triggered_at = datetime.now(timezone.utc)
            a.triggered_price = q["price"]
            fired.append({"id": a.id, "symbol": a.symbol, "price": a.price,
                          "direction": a.direction, "triggered_price": q["price"]})
    db.commit()
    return {"triggered": fired,
            "active": sum(1 for a in active if a.status == "active")}


# ------------------------------------------------------------- track record

@router.post("/track-record")
def track_record(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Grade every open plan against actual subsequent candles, then report
    the engine's own scorecard. One candle fetch per distinct symbol."""
    plans = (db.query(TradePlan).filter(TradePlan.user_id == user.id)
             .order_by(TradePlan.created_at.desc()).limit(100).all())
    by_symbol = defaultdict(list)
    for p in plans:
        if p.status == "open":
            by_symbol[p.symbol].append(p)
    fetch_errors = 0
    for symbol, symbol_plans in by_symbol.items():
        try:
            candles = get_candles(symbol, "6M", "1D")["candles"]
        except (MarketDataError, Exception):
            fetch_errors += 1
            continue
        for p in symbol_plans:
            p.status = grade_plan(p, candles)
    db.commit()

    statuses = [p.status for p in plans]
    return {
        "scorecard": aggregate(statuses),
        "plans": [{"id": p.id, "symbol": p.symbol, "state": p.setup_state,
                   "entry_high": p.entry_high, "stop_loss": p.stop_loss,
                   "target1": p.target1, "target2": p.target2,
                   "confidence": p.confidence, "status": p.status,
                   "created_at": p.created_at.isoformat()} for p in plans[:12]],
        "total_plans": len(plans),
        "fetch_errors": fetch_errors,
    }
