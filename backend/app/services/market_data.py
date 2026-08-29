"""Market data layer.

Design rule (from our architecture): every payload carries a `source`
block — provider name, a human-clickable URL, and the fetch timestamp —
so the UI can always prove where a number came from.

Phase 1 ships one loader (Yahoo Finance via yfinance: NSE `.NS`,
BSE `.BO`, US tickers). The public functions here are the seam where
the Phase-5 fallback chain (Angel One / Dhan / NSE bhavcopy) plugs in
without touching the routers.
"""
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

# UI label -> yfinance period
RANGES = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "5Y": "5y", "MAX": "max"}

# UI label -> (yfinance interval, ranges Yahoo actually supports for it)
INTERVALS = {
    "15m": ("15m", ["1M"]),                          # Yahoo keeps ~60 days of 15-minute bars
    "1H": ("1h", ["1M", "3M", "6M", "1Y"]),          # ~730 days of hourly bars
    "1D": ("1d", list(RANGES.keys())),               # decades
    "1W": ("1wk", list(RANGES.keys())),              # decades
}

PROVIDER_NAME = "Yahoo Finance (via yfinance)"


class MarketDataError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _source_block(symbol: str, note: str | None = None) -> dict:
    block = {
        "provider": PROVIDER_NAME,
        "url": f"https://finance.yahoo.com/quote/{symbol}",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if note:
        block["note"] = note
    return block


def get_candles(symbol: str, range_label: str, interval_label: str) -> dict:
    symbol = symbol.upper().strip()
    if range_label not in RANGES:
        raise MarketDataError(422, f"Unknown range '{range_label}'. Use one of {list(RANGES)}.")
    if interval_label not in INTERVALS:
        raise MarketDataError(422, f"Unknown interval '{interval_label}'. Use one of {list(INTERVALS)}.")

    yf_interval, allowed_ranges = INTERVALS[interval_label]
    note = None
    if range_label not in allowed_ranges:
        # Clamp instead of erroring, and tell the user why in the source note.
        clamped = allowed_ranges[-1]
        note = (
            f"Yahoo Finance limits {interval_label} history; "
            f"range clamped from {range_label} to {clamped}."
        )
        range_label = clamped

    ticker = yf.Ticker(symbol)
    try:
        df = ticker.history(period=RANGES[range_label], interval=yf_interval, auto_adjust=False)
    except Exception as exc:  # network / provider hiccups
        raise MarketDataError(502, f"Data provider error while fetching {symbol}: {exc}")

    if df is None or df.empty:
        raise MarketDataError(
            404,
            f"No data found for '{symbol}'. For Indian stocks use the NSE (.NS) or "
            f"BSE (.BO) suffix, e.g. RELIANCE.NS — try the search box.",
        )

    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    candles = [
        {
            "time": int(ts.timestamp()),
            "open": round(float(row.Open), 4),
            "high": round(float(row.High), 4),
            "low": round(float(row.Low), 4),
            "close": round(float(row.Close), 4),
            "volume": int(row.Volume) if pd.notna(row.Volume) else 0,
        }
        for ts, row in df.iterrows()
    ]

    last_close = candles[-1]["close"]
    prev_close = candles[-2]["close"] if len(candles) > 1 else last_close
    change = round(last_close - prev_close, 4)

    currency = None
    try:
        currency = ticker.fast_info["currency"]
    except Exception:
        pass

    return {
        "symbol": symbol,
        "interval": interval_label,
        "range": range_label,
        "candles": candles,
        "meta": {
            "currency": currency or ("INR" if symbol.endswith((".NS", ".BO")) else "USD"),
            "last_close": last_close,
            "prev_close": prev_close,
            "change": change,
            "change_pct": round((change / prev_close) * 100, 2) if prev_close else 0.0,
            "candle_count": len(candles),
        },
        "source": _source_block(symbol, note),
    }


def search_symbols(query: str) -> dict:
    query = query.strip()
    if len(query) < 2:
        return {"results": [], "source": _source_block("")}

    # 1) Local curated search first: company NAMES, typo-tolerant, covers
    #    stocks + ETFs + commodities + indices + crypto, no .NS needed.
    from . import markets  # lazy import (markets imports from this module)
    results: list[dict] = []
    try:
        results.extend(markets.local_search(query))
    except Exception:
        pass
    seen = {r["symbol"] for r in results}

    # 2) Yahoo's search fills in everything outside the curated lists.
    try:
        found = yf.Search(query, max_results=10)
        yahoo_rows = []
        for q in found.quotes or []:
            if q.get("quoteType") not in ("EQUITY", "ETF", "INDEX"):
                continue
            yahoo_rows.append(
                {
                    "symbol": q.get("symbol"),
                    "name": q.get("shortname") or q.get("longname") or q.get("symbol"),
                    "exchange": q.get("exchange", ""),
                    "type": q.get("quoteType", ""),
                }
            )
        # India-first ordering within Yahoo results too
        yahoo_rows.sort(key=lambda r: 0 if str(r["symbol"]).endswith((".NS", ".BO")) else 1)
        for r in yahoo_rows:
            if r["symbol"] and r["symbol"] not in seen:
                seen.add(r["symbol"])
                results.append(r)
    except Exception:
        # Fallback: probe likely symbols directly (US, NSE, BSE variants).
        for candidate in (query.upper(), f"{query.upper()}.NS", f"{query.upper()}.BO"):
            if candidate in seen:
                continue
            try:
                df = yf.Ticker(candidate).history(period="5d", interval="1d")
                if df is not None and not df.empty:
                    results.append(
                        {"symbol": candidate, "name": candidate, "exchange": "", "type": "EQUITY"}
                    )
            except Exception:
                continue

    return {"results": results[:10], "source": _source_block(query)}


def batch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Last price + 1D change for a list of symbols, one batched call.
    Missing symbols are simply absent from the result — callers stay honest."""
    out: dict[str, dict] = {}
    if not symbols:
        return out
    try:
        df = yf.download(symbols, period="7d", interval="1d", group_by="ticker",
                         progress=False, threads=True, auto_adjust=False)
        multi = isinstance(df.columns, pd.MultiIndex)
        for s in symbols:
            try:
                closes = (df[s] if multi else df)["Close"].dropna()
                if len(closes) >= 2:
                    last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                    out[s] = {"price": round(last, 2),
                              "change_pct": round((last / prev - 1) * 100, 2) if prev else 0.0}
                elif len(closes) == 1:
                    out[s] = {"price": round(float(closes.iloc[-1]), 2), "change_pct": 0.0}
            except Exception:
                continue
    except Exception:
        pass
    return out
