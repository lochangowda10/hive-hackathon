"""Thesis API — save a thesis (snapshot of computed numbers), list theses,
and re-check health by diffing a fresh report against the snapshot.
Also serves "what changed" for any symbol vs its latest saved snapshot.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Thesis, User
from ..services.thesis_monitor import diff_snapshots, snapshot_from_report
from .research import _build_report

router = APIRouter(prefix="/api/thesis", tags=["thesis"])


class ThesisCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    note: str = Field(default="", max_length=2000)


def _row(t: Thesis) -> dict:
    snap = json.loads(t.snapshot)
    return {
        "id": t.id, "symbol": t.symbol, "name": t.name, "note": t.note,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "last_checked_at": t.last_checked_at.isoformat() if t.last_checked_at else None,
        "last_health": t.last_health,
        "last_changes": json.loads(t.last_changes) if t.last_changes else [],
        "snapshot": snap,
    }


@router.post("")
def save_thesis(body: ThesisCreate, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    report = _build_report(body.symbol)  # raises HTTPException on missing data
    snap = snapshot_from_report(report)
    t = Thesis(user_id=user.id, symbol=report["symbol"], name=report["name"],
               note=body.note, snapshot=json.dumps(snap),
               last_health=100.0, last_changes=json.dumps(
                   [{"kind": "stable", "text": "Thesis saved. Monitoring begins."}]),
               last_checked_at=datetime.now(timezone.utc))
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"thesis": _row(t), "saved_from_engine_version": report["engine_version"],
            "source": report["source"]}


@router.get("")
def list_theses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(Thesis).filter(Thesis.user_id == user.id)
            .order_by(Thesis.created_at.desc()).all())
    return {"theses": [_row(t) for t in rows]}


@router.post("/{thesis_id}/check")
def check_thesis(thesis_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    t = (db.query(Thesis).filter(Thesis.id == thesis_id, Thesis.user_id == user.id)
         .first())
    if not t:
        raise HTTPException(404, "Thesis not found.")
    report = _build_report(t.symbol)
    new_snap = snapshot_from_report(report)
    diff = diff_snapshots(json.loads(t.snapshot), new_snap)
    t.last_health = diff["health"]
    t.last_changes = json.dumps(diff["changes"])
    t.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    return {"thesis_id": t.id, "symbol": t.symbol, **diff,
            "snapshot_then": json.loads(t.snapshot), "snapshot_now": new_snap,
            "current_verdict": report["verdict"], "current_ai_score": report["ai_score"],
            "current_thesis": report["thesis"], "source": report["source"]}


@router.delete("/{thesis_id}")
def delete_thesis(thesis_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    t = (db.query(Thesis).filter(Thesis.id == thesis_id, Thesis.user_id == user.id)
         .first())
    if not t:
        raise HTTPException(404, "Thesis not found.")
    db.delete(t)
    db.commit()
    return {"deleted": thesis_id}
