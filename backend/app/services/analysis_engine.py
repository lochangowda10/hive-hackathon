"""The Analyst Engine — pure mathematics, zero AI.

Reproduces what a chart analyst draws by hand: swing pivots, horizontal
support/resistance zones, trendlines, breakout detection, and a
scenario-based trade plan with an explainable confidence score.

Every number the platform ever shows a user is computed here (or fetched
from a data source). The LLM never originates a number.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass


# ---------------------------------------------------------------- indicators

def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def atr(candles: list[dict], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


# ------------------------------------------------------------------- pivots

@dataclass
class Pivot:
    index: int
    time: int
    price: float
    kind: str  # "high" | "low"


def find_pivots(candles: list[dict], k: int = 3) -> list[Pivot]:
    """A swing high is a high greater than the k highs on each side
    (swing low symmetric). k=3 matches how analysts eyeball daily charts."""
    pivots: list[Pivot] = []
    n = len(candles)
    for i in range(k, n - k):
        hi = candles[i]["high"]
        lo = candles[i]["low"]
        if all(hi > candles[j]["high"] for j in range(i - k, i + k + 1) if j != i):
            pivots.append(Pivot(i, candles[i]["time"], hi, "high"))
        if all(lo < candles[j]["low"] for j in range(i - k, i + k + 1) if j != i):
            pivots.append(Pivot(i, candles[i]["time"], lo, "low"))
    return pivots


# -------------------------------------------------------------------- zones

def build_zones(pivots: list[Pivot], last_close: float, atr_value: float,
                n_candles: int, max_per_side: int = 3) -> list[dict]:
    """Cluster pivot prices into horizontal S/R zones.

    Tolerance is ATR-scaled so it adapts to each stock's volatility.
    Strength = touches + recency bonus (recent zones matter more).
    """
    if not pivots or not atr_value:
        return []
    tol = 0.6 * atr_value
    width_cap = 1.5 * atr_value
    clusters: list[list[Pivot]] = []
    for p in sorted(pivots, key=lambda x: x.price):
        if clusters:
            prices = [q.price for q in clusters[-1]]
            near = abs(p.price - statistics.mean(prices)) <= tol
            within_cap = (max(prices + [p.price]) - min(prices + [p.price])) <= width_cap
            if near and within_cap:
                clusters[-1].append(p)
                continue
        clusters.append([p])

    zones = []
    for cluster in clusters:
        if len(cluster) < 2:  # a zone needs at least two touches
            continue
        prices = [p.price for p in cluster]
        recency = max(p.index for p in cluster) / max(n_candles - 1, 1)
        strength = round(len(cluster) + 2 * recency, 2)
        mid = statistics.mean(prices)
        pad = 0.15 * atr_value
        zones.append({
            "price_low": round(min(prices) - pad, 2),
            "price_high": round(max(prices) + pad, 2),
            "mid": round(mid, 2),
            "kind": "resistance" if mid > last_close else "support",
            "touches": len(cluster),
            "strength": strength,
            "last_touch_time": max(p.time for p in cluster),
        })

    supports = sorted([z for z in zones if z["kind"] == "support"],
                      key=lambda z: z["strength"], reverse=True)[:max_per_side]
    resistances = sorted([z for z in zones if z["kind"] == "resistance"],
                         key=lambda z: z["strength"], reverse=True)[:max_per_side]
    return sorted(supports + resistances, key=lambda z: z["mid"])


# --------------------------------------------------------------- trendlines

def build_trendlines(pivots: list[Pivot], candles: list[dict],
                     atr_value: float) -> list[dict]:
    """Connect swing lows (rising) or swing highs (falling) into trendlines,
    projected to the latest candle. Only lines with >=2 touches survive."""
    if not atr_value:
        return []
    lines = []
    last = candles[-1]

    for kind, direction in (("low", "up"), ("high", "down")):
        pts = [p for p in pivots if p.kind == kind][-5:]
        if len(pts) < 2:
            continue
        a, b = pts[0], pts[-1]
        if b.index == a.index:
            continue
        slope = (b.price - a.price) / (b.index - a.index)
        if direction == "up" and slope <= 0:
            continue
        if direction == "down" and slope >= 0:
            continue
        touches = sum(
            1 for p in pts
            if abs((a.price + slope * (p.index - a.index)) - p.price) <= 0.5 * atr_value
        )
        if touches < 2:
            continue
        end_index = len(candles) - 1
        lines.append({
            "time1": a.time,
            "price1": round(a.price, 2),
            "time2": last["time"],
            "price2": round(a.price + slope * (end_index - a.index), 2),
            "direction": direction,
            "touches": touches,
        })
    return lines


# ------------------------------------------------------- setup + trade plan

def detect_setup(candles: list[dict], zones: list[dict], ind: dict) -> dict:
    """Classify the current state the way the reel presenter would call it,
    then derive a scenario-based plan. Honest by design: returns
    'no_clean_setup' with no plan when nothing is there."""
    closes = [c["close"] for c in candles]
    last = candles[-1]
    last_close = last["close"]
    a = ind["atr14"]

    resistances = [z for z in zones if z["kind"] == "resistance"]
    supports = [z for z in zones if z["kind"] == "support"]
    nearest_res = min(resistances, key=lambda z: z["mid"]) if resistances else None
    nearest_sup = max(supports, key=lambda z: z["mid"]) if supports else None

    state, bias, key_zone, markers = "no_clean_setup", "neutral", None, []

    # Breakout: close crossed above a multi-touch zone within the last 5 bars
    broken = [z for z in supports if z["touches"] >= 2 and z["kind"] == "support"]
    for z in sorted(broken, key=lambda z: z["mid"], reverse=True):
        crossed_recently = any(
            candles[i - 1]["close"] <= z["price_high"] < candles[i]["close"]
            for i in range(max(1, len(candles) - 5), len(candles))
        )
        if crossed_recently and last_close > z["price_high"]:
            state, bias, key_zone = "breakout_above_resistance", "bullish", z
            for i in range(max(1, len(candles) - 5), len(candles)):
                if candles[i - 1]["close"] <= z["price_high"] < candles[i]["close"]:
                    markers.append({"time": candles[i]["time"], "position": "belowBar",
                                    "shape": "arrowUp", "label": "Breakout"})
                    break
            break

    if state == "no_clean_setup" and a:
        window = candles[-15:]
        band = max(c["high"] for c in window) - min(c["low"] for c in window)
        uptrend = (ind["sma50"] and ind["sma200"]
                   and last_close > ind["sma50"] > ind["sma200"])
        downtrend = (ind["sma50"] and ind["sma200"]
                     and last_close < ind["sma50"] < ind["sma200"])
        if band < 3.5 * a and nearest_res:
            state = "consolidation_below_resistance"
            bias = "bullish" if uptrend else "neutral"
            key_zone = nearest_res
        elif uptrend and nearest_sup and abs(last_close - nearest_sup["price_high"]) <= 1.2 * a:
            state, bias, key_zone = "pullback_to_support", "bullish", nearest_sup
        elif downtrend:
            state, bias = "downtrend", "bearish"
        elif uptrend:
            # Trend is healthy but price is stretched away from the base:
            # the honest call is "wait for the pullback", not silence.
            state, bias = "strong_uptrend_extended", "bullish"

    plan = None
    if a and bias == "bullish" and state != "downtrend":
        if state == "breakout_above_resistance" and key_zone:
            entry_low, entry_high = key_zone["price_high"], key_zone["price_high"] + 0.3 * a
            stop = key_zone["price_low"] - 0.8 * a
        elif state == "pullback_to_support" and key_zone:
            entry_low, entry_high = key_zone["price_low"], key_zone["price_high"]
            stop = key_zone["price_low"] - 1.2 * a
        elif state == "consolidation_below_resistance" and key_zone:
            # Conditional plan: valid only IF price breaks the zone
            entry_low, entry_high = key_zone["price_high"], key_zone["price_high"] + 0.3 * a
            stop = last_close - 1.5 * a
        else:
            entry_low = entry_high = stop = None

        if entry_low is not None:
            entry_mid = (entry_low + entry_high) / 2
            above = sorted([z for z in zones if z["mid"] > entry_high],
                           key=lambda z: z["mid"])
            t1 = above[0]["mid"] if above else entry_mid + 2 * a
            t2 = above[1]["mid"] if len(above) > 1 else max(t1 + 1.5 * a, entry_mid + 3.5 * a)
            risk = entry_mid - stop
            rr = round((t1 - entry_mid) / risk, 2) if risk > 0 else 0
            if rr >= 1.0:
                plan = {
                    "entry_low": round(entry_low, 2), "entry_high": round(entry_high, 2),
                    "stop_loss": round(stop, 2),
                    "target1": round(t1, 2), "target2": round(t2, 2),
                    "risk_reward": rr,
                    "conditional": state == "consolidation_below_resistance",
                }
            else:
                state, plan = "no_clean_setup", None

    return {"state": state, "bias": bias, "plan": plan, "markers": markers,
            "key_zone": key_zone}


def confidence_factors(setup: dict, ind: dict, candles: list[dict]) -> tuple[int, list[dict]]:
    """Explainable 0-100 score. Each factor's contribution is returned so the
    UI can show exactly WHY the score is what it is."""
    if not setup["plan"]:
        return 0, []
    last_close = candles[-1]["close"]
    factors = []

    trend = 0
    if ind["sma50"] and ind["sma200"]:
        if last_close > ind["sma50"] > ind["sma200"]:
            trend = 25
        elif last_close > ind["sma50"]:
            trend = 14
    factors.append({"name": "Trend alignment (price vs 50/200 SMA)",
                    "contribution": trend, "max": 25})

    vol = 0
    vr = ind["volume_ratio"]
    if vr is not None:
        vol = 20 if vr >= 1.3 else 10 if vr >= 1.0 else 0
    factors.append({"name": f"Volume confirmation ({vr}x of 20-bar average)" if vr else "Volume confirmation",
                    "contribution": vol, "max": 20})

    zone = 0
    kz = setup.get("key_zone")
    if kz:
        zone = 20 if kz["touches"] >= 3 else 12
    factors.append({"name": f"Level strength ({kz['touches']} touches)" if kz else "Level strength",
                    "contribution": zone, "max": 20})

    r = ind["rsi14"]
    rsi_score = 0
    if r is not None:
        rsi_score = 15 if 45 <= r <= 70 else 6 if 35 <= r < 45 or 70 < r <= 75 else 0
    factors.append({"name": f"Momentum health (RSI {round(r,1) if r is not None else '—'})",
                    "contribution": rsi_score, "max": 15})

    rr = setup["plan"]["risk_reward"]
    rr_score = 20 if rr >= 2 else 12 if rr >= 1.5 else 6
    factors.append({"name": f"Risk-reward ({rr}:1 to first target)",
                    "contribution": rr_score, "max": 20})

    return sum(f["contribution"] for f in factors), factors


# ------------------------------------------------------------------- engine

def analyze(candles: list[dict]) -> dict:
    """Full deterministic analysis of an OHLCV series."""
    if len(candles) < 40:
        raise ValueError(
            "Not enough candles for a reliable analysis (need at least 40). "
            "Try a longer range or a smaller interval."
        )
    closes = [c["close"] for c in candles]
    vols = [c["volume"] for c in candles]
    a = atr(candles)
    vol_avg = sma([float(v) for v in vols], 20)
    ind = {
        "last_close": round(closes[-1], 2),
        "atr14": round(a, 2) if a else None,
        "sma20": round(sma(closes, 20), 2) if sma(closes, 20) else None,
        "sma50": round(sma(closes, 50), 2) if sma(closes, 50) else None,
        "sma200": round(sma(closes, 200), 2) if sma(closes, 200) else None,
        "rsi14": round(rsi(closes), 2) if rsi(closes) is not None else None,
        "avg_volume_20": int(vol_avg) if vol_avg else None,
        "volume_ratio": round(vols[-1] / vol_avg, 2) if vol_avg else None,
    }
    pivots = find_pivots(candles)
    zones = build_zones(pivots, closes[-1], a or 0, len(candles))
    trendlines = build_trendlines(pivots, candles, a or 0)
    setup = detect_setup(candles, zones, ind)
    confidence, factors = confidence_factors(setup, ind, candles)

    supports = [z for z in zones if z["kind"] == "support"]
    resistances = [z for z in zones if z["kind"] == "resistance"]
    watch = {
        "nearest_support": max(supports, key=lambda z: z["mid"]) if supports else None,
        "nearest_resistance": min(resistances, key=lambda z: z["mid"]) if resistances else None,
        "sma20": ind["sma20"],
        "recent_swing_low": round(min(c["low"] for c in candles[-20:]), 2),
        "recent_swing_high": round(max(c["high"] for c in candles[-20:]), 2),
    }

    return {
        "as_of": candles[-1]["time"],
        "indicators": ind,
        "zones": zones,
        "trendlines": trendlines,
        "markers": setup.pop("markers"),
        "setup": {
            "state": setup["state"],
            "bias": setup["bias"],
            "plan": setup["plan"],
            "confidence": confidence,
            "factors": factors,
            "watch": watch,
        },
    }
