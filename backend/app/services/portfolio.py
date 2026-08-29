"""The Mirror — portfolio import + behavior analytics.

Broker exports differ wildly, so the parser is tolerant by design: it sniffs
the header row (skipping preamble lines), maps column synonyms, auto-detects
tradebook vs holdings, and reports exactly what it mapped and what it
skipped. All analytics are pure math with honest sample-size caveats; the
LLM never computes a statistic. Files are parsed on the user's own server
and stored only in the local database.
"""
from __future__ import annotations

import csv
import io
import re
import statistics
from collections import defaultdict, deque
from datetime import datetime, timezone

import pandas as pd

from .market_data import _source_block

SYNONYMS = {
    "symbol": ["symbol", "ticker", "scrip", "scrip code", "trading symbol",
               "stock symbol", "instrument", "tradingsymbol", "nse symbol"],
    "name": ["stock name", "name", "company", "company name", "security",
             "instrument name", "scrip name", "name of the instrument", "stock"],
    "qty": ["qty", "quantity", "shares", "units", "filled qty", "net qty",
            "qty.", "quantity available"],
    "price": ["price", "avg price", "average price", "avg. cost", "avg cost",
              "buy price", "purchase price", "rate", "trade price",
              "avg buy price", "average cost price", "avg. buy price",
              "average buy price", "buy average", "cost price"],
    "side": ["type", "side", "transaction type", "buy/sell", "order type",
             "trade type", "action", "b/s", "buy sell"],
    "date": ["date", "trade date", "order date", "execution date",
             "order execution time", "timestamp", "trade time", "executed at"],
    "ltp": ["ltp", "current price", "cmp", "last price", "market price",
            "closing price", "close price", "current value price"],
}


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", str(h).strip().lower().replace("_", " "))


def _clean_num(v) -> float | None:
    if v is None:
        return None
    s = re.sub(r"[₹,\s]", "", str(v)).replace("(", "-").replace(")", "")
    try:
        return float(s)
    except ValueError:
        return None


def _read_table(data: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data), header=None, dtype=str)
    # Broker CSVs often start with short preamble lines ("Export generated
    # on..."), which makes pandas lock the column count at 1 and drop every
    # real row. Read manually and pad ragged rows instead.
    text = data.decode("utf-8-sig", errors="replace")
    raw_rows = [r for r in csv.reader(io.StringIO(text))]
    if not raw_rows:
        raise ValueError("The file is empty.")
    width = max(len(r) for r in raw_rows)
    padded = [r + [""] * (width - len(r)) for r in raw_rows]
    return pd.DataFrame(padded, dtype=str)


def _find_header(df: pd.DataFrame) -> tuple[int, dict[str, int]]:
    """Scan the first rows for the one that looks like a broker header."""
    best = (-1, {})
    for ridx in range(min(15, len(df))):
        row = [_norm_header(x) for x in df.iloc[ridx].tolist()]
        mapping: dict[str, int] = {}
        for field, names in SYNONYMS.items():
            for cidx, cell in enumerate(row):
                if cell in names and field not in mapping:
                    mapping[field] = cidx
        score = len(mapping)
        if score > len(best[1]):
            best = (ridx, mapping)
    if len(best[1]) < 2:
        raise ValueError(
            "Couldn't recognize the columns in this file. Expected a broker "
            "export with columns like Symbol/Stock Name, Quantity, Price "
            "(and Buy/Sell + Date for tradebooks)."
        )
    return best


def _resolve_symbol(raw_symbol: str | None, raw_name: str | None) -> tuple[str | None, str]:
    """Resolve to a Yahoo symbol using ONLY local curated data (no network)."""
    from .markets import SEGMENTS, local_search
    known: dict[str, str] = {}
    for seg in SEGMENTS.values():
        known.update(seg["symbols"])

    if raw_symbol:
        cand = re.sub(r"\.(NS|BO)$", "", str(raw_symbol).strip().upper())
        for suffix in (".NS", ".BO"):
            if cand + suffix in known:
                return cand + suffix, known[cand + suffix]
        if re.fullmatch(r"[A-Z0-9&-]{1,15}", cand):
            if cand in known:  # US symbols
                return cand, known[cand]
            return cand + ".NS", (raw_name or cand)  # best-effort NSE guess
    if raw_name:
        hits = local_search(str(raw_name), limit=1)
        if hits:
            return hits[0]["symbol"], hits[0]["name"]
    return None, (raw_name or raw_symbol or "Unknown")


def parse_broker_file(data: bytes, filename: str) -> dict:
    """Returns {kind: 'tradebook'|'holdings', rows: [...], report: {...}}."""
    df = _read_table(data, filename)
    header_row, cols = _find_header(df)
    body = df.iloc[header_row + 1:]

    has_side = "side" in cols
    side_values = set()
    if has_side:
        for v in body.iloc[:, cols["side"]].dropna().head(50):
            side_values.add(str(v).strip().upper()[:1])
    kind = "tradebook" if has_side and side_values & {"B", "S"} else "holdings"

    rows, skipped = [], 0
    for _, r in body.iterrows():
        def get(f):
            if f not in cols or pd.isna(r.iloc[cols[f]]):
                return None
            val = str(r.iloc[cols[f]]).strip()
            return val or None
        qty = _clean_num(get("qty"))
        price = _clean_num(get("price"))
        if qty is None or price is None or qty == 0:
            skipped += 1
            continue
        symbol, name = _resolve_symbol(get("symbol"), get("name"))
        row = {
            "symbol_raw": get("symbol") or get("name") or "?",
            "symbol": symbol,
            "name": name,
            "quantity": abs(qty),
            "price": price,
            "ltp": _clean_num(get("ltp")),
        }
        if kind == "tradebook":
            side_raw = (get("side") or "").strip().upper()
            row["side"] = "BUY" if side_raw.startswith("B") else "SELL" if side_raw.startswith("S") else None
            if row["side"] is None:
                skipped += 1
                continue
            dt = pd.to_datetime(get("date"), errors="coerce", dayfirst=True) if "date" in cols else pd.NaT
            row["trade_date"] = None if pd.isna(dt) else dt.to_pydatetime().replace(tzinfo=None)
        rows.append(row)

    if not rows:
        raise ValueError("The file was recognized but no usable rows were found.")
    return {
        "kind": kind,
        "rows": rows,
        "report": {
            "header_row": header_row + 1,
            "columns_mapped": {k: int(v) for k, v in cols.items()},
            "imported": len(rows),
            "skipped": skipped,
            "unresolved_symbols": sum(1 for x in rows if not x["symbol"]),
        },
    }


# ---------------------------------------------------------------- analytics

def fifo_round_trips(trades: list[dict]) -> tuple[list[dict], float]:
    """FIFO-match buys to sells per symbol -> closed round trips + realized P&L."""
    lots: dict[str, deque] = defaultdict(deque)
    trips: list[dict] = []
    realized = 0.0
    for t in sorted(trades, key=lambda x: (x["trade_date"] or datetime.min, x["id"])):
        key = t["symbol"] or t["symbol_raw"]
        if t["side"] == "BUY":
            lots[key].append({"qty": t["quantity"], "price": t["price"], "date": t["trade_date"]})
            continue
        remaining = t["quantity"]
        while remaining > 1e-9 and lots[key]:
            lot = lots[key][0]
            take = min(remaining, lot["qty"])
            pnl = (t["price"] - lot["price"]) * take
            realized += pnl
            days = None
            if lot["date"] and t["trade_date"]:
                days = max((t["trade_date"] - lot["date"]).days, 0)
            trips.append({
                "symbol": key, "name": t["name"], "qty": take,
                "buy_price": lot["price"], "sell_price": t["price"],
                "pnl": round(pnl, 2),
                "pnl_pct": round((t["price"] / lot["price"] - 1) * 100, 2) if lot["price"] else 0.0,
                "days": days,
            })
            lot["qty"] -= take
            remaining -= take
            if lot["qty"] <= 1e-9:
                lots[key].popleft()
    return trips, round(realized, 2)


def behavior_profile(trips: list[dict], trades: list[dict]) -> dict:
    n = len(trips)
    if n < 5:
        return {
            "ready": False,
            "round_trips": n,
            "message": (f"Only {n} closed round-trip(s) found — the Mirror needs at "
                        "least 5 completed buy→sell cycles to say anything honest "
                        "about your trading personality. Import a longer tradebook."),
        }
    wins = [t for t in trips if t["pnl"] > 0]
    losses = [t for t in trips if t["pnl"] <= 0]
    win_rate = round(len(wins) / n * 100, 1)
    avg_win = round(statistics.mean(t["pnl_pct"] for t in wins), 2) if wins else 0.0
    avg_loss = round(statistics.mean(t["pnl_pct"] for t in losses), 2) if losses else 0.0
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss else None
    holds = [t["days"] for t in trips if t["days"] is not None]
    median_hold = int(statistics.median(holds)) if holds else None

    traits = []
    if median_hold is not None:
        style = ("Scalper reflexes" if median_hold <= 3 else
                 "Swing trader" if median_hold <= 30 else
                 "Positional" if median_hold <= 90 else "Investor patience")
        traits.append({"trait": "Holding style", "verdict": style,
                       "evidence": f"Median holding period: {median_hold} days across {len(holds)} trips."})
    if wins and losses:
        if abs(avg_loss) > avg_win:
            traits.append({"trait": "Exit discipline", "verdict": "Lets losers run",
                           "evidence": f"Average loss {avg_loss}% is larger than average win {avg_win}% — the classic loss-aversion pattern."})
        else:
            traits.append({"trait": "Exit discipline", "verdict": "Cuts losses, rides winners",
                           "evidence": f"Average win {avg_win}% vs average loss {avg_loss}%."})
    traits.append({"trait": "Hit rate", "verdict": f"{win_rate}% winners",
                   "evidence": f"{len(wins)} winning vs {len(losses)} losing round trips (n={n})."})
    if profit_factor is not None:
        verdict = ("Edge confirmed" if profit_factor >= 1.5 else
                   "Roughly break-even engine" if profit_factor >= 0.9 else "Negative expectancy")
        traits.append({"trait": "Profit factor", "verdict": f"{profit_factor} — {verdict}",
                       "evidence": "Gross profits ÷ gross losses on closed trips."})
    sym_counts = defaultdict(int)
    for t in trades:
        sym_counts[t["name"] or t["symbol_raw"]] += 1
    favorite = max(sym_counts.items(), key=lambda x: x[1]) if sym_counts else None
    if favorite and favorite[1] >= 4:
        traits.append({"trait": "Favorite battlefield", "verdict": favorite[0],
                       "evidence": f"{favorite[1]} trades in this name alone."})

    badges = []
    if n >= 10:
        badges.append("🎖 10+ round trips")
    if profit_factor and profit_factor >= 1.5:
        badges.append("🏆 Profit factor 1.5+")
    if win_rate >= 55:
        badges.append("🎯 55%+ hit rate")
    if median_hold is not None and median_hold >= 90:
        badges.append("💎 Diamond hands")
    if median_hold is not None and 5 <= median_hold <= 30:
        badges.append("🌊 True swing trader")

    best = max(trips, key=lambda t: t["pnl"])
    worst = min(trips, key=lambda t: t["pnl"])
    return {
        "ready": True,
        "round_trips": n,
        "win_rate": win_rate,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "profit_factor": profit_factor,
        "median_hold_days": median_hold,
        "best_trade": best,
        "worst_trade": worst,
        "traits": traits,
        "badges": badges,
    }


def holdings_summary(holdings: list[dict], live: dict[str, float]) -> dict:
    positions = []
    invested = current = 0.0
    live_missing = 0
    for h in holdings:
        inv = h["quantity"] * h["avg_price"]
        ltp = live.get(h["symbol"]) if h["symbol"] else None
        if ltp is None:
            ltp = h.get("ltp_imported") or h["avg_price"]
            live_missing += 1
            live_src = "file/avg"
        else:
            live_src = "live"
        cur = h["quantity"] * ltp
        invested += inv
        current += cur
        positions.append({
            "symbol": h["symbol"], "symbol_raw": h["symbol_raw"], "name": h["name"],
            "quantity": h["quantity"], "avg_price": round(h["avg_price"], 2),
            "ltp": round(ltp, 2), "ltp_source": live_src,
            "invested": round(inv, 2), "current": round(cur, 2),
            "pnl": round(cur - inv, 2),
            "pnl_pct": round((cur / inv - 1) * 100, 2) if inv else 0.0,
        })
    positions.sort(key=lambda p: p["current"], reverse=True)
    for p in positions:
        p["weight_pct"] = round(p["current"] / current * 100, 2) if current else 0.0
    top3 = round(sum(p["weight_pct"] for p in positions[:3]), 1)
    return {
        "positions": positions,
        "invested": round(invested, 2),
        "current": round(current, 2),
        "pnl": round(current - invested, 2),
        "pnl_pct": round((current / invested - 1) * 100, 2) if invested else 0.0,
        "position_count": len(positions),
        "top3_concentration_pct": top3,
        "live_quotes_missing": live_missing,
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def fetch_live_prices(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    import yfinance as yf
    out: dict[str, float] = {}
    try:
        df = yf.download(symbols, period="5d", interval="1d", group_by="ticker",
                         progress=False, threads=True, auto_adjust=False)
        multi = isinstance(df.columns, pd.MultiIndex)
        for s in symbols:
            try:
                closes = (df[s] if multi else df)["Close"].dropna()
                if len(closes):
                    out[s] = float(closes.iloc[-1])
            except Exception:
                continue
    except Exception:
        pass
    return out


def portfolio_source(note: str | None = None) -> dict:
    s = _source_block("") | {
        "provider": "Your imported broker file + Yahoo Finance live quotes",
    }
    if note:
        s["note"] = note
    return s
