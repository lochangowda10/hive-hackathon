"""Market Scanner - the honest answer to "which stocks look bullish?"

Runs the SAME deterministic analyst engine across an entire curated
universe in one batched data fetch, ranks computed setups by confidence,
and reports exactly which techniques were applied. The LLM never picks a
stock; it may only discuss what this scanner computed.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from .analysis_engine import analyze
from .market_data import _source_block
from .markets import SEGMENTS

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 600  # seconds

TECHNIQUES = [
    "Batch-fetched 6 months of daily candles for the whole universe (one Yahoo call)",
    "Swing pivot detection (fractal k=3) per stock",
    "ATR-scaled support/resistance zone clustering (width-capped)",
    "Trendline fitting through swing points",
    "State machine: breakout / pullback / consolidation / extended / downtrend",
    "Volume confirmation vs 20-bar average",
    "ATR-based entry-stop-target plans with risk:reward filter (>=1)",
    "Explainable 0-100 confidence scoring, then honesty filter and ranking",
]

_BULLISH_WATCH = {"strong_uptrend_extended", "consolidation_below_resistance"}


def _candles_from(sub: pd.DataFrame) -> list[dict]:
    sub = sub.dropna(subset=["Open", "High", "Low", "Close"])
    return [
        {"time": int(ts.timestamp()), "open": float(r.Open), "high": float(r.High),
         "low": float(r.Low), "close": float(r.Close),
         "volume": int(r.Volume) if pd.notna(r.Volume) else 0}
        for ts, r in sub.iterrows()
    ]


def scan(segment: str = "india_large", top: int = 5) -> dict:
    if segment not in SEGMENTS:
        raise KeyError(f"Unknown segment '{segment}'. Options: {list(SEGMENTS)}")
    key = f"{segment}:{top}"
    now = time.time()
    if key in _CACHE and now - _CACHE[key][0] < _TTL:
        return _CACHE[key][1]

    t0 = time.time()
    meta = SEGMENTS[segment]
    symbols = meta["symbols"]
    df = yf.download(list(symbols), period="6mo", interval="1d",
                     group_by="ticker", progress=False, threads=True, auto_adjust=False)

    actionable, watchlist, scanned, failed = [], [], 0, 0
    multi = isinstance(df.columns, pd.MultiIndex)
    for sym, name in symbols.items():
        try:
            candles = _candles_from(df[sym] if multi else df)
            if len(candles) < 40:
                failed += 1
                continue
            result = analyze(candles)
            scanned += 1
            setup = result["setup"]
            row = {
                "symbol": sym, "name": name,
                "state": setup["state"], "bias": setup["bias"],
                "confidence": setup["confidence"],
                "last_close": result["indicators"]["last_close"],
                "rsi": result["indicators"]["rsi14"],
                "plan": setup["plan"],
            }
            if setup["plan"]:
                actionable.append(row)
            elif setup["state"] in _BULLISH_WATCH and setup["bias"] == "bullish":
                watchlist.append(row)
        except Exception:
            failed += 1

    actionable.sort(key=lambda r: r["confidence"], reverse=True)
    watchlist.sort(key=lambda r: (r["rsi"] or 0), reverse=True)

    payload = {
        "segment": segment,
        "universe": f"{meta['label']} — {meta.get('universe', '')}",
        "scanned": scanned,
        "failed": failed,
        "actionable": actionable[:top],
        "watchlist": watchlist[:top],
        "techniques": TECHNIQUES,
        "duration_ms": int((time.time() - t0) * 1000),
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": _source_block("") | {
            "provider": "SwingLens engine over Yahoo Finance daily candles",
            "note": f"Curated universe scan, cached {_TTL // 60} min. Research/education, not advice.",
        },
    }
    _CACHE[key] = (now, payload)
    return payload
