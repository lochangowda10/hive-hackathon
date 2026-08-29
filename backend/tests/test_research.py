"""Research engine unit tests — synthetic fundamentals, zero network.
The scoring math must be deterministic and honest: no network, no LLM."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.research_engine import (  # noqa: E402
    detect_value_trap, fair_value, research_report, score_cash_flow,
    score_financial_health, score_growth, score_profitability,
)


def _growth_company():
    """Synthetic quality grower: rising revenue/profit/FCF, low debt."""
    income = [
        {"period": "2025-03-31", "revenue": 1500.0, "gross_profit": 600.0,
         "ebitda": 375.0, "ebit": 330.0, "interest_expense": 10.0,
         "net_income": 225.0, "eps": 15.0},
        {"period": "2024-03-31", "revenue": 1200.0, "gross_profit": 456.0,
         "ebitda": 276.0, "ebit": 240.0, "interest_expense": 10.0,
         "net_income": 156.0, "eps": 10.4},
        {"period": "2023-03-31", "revenue": 1000.0, "gross_profit": 360.0,
         "ebitda": 210.0, "ebit": 180.0, "interest_expense": 12.0,
         "net_income": 110.0, "eps": 7.3},
        {"period": "2022-03-31", "revenue": 900.0, "gross_profit": 315.0,
         "ebitda": 180.0, "ebit": 150.0, "interest_expense": 14.0,
         "net_income": 90.0, "eps": 6.0},
    ]
    balance = [
        {"period": "2025-03-31", "total_debt": 100.0, "cash": 250.0,
         "equity": 1100.0, "current_assets": 700.0, "current_liabilities": 350.0},
        {"period": "2024-03-31", "total_debt": 150.0, "cash": 180.0,
         "equity": 900.0, "current_assets": 560.0, "current_liabilities": 300.0},
    ]
    cashflow = [
        {"period": "2025-03-31", "ocf": 320.0, "capex": -80.0, "fcf": 240.0},
        {"period": "2024-03-31", "ocf": 240.0, "capex": -70.0, "fcf": 170.0},
        {"period": "2023-03-31", "ocf": 190.0, "capex": -60.0, "fcf": 130.0},
    ]
    return {"symbol": "GROW.NS", "name": "Grow Co", "sector": "Technology",
            "industry": "Software", "currency": "INR", "market_cap": 3e10,
            "shares_outstanding": 15_000_000, "trailing_pe": 22.0,
            "price_to_book": 3.0, "trailing_eps": 15.0,
            "book_value_per_share": 73.3, "dividend_yield": None,
            "is_financial": False, "income": income, "balance": balance,
            "cashflow": cashflow, "data_quality": 90, "period_label": "2025-03-31",
            "source": {"provider": "synthetic-test"}}


def _value_trap():
    """Cheap-looking but deteriorating: falling revenue, negative FCF, rising debt."""
    f = _growth_company()
    f["symbol"] = "TRAP.NS"
    f["income"] = [
        {"period": "2025-03-31", "revenue": 800.0, "gross_profit": 200.0,
         "ebitda": 80.0, "ebit": 40.0, "interest_expense": 35.0,
         "net_income": 5.0, "eps": 0.3},
        {"period": "2024-03-31", "revenue": 1000.0, "gross_profit": 280.0,
         "ebitda": 130.0, "ebit": 90.0, "interest_expense": 25.0,
         "net_income": 45.0, "eps": 3.0},
        {"period": "2023-03-31", "revenue": 1150.0, "gross_profit": 345.0,
         "ebitda": 190.0, "ebit": 145.0, "interest_expense": 20.0,
         "net_income": 85.0, "eps": 5.7},
    ]
    f["balance"] = [
        {"period": "2025-03-31", "total_debt": 600.0, "cash": 40.0,
         "equity": 500.0, "current_assets": 350.0, "current_liabilities": 380.0},
        {"period": "2024-03-31", "total_debt": 450.0, "cash": 60.0,
         "equity": 520.0, "current_assets": 400.0, "current_liabilities": 350.0},
    ]
    f["cashflow"] = [
        {"period": "2025-03-31", "ocf": 30.0, "capex": -90.0, "fcf": -60.0},
        {"period": "2024-03-31", "ocf": 90.0, "capex": -80.0, "fcf": 10.0},
    ]
    f["trailing_pe"] = 6.0  # "cheap"
    f["trailing_eps"] = 0.3
    return f


def test_health_score_bands():
    f = _growth_company()
    h = score_financial_health(f)
    assert 0 <= h["score"] <= 100
    assert h["band"] in ("Fair", "Good", "Great", "Excellent")
    assert len(h["factors"]) == 9


def test_growth_detects_cagr_and_acceleration():
    g = score_growth(_growth_company())
    assert g["revenue_cagr_3y"] is not None
    assert 0.15 < g["revenue_cagr_3y"] < 0.25  # 900 -> 1500 over 3y ~ 18.6%
    assert g["accelerating"] is True           # 25% latest > 20% prior


def test_cash_flow_clean_vs_trap():
    clean = score_cash_flow(_growth_company())
    assert clean["band"] in ("Good", "Great", "Excellent")
    assert clean["warnings"] == []
    trap = score_cash_flow(_value_trap())
    assert "negative_fcf: company burned cash in the latest year" in trap["warnings"]


def test_value_trap_detection():
    f = _value_trap()
    g, p, c = score_growth(f), score_profitability(f), score_cash_flow(f)
    trap = detect_value_trap(f, g, p, c)
    assert trap["risk"] in ("HIGH", "MODERATE")
    assert len(trap["signals"]) >= 2


def test_fair_value_blends_models():
    fv = fair_value(_growth_company(), price=150.0, growth=score_growth(_growth_company()))
    assert fv["available"]
    assert fv["base"] > 0
    assert fv["bear"] < fv["base"] < fv["bull"]
    assert fv["upside_pct"] is not None
    assert len(fv["models"]) >= 3
    assert 10 <= fv["confidence"] <= 95


def test_fair_value_insufficient_data():
    f = _growth_company()
    f["trailing_eps"] = None
    f["cashflow"] = []
    f["income"][0]["ebitda"] = None
    fv = fair_value(f, price=100.0, growth=score_growth(f))
    assert fv["available"] is False
    assert "insufficient_data" in fv["note"]


def test_report_penalizes_value_trap():
    good = research_report(_growth_company(), price=150.0,
                           technical={"confidence": 70}, catalyst_score=40.0)
    bad = research_report(_value_trap(), price=100.0,
                          technical={"confidence": 30}, catalyst_score=10.0)
    assert good["ai_score"] > bad["ai_score"]
    assert good["verdict"] in VERDICT_SET
    assert bad["value_trap"]["risk"] in ("HIGH", "MODERATE")
    assert good["thesis"]["why_buy"], "quality company must produce buy reasons"
    assert bad["thesis"]["why_not"], "trap must produce risks"
    assert "validation_note" in good


VERDICT_SET = {"STRONG SELL", "SELL", "REDUCE", "HOLD", "WATCH",
               "ACCUMULATE", "BUY", "STRONG BUY"}


def test_profitability_trend():
    p = score_profitability(_growth_company())
    assert p["margin_trend"] == "expanding"  # EBITDA margin 20% -> 25%
    assert p["roe"] and p["roe"] > 0.15
