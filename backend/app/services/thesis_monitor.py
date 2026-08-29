"""Thesis Monitor — the flagship differentiator.

A thesis is saved as a snapshot of computed numbers (never narrative alone).
Re-checking recomputes the research report and diffs it against the
snapshot: health drops only when the evidence that justified the thesis
actually weakened, and every deduction is listed. Deterministic; no LLM.
"""
from __future__ import annotations

VERDICT_ORDER = ["STRONG SELL", "SELL", "REDUCE", "HOLD", "WATCH",
                 "ACCUMULATE", "BUY", "STRONG BUY"]

CORE_SCORES = [("financial_health", "Financial health"),
               ("growth", "Growth"),
               ("cash_flow", "Cash flow"),
               ("profitability", "Profitability"),
               ("technical", "Technical")]


def snapshot_from_report(report: dict) -> dict:
    """The numbers a thesis stands on."""
    s = report["scores"]
    fv = report.get("fair_value") or {}
    return {
        "ai_score": report.get("ai_score"),
        "verdict": report.get("verdict"),
        "price": fv.get("current_price"),
        "fair_value": fv.get("base") if fv.get("available") else None,
        "upside_pct": fv.get("upside_pct") if fv.get("available") else None,
        "confidence": report.get("confidence"),
        "scores": {
            "financial_health": s["financial_health"]["score"],
            "growth": s["growth"]["score"],
            "cash_flow": s["cash_flow"]["score"],
            "profitability": s["profitability"]["score"],
            "technical": s["technical"]["score"],
            "risk": s["risk"]["score"],
        },
        "positive_count": len(report["thesis"]["why_buy"]),
        "negative_count": len(report["thesis"]["why_not"]),
        "value_trap": report["value_trap"]["risk"],
        "data_freshness": report.get("data_freshness"),
    }


def diff_snapshots(old: dict, new: dict) -> dict:
    """Deterministic thesis health + human-readable change lines."""
    changes: list[dict] = []
    health = 100.0

    def add(kind: str, text: str, penalty: float = 0.0):
        changes.append({"kind": kind, "text": text})
        nonlocal health
        health -= penalty

    # core score drift
    for key, label in CORE_SCORES:
        o = (old.get("scores") or {}).get(key)
        n = (new.get("scores") or {}).get(key)
        if o is None or n is None:
            continue
        d = n - o
        if d <= -10:
            add("weakened", f"{label} weakened: {o} → {n} ({d})", penalty=min(8 + abs(d) // 4, 16))
        elif d >= 10:
            add("strengthened", f"{label} improved: {o} → {n} (+{d})")

    # AI score drift
    o_ai, n_ai = old.get("ai_score"), new.get("ai_score")
    if o_ai is not None and n_ai is not None and o_ai != n_ai:
        d = n_ai - o_ai
        if d < -5:
            add("weakened", f"AI score fell {o_ai} → {n_ai}", penalty=abs(d))
        elif d > 5:
            add("strengthened", f"AI score rose {o_ai} → {n_ai}")

    # fair value / upside drift
    o_fv, n_fv = old.get("fair_value"), new.get("fair_value")
    if o_fv and n_fv and o_fv > 0:
        pct = (n_fv / o_fv - 1) * 100
        if abs(pct) >= 5:
            add("weakened" if pct < 0 else "strengthened",
                f"Fair value {pct:+.0f}% (recomputed models)", penalty=10 if pct < 0 else 0)
    o_up, n_up = old.get("upside_pct"), new.get("upside_pct")
    if o_up is not None and n_up is not None and abs(n_up - o_up) >= 10:
        add("weakened" if n_up < o_up else "strengthened",
            f"Upside {o_up:+.0f}% → {n_up:+.0f}%", penalty=8 if n_up < o_up else 0)

    # verdict migration
    o_v, n_v = old.get("verdict"), new.get("verdict")
    if o_v in VERDICT_ORDER and n_v in VERDICT_ORDER and o_v != n_v:
        down = VERDICT_ORDER.index(n_v) < VERDICT_ORDER.index(o_v)
        add("weakened" if down else "strengthened",
            f"Verdict {o_v} → {n_v}", penalty=12 if down else 0)

    # risk-factor count change
    o_neg, n_neg = old.get("negative_count", 0), new.get("negative_count", 0)
    if n_neg > o_neg:
        add("weakened", f"{n_neg - o_neg} new risk factor(s) detected",
            penalty=5 * (n_neg - o_neg))
    o_pos, n_pos = old.get("positive_count", 0), new.get("positive_count", 0)
    if n_pos < o_pos:
        add("weakened", f"{o_pos - n_pos} supporting factor(s) no longer hold",
            penalty=6 * (o_pos - n_pos))
    if old.get("value_trap") != new.get("value_trap") and new.get("value_trap") in ("MODERATE", "HIGH"):
        add("weakened", f"Value-trap risk is now {new['value_trap']}", penalty=10)

    if not changes:
        changes.append({"kind": "stable", "text": "No material change in the thesis evidence."})

    return {"health": round(max(0.0, min(100.0, health)), 1),
            "changes": changes,
            "weakened": sum(1 for c in changes if c["kind"] == "weakened"),
            "strengthened": sum(1 for c in changes if c["kind"] == "strengthened")}
