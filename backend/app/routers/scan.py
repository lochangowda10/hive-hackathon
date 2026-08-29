from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..services.scanner import scan

router = APIRouter(prefix="/api/scan", tags=["scan"], dependencies=[Depends(get_current_user)])


@router.get("")
def run_scan(segment: str = "india_large", top: int = Query(5, ge=1, le=10)):
    try:
        return scan(segment, top)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"Scan failed at the data provider: {exc}")
