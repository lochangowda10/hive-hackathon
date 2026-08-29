from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..services.markets import get_overview, get_segment, list_segments

router = APIRouter(prefix="/api/markets", tags=["markets"],
                   dependencies=[Depends(get_current_user)])


@router.get("/segments")
def segments():
    return {"segments": list_segments()}


@router.get("/overview")
def overview():
    try:
        return get_overview()
    except Exception as exc:
        raise HTTPException(502, f"Market data provider error: {exc}")


@router.get("/{segment}")
def segment(segment: str):
    try:
        return get_segment(segment)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"Market data provider error: {exc}")
