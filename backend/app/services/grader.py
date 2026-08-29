"""The Engine Scorecard - the platform grades its own predictions.

Every saved trade plan is checked against what price ACTUALLY did after it
was created: did price touch the entry zone, then hit target 1 / target 2,
or hit the stop first? Conservative rule: if stop and target fall inside
the same candle, it counts as stopped. Plans whose entry never triggers
expire after 60 bars. Pure math over real candles - the scorecard cannot
be flattered.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .market_data import MarketDataError, get_candles

EXPIRY_BARS = 60


def grade_plan(plan, candles: list[dict]) -> dict:
    """Returns {status, detail, outcome_price|None, bars_checked}."""
    created_ts = plan.created_at.replace(tzinfo=timezone.utc).timestamp()
    after = [c for c in candles if c["time"] > created_ts]
    if not after:
        return {"status": "open", "detail": "No candles yet since the call.", "outcome_price": None, "bars_checked": 0}

    entered = False
    hit_t1 = False
    for i, c in enumerate(after):
        if not entered:
            # entry zone touched?
            if c["low"] <= plan.entry_high and c["high"] >= plan.entry_low:
                entered = True
            elif i + 1 >= EXPIRY_BARS:
                return {"status": "expired",
                        "detail": f"Entry zone never triggered within {EXPIRY_BARS} bars.",
                        "outcome_price": None, "bars_checked": i + 1}
            if not entered:
                continue
        # conservative: stop checked before targets within the same candle
        if not hit_t1 and c["low"] <= plan.stop_loss:
            return {"status": "stopped", "detail": "Stop-loss hit before target 1.",
                    "outcome_price": plan.stop_loss, "bars_checked": i + 1}
        if c["high"] >= plan.target2:
            return {"status": "hit_t2", "detail": "Target 2 reached.",
                    "outcome_price": plan.target2, "bars_checked": i + 1}
        if c["high"] >= plan.target1:
            hit_t1 = True
        if hit_t1 and c["low"] <= plan.stop_loss:
            return {"status": "hit_t1", "detail": "Target 1 hit, then pulled back to the stop.",
                    "outcome_price": plan.target1, "bars_checked": i + 1}
        if i + 1 >= EXPIRY_BARS:
            break

    if hit_t1:
        return {"status": "hit_t1", "detail": "Target 1 reached.",
                "outcome_price": plan.target1, "bars_checked": min(len(after), EXPIRY_BARS)}
    if len(after) >= EXPIRY_BARS:
        return {"status": "expired", "detail": f"Neither stop nor target within {EXPIRY_BARS} bars of entry.",
                "outcome_price": None, "bars_checked": EXPIRY_BARS}
    return {"status": "open", "detail": "Trade still in play.", "outcome_price": None,
            "bars_checked": len(after)}


def grade_user_plans(plans) -> list[dict]:
    """Grade all open plans; returns per-plan results (candles fetched once per symbol+interval)."""
    cache: dict[tuple, list[dict]] = {}
    results = []
    for p in plans:
        key = (p.symbol, p.interval)
        if key not in cache:
            try:
                cache[key] = get_candles(p.symbol, "6M", p.interval)["candles"]
            except MarketDataError:
                cache[key] = []
        if not cache[key]:
            results.append({"plan_id": p.id, "status": p.status,
                            "detail": "Data unavailable right now - left as is."})
            continue
        g = grade_plan(p, cache[key])
        results.append({"plan_id": p.id, **g})
    return results


def scorecard(plans) -> dict:
    by = {"open": 0, "hit_t1": 0, "hit_t2": 0, "stopped": 0, "expired": 0}
    conf_win, conf_loss = [], []
    for p in plans:
        by[p.status] = by.get(p.status, 0) + 1
        if p.status in ("hit_t1", "hit_t2") and p.confidence is not None:
            conf_win.append(p.confidence)
        elif p.status == "stopped" and p.confidence is not None:
            conf_loss.append(p.confidence)
    decided = by["hit_t1"] + by["hit_t2"] + by["stopped"]
    return {
        "total": len(plans),
        **by,
        "decided": decided,
        "success_rate": round((by["hit_t1"] + by["hit_t2"]) / decided * 100, 1) if decided else None,
        "avg_confidence_winners": round(sum(conf_win) / len(conf_win), 1) if conf_win else None,
        "avg_confidence_losers": round(sum(conf_loss) / len(conf_loss), 1) if conf_loss else None,
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "honesty": "Graded against real candles with a conservative same-candle rule; this number cannot be flattered.",
    }
