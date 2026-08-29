from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import TradePlan, User
from ..services.analysis_engine import analyze
from ..services.market_data import MarketDataError, get_candles
from ..services.narration import narrate

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/{symbol}")
def run_analysis(
    symbol: str,
    range: str = "1Y",
    interval: str = "1D",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        data = get_candles(symbol, range_label=range, interval_label=interval)
    except MarketDataError as exc:
        raise HTTPException(exc.status_code, exc.message)

    try:
        result = analyze(data["candles"])
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    narration, verification = narrate(result)

    plan_id = None
    plan = result["setup"]["plan"]
    if plan:
        row = TradePlan(
            user_id=user.id,
            symbol=data["symbol"],
            interval=data["interval"],
            setup_state=result["setup"]["state"],
            entry_low=plan["entry_low"],
            entry_high=plan["entry_high"],
            stop_loss=plan["stop_loss"],
            target1=plan["target1"],
            target2=plan["target2"],
            risk_reward=plan["risk_reward"],
            confidence=result["setup"]["confidence"],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        plan_id = row.id

    return {
        "symbol": data["symbol"],
        "interval": data["interval"],
        "range": data["range"],
        **result,
        "narration": narration,
        "verification": verification,
        "saved_plan_id": plan_id,
        "source": data["source"],
        "disclaimer": "Research and education only — not investment advice.",
    }


@router.get("/plans")
def my_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(TradePlan)
        .filter(TradePlan.user_id == user.id)
        .order_by(TradePlan.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id, "symbol": r.symbol, "interval": r.interval,
            "setup_state": r.setup_state, "entry_low": r.entry_low,
            "entry_high": r.entry_high, "stop_loss": r.stop_loss,
            "target1": r.target1, "target2": r.target2,
            "risk_reward": r.risk_reward, "confidence": r.confidence,
            "status": r.status, "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
