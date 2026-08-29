"""The Engine Track Record - self-grading of saved trade plans.

Every plan the analyst engine ever generated is graded against what price
ACTUALLY did afterwards. Pessimistic same-candle rule: the stop is checked
before targets, so the scorecard can only understate, never flatter.
Statuses: open (waiting or running) | hit_t1 | hit_t2 | stopped | expired.
"""
from __future__ import annotations

from datetime import timezone

EXPIRY_BARS = 40  # no entry-zone touch within ~2 trading months -> expired


def grade_plan(plan, candles: list[dict]) -> str:
    """plan needs .entry_high .stop_loss .target1 .target2 .created_at"""
    start_ts = int(plan.created_at.replace(tzinfo=timezone.utc).timestamp())
    after = [c for c in candles if c["time"] > start_ts]
    triggered = False
    hit1 = False
    bars_waiting = 0
    for c in after:
        if not triggered:
            if c["low"] <= plan.entry_high:
                triggered = True  # assume fill at entry_high, then judge this same candle
            else:
                bars_waiting += 1
                if bars_waiting >= EXPIRY_BARS:
                    return "expired"
                continue
        # Pessimistic ordering: stop before targets on the same candle.
        if c["low"] <= plan.stop_loss:
            return "hit_t1" if hit1 else "stopped"
        if c["high"] >= plan.target2:
            return "hit_t2"
        if c["high"] >= plan.target1:
            hit1 = True
    return "open"


def aggregate(statuses: list[str]) -> dict:
    counts = {s: statuses.count(s) for s in ("hit_t1", "hit_t2", "stopped", "expired", "open")}
    closed = counts["hit_t1"] + counts["hit_t2"] + counts["stopped"]
    wins = counts["hit_t1"] + counts["hit_t2"]
    return {
        **counts,
        "graded_closed": closed,
        "win_rate": round(wins / closed * 100, 1) if closed else None,
        "note": ("Graded with a pessimistic same-candle rule (stop checked before "
                 "targets) so this scorecard can only understate the engine."),
    }
