"""Deterministic unit tests for the Analyst Engine (pytest).

Run from backend/:  venv\\Scripts\\activate  ->  pytest -q
"""
import math

from app.services.analysis_engine import (
    analyze, atr, build_zones, find_pivots, rsi, sma,
)
from app.services.narration import _allowed_numbers, _verify


def make_candle(t, o, h, l, c, v=1000):
    return {"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v}


def synthetic_breakout(n=120):
    """Uptrend -> wobbly consolidation band ~98..103 -> breakout with volume.
    The wobble matters: flat plateaus (equal highs) are not pivots, by design."""
    candles = []
    price = 70.0
    for i in range(n):
        if i < 60:                      # uptrend with slight wobble
            price += 0.5
            w = 0.1 * (i % 3)
            candles.append(make_candle(i * 86400, price - 0.3, price + 0.6 + w,
                                       price - 0.8 - w, price))
        elif i < n - 3:                 # triangle-wave consolidation
            j = i - 60
            cyc = j % 8
            base = 100 + (2.0 - 0.15 * cyc if cyc < 4 else -2.0 + 0.15 * (cyc - 4))
            w = 0.07 * (j % 5)
            candles.append(make_candle(i * 86400, base - 0.4, base + 0.7 + w,
                                       base - 0.7 - w, base))
        else:                           # breakout candles on 3x volume
            price = 103.5 + (i - (n - 3)) * 1.2
            candles.append(make_candle(i * 86400, price - 0.5, price + 0.8,
                                       price - 0.9, price, v=3000))
    return candles


def test_sma_and_rsi_and_atr_basics():
    closes = [float(i) for i in range(1, 31)]
    assert sma(closes, 10) == sum(range(21, 31)) / 10
    assert sma(closes, 100) is None
    r = rsi(closes)
    assert r is not None and r > 95        # monotonic rise -> RSI near 100
    candles = [make_candle(i, 10, 11, 9, 10) for i in range(20)]
    assert math.isclose(atr(candles), 2.0, rel_tol=1e-6)


def test_pivots_found_on_zigzag():
    candles = []
    for i in range(40):
        cyc = i % 10
        base = 100 + (cyc if cyc <= 5 else 10 - cyc)  # triangle wave, unique peaks
        candles.append(make_candle(i, base, base + 1, base - 1, base))
    pivots = find_pivots(candles)
    assert any(p.kind == "high" for p in pivots)
    assert any(p.kind == "low" for p in pivots)


def test_zones_require_two_touches():
    candles = synthetic_breakout()
    pivots = find_pivots(candles)
    zones = build_zones(pivots, candles[-1]["close"], atr(candles), len(candles))
    assert all(z["touches"] >= 2 for z in zones)
    assert all(z["price_low"] < z["price_high"] for z in zones)


def test_full_analyze_breakout_payload():
    result = analyze(synthetic_breakout())
    setup = result["setup"]
    assert setup["state"] in ("breakout_above_resistance", "consolidation_below_resistance",
                              "pullback_to_support")
    if setup["plan"]:
        p = setup["plan"]
        assert p["stop_loss"] < p["entry_low"] <= p["entry_high"] < p["target1"] <= p["target2"]
        assert p["risk_reward"] >= 1.0
        assert 0 <= setup["confidence"] <= 100
        assert sum(f["max"] for f in setup["factors"]) == 100


def test_analyze_rejects_short_series():
    import pytest
    with pytest.raises(ValueError):
        analyze([make_candle(i, 10, 11, 9, 10) for i in range(10)])


def test_verifier_removes_invented_numbers():
    payload = {"setup": {"plan": {"entry_low": 101.0}}, "indicators": {"last_close": 103.55}}
    allowed = _allowed_numbers(payload)
    text = "Entry sits at 101.00 which is sound. The stock will hit 999.99 next week."
    clean, removed = _verify(text, allowed)
    assert removed == 1
    assert "999.99" not in clean
    assert "101.00" in clean


# ---------------------------------------------------------- indicator suite

def test_every_registry_indicator_computes_without_error():
    """Integrity test: every indicator in the catalog must run on real-shaped
    data with default params and produce well-formed series."""
    from app.services.indicators import REGISTRY, compute
    candles = synthetic_breakout(300)
    for ind_id in REGISTRY:
        out = compute(ind_id, candles, {})
        assert out["pane"] in ("overlay", "sub")
        assert isinstance(out["series"], list) and out["series"], ind_id
        for s in out["series"]:
            assert s["type"] in ("line", "histogram")
            for pt in s["data"]:
                assert "time" in pt and "value" in pt and pt["value"] == pt["value"], ind_id  # no NaN


def test_indicator_math_spot_checks():
    from app.services.indicators import _ema, _sma, compute
    assert _sma([1, 2, 3, 4, 5], 5)[-1] == 3
    e = _ema([1.0] * 50, 10)
    assert abs(e[-1] - 1.0) < 1e-9
    candles = synthetic_breakout(300)
    rsi_out = compute("rsi", candles, {"period": 14})
    vals = [p["value"] for p in rsi_out["series"][0]["data"]]
    assert all(0 <= v <= 100 for v in vals)
    adx_out = compute("adx", candles, {})
    assert {s["name"] for s in adx_out["series"]} == {"ADX", "+DI", "-DI"}
    bb = compute("bollinger", candles, {})
    up = {p["time"]: p["value"] for p in bb["series"][0]["data"]}
    dn = {p["time"]: p["value"] for p in bb["series"][2]["data"]}
    assert all(up[t] >= dn[t] for t in up if t in dn)


def test_indicator_param_clamping():
    from app.services.indicators import compute
    candles = synthetic_breakout(100)
    out = compute("rsi", candles, {"period": 99999, "source": "nonsense"})
    assert out["params"]["period"] == 100      # clamped to max
    assert out["params"]["source"] == "close"  # invalid option -> default


# ------------------------------------------------------------ markets suite

def test_markets_batch_quotes_shaping(monkeypatch):
    import pandas as pd
    from app.services import markets as mk

    idx = pd.date_range("2026-07-08", periods=5, freq="D")
    def fake_download(symbols, **kw):
        cols = pd.MultiIndex.from_product([symbols, ["Close", "Volume"]])
        df = pd.DataFrame(index=idx, columns=cols, dtype=float)
        for i, s in enumerate(symbols):
            df[(s, "Close")] = [100 + i, 101 + i, 102 + i, 103 + i, 105 + i]
            df[(s, "Volume")] = [1000] * 5
        return df
    monkeypatch.setattr(mk.yf, "download", fake_download)
    mk._CACHE.clear()

    seg = mk.get_segment("india_large")
    assert seg["items"], "quotes should not be empty"
    row = seg["items"][0]
    assert {"symbol", "name", "price", "change", "change_pct", "volume", "spark", "currency"} <= set(row)
    assert row["currency"] == "₹" and len(row["spark"]) == 5
    assert seg["items"] == sorted(seg["items"], key=lambda x: x["change_pct"], reverse=True)

    # cache: second call must NOT re-download
    calls = {"n": 0}
    monkeypatch.setattr(mk.yf, "download", lambda *a, **k: calls.__setitem__("n", calls["n"] + 1) or fake_download(a[0]))
    assert mk.get_segment("india_large")["items"]
    assert calls["n"] == 0

    import pytest
    with pytest.raises(KeyError):
        mk.get_segment("moon_rocks")


# --------------------------------------------------------------- news suite

def _fake_entry(title, link, src):
    class S: pass
    e = {"title": title, "link": link, "published_parsed": (2026, 7, 16, 10, 0, 0, 0, 0, 0)}
    class E(dict):
        source = type("Src", (), {"title": src})()
        def __getattr__(self, k):
            try: return self[k]
            except KeyError: raise AttributeError(k)
    out = E(e)
    return out

def test_news_corroboration_and_cache(monkeypatch):
    from app.services import news as nw
    nw._CACHE.clear()

    def fake_parse(url):
        if "economictimes" in url:
            return {"entries": [_fake_entry("Reliance Q1 profit jumps 12% on retail growth", "https://et.com/a1", "Economic Times")]}
        if "moneycontrol" in url:
            return {"entries": [_fake_entry("Reliance Q1 profit surges 12% led by retail", "https://mc.com/b2", "Moneycontrol")]}
        if "livemint" in url:
            return {"entries": [_fake_entry("Rupee slips against dollar in early trade", "https://lm.com/c3", "LiveMint")]}
        return {"entries": []}
    monkeypatch.setattr(nw.feedparser, "parse", fake_parse)

    out = nw.get_market_news()
    stories = {s["title"]: s for s in out["items"]}
    confirmed = [s for s in out["items"] if s["confirmed"]]
    assert len(confirmed) == 1, "the two similar Reliance headlines must merge and confirm"
    assert set(confirmed[0]["corroborated_by"]) == {"Economic Times", "Moneycontrol"}
    unverified = [s for s in out["items"] if not s["confirmed"]]
    assert any("Rupee" in s["title"] for s in unverified)
    assert set(out["feeds_ok"]) >= {"Economic Times Markets", "Moneycontrol Markets", "LiveMint Markets"}
    assert out["feeds_failed"]  # the google feeds returned no entries -> reported honestly

    calls = {"n": 0}
    monkeypatch.setattr(nw.feedparser, "parse", lambda u: calls.__setitem__("n", calls["n"] + 1) or {"entries": []})
    nw.get_market_news()
    assert calls["n"] == 0, "second call must be served from cache"


def test_local_search_beginner_queries():
    from app.services.markets import local_search
    assert local_search("larsen and turbo")[0]["symbol"] == "LT.NS"
    golds = {r["symbol"] for r in local_search("gold")}
    assert "GOLDBEES.NS" in golds and ("GC=F" in golds or "GLD" in golds)
    assert local_search("bitcoin")[0]["symbol"] == "BTC-USD"
    assert local_search("xzqy") == []


def test_extended_uptrend_state_with_watch_levels():
    """AAPL-at-highs scenario: healthy trend + steep extension -> the engine
    must say 'strong_uptrend_extended' and still hand over levels to watch."""
    from app.services.analysis_engine import analyze
    cs, price = [], 100.0
    for i in range(240):
        if i < 228:
            price += 0.4 + 0.15 * ((i % 7) - 3) / 3
            w = 0.3 + 0.1 * (i % 3)
            cs.append(make_candle(i * 86400, price - 0.2, price + w, price - w, price))
        else:
            price *= 1.02
            cs.append(make_candle(i * 86400, price - 1, price + 1.5, price - 2, price, 1500))
    r = analyze(cs)
    assert r["setup"]["state"] in ("strong_uptrend_extended", "breakout_above_resistance")
    w = r["setup"]["watch"]
    assert w["nearest_support"] is not None or w["recent_swing_low"] is not None
    assert w["sma20"] is not None and w["recent_swing_high"] >= w["recent_swing_low"]


# ----------------------------------------------------- scanner + chat memory

def test_scanner_ranks_engine_setups(monkeypatch):
    import pandas as pd
    from app.services import scanner as sc
    sc._CACHE.clear()
    breakout = synthetic_breakout(120)
    flat = [make_candle(i * 86400, 50, 50.6, 49.4, 50 + 0.01 * (i % 3)) for i in range(120)]

    def fake_download(symbols, **kw):
        idx = pd.to_datetime([c["time"] for c in breakout], unit="s")
        cols = pd.MultiIndex.from_product([symbols, ["Open", "High", "Low", "Close", "Volume"]])
        df = pd.DataFrame(index=idx, columns=cols, dtype=float)
        for i, s in enumerate(symbols):
            src = breakout if i == 0 else flat
            for f, k in (("Open", "open"), ("High", "high"), ("Low", "low"),
                         ("Close", "close"), ("Volume", "volume")):
                df[(s, f)] = [c[k] for c in src]
        return df
    monkeypatch.setattr(sc.yf, "download", fake_download)

    out = sc.scan("india_large", top=5)
    assert out["scanned"] > 0 and out["techniques"]
    assert out["actionable"], "the breakout symbol must surface as actionable"
    first = out["actionable"][0]
    assert first["plan"]["risk_reward"] >= 1.0 and 0 <= first["confidence"] <= 100
    # cache
    monkeypatch.setattr(sc.yf, "download", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no refetch")))
    assert sc.scan("india_large", top=5)["scanned"] == out["scanned"]


def test_chat_history_persists(monkeypatch):
    from fastapi.testclient import TestClient
    import app.routers.ai as ai_mod
    from app.main import app
    monkeypatch.setattr(ai_mod, "search_symbols",
                        lambda q: {"results": [{"symbol": "SUZLON.NS", "name": "Suzlon", "exchange": "NSI", "type": "EQUITY"}]})
    import uuid
    c = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    r = c.post("/api/auth/register",
               json={"username": f"chat_{uid}", "email": f"{uid}@t.com", "password": "password123"})
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = c.post("/api/ai/chat", headers=H, json={"message": "analyse suzlon"})
    conv_id = r.json()["conversation_id"]
    assert r.json()["action"]["symbol"] == "SUZLON.NS"
    convs = c.get("/api/ai/conversations", headers=H).json()
    assert any(cv["id"] == conv_id for cv in convs)
    msgs = c.get(f"/api/ai/conversations/{conv_id}/messages", headers=H).json()
    assert [m["role"] for m in msgs] == ["user", "ai"]
    assert c.delete(f"/api/ai/conversations/{conv_id}", headers=H).json()["deleted"] == conv_id
    assert c.get(f"/api/ai/conversations/{conv_id}/messages", headers=H).status_code == 404


# ------------------------------------------------------------ showcase suite

def test_demo_seeding_and_health_flag(monkeypatch):
    from app import config, main
    from app.database import SessionLocal
    from app.models import User
    monkeypatch.setattr(config, "DEMO_MODE", True)
    main.seed_demo_user()
    main.seed_demo_user()  # idempotent
    db = SessionLocal()
    try:
        assert db.query(User).filter(User.email == config.DEMO_EMAIL).count() == 1
    finally:
        db.close()
    from fastapi.testclient import TestClient
    c = TestClient(main.app)
    assert c.get("/api/health").json()["demo"] is True


def test_cloud_adapter_selection_and_grounded_errors(monkeypatch):
    from app import config
    from app.services.llm import base
    monkeypatch.setattr(config, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(base, "LLM_PROVIDER", "ollama", raising=False)
    # factory re-imports from config module each call
    import app.config as cfg
    monkeypatch.setattr(cfg, "LLM_PROVIDER", "cloud")
    llm = base.get_llm()
    assert llm.provider_name == "cloud"
    monkeypatch.setattr(cfg, "CLOUD_LLM_API_KEY", "")
    st = llm.status()
    assert st["online"] is False and "groq" in st["detail"].lower()
    import pytest
    from app.services.llm.base import LLMUnavailable
    with pytest.raises(LLMUnavailable):
        llm.chat([{"role": "user", "content": "hi"}])


# ------------------------------------------------------------- mirror suite

def test_parser_handles_both_sample_broker_formats():
    from pathlib import Path
    from app.services.portfolio import parse_broker_file
    root = Path(__file__).resolve().parents[2] / "sample_data"

    tb = parse_broker_file((root / "groww_style_tradebook.csv").read_bytes(),
                           "groww_style_tradebook.csv")
    assert tb["kind"] == "tradebook"
    assert tb["report"]["imported"] == 14 and tb["report"]["skipped"] >= 0
    dixon = [r for r in tb["rows"] if "Dixon" in (r["name"] or "")][0]
    assert dixon["price"] == 14250.0  # comma-in-quotes number parsed
    assert all(r["side"] in ("BUY", "SELL") for r in tb["rows"])
    assert all(r["trade_date"] is not None for r in tb["rows"])  # dayfirst dates

    hd = parse_broker_file((root / "indmoney_style_holdings.csv").read_bytes(),
                           "indmoney_style_holdings.csv")
    assert hd["kind"] == "holdings"
    rel = [r for r in hd["rows"] if r["symbol"] == "RELIANCE.NS"][0]
    assert rel["ltp"] == 1296.6 and rel["quantity"] == 12
    lt = [r for r in hd["rows"] if "Larsen" in (r["name"] or "")]
    assert lt and lt[0]["symbol"] == "LT.NS"


def test_fifo_partial_lots_exact_math():
    from datetime import datetime
    from app.services.portfolio import fifo_round_trips
    D = lambda d: datetime(2026, 1, d)
    trades = [
        {"id": 1, "symbol": "X.NS", "symbol_raw": "X", "name": "X", "side": "BUY",  "quantity": 10, "price": 100.0, "trade_date": D(1)},
        {"id": 2, "symbol": "X.NS", "symbol_raw": "X", "name": "X", "side": "BUY",  "quantity": 10, "price": 110.0, "trade_date": D(5)},
        {"id": 3, "symbol": "X.NS", "symbol_raw": "X", "name": "X", "side": "SELL", "quantity": 15, "price": 120.0, "trade_date": D(20)},
    ]
    trips, realized = fifo_round_trips(trades)
    assert realized == 10 * 20 + 5 * 10 == 250
    assert [t["qty"] for t in trips] == [10, 5]
    assert trips[0]["days"] == 19 and trips[1]["days"] == 15


def test_behavior_profile_honesty_and_traits():
    from app.services.portfolio import behavior_profile
    few = [{"symbol": "A", "name": "A", "qty": 1, "buy_price": 10, "sell_price": 12,
            "pnl": 2.0, "pnl_pct": 20.0, "days": 5}] * 3
    p = behavior_profile(few, [])
    assert p["ready"] is False and "5" in p["message"]

    trips = []
    for i in range(6):
        trips.append({"symbol": "A", "name": "A", "qty": 1, "buy_price": 100,
                      "sell_price": 104, "pnl": 4.0, "pnl_pct": 4.0, "days": 12})
    for i in range(4):
        trips.append({"symbol": "B", "name": "B", "qty": 1, "buy_price": 100,
                      "sell_price": 91, "pnl": -9.0, "pnl_pct": -9.0, "days": 25})
    p = behavior_profile(trips, [])
    assert p["ready"] and p["round_trips"] == 10 and p["win_rate"] == 60.0
    assert any(t["verdict"] == "Lets losers run" for t in p["traits"])
    assert any("Swing trader" in t["verdict"] for t in p["traits"])
    assert "🎖 10+ round trips" in p["badges"]


def test_portfolio_import_roundtrip_api(monkeypatch):
    import uuid
    from pathlib import Path
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import portfolio as pf
    monkeypatch.setattr(pf, "fetch_live_prices", lambda syms: {s: 100.0 for s in syms})
    import app.routers.portfolio as pr
    monkeypatch.setattr(pr, "fetch_live_prices", lambda syms: {s: 100.0 for s in syms})

    root = Path(__file__).resolve().parents[2] / "sample_data"
    c = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    r = c.post("/api/auth/register",
               json={"username": f"pf_{uid}", "email": f"{uid}@p.com", "password": "password123"})
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = c.post("/api/portfolio/import", headers=H, data={"broker": "indmoney"},
               files={"file": ("holdings.csv", (root / "indmoney_style_holdings.csv").read_bytes(), "text/csv")})
    assert r.status_code == 200 and r.json()["kind"] == "holdings"

    r = c.post("/api/portfolio/import", headers=H, data={"broker": "groww"},
               files={"file": ("tradebook.csv", (root / "groww_style_tradebook.csv").read_bytes(), "text/csv")})
    assert r.json()["kind"] == "tradebook" and r.json()["imported"] == 14

    s = c.get("/api/portfolio/summary", headers=H).json()
    assert s["position_count"] == 5 and s["invested"] > 0

    b = c.get("/api/portfolio/behavior", headers=H).json()
    assert b["profile"]["ready"] is True and b["profile"]["round_trips"] == 7
    assert b["realized_pnl"] != 0

    # re-import same broker replaces, not duplicates
    c.post("/api/portfolio/import", headers=H, data={"broker": "groww"},
           files={"file": ("tradebook.csv", (root / "groww_style_tradebook.csv").read_bytes(), "text/csv")})
    b2 = c.get("/api/portfolio/behavior", headers=H).json()
    assert b2["trade_count"] == 14

    d = c.delete("/api/portfolio", headers=H).json()
    assert d["deleted_holdings"] == 5 and d["deleted_trades"] == 14


# ------------------------------------------------------- alive-phase suite

def _plan(entry_high, stop, t1, t2, created_day=1):
    from datetime import datetime
    class P: pass
    p = P()
    p.entry_high, p.stop_loss, p.target1, p.target2 = entry_high, stop, t1, t2
    p.created_at = datetime(2026, 1, created_day)
    return p


def _c(day, low, high):
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
    return {"time": int(base.timestamp()),
            "low": low, "high": high, "open": low, "close": high, "volume": 1}


def test_grading_all_paths():
    from app.services.grading import EXPIRY_BARS, aggregate, grade_plan
    plan = _plan(entry_high=100, stop=95, t1=110, t2=120)
    # T1 then T2, stop never hit
    assert grade_plan(plan, [_c(2, 99, 101), _c(3, 100, 111), _c(4, 105, 121)]) == "hit_t2"
    # T1 hit, then stop -> pessimistic but locked win at T1
    assert grade_plan(plan, [_c(2, 99, 101), _c(3, 100, 111), _c(4, 94, 105)]) == "hit_t1"
    # stop before any target
    assert grade_plan(plan, [_c(2, 99, 101), _c(3, 94, 103)]) == "stopped"
    # same candle touches stop AND t1 -> pessimistic: stopped
    assert grade_plan(plan, [_c(2, 99, 101), _c(3, 94, 111)]) == "stopped"
    # never enters the zone -> expired after EXPIRY_BARS
    far = [_c(2 + i, 150, 160) for i in range(EXPIRY_BARS + 1)]
    assert grade_plan(plan, far) == "expired"
    # triggered, nothing resolved -> still open
    assert grade_plan(plan, [_c(2, 99, 101), _c(3, 98, 104)]) == "open"
    agg = aggregate(["hit_t1", "hit_t2", "stopped", "open", "expired"])
    assert agg["graded_closed"] == 3 and agg["win_rate"] == 66.7


def test_watchlist_alerts_and_track_record_api(monkeypatch):
    import uuid
    from fastapi.testclient import TestClient
    from app.main import app
    import app.routers.tracking as tr

    monkeypatch.setattr(tr, "batch_quotes",
                        lambda syms: {s: {"price": 105.0, "change_pct": 1.2} for s in syms})
    c = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    r = c.post("/api/auth/register",
               json={"username": f"al_{uid}", "email": f"{uid}@a.com", "password": "password123"})
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # watchlist toggle on/off + quotes merged
    assert c.post("/api/watchlist/SUZLON.NS?name=Suzlon", headers=H).json()["watched"] is True
    wl = c.get("/api/watchlist", headers=H).json()["items"]
    assert wl[0]["symbol"] == "SUZLON.NS" and wl[0]["price"] == 105.0
    assert c.post("/api/watchlist/SUZLON.NS", headers=H).json()["watched"] is False

    # alert above 104 with price 105 -> fires; below 90 stays active
    a1 = c.post("/api/alerts?symbol=X.NS&price=104&direction=above", headers=H).json()
    c.post("/api/alerts?symbol=X.NS&price=90&direction=below", headers=H)
    fired = c.post("/api/alerts/check", headers=H).json()
    assert [f["id"] for f in fired["triggered"]] == [a1["id"]] and fired["active"] == 1

    # track record: plant a plan, mock candles that hit T2
    from app.database import SessionLocal
    from app.models import TradePlan, User
    from datetime import datetime
    db = SessionLocal()
    me = db.query(User).filter(User.email == f"{uid}@a.com").one()
    db.add(TradePlan(user_id=me.id, symbol="Y.NS", interval="1D", setup_state="breakout_above_resistance",
                     entry_low=99, entry_high=100, stop_loss=95, target1=110, target2=120,
                     risk_reward=2.0, confidence=70, created_at=datetime(2026, 1, 1)))
    db.commit(); db.close()
    monkeypatch.setattr(tr, "get_candles",
                        lambda s, r_, i: {"candles": [_c(2, 99, 101), _c(3, 100, 121)]})
    out = c.post("/api/track-record", headers=H).json()
    assert out["scorecard"]["hit_t2"] == 1 and out["scorecard"]["win_rate"] == 100.0
    assert out["plans"][0]["status"] == "hit_t2"
