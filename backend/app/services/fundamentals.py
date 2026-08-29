"""Fundamental data provider — the ONLY module that talks to yfinance for
statements/ratios. Adapter rule: if we swap to a licensed fundamentals feed
later, nothing outside this file changes.

Design contract (per ARCHITECTURE.md):
- Returns normalized, labeled data. Never guesses. Missing fields are
  reported as missing and reduce `data_quality`.
- Every payload carries a `source` block (§25/§48).
- In-memory TTL cache keeps the dashboard fast (§39); DB-backed cache
  arrives in Phase 5.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import yfinance as yf

PROVIDER_NAME = "Yahoo Finance (via yfinance)"
_TTL = 6 * 3600  # fundamentals change quarterly at most
_cache: dict[str, tuple[float, dict]] = {}

# Expected annual line items per statement, with provider row-name synonyms.
INCOME_ITEMS = {
    "revenue": ["Total Revenue"],
    "gross_profit": ["Gross Profit"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "ebit": ["EBIT", "Operating Income"],
    "interest_expense": ["Interest Expense"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "eps": ["Diluted EPS", "Basic EPS"],
}
BALANCE_ITEMS = {
    "total_debt": ["Total Debt"],
    "cash": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "receivables": ["Receivables"],
    "inventory": ["Inventory"],
}
CASHFLOW_ITEMS = {
    "ocf": ["Operating Cash Flow"],
    "capex": ["Capital Expenditure"],
    "fcf": ["Free Cash Flow"],
    "dividends": ["Cash Dividends Paid"],
}


def _statement(df, items: dict, limit: int = 5) -> list[dict]:
    """Normalize a provider statement into [{period, ...items}] newest-first."""
    if df is None or df.empty:
        return []
    periods: dict[str, dict] = {}
    order: list[str] = []
    for col in list(df.columns)[:limit]:
        label = str(col.date()) if hasattr(col, "date") else str(col)
        periods[label] = {"period": label}
        order.append(label)
    present = 0
    for key, names in items.items():
        row = None
        for name in names:
            if name in df.index:
                row = df.loc[name]
                break
        for col in list(df.columns)[:limit]:
            label = str(col.date()) if hasattr(col, "date") else str(col)
            v = row[col] if row is not None else None
            val = float(v) if (v is not None and v == v) else None
            periods[label][key] = val
        if row is not None:
            present += 1
    years = [periods[p] for p in order]
    for y in years:
        # derived: FCF when provider doesn't give it
        if y.get("fcf") is None and y.get("ocf") is not None and y.get("capex") is not None:
            y["fcf"] = y["ocf"] + y["capex"]  # capex is negative in provider convention
    return years, present


def _source_block(symbol: str) -> dict:
    return {
        "provider": PROVIDER_NAME,
        "url": f"https://finance.yahoo.com/quote/{symbol}/financials",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def get_fundamentals(symbol: str) -> dict:
    """Normalized fundamentals payload. Raises ValueError('insufficient_data')
    when there is nothing usable — callers must show that, never invent."""
    symbol = symbol.upper().strip()
    hit = _cache.get(symbol)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]

    t = yf.Ticker(symbol)
    try:
        income, inc_present = _statement(t.get_income_stmt(freq="yearly"), INCOME_ITEMS)
        balance, bal_present = _statement(t.get_balance_sheet(freq="yearly"), BALANCE_ITEMS)
        cashflow, cf_present = _statement(t.get_cashflow(freq="yearly"), CASHFLOW_ITEMS)
    except Exception as exc:
        raise ValueError(f"insufficient_data: fundamentals provider error for {symbol}: {exc}")

    info = {}
    try:
        info = t.info or {}
    except Exception:
        pass

    total_items = len(INCOME_ITEMS) + len(BALANCE_ITEMS) + len(CASHFLOW_ITEMS)
    present = inc_present + bal_present + cf_present
    has_years = bool(income) and len(income) >= 2
    data_quality = round(100 * (present / total_items) * (1.0 if has_years else 0.4))

    if not income or income[0].get("revenue") is None:
        raise ValueError(
            f"insufficient_data: no income statement for {symbol}. "
            "Indices/ETFs/commodities have no fundamentals — research scores need a company."
        )

    payload = {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency") or ("INR" if symbol.endswith((".NS", ".BO")) else "USD"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "trailing_pe": info.get("trailingPE"),
        "price_to_book": info.get("priceToBook"),
        "trailing_eps": info.get("trailingEps"),
        "book_value_per_share": info.get("bookValue"),
        "dividend_yield": info.get("dividendYield"),
        "is_financial": (info.get("sector") or "").lower() in ("financial services", "financial")
                        or "bank" in (info.get("industry") or "").lower(),
        "income": income,      # [{period, revenue, ebitda, ebit, net_income, eps, ...}] newest first
        "balance": balance,
        "cashflow": cashflow,
        "data_quality": data_quality,
        "period_label": income[0]["period"] if income else None,
        "source": _source_block(symbol),
    }
    _cache[symbol] = (time.time(), payload)
    return payload
