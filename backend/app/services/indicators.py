"""Indicator engine — a registry of technical indicators.

Every indicator is pure math over OHLCV (no AI anywhere), returns series
aligned to candle times, and carries educational metadata (what it is, how
to read it, difficulty level) so the UI can teach beginners while serving
advanced users. Adding a new indicator = one function + one registry entry.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone


# ------------------------------------------------------------ math helpers

def _sma(vals, p):
    out = [None] * len(vals)
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= p:
            s -= vals[i - p]
        if i >= p - 1:
            out[i] = s / p
    return out


def _ema(vals, p):
    out = [None] * len(vals)
    if len(vals) < p:
        return out
    seed = sum(vals[:p]) / p
    out[p - 1] = seed
    k = 2 / (p + 1)
    for i in range(p, len(vals)):
        out[i] = vals[i] * k + out[i - 1] * (1 - k)
    return out


def _rma(vals, p):  # Wilder smoothing
    out = [None] * len(vals)
    if len(vals) < p:
        return out
    out[p - 1] = sum(vals[:p]) / p
    for i in range(p, len(vals)):
        out[i] = (out[i - 1] * (p - 1) + vals[i]) / p
    return out


def _wma(vals, p):
    out = [None] * len(vals)
    denom = p * (p + 1) / 2
    for i in range(p - 1, len(vals)):
        out[i] = sum(vals[i - p + 1 + j] * (j + 1) for j in range(p)) / denom
    return out


def _stdev(vals, p):
    out = [None] * len(vals)
    for i in range(p - 1, len(vals)):
        w = vals[i - p + 1: i + 1]
        m = sum(w) / p
        out[i] = math.sqrt(sum((x - m) ** 2 for x in w) / p)
    return out


def _tr(c):
    trs = [c[0]["high"] - c[0]["low"]]
    for i in range(1, len(c)):
        trs.append(max(c[i]["high"] - c[i]["low"],
                       abs(c[i]["high"] - c[i - 1]["close"]),
                       abs(c[i]["low"] - c[i - 1]["close"])))
    return trs


def _hh(vals, p):
    return [max(vals[max(0, i - p + 1): i + 1]) if i >= p - 1 else None for i in range(len(vals))]


def _ll(vals, p):
    return [min(vals[max(0, i - p + 1): i + 1]) if i >= p - 1 else None for i in range(len(vals))]


def _pick_source(c, source):
    if source == "open":
        return [x["open"] for x in c]
    if source == "high":
        return [x["high"] for x in c]
    if source == "low":
        return [x["low"] for x in c]
    if source == "hl2":
        return [(x["high"] + x["low"]) / 2 for x in c]
    if source == "hlc3":
        return [(x["high"] + x["low"] + x["close"]) / 3 for x in c]
    if source == "ohlc4":
        return [(x["open"] + x["high"] + x["low"] + x["close"]) / 4 for x in c]
    return [x["close"] for x in c]


def _pts(times, vals):
    return [{"time": t, "value": round(v, 4)} for t, v in zip(times, vals) if v is not None]


def _line(name, times, vals, color, style=0, width=1):
    return {"name": name, "type": "line", "color": color, "lineStyle": style,
            "lineWidth": width, "data": _pts(times, vals)}


def _hist(name, times, vals, color):
    return {"name": name, "type": "histogram", "color": color, "data": _pts(times, vals)}


# --------------------------------------------------------------- overlays

def i_sma(c, t, p):
    return [_line(f"SMA {p['period']}", t, _sma(_pick_source(c, p["source"]), p["period"]), "#4f9cf9")]


def i_ema(c, t, p):
    return [_line(f"EMA {p['period']}", t, _ema(_pick_source(c, p["source"]), p["period"]), "#e8b64c")]


def i_wma(c, t, p):
    return [_line(f"WMA {p['period']}", t, _wma(_pick_source(c, p["source"]), p["period"]), "#c084fc")]


def i_bollinger(c, t, p):
    src = _pick_source(c, p["source"])
    mid = _sma(src, p["period"])
    sd = _stdev(src, p["period"])
    up = [m + p["mult"] * s if m is not None and s is not None else None for m, s in zip(mid, sd)]
    dn = [m - p["mult"] * s if m is not None and s is not None else None for m, s in zip(mid, sd)]
    return [_line("BB upper", t, up, "#4f9cf9", 2), _line("BB mid", t, mid, "#8b9bb4"),
            _line("BB lower", t, dn, "#4f9cf9", 2)]


def i_keltner(c, t, p):
    mid = _ema([x["close"] for x in c], p["period"])
    a = _rma(_tr(c), p["atr_period"])
    up = [m + p["mult"] * x if m is not None and x is not None else None for m, x in zip(mid, a)]
    dn = [m - p["mult"] * x if m is not None and x is not None else None for m, x in zip(mid, a)]
    return [_line("KC upper", t, up, "#22c07a", 2), _line("KC mid", t, mid, "#8b9bb4"),
            _line("KC lower", t, dn, "#22c07a", 2)]


def i_donchian(c, t, p):
    hh = _hh([x["high"] for x in c], p["period"])
    ll = _ll([x["low"] for x in c], p["period"])
    mid = [(a + b) / 2 if a is not None and b is not None else None for a, b in zip(hh, ll)]
    return [_line("DC upper", t, hh, "#38bdf8", 2), _line("DC mid", t, mid, "#8b9bb4"),
            _line("DC lower", t, ll, "#38bdf8", 2)]


def i_supertrend(c, t, p):
    a = _rma(_tr(c), p["period"])
    hl2 = [(x["high"] + x["low"]) / 2 for x in c]
    n = len(c)
    ub = [None] * n
    lb = [None] * n
    up_line = [None] * n
    dn_line = [None] * n
    trend = 1
    fub = flb = None
    for i in range(n):
        if a[i] is None:
            continue
        bub = hl2[i] + p["mult"] * a[i]
        blb = hl2[i] - p["mult"] * a[i]
        fub = bub if fub is None or bub < fub or c[i - 1]["close"] > fub else fub
        flb = blb if flb is None or blb > flb or c[i - 1]["close"] < flb else flb
        prev_trend = trend
        if c[i]["close"] > fub:
            trend = 1
        elif c[i]["close"] < flb:
            trend = -1
        if trend != prev_trend:  # band resets on flip
            fub, flb = bub, blb
        (up_line if trend == 1 else dn_line)[i] = flb if trend == 1 else fub
        ub[i], lb[i] = fub, flb
    return [_line("Supertrend up", t, up_line, "#22c07a", 0, 2),
            _line("Supertrend down", t, dn_line, "#ef5350", 0, 2)]


def i_psar(c, t, p):
    n = len(c)
    out = [None] * n
    if n < 3:
        return [_line("PSAR", t, out, "#e8b64c", 1)]
    af_step, af_max = p["step"], p["max"]
    up = c[1]["close"] > c[0]["close"]
    sar = c[0]["low"] if up else c[0]["high"]
    ep = c[0]["high"] if up else c[0]["low"]
    af = af_step
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if up:
            sar = min(sar, c[i - 1]["low"], c[max(0, i - 2)]["low"])
            if c[i]["low"] < sar:
                up, sar, ep, af = False, ep, c[i]["low"], af_step
            elif c[i]["high"] > ep:
                ep, af = c[i]["high"], min(af + af_step, af_max)
        else:
            sar = max(sar, c[i - 1]["high"], c[max(0, i - 2)]["high"])
            if c[i]["high"] > sar:
                up, sar, ep, af = True, ep, c[i]["high"], af_step
            elif c[i]["low"] < ep:
                ep, af = c[i]["low"], min(af + af_step, af_max)
        out[i] = sar
    return [_line("PSAR", t, out, "#e8b64c", 1)]


def i_ichimoku(c, t, p):
    highs = [x["high"] for x in c]
    lows = [x["low"] for x in c]
    mid = lambda hp, lp: [(a + b) / 2 if a is not None and b is not None else None
                          for a, b in zip(_hh(highs, hp), _ll(lows, lp))]
    tenkan = mid(p["tenkan"], p["tenkan"])
    kijun = mid(p["kijun"], p["kijun"])
    senkou_a_raw = [(a + b) / 2 if a is not None and b is not None else None for a, b in zip(tenkan, kijun)]
    senkou_b_raw = mid(p["senkou_b"], p["senkou_b"])
    shift = p["kijun"]
    n = len(c)
    sa = [None] * n
    sb = [None] * n
    chikou = [None] * n
    for i in range(n):
        if i + shift < n:
            sa[i + shift] = senkou_a_raw[i]
            sb[i + shift] = senkou_b_raw[i]
        if i - shift >= 0:
            chikou[i - shift] = c[i]["close"]
    return [_line("Tenkan", t, tenkan, "#4f9cf9"), _line("Kijun", t, kijun, "#ef5350"),
            _line("Senkou A", t, sa, "#22c07a", 2), _line("Senkou B", t, sb, "#f97316", 2),
            _line("Chikou", t, chikou, "#c084fc", 1)]


def i_vwap(c, t, p):
    cum_pv = cum_v = 0.0
    out = []
    for x in c:
        tp = (x["high"] + x["low"] + x["close"]) / 3
        cum_pv += tp * max(x["volume"], 0)
        cum_v += max(x["volume"], 0)
        out.append(cum_pv / cum_v if cum_v else None)
    return [_line("VWAP (anchored to range start)", t, out, "#f97316", 0, 2)]


def i_week52(c, t, p):
    w = p["window"]
    return [_line(f"{w}-bar high", t, _hh([x["high"] for x in c], w), "#22c07a", 2),
            _line(f"{w}-bar low", t, _ll([x["low"] for x in c], w), "#ef5350", 2)]


def i_pivots(c, t, p):
    """Traditional pivots from the previous period (day->month grouping by interval length)."""
    n = len(c)
    if n < 2:
        return []
    span = t[1] - t[0]
    group_fmt = "%Y-%m-%d" if span < 86400 else ("%G-%V" if span < 7 * 86400 else "%Y-%m")
    keys = [datetime.fromtimestamp(x, tz=timezone.utc).strftime(group_fmt) for x in t]
    lines = {k: [None] * n for k in ("P", "R1", "S1", "R2", "S2")}
    prev = None
    cur_key = keys[0]
    cur = {"h": c[0]["high"], "l": c[0]["low"], "c": c[0]["close"]}
    for i in range(n):
        if keys[i] != cur_key:
            prev, cur_key = cur, keys[i]
            cur = {"h": c[i]["high"], "l": c[i]["low"], "c": c[i]["close"]}
        else:
            cur["h"] = max(cur["h"], c[i]["high"])
            cur["l"] = min(cur["l"], c[i]["low"])
            cur["c"] = c[i]["close"]
        if prev:
            P = (prev["h"] + prev["l"] + prev["c"]) / 3
            lines["P"][i] = P
            lines["R1"][i] = 2 * P - prev["l"]
            lines["S1"][i] = 2 * P - prev["h"]
            lines["R2"][i] = P + (prev["h"] - prev["l"])
            lines["S2"][i] = P - (prev["h"] - prev["l"])
    return [_line("Pivot P", t, lines["P"], "#e8b64c", 2),
            _line("R1", t, lines["R1"], "#ef5350", 2), _line("S1", t, lines["S1"], "#22c07a", 2),
            _line("R2", t, lines["R2"], "#ef5350", 1), _line("S2", t, lines["S2"], "#22c07a", 1)]


# ------------------------------------------------------------- oscillators

def i_rsi(c, t, p):
    src = _pick_source(c, p["source"])
    gains = [0.0] + [max(src[i] - src[i - 1], 0) for i in range(1, len(src))]
    losses = [0.0] + [max(src[i - 1] - src[i], 0) for i in range(1, len(src))]
    ag, al = _rma(gains[1:], p["period"]), _rma(losses[1:], p["period"])
    out = [None]
    for g, l in zip(ag, al):
        out.append(None if g is None else (100.0 if l == 0 else 100 - 100 / (1 + g / l)))
    return [_line(f"RSI {p['period']}", t, out, "#c084fc", 0, 2)]


def i_stochastic(c, t, p):
    hh = _hh([x["high"] for x in c], p["k"])
    ll = _ll([x["low"] for x in c], p["k"])
    k_raw = [None if h is None or h == l else (x["close"] - l) / (h - l) * 100
             for x, h, l in zip(c, hh, ll)]
    k_s = _sma([v for v in k_raw], p["smooth"]) if all(v is not None for v in k_raw) else _sma_none(k_raw, p["smooth"])
    d = _sma_none(k_s, p["d"])
    return [_line("%K", t, k_s, "#4f9cf9", 0, 2), _line("%D", t, d, "#e8b64c")]


def _sma_none(vals, p):
    out = [None] * len(vals)
    for i in range(len(vals)):
        w = vals[max(0, i - p + 1): i + 1]
        if len(w) == p and all(v is not None for v in w):
            out[i] = sum(w) / p
    return out


def i_stochrsi(c, t, p):
    rsi_line = i_rsi(c, t, {"period": p["rsi"], "source": "close"})[0]
    vals = {pt["time"]: pt["value"] for pt in rsi_line["data"]}
    r = [vals.get(x) for x in t]
    hh = [max(v for v in r[max(0, i - p["stoch"] + 1): i + 1] if v is not None)
          if r[i] is not None and all(v is not None for v in r[max(0, i - p["stoch"] + 1): i + 1]) and i >= p["stoch"] - 1
          else None for i in range(len(r))]
    ll = [min(v for v in r[max(0, i - p["stoch"] + 1): i + 1] if v is not None)
          if hh[i] is not None else None for i in range(len(r))]
    k = [None if hh[i] is None or hh[i] == ll[i] else (r[i] - ll[i]) / (hh[i] - ll[i]) * 100
         for i in range(len(r))]
    k_s = _sma_none(k, p["k"])
    d = _sma_none(k_s, p["d"])
    return [_line("StochRSI %K", t, k_s, "#4f9cf9", 0, 2), _line("StochRSI %D", t, d, "#e8b64c")]


def i_macd(c, t, p):
    src = _pick_source(c, p["source"])
    fast, slow = _ema(src, p["fast"]), _ema(src, p["slow"])
    macd = [f - s if f is not None and s is not None else None for f, s in zip(fast, slow)]
    signal = _ema_none(macd, p["signal"])
    hist = [m - s if m is not None and s is not None else None for m, s in zip(macd, signal)]
    return [_hist("Histogram", t, hist, "#8b9bb4"),
            _line("MACD", t, macd, "#4f9cf9", 0, 2), _line("Signal", t, signal, "#e8b64c")]


def _ema_none(vals, p):
    idx = [i for i, v in enumerate(vals) if v is not None]
    out = [None] * len(vals)
    if len(idx) < p:
        return out
    start = idx[0]
    clean = vals[start:]
    e = _ema(clean, p)
    for i, v in enumerate(e):
        out[start + i] = v
    return out


def i_cci(c, t, p):
    tp = [(x["high"] + x["low"] + x["close"]) / 3 for x in c]
    m = _sma(tp, p["period"])
    out = [None] * len(c)
    for i in range(p["period"] - 1, len(c)):
        w = tp[i - p["period"] + 1: i + 1]
        md = sum(abs(x - m[i]) for x in w) / p["period"]
        out[i] = (tp[i] - m[i]) / (0.015 * md) if md else 0
    return [_line(f"CCI {p['period']}", t, out, "#38bdf8", 0, 2)]


def i_adx(c, t, p):
    n = len(c)
    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, n):
        up = c[i]["high"] - c[i - 1]["high"]
        dn = c[i - 1]["low"] - c[i]["low"]
        plus_dm.append(up if up > dn and up > 0 else 0.0)
        minus_dm.append(dn if dn > up and dn > 0 else 0.0)
    atr_s = _rma(_tr(c)[1:], p["period"])
    pdi_s = _rma(plus_dm[1:], p["period"])
    mdi_s = _rma(minus_dm[1:], p["period"])
    pdi = [None]
    mdi = [None]
    dx = []
    for a, pd, md in zip(atr_s, pdi_s, mdi_s):
        if a is None or not a:
            pdi.append(None); mdi.append(None); dx.append(None)
            continue
        pv, mv = 100 * pd / a, 100 * md / a
        pdi.append(pv); mdi.append(mv)
        dx.append(100 * abs(pv - mv) / (pv + mv) if pv + mv else None)
    adx = [None] + _rma_none(dx, p["period"])
    return [_line("ADX", t, adx, "#e8b64c", 0, 2),
            _line("+DI", t, pdi, "#22c07a"), _line("-DI", t, mdi, "#ef5350")]


def _rma_none(vals, p):
    idx = [i for i, v in enumerate(vals) if v is not None]
    out = [None] * len(vals)
    if len(idx) < p:
        return out
    start = idx[0]
    r = _rma(vals[start:], p)
    for i, v in enumerate(r):
        out[start + i] = v
    return out


def i_willr(c, t, p):
    hh = _hh([x["high"] for x in c], p["period"])
    ll = _ll([x["low"] for x in c], p["period"])
    out = [None if h is None or h == l else -100 * (h - x["close"]) / (h - l)
           for x, h, l in zip(c, hh, ll)]
    return [_line(f"Williams %R {p['period']}", t, out, "#f97316", 0, 2)]


def i_momentum(c, t, p):
    src = _pick_source(c, p["source"])
    out = [src[i] - src[i - p["period"]] if i >= p["period"] else None for i in range(len(src))]
    return [_line(f"Momentum {p['period']}", t, out, "#4f9cf9", 0, 2)]


def i_roc(c, t, p):
    src = _pick_source(c, p["source"])
    out = [(src[i] / src[i - p["period"]] - 1) * 100 if i >= p["period"] and src[i - p["period"]] else None
           for i in range(len(src))]
    return [_line(f"ROC {p['period']}", t, out, "#38bdf8", 0, 2)]


def i_ao(c, t, p):
    hl2 = [(x["high"] + x["low"]) / 2 for x in c]
    f, s = _sma(hl2, 5), _sma(hl2, 34)
    out = [a - b if a is not None and b is not None else None for a, b in zip(f, s)]
    return [_hist("Awesome Oscillator", t, out, "#22c07a")]


def i_atr(c, t, p):
    return [_line(f"ATR {p['period']}", t, [None] + _rma(_tr(c)[1:], p["period"]), "#f97316", 0, 2)]


def i_obv(c, t, p):
    out = [0.0]
    for i in range(1, len(c)):
        d = c[i]["volume"] if c[i]["close"] > c[i - 1]["close"] else (-c[i]["volume"] if c[i]["close"] < c[i - 1]["close"] else 0)
        out.append(out[-1] + d)
    return [_line("OBV", t, out, "#4f9cf9", 0, 2)]


def i_mfi(c, t, p):
    tp = [(x["high"] + x["low"] + x["close"]) / 3 for x in c]
    pos = [0.0]
    neg = [0.0]
    for i in range(1, len(c)):
        flow = tp[i] * c[i]["volume"]
        pos.append(flow if tp[i] > tp[i - 1] else 0.0)
        neg.append(flow if tp[i] < tp[i - 1] else 0.0)
    out = [None] * len(c)
    P = p["period"]
    for i in range(P, len(c)):
        ps, ns = sum(pos[i - P + 1: i + 1]), sum(neg[i - P + 1: i + 1])
        out[i] = 100.0 if ns == 0 else 100 - 100 / (1 + ps / ns)
    return [_line(f"MFI {p['period']}", t, out, "#22c07a", 0, 2)]


def i_cmf(c, t, p):
    mfv = []
    for x in c:
        rng = x["high"] - x["low"]
        mfv.append(((x["close"] - x["low"]) - (x["high"] - x["close"])) / rng * x["volume"] if rng else 0.0)
    out = [None] * len(c)
    P = p["period"]
    for i in range(P - 1, len(c)):
        vs = sum(x["volume"] for x in c[i - P + 1: i + 1])
        out[i] = sum(mfv[i - P + 1: i + 1]) / vs if vs else None
    return [_line(f"CMF {p['period']}", t, out, "#c084fc", 0, 2)]


def i_volma(c, t, p):
    vols = [float(x["volume"]) for x in c]
    colors_hist = _hist("Volume", t, vols, "#3a4a68")
    return [colors_hist, _line(f"Vol MA {p['period']}", t, _sma(vols, p["period"]), "#e8b64c", 0, 2)]


# ----------------------------------------------------------------- registry

_SRC = {"default": "close", "options": ["open", "high", "low", "close", "hl2", "hlc3", "ohlc4"]}

REGISTRY: dict[str, dict] = {
    # ---- Trend (overlay)
    "sma": {"name": "Simple Moving Average", "category": "Trend", "level": "beginner", "pane": "overlay",
            "params": {"period": {"default": 20, "min": 2, "max": 500}, "source": _SRC}, "fn": i_sma,
            "description": "The average price over N candles — the most basic trend line.",
            "how_to_read": "Price above a rising SMA = uptrend. The 50 and 200 SMAs are the classic trend filters; their crossover is the famous golden/death cross."},
    "ema": {"name": "Exponential Moving Average", "category": "Trend", "level": "beginner", "pane": "overlay",
            "params": {"period": {"default": 21, "min": 2, "max": 500}, "source": _SRC}, "fn": i_ema,
            "description": "A moving average that reacts faster by weighting recent prices more.",
            "how_to_read": "Swing traders often use the 21 EMA as dynamic support in trends: pullbacks that hold it keep the trend alive."},
    "wma": {"name": "Weighted Moving Average", "category": "Trend", "level": "intermediate", "pane": "overlay",
            "params": {"period": {"default": 20, "min": 2, "max": 500}, "source": _SRC}, "fn": i_wma,
            "description": "Like EMA but with linear weighting — even snappier to recent moves.",
            "how_to_read": "Use it when the EMA feels too slow; expect more whipsaws in sideways markets."},
    "supertrend": {"name": "Supertrend", "category": "Trend", "level": "beginner", "pane": "overlay",
                   "params": {"period": {"default": 10, "min": 2, "max": 100}, "mult": {"default": 3.0, "min": 0.5, "max": 10}}, "fn": i_supertrend,
                   "description": "An ATR-based trailing line that flips green (bullish) or red (bearish).",
                   "how_to_read": "Green line below price = stay long, use it as a trailing stop. A flip to red is the exit/reverse signal. Very popular with Indian intraday traders."},
    "psar": {"name": "Parabolic SAR", "category": "Trend", "level": "intermediate", "pane": "overlay",
             "params": {"step": {"default": 0.02, "min": 0.001, "max": 0.2}, "max": {"default": 0.2, "min": 0.02, "max": 1}}, "fn": i_psar,
             "description": "Dots that trail price and accelerate as the trend extends.",
             "how_to_read": "Dots below price = uptrend; when price crosses the dots, the trend flips. Works best in trending markets, whipsaws in ranges."},
    "ichimoku": {"name": "Ichimoku Cloud", "category": "Trend", "level": "advanced", "pane": "overlay",
                 "params": {"tenkan": {"default": 9, "min": 2, "max": 100}, "kijun": {"default": 26, "min": 2, "max": 200}, "senkou_b": {"default": 52, "min": 2, "max": 400}}, "fn": i_ichimoku,
                 "description": "A complete Japanese system: trend, momentum, and support/resistance in one view.",
                 "how_to_read": "Price above the cloud = bullish regime; the cloud ahead projects future support/resistance. Tenkan/Kijun cross works like a fast MA cross."},
    "vwap": {"name": "VWAP (anchored)", "category": "Trend", "level": "intermediate", "pane": "overlay",
             "params": {}, "fn": i_vwap,
             "description": "Volume-weighted average price, anchored to the start of the loaded range.",
             "how_to_read": "The institutional 'fair value' line: price holding above VWAP means buyers paid up; reclaim/reject at VWAP is a classic intraday signal."},
    # ---- Volatility (overlay)
    "bollinger": {"name": "Bollinger Bands", "category": "Volatility", "level": "beginner", "pane": "overlay",
                  "params": {"period": {"default": 20, "min": 2, "max": 200}, "mult": {"default": 2.0, "min": 0.5, "max": 5}, "source": _SRC}, "fn": i_bollinger,
                  "description": "A moving average with bands 2 standard deviations away — a volatility envelope.",
                  "how_to_read": "Tight bands (squeeze) = energy building for a big move. Rides along the upper band signal strong trends, not automatic sells."},
    "keltner": {"name": "Keltner Channels", "category": "Volatility", "level": "intermediate", "pane": "overlay",
                "params": {"period": {"default": 20, "min": 2, "max": 200}, "atr_period": {"default": 10, "min": 2, "max": 100}, "mult": {"default": 2.0, "min": 0.5, "max": 5}}, "fn": i_keltner,
                "description": "EMA-centered channel sized by ATR instead of standard deviation.",
                "how_to_read": "Bollinger squeezing INSIDE Keltner = the 'TTM squeeze', a favorite pre-breakout condition."},
    "donchian": {"name": "Donchian Channels", "category": "Volatility", "level": "beginner", "pane": "overlay",
                 "params": {"period": {"default": 20, "min": 2, "max": 200}}, "fn": i_donchian,
                 "description": "The highest high and lowest low of the last N candles.",
                 "how_to_read": "A close above the upper channel is the classic turtle-trader breakout entry; the mid-line is a common trailing exit."},
    # ---- Levels (overlay)
    "pivots": {"name": "Pivot Points (Traditional)", "category": "Levels", "level": "intermediate", "pane": "overlay",
               "params": {}, "fn": i_pivots,
               "description": "Floor-trader levels (P, R1/R2, S1/S2) computed from the previous period.",
               "how_to_read": "Intraday charts pivot off yesterday; daily charts off last week/month. Price opening above P leans bullish; R1/S1 are the first reaction zones."},
    "week52": {"name": "Rolling High/Low (52-wk style)", "category": "Levels", "level": "beginner", "pane": "overlay",
               "params": {"window": {"default": 252, "min": 10, "max": 1000}}, "fn": i_week52,
               "description": "The rolling N-bar highest high and lowest low (252 daily bars ≈ 52 weeks).",
               "how_to_read": "Stocks breaking to fresh 52-week highs are momentum leaders; the level itself acts as a magnet and a battleground."},
    # ---- Momentum (sub-pane)
    "rsi": {"name": "RSI", "category": "Momentum", "level": "beginner", "pane": "sub", "reference_lines": [30, 70],
            "params": {"period": {"default": 14, "min": 2, "max": 100}, "source": _SRC}, "fn": i_rsi,
            "description": "Measures the speed of price moves on a 0–100 scale.",
            "how_to_read": "Above 70 = hot (overbought), below 30 = washed out (oversold) — but in strong trends RSI staying 50–80 is health, not a sell. Divergence vs price is the pro signal."},
    "stochastic": {"name": "Stochastic", "category": "Momentum", "level": "beginner", "pane": "sub", "reference_lines": [20, 80],
                   "params": {"k": {"default": 14, "min": 2, "max": 100}, "smooth": {"default": 3, "min": 1, "max": 20}, "d": {"default": 3, "min": 1, "max": 20}}, "fn": i_stochastic,
                   "description": "Where the close sits inside the recent high-low range (0–100).",
                   "how_to_read": "%K crossing above %D below 20 is the classic buy trigger in an uptrend pullback."},
    "stochrsi": {"name": "Stochastic RSI", "category": "Momentum", "level": "advanced", "pane": "sub", "reference_lines": [20, 80],
                 "params": {"rsi": {"default": 14, "min": 2, "max": 100}, "stoch": {"default": 14, "min": 2, "max": 100}, "k": {"default": 3, "min": 1, "max": 20}, "d": {"default": 3, "min": 1, "max": 20}}, "fn": i_stochrsi,
                 "description": "A stochastic applied to RSI itself — an extra-sensitive momentum trigger.",
                 "how_to_read": "Fires earlier than RSI but with more noise; best used only in the direction of the bigger trend."},
    "macd": {"name": "MACD", "category": "Momentum", "level": "beginner", "pane": "sub",
             "params": {"fast": {"default": 12, "min": 2, "max": 100}, "slow": {"default": 26, "min": 3, "max": 200}, "signal": {"default": 9, "min": 2, "max": 50}, "source": _SRC}, "fn": i_macd,
             "description": "The gap between a fast and slow EMA, plus its signal line and histogram.",
             "how_to_read": "MACD crossing above signal = momentum turning up; histogram shrinking warns the move is tiring. Zero-line crosses mark trend changes."},
    "cci": {"name": "CCI", "category": "Momentum", "level": "intermediate", "pane": "sub", "reference_lines": [-100, 100],
            "params": {"period": {"default": 20, "min": 2, "max": 100}}, "fn": i_cci,
            "description": "How far price has stretched from its typical average.",
            "how_to_read": "Above +100 = strong upside momentum (trend traders buy strength); a return from below -100 flags mean-reversion bounces."},
    "adx": {"name": "ADX / DI", "category": "Momentum", "level": "intermediate", "pane": "sub", "reference_lines": [25],
            "params": {"period": {"default": 14, "min": 2, "max": 100}}, "fn": i_adx,
            "description": "Trend STRENGTH (ADX) plus direction (+DI vs -DI).",
            "how_to_read": "ADX above 25 = a real trend worth trading; below 20 = chop, breakouts fail. +DI above -DI = bulls in control."},
    "willr": {"name": "Williams %R", "category": "Momentum", "level": "intermediate", "pane": "sub", "reference_lines": [-20, -80],
              "params": {"period": {"default": 14, "min": 2, "max": 100}}, "fn": i_willr,
              "description": "Stochastic's twin on a 0 to -100 scale.",
              "how_to_read": "Above -20 = overbought zone, below -80 = oversold; exits from the zones are the triggers."},
    "momentum": {"name": "Momentum", "category": "Momentum", "level": "beginner", "pane": "sub", "reference_lines": [0],
                 "params": {"period": {"default": 10, "min": 1, "max": 100}, "source": _SRC}, "fn": i_momentum,
                 "description": "Simply: today's price minus the price N candles ago.",
                 "how_to_read": "Above zero and rising = accelerating move. The simplest momentum confirmation there is."},
    "roc": {"name": "Rate of Change", "category": "Momentum", "level": "beginner", "pane": "sub", "reference_lines": [0],
            "params": {"period": {"default": 12, "min": 1, "max": 100}, "source": _SRC}, "fn": i_roc,
            "description": "Momentum expressed as a percentage change.",
            "how_to_read": "Lets you compare momentum across stocks fairly (a ₹100 and ₹5,000 stock on the same scale)."},
    "ao": {"name": "Awesome Oscillator", "category": "Momentum", "level": "intermediate", "pane": "sub", "reference_lines": [0],
           "params": {}, "fn": i_ao,
           "description": "Bill Williams' 5 vs 34 period midpoint momentum histogram.",
           "how_to_read": "Zero-line crosses and 'twin peaks' below zero are its classic signals."},
    # ---- Volatility (sub)
    "atr": {"name": "ATR", "category": "Volatility", "level": "beginner", "pane": "sub",
            "params": {"period": {"default": 14, "min": 2, "max": 100}}, "fn": i_atr,
            "description": "The average size of a candle's true range — the market's temperature.",
            "how_to_read": "Not a direction signal: use it to size stops (e.g. 1.5×ATR below entry) so normal noise doesn't stop you out. Our Analyze engine does exactly this."},
    # ---- Volume (sub)
    "volma": {"name": "Volume + MA", "category": "Volume", "level": "beginner", "pane": "sub",
              "params": {"period": {"default": 20, "min": 2, "max": 200}}, "fn": i_volma,
              "description": "Volume bars with their moving average.",
              "how_to_read": "A breakout on volume well above its MA is real; a breakout on quiet volume is suspect. Volume is the lie detector."},
    "obv": {"name": "On-Balance Volume", "category": "Volume", "level": "intermediate", "pane": "sub",
            "params": {}, "fn": i_obv,
            "description": "A running total that adds volume on up days and subtracts it on down days.",
            "how_to_read": "OBV making new highs before price does = accumulation; OBV lagging a price high = the rally lacks fuel."},
    "mfi": {"name": "Money Flow Index", "category": "Volume", "level": "intermediate", "pane": "sub", "reference_lines": [20, 80],
            "params": {"period": {"default": 14, "min": 2, "max": 100}}, "fn": i_mfi,
            "description": "RSI weighted by volume — 'RSI with a lie detector attached'.",
            "how_to_read": "Same zones as RSI (80/20) but divergences carry more weight because volume backs them."},
    "cmf": {"name": "Chaikin Money Flow", "category": "Volume", "level": "advanced", "pane": "sub", "reference_lines": [0],
            "params": {"period": {"default": 20, "min": 2, "max": 100}}, "fn": i_cmf,
            "description": "Measures whether closes are happening near highs (buying) or lows (selling), volume-weighted.",
            "how_to_read": "Sustained positive CMF during a sideways base = quiet accumulation before markup."},
}


def registry_meta() -> list[dict]:
    return [
        {"id": k, **{f: v[f] for f in ("name", "category", "level", "pane", "description", "how_to_read")},
         "reference_lines": v.get("reference_lines", []),
         "params": {name: {kk: vv for kk, vv in spec.items() if kk != "options"} | ({"options": spec["options"]} if "options" in spec else {})
                    for name, spec in v["params"].items()}}
        for k, v in REGISTRY.items()
    ]


def compute(indicator_id: str, candles: list[dict], params: dict) -> dict:
    if indicator_id not in REGISTRY:
        raise KeyError(f"Unknown indicator '{indicator_id}'")
    entry = REGISTRY[indicator_id]
    merged = {}
    for name, spec in entry["params"].items():
        raw = params.get(name, spec["default"])
        if "options" in spec:
            merged[name] = raw if raw in spec["options"] else spec["default"]
        else:
            try:
                val = float(raw)
            except (TypeError, ValueError):
                val = spec["default"]
            val = max(spec["min"], min(spec["max"], val))
            merged[name] = int(val) if float(val).is_integer() and not isinstance(spec["default"], float) else val
    times = [c["time"] for c in candles]
    return {
        "id": indicator_id,
        "name": entry["name"],
        "pane": entry["pane"],
        "reference_lines": entry.get("reference_lines", []),
        "params": merged,
        "series": entry["fn"](candles, times, merged),
    }
