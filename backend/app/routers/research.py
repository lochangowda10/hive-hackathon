"""Research terminal API — composite fundamental/valuation/technical
intelligence per symbol, plus discovery lists ranked by the AI score.

Thin layer: fetch price + technicals + fundamentals, call the engine,
return. All math lives in services/research_engine.py.
"""
import time

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..services.analysis_engine import analyze
from ..services.fundamentals import get_fundamentals
from ..services.market_data import MarketDataError, get_candles
from ..services.markets import SEGMENTS
from ..services.news import get_symbol_news
from ..services.research_engine import research_report

router = APIRouter(prefix="/api/research", tags=["research"],
                   dependencies=[Depends(get_current_user)])

_TTL = 3600  # research payloads cached 1h per symbol
_report_cache: dict[str, tuple[float, dict]] = {}
_DISCOVERY_TTL = 1800
_discovery_cache: dict[str, tuple[float, dict]] = {}

DISCOVERY_LISTS = {
    "most_undervalued": ("Most Undervalued", "upside", True),
    "most_overvalued": ("Most Overvalued", "upside", False),
    "quality": ("Quality Stocks", "ai", True),
    "growth": ("Growth Stocks", "growth", True),
    "cash_flow": ("Strong Cash Flow", "cash_flow", True),
    "value_traps": ("Value Trap Warnings", "trap", True),
}


def _catalyst_score(symbol: str) -> float | None:
    """Deterministic: confirmed multi-source headlines carry weight.
    0-100 from recent confirmed news count. No AI guessing."""
    try:
        news = get_symbol_news(symbol)
    except Exception:
        return None
    items = news.get("items") or []
    confirmed = sum(1 for i in items if i.get("confirmed"))
    if not items:
        return 0.0
    return float(min(100, 20 * confirmed + 5 * len(items)))


def _build_report(symbol: str) -> dict:
    symbol = symbol.upper().strip()
    hit = _report_cache.get(symbol)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]

    try:
        price_payload = get_candles(symbol, "1Y", "1D")
    except MarketDataError as exc:
        raise HTTPException(exc.status_code, exc.message)
    price = price_payload["meta"]["last_close"]

    try:
        f = get_fundamentals(symbol)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    technical = None
    try:
        technical = analyze(price_payload["candles"])["setup"]
    except Exception:
        pass  # technicals are one component; absence lowers confidence, not a crash

    report = research_report(f, price, technical=technical,
                             catalyst_score=_catalyst_score(symbol))
    _report_cache[symbol] = (time.time(), report)
    return report


@router.get("/discovery/lists")
def discovery_lists():
    return {"lists": [{"id": k, "label": v[0]} for k, v in DISCOVERY_LISTS.items()]}


@router.get("/discovery/{list_id}")
def discovery(list_id: str, universe: str = "india_large"):
    if list_id not in DISCOVERY_LISTS:
        raise HTTPException(422, f"Unknown list '{list_id}'. Use one of {list(DISCOVERY_LISTS)}.")
    if universe not in SEGMENTS:
        raise HTTPException(422, f"Unknown universe '{universe}'. Use one of {list(SEGMENTS)}.")
    key = f"{list_id}:{universe}"
    hit = _discovery_cache.get(key)
    if hit and time.time() - hit[0] < _DISCOVERY_TTL:
        return hit[1]

    rows = []
    for sym, name in SEGMENTS[universe]["symbols"].items():
        try:
            r = _build_report(sym)
        except HTTPException:
            continue
        fv = r["fair_value"]
        rows.append({
            "symbol": sym, "name": name, "sector": r.get("sector"),
            "price": fv.get("current_price") if fv.get("available") else None,
            "fair_value": fv.get("base") if fv.get("available") else None,
            "upside_pct": fv.get("upside_pct") if fv.get("available") else None,
            "ai_score": r["ai_score"], "ai_band": r["ai_band"], "verdict": r["verdict"],
            "health": r["scores"]["financial_health"]["band"],
            "cash_flow": r["scores"]["cash_flow"]["band"],
            "growth": r["scores"]["growth"]["score"],
            "risk": r["scores"]["risk"]["band"],
            "value_trap": r["value_trap"]["risk"],
            "confidence": r["confidence"], "data_quality": r["data_quality"],
        })

    _, sort_key, desc = DISCOVERY_LISTS[list_id]
    if sort_key == "upside":
        rows = [r for r in rows if r["upside_pct"] is not None and r["value_trap"] != "HIGH"]
        rows.sort(key=lambda r: r["upside_pct"], reverse=desc)
    elif sort_key == "trap":
        rows = [r for r in rows if r["value_trap"] in ("HIGH", "MODERATE")]
        rows.sort(key=lambda r: 0 if r["value_trap"] == "HIGH" else 1)
    elif sort_key in ("ai", "growth", "cash_flow"):
        field = {"ai": "ai_score", "growth": "growth"}.get(sort_key, "ai_score")
        if sort_key == "cash_flow":
            rows = [r for r in rows if r["cash_flow"] in ("Good", "Great", "Excellent")]
        rows = [r for r in rows if r[field] is not None]
        rows.sort(key=lambda r: r[field], reverse=True)

    payload = {"list": list_id, "label": DISCOVERY_LISTS[list_id][0],
               "universe": universe, "count": len(rows), "rows": rows,
               "note": "Ranked by computed scores from reported financials - research/education, not advice.",
               "source": {"provider": "SwingLens research engine",
                          "fetched_at": rows and None or None}}
    _discovery_cache[key] = (time.time(), payload)
    return payload


@router.get("/{symbol}")
def research(symbol: str):
    return _build_report(symbol)


@router.get("/{symbol}/financials")
def financials(symbol: str):
    try:
        f = get_fundamentals(symbol)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return {"symbol": f["symbol"], "name": f["name"], "currency": f["currency"],
            "income": f["income"], "balance": f["balance"], "cashflow": f["cashflow"],
            "data_quality": f["data_quality"], "source": f["source"]}
