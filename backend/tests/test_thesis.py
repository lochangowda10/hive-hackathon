"""Thesis Monitor unit tests — synthetic snapshots, zero network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.thesis_monitor import diff_snapshots, snapshot_from_report  # noqa: E402


def _snap(ai=70, verdict="ACCUMULATE", fv=200.0, upside=25.0, pos=5, neg=2,
          scores=None, trap="MINIMAL"):
    return {
        "ai_score": ai, "verdict": verdict, "price": 160.0,
        "fair_value": fv, "upside_pct": upside, "confidence": 70,
        "scores": scores or {"financial_health": 70, "growth": 65,
                             "cash_flow": 70, "profitability": 68,
                             "technical": 60, "risk": 30},
        "positive_count": pos, "negative_count": neg,
        "value_trap": trap, "data_freshness": "2025-03-31",
    }


def test_snapshot_from_report_shape():
    report = {
        "ai_score": 72, "verdict": "ACCUMULATE", "confidence": 60,
        "scores": {"financial_health": {"score": 70}, "cash_flow": {"score": 65},
                   "growth": {"score": 60}, "profitability": {"score": 66},
                   "valuation": {"score": 55}, "technical": {"score": 50},
                   "risk": {"score": 35}},
        "fair_value": {"available": True, "current_price": 150.0,
                       "base": 210.0, "upside_pct": 40.0},
        "thesis": {"why_buy": ["a", "b"], "why_not": ["x"]},
        "value_trap": {"risk": "LOW"}, "data_freshness": "2025-03-31",
    }
    s = snapshot_from_report(report)
    assert s["ai_score"] == 72 and s["fair_value"] == 210.0
    assert s["scores"]["financial_health"] == 70
    assert s["positive_count"] == 2 and s["negative_count"] == 1


def test_no_change_is_stable_and_healthy():
    d = diff_snapshots(_snap(), _snap())
    assert d["health"] == 100.0
    assert d["changes"][0]["kind"] == "stable"


def test_weakening_drops_health_and_explains():
    old = _snap()
    new = _snap(ai=58, verdict="WATCH", fv=180.0, upside=12.0, pos=3, neg=4,
                scores={"financial_health": 55, "growth": 50, "cash_flow": 70,
                        "profitability": 68, "technical": 45, "risk": 55},
                trap="MODERATE")
    d = diff_snapshots(old, new)
    assert d["health"] < 60
    assert d["weakened"] >= 4
    texts = " ".join(c["text"] for c in d["changes"])
    assert "Growth weakened" in texts
    assert "Verdict ACCUMULATE → WATCH" in texts
    assert "new risk factor" in texts
    assert "Value-trap" in texts


def test_strengthening_keeps_health_high():
    old = _snap()
    new = _snap(ai=78, verdict="BUY", fv=230.0, upside=40.0,
                scores={"financial_health": 78, "growth": 72, "cash_flow": 74,
                        "profitability": 70, "technical": 68, "risk": 25})
    d = diff_snapshots(old, new)
    assert d["health"] == 100.0  # improvements never subtract
    assert d["strengthened"] >= 3


def test_health_never_below_zero():
    old = _snap(ai=90, verdict="STRONG BUY", pos=7, neg=0)
    new = _snap(ai=30, verdict="STRONG SELL", fv=90.0, upside=-40.0, pos=0, neg=7,
                scores={"financial_health": 20, "growth": 15, "cash_flow": 20,
                        "profitability": 18, "technical": 10, "risk": 90},
                trap="HIGH")
    d = diff_snapshots(old, new)
    assert 0.0 <= d["health"] <= 100.0
