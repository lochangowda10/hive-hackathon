"""Research engine — fundamental scores, multi-model fair value, composite
AI score, thesis generation, verdict. Pure math over the normalized
fundamentals payload (services/fundamentals.py) plus technicals from the
existing analysis engine. No LLM call anywhere in this file.

Everything returns factors/explanations so the UI can show WHY (§9, §28).
Missing data lowers scores/confidence and is labeled — never guessed (§48).
"""
from __future__ import annotations

import statistics

ENGINE_VERSION = "research-v1"


# ---------------------------------------------------------------- helpers

def _cagr(end: float | None, start: float | None, years: int) -> float | None:
    if end is None or start is None or start <= 0 or end <= 0 or years < 1:
        return None
    return (end / start) ** (1 / years) - 1


def _band(score: float | None, bands: list[tuple[float, str]]) -> str | None:
    if score is None:
        return None
    for threshold, label in bands:
        if score <= threshold:
            return label
    return bands[-1][1]


def _lin(vals: list[tuple[float, float]], lo: float, hi: float,
         pts: float, invert: bool = False) -> float:
    """Linear interpolate score of vals across [lo,hi] -> [0,pts]."""
    out = []
    for v, default in vals:
        if v is None:
            out.append(default * pts)
            continue
        x = min(max((v - lo) / (hi - lo), 0.0), 1.0)
        out.append((1 - x if invert else x) * pts)
    return sum(out) / len(out) if out else 0.0


def _points(score_fn, *args, pts: float, label: str, fmt=str) -> dict:
    v = score_fn(*args)
    return {"name": label, "value": fmt(v) if v is not None else None,
            "points": round(v * pts if v is not None else 0.0, 1), "max": pts}


HEALTH_BANDS = [(20, "Very Weak"), (40, "Weak"), (60, "Fair"),
                (75, "Good"), (90, "Great"), (101, "Excellent")]
CF_BANDS = [(25, "Poor"), (45, "Fair"), (65, "Good"), (85, "Great"), (101, "Excellent")]
AI_BANDS = [(40, "Avoid"), (50, "Weak"), (60, "Neutral"), (70, "Watchlist"),
            (80, "Attractive"), (90, "Strong"), (101, "Exceptional")]


def _latest(years: list[dict], key: str, n: int = 5) -> list[float]:
    return [y[key] for y in years[:n] if y.get(key) is not None]


# ---------------------------------------------------------------- scores

def score_financial_health(f: dict) -> dict:
    inc, bal, cf = f["income"], f["balance"], f["cashflow"]
    i0 = inc[0]
    b0 = bal[0] if bal else {}
    factors: list[dict] = []

    def add(label, value, ratio, pts):
        factors.append({"name": label, "value": value,
                        "points": round(ratio * pts, 1), "max": pts})

    ebit, interest = i0.get("ebit"), i0.get("interest_expense")
    ic = (ebit / abs(interest)) if (ebit and interest) else (10.0 if not interest else None)
    add("Interest coverage (EBIT/interest)", round(ic, 1) if ic is not None else None,
        _lin([(ic, 0.5)], 0, 8, 1), 15)

    debt = b0.get("total_debt")
    ebitda = i0.get("ebitda") or i0.get("ebit")
    cash = b0.get("cash") or 0
    nde = ((debt - cash) / ebitda) if (debt is not None and ebitda and ebitda > 0) else None
    add("Net debt / EBITDA", round(nde, 2) if nde is not None else None,
        _lin([(nde, 0.6)], 4, 0, 1), 15)

    cr = (b0.get("current_assets") / b0["current_liabilities"]
          if b0.get("current_assets") and b0.get("current_liabilities") else None)
    add("Current ratio", round(cr, 2) if cr is not None else None,
        _lin([(cr, 0.5)], 0.8, 2.0, 1), 10)

    equity = b0.get("equity")
    ni = i0.get("net_income")
    roe = (ni / equity) if (ni is not None and equity) else None
    add("ROE", f"{roe * 100:.1f}%" if roe is not None else None,
        _lin([(roe, 0.5)], 0, 0.25, 1), 10)

    cap_employed = (equity or 0) + (debt or 0)
    roce = (ebit / cap_employed) if (ebit and cap_employed) else None
    add("ROCE (EBIT/capital employed)", f"{roce * 100:.1f}%" if roce is not None else None,
        _lin([(roce, 0.5)], 0, 0.25, 1), 10)

    rev = i0.get("revenue")
    pat_m = (ni / rev) if (ni is not None and rev) else None
    add("PAT margin", f"{pat_m * 100:.1f}%" if pat_m is not None else None,
        _lin([(pat_m, 0.5)], 0, 0.20, 1), 10)

    ebitda_m = (ebitda / rev) if (ebitda and rev) else None
    add("EBITDA margin", f"{ebitda_m * 100:.1f}%" if ebitda_m is not None else None,
        _lin([(ebitda_m, 0.5)], 0, 0.35, 1), 10)

    fcf0 = cf[0].get("fcf") if cf else None
    add("Positive free cash flow", fcf0 is not None and fcf0 > 0,
        1.0 if (fcf0 or 0) > 0 else (0.3 if fcf0 is not None else 0.5), 10)

    if len(bal) >= 2 and bal[0].get("total_debt") is not None and bal[1].get("total_debt"):
        delever = bal[0]["total_debt"] <= bal[1]["total_debt"]
        add("Deleveraging trend (YoY debt)", "declining" if delever else "rising",
            1.0 if delever else 0.3, 10)
    else:
        add("Deleveraging trend (YoY debt)", None, 0.5, 10)

    score = sum(x["points"] for x in factors)
    return {"score": round(score), "band": _band(score, HEALTH_BANDS), "factors": factors}


def score_cash_flow(f: dict) -> dict:
    inc, cf = f["income"], f["cashflow"]
    factors: list[dict] = []
    if not cf:
        return {"score": None, "band": None, "factors": [],
                "note": "insufficient_data: no cash-flow statement"}
    c0 = cf[0]
    ni0 = inc[0].get("net_income")
    rev0 = inc[0].get("revenue")

    ocf_pat = (c0.get("ocf") / ni0) if (c0.get("ocf") and ni0 and ni0 > 0) else None
    factors.append({"name": "OCF / PAT (cash backing of profit)",
                    "value": round(ocf_pat, 2) if ocf_pat is not None else None,
                    "points": round(_lin([(ocf_pat, 0.5)], 0.5, 1.5, 1) * 20, 1), "max": 20})

    fcf_m = (c0.get("fcf") / rev0) if (c0.get("fcf") is not None and rev0) else None
    factors.append({"name": "FCF margin", "value": f"{fcf_m * 100:.1f}%" if fcf_m is not None else None,
                    "points": round(_lin([(fcf_m, 0.5)], -0.05, 0.20, 1) * 20, 1), "max": 20})

    fcfs = _latest(cf, "fcf", 4)
    fcf_g = _cagr(fcfs[0], fcfs[-1], len(fcfs) - 1) if len(fcfs) >= 2 else None
    factors.append({"name": "FCF CAGR (multi-year)", "value": f"{fcf_g * 100:.1f}%" if fcf_g is not None else None,
                    "points": round(_lin([(fcf_g, 0.5)], -0.1, 0.25, 1) * 20, 1), "max": 20})

    pos_years = sum(1 for v in fcfs if v > 0)
    factors.append({"name": f"Positive FCF years ({pos_years}/{len(fcfs)})",
                    "value": pos_years,
                    "points": round((pos_years / len(fcfs)) * 20 if fcfs else 10, 1), "max": 20})

    capex, ocf = c0.get("capex"), c0.get("ocf")
    capex_ratio = (abs(capex) / ocf) if (capex is not None and ocf and ocf > 0) else None
    factors.append({"name": "Capex intensity (capex/OCF)",
                    "value": f"{capex_ratio * 100:.0f}%" if capex_ratio is not None else None,
                    "points": round(_lin([(capex_ratio, 0.5)], 1.2, 0.3, 1) * 20, 1), "max": 20})

    warnings = []
    if len(inc) >= 2 and len(cf) >= 2:
        pat_up = (inc[0].get("net_income") or 0) > (inc[1].get("net_income") or 0)
        ocf_dn = (cf[0].get("ocf") or 0) < (cf[1].get("ocf") or 0)
        if pat_up and ocf_dn:
            warnings.append("aggressive_accounting: profit rising while operating cash flow fell")
    if c0.get("fcf") is not None and c0["fcf"] < 0:
        warnings.append("negative_fcf: company burned cash in the latest year")

    score = sum(x["points"] for x in factors)
    return {"score": round(score), "band": _band(score, CF_BANDS),
            "factors": factors, "warnings": warnings}


def score_growth(f: dict) -> dict:
    inc = f["income"]
    factors: list[dict] = []

    def cagr_factor(key, label, n, pts):
        vals = _latest(inc, key, n + 1)
        g = _cagr(vals[0], vals[-1], len(vals) - 1) if len(vals) >= 2 else None
        factors.append({"name": label, "value": f"{g * 100:.1f}%" if g is not None else None,
                        "points": round(_lin([(g, 0.5)], -0.05, 0.25, 1) * pts, 1), "max": pts})
        return g, vals

    rg, revs = cagr_factor("revenue", "Revenue CAGR (3Y)", 3, 30)
    pg, _ = cagr_factor("net_income", "PAT CAGR (3Y)", 3, 30)
    eg, _ = cagr_factor("eps", "EPS CAGR (3Y)", 3, 20)

    acceleration = False
    if len(revs) >= 3 and revs[-2] and revs[-2] > 0:
        latest_g = revs[0] / revs[1] - 1
        prior_g = revs[1] / revs[2] - 1
        acceleration = latest_g > prior_g > 0 and (rg is None or latest_g > rg)
        factors.append({"name": "Acceleration: latest growth vs trend",
                        "value": "GROWTH ACCELERATION" if acceleration else "steady/decelerating",
                        "points": 20 if acceleration else 8, "max": 20})
    else:
        factors.append({"name": "Acceleration: latest growth vs trend", "value": None,
                        "points": 10, "max": 20})

    score = sum(x["points"] for x in factors)
    return {"score": round(score), "band": _band(score, HEALTH_BANDS),
            "factors": factors, "accelerating": acceleration,
            "revenue_cagr_3y": rg, "pat_cagr_3y": pg, "eps_cagr_3y": eg}


def score_profitability(f: dict) -> dict:
    inc = f["income"]
    bal = f["balance"]
    i0 = inc[0]
    rev = i0.get("revenue")
    factors: list[dict] = []

    def margin(key, label, hi, pts):
        m = (i0.get(key) / rev) if (i0.get(key) is not None and rev) else None
        factors.append({"name": label, "value": f"{m * 100:.1f}%" if m is not None else None,
                        "points": round(_lin([(m, 0.5)], 0, hi, 1) * pts, 1), "max": pts})
        return m

    margin("gross_profit", "Gross margin", 0.60, 15)
    margin("ebitda", "EBITDA margin", 0.35, 20)
    margin("net_income", "PAT margin", 0.20, 15)

    equity = bal[0].get("equity") if bal else None
    debt = bal[0].get("total_debt") if bal else None
    ni = i0.get("net_income")
    roe = (ni / equity) if (ni is not None and equity) else None
    factors.append({"name": "ROE", "value": f"{roe * 100:.1f}%" if roe is not None else None,
                    "points": round(_lin([(roe, 0.5)], 0, 0.25, 1) * 20, 1), "max": 20})

    cap_employed = (equity or 0) + (debt or 0)
    roce = (i0.get("ebit") / cap_employed) if (i0.get("ebit") and cap_employed) else None
    factors.append({"name": "ROCE", "value": f"{roce * 100:.1f}%" if roce is not None else None,
                    "points": round(_lin([(roce, 0.5)], 0, 0.25, 1) * 15, 1), "max": 15})

    # margin trend (3Y)
    trend = None
    if len(inc) >= 3:
        m_now = (inc[0].get("ebitda") or 0) / inc[0]["revenue"] if inc[0].get("revenue") else None
        m_then = (inc[2].get("ebitda") or 0) / inc[2]["revenue"] if inc[2].get("revenue") else None
        if m_now is not None and m_then:
            trend = "expanding" if m_now > m_then * 1.02 else "compressing" if m_now < m_then * 0.98 else "flat"
    factors.append({"name": "EBITDA margin trend (3Y)", "value": trend,
                    "points": 15 if trend == "expanding" else 7 if trend == "flat" else 2 if trend else 7,
                    "max": 15})

    score = sum(x["points"] for x in factors)
    return {"score": round(score), "band": _band(score, HEALTH_BANDS),
            "factors": factors, "roe": roe, "roce": roce, "margin_trend": trend}


# ------------------------------------------------------------ value traps

def detect_value_trap(f: dict, growth: dict, prof: dict, cf: dict) -> dict:
    """Cheap + deteriorating = trap (§45/§46)."""
    signals = []
    if growth.get("revenue_cagr_3y") is not None and growth["revenue_cagr_3y"] < 0:
        signals.append("Revenue declining over 3Y")
    if growth.get("pat_cagr_3y") is not None and growth["pat_cagr_3y"] < 0:
        signals.append("Profit declining over 3Y")
    if prof.get("margin_trend") == "compressing":
        signals.append("Margins compressing")
    if prof.get("roce") is not None and prof["roce"] < 0.08:
        signals.append(f"ROCE weak ({prof['roce'] * 100:.1f}%)")
    if cf.get("warnings"):
        signals.extend(cf["warnings"])
    bal = f["balance"]
    if len(bal) >= 2 and bal[0].get("total_debt") is not None and bal[1].get("total_debt") \
            and bal[0]["total_debt"] > bal[1]["total_debt"] * 1.15:
        signals.append("Debt rising >15% YoY")

    risk = "HIGH" if len(signals) >= 3 else "MODERATE" if len(signals) >= 2 \
        else "LOW" if signals else "MINIMAL"
    return {"risk": risk, "signals": signals}


# --------------------------------------------------------- fair value (§3)

def _dcf(fcf_per_share: float, g: float, r: float, tg: float = 0.03, years: int = 5) -> float:
    pv = sum(fcf_per_share * (1 + g) ** t / (1 + r) ** t for t in range(1, years + 1))
    tv = fcf_per_share * (1 + g) ** years * (1 + tg) / (r - tg)
    return pv + tv / (1 + r) ** years


def fair_value(f: dict, price: float, growth: dict) -> dict:
    """Multi-model blend with sector-aware weights (ARCHITECTURE.md §F).
    Returns bear/conservative/base/bull, model detail, and confidence."""
    models: dict[str, float] = {}
    notes = []

    eps = f.get("trailing_eps")
    rev_cagr = growth.get("revenue_cagr_3y")
    g_base = min(max(rev_cagr if rev_cagr is not None else 0.08, 0.0), 0.15)
    shares = f.get("shares_outstanding")

    # Earnings multiple: fair PE = min(hist/provided PE sanity, industry-ish cap)
    if eps and eps > 0:
        pe_now = f.get("trailing_pe")
        fair_pe = min(pe_now * 0.9 if pe_now else 20, 40)
        models["earnings_multiple"] = fair_pe * eps * (1 + g_base)

        # PEG: fair PE = growth% clamped
        peg_pe = min(max((rev_cagr or 0.10) * 100, 5), 40)
        models["peg"] = peg_pe * eps

    # DCF + FCF yield on per-share FCF
    cf = f["cashflow"]
    if shares and cf:
        fcfs = _latest(cf, "fcf", 3)
        if fcfs:
            fcf_ps = statistics.mean(fcfs) / shares
            if fcf_ps > 0:
                models["dcf"] = _dcf(fcf_ps, g_base, 0.12)
                models["fcf_yield"] = fcf_ps / 0.08

    # EV/EBITDA
    i0 = f["income"][0]
    b0 = f["balance"][0] if f["balance"] else {}
    ebitda = i0.get("ebitda")
    if ebitda and shares:
        net_debt = (b0.get("total_debt") or 0) - (b0.get("cash") or 0)
        sector_mult = 12.0  # neutral default; provider industry multiples in Phase 2
        models["ev_ebitda"] = (sector_mult * ebitda - net_debt) / shares

    # Banks/financials: justified P/B from ROE
    if f.get("is_financial"):
        bvps = f.get("book_value_per_share")
        ni, eq = i0.get("net_income"), b0.get("equity")
        roe = (ni / eq) if (ni is not None and eq) else None
        if bvps and roe and roe > 0.05:
            coe, gdiv = 0.13, 0.05
            justified_pb = max((roe - gdiv) / (coe - gdiv), 0.2)
            models["pb_roe"] = bvps * justified_pb

    if not models:
        return {"available": False, "note": "insufficient_data: no valuation model had enough inputs",
                "models": {}, "confidence": 0}

    weights = ({"pb_roe": 0.40, "earnings_multiple": 0.30, "peg": 0.15, "dcf": 0.15}
               if f.get("is_financial") else
               {"dcf": 0.30, "earnings_multiple": 0.20, "ev_ebitda": 0.15,
                "fcf_yield": 0.15, "peg": 0.10})
    usable = {k: v for k, v in models.items() if k in weights and v > 0}
    wsum = sum(weights[k] for k in usable)
    base = sum(usable[k] * weights[k] for k in usable) / wsum if wsum else None

    # scenarios: ±5% band plus a DCF re-run with stressed growth/discount
    bear = base * 0.95 if base else None
    bull = base * 1.05 if base else None
    if "dcf" in usable and shares and cf:
        fcfs = _latest(cf, "fcf", 3)
        fcf_ps = statistics.mean(fcfs) / shares
        if fcf_ps > 0 and base:
            w_dcf = weights.get("dcf", 0.3) / wsum
            bear += (_dcf(fcf_ps, g_base * 0.5, 0.13) - usable["dcf"]) * w_dcf
            bull += (_dcf(fcf_ps, min(g_base * 1.25, 0.20), 0.11) - usable["dcf"]) * w_dcf

    vals = list(usable.values())
    dispersion = (statistics.pstdev(vals) / statistics.mean(vals)) if len(vals) > 1 else 0.35
    agreement = "high" if dispersion < 0.25 else "moderate" if dispersion < 0.45 else "low"
    confidence = round(max(10, min(95,
        25 + 10 * len(usable) - 70 * dispersion + 0.35 * f["data_quality"])))
    # Agreement is a hard ceiling: disagreeing models must not look confident.
    confidence = min(confidence, {"high": 90, "moderate": 65, "low": 50}[agreement])

    out = {
        "available": True,
        "currency": f["currency"],
        "current_price": price,
        "bear": round(bear, 2) if bear else None,
        "conservative": round(base * 0.9, 2) if base else None,
        "base": round(base, 2) if base else None,
        "bull": round(bull, 2) if bull else None,
        "upside_pct": round((base / price - 1) * 100, 1) if (base and price) else None,
        "models": {k: round(v, 2) for k, v in usable.items()},
        "model_weights": {k: round(weights[k] / wsum, 2) for k in usable},
        "assumptions": {
            "growth_used": f"{g_base * 100:.1f}% (revenue 3Y CAGR, capped 15%)",
            "discount_rate": "12% base (13% bear / 11% bull)",
            "terminal_growth": "3%",
            "note": "Estimates from reported financials; not analyst consensus.",
        },
        "model_agreement": agreement,
        "confidence": confidence,
    }
    return out


# ------------------------------------------------- risk (spec s.30) + composite

def score_risk(f: dict, health: dict, fv: dict) -> dict:
    factors = []
    b0 = f["balance"][0] if f["balance"] else {}
    debt = b0.get("total_debt") or 0
    equity = b0.get("equity") or 0
    de = debt / equity if equity else None
    lev_risk = 30 if de is not None and de > 2 else 15 if de is not None and de > 1 else 5
    factors.append({"name": "Financial leverage (D/E)",
                    "value": round(de, 2) if de is not None else None, "risk_points": lev_risk})
    val_risk = 25 if (fv.get("available") and (fv.get("upside_pct") or 0) < -10) \
        else 10 if fv.get("available") else 20
    factors.append({"name": "Valuation risk", "value": fv.get("upside_pct"), "risk_points": val_risk})
    earn_var = 0
    nis = _latest(f["income"], "net_income", 4)
    if len(nis) >= 3 and statistics.mean(nis) > 0:
        cv = statistics.pstdev(nis) / statistics.mean(nis)
        earn_var = 20 if cv > 0.5 else 10 if cv > 0.25 else 5
    factors.append({"name": "Earnings variability", "value": None, "risk_points": earn_var})
    dq_risk = max(0, 25 - round(f["data_quality"] * 0.25))
    factors.append({"name": "Data quality shortfall", "value": f["data_quality"], "risk_points": dq_risk})

    total = sum(x["risk_points"] for x in factors)
    band = "Low" if total < 25 else "Moderate" if total < 50 else "High" if total < 75 else "Very High"
    return {"score": min(total, 100), "band": band, "factors": factors}


AI_WEIGHTS = {"fundamentals": 0.25, "valuation": 0.20, "growth": 0.15,
              "cash_flow": 0.10, "technical": 0.10, "catalysts": 0.10,
              "quality": 0.05, "safety": 0.05}

VERDICTS = [(40, "STRONG SELL"), (50, "SELL"), (58, "REDUCE"), (64, "HOLD"),
            (72, "WATCH"), (80, "ACCUMULATE"), (88, "BUY"), (101, "STRONG BUY")]


def research_report(f: dict, price: float, technical: dict | None = None,
                    catalyst_score: float | None = None) -> dict:
    """Full composite research payload for one symbol."""
    health = score_financial_health(f)
    cashf = score_cash_flow(f)
    growth = score_growth(f)
    prof = score_profitability(f)
    fv = fair_value(f, price, growth)
    trap = detect_value_trap(f, growth, prof, cashf)
    risk = score_risk(f, health, fv)

    # valuation score: upside mapped, value-trap penalty applied (spec s.45)
    if fv.get("available") and fv.get("upside_pct") is not None:
        vscore = _lin([(fv["upside_pct"], 0.5)], -20, 50, 1) * 100
        if trap["risk"] == "HIGH":
            vscore *= 0.4
        elif trap["risk"] == "MODERATE":
            vscore *= 0.7
    else:
        vscore = None

    tech_score = technical.get("confidence") if technical else None
    cat_score = catalyst_score

    components = {
        "fundamentals": health["score"], "valuation": round(vscore) if vscore is not None else None,
        "growth": growth["score"], "cash_flow": cashf["score"],
        "technical": tech_score, "catalysts": round(cat_score) if cat_score is not None else None,
        "quality": prof["score"], "safety": 100 - risk["score"],
    }
    usable = {k: v for k, v in components.items() if v is not None}
    wsum = sum(AI_WEIGHTS[k] for k in usable)
    ai_score = round(sum(usable[k] * AI_WEIGHTS[k] for k in usable) / wsum) if wsum else None
    verdict = _band(ai_score + 1 if ai_score is not None else None, VERDICTS)

    # ---- thesis: positives/negatives from actual computed factors (s.14/28)
    pos, neg = [], []
    if growth.get("accelerating"):
        pos.append("Growth acceleration: latest revenue growth is above its 3Y trend")
    if growth.get("revenue_cagr_3y") and growth["revenue_cagr_3y"] > 0.12:
        pos.append(f"Revenue compounding at {growth['revenue_cagr_3y'] * 100:.0f}% (3Y CAGR)")
    if prof.get("roce") and prof["roce"] > 0.15:
        pos.append(f"Strong capital efficiency: ROCE {prof['roce'] * 100:.0f}%")
    if prof.get("margin_trend") == "expanding":
        pos.append("Margins expanding over 3 years")
    if cashf["score"] and cashf["score"] >= 65:
        pos.append(f"Cash flow is {cashf['band']} - profits are cash-backed")
    if fv.get("available") and (fv.get("upside_pct") or 0) > 15:
        pos.append(f"Trades ~{fv['upside_pct']:.0f}% below blended fair value ({fv['model_agreement']} model agreement)")
    if tech_score and tech_score >= 60:
        pos.append(f"Technical structure constructive (score {tech_score}/100)")
    if health["score"] and health["score"] >= 60:
        pos.append(f"Balance sheet {health['band'].lower()} (health {health['score']}/100)")

    if growth.get("revenue_cagr_3y") is not None and growth["revenue_cagr_3y"] < 0.03:
        neg.append("Revenue growth is weak or declining")
    if prof.get("margin_trend") == "compressing":
        neg.append("Margins compressing over 3 years")
    for w in cashf.get("warnings", []):
        neg.append(w.replace("_", " "))
    if trap["signals"]:
        neg.append(f"Value-trap signals ({trap['risk']}): " + "; ".join(trap["signals"][:3]))
    if fv.get("available") and (fv.get("upside_pct") or 0) < -10:
        neg.append(f"Trades ~{abs(fv['upside_pct']):.0f}% ABOVE blended fair value")
    if risk["score"] >= 50:
        neg.append(f"Elevated risk profile ({risk['band']})")
    if not fv.get("available"):
        neg.append("Fair value unavailable - insufficient fundamental data")

    return {
        "symbol": f["symbol"], "name": f["name"], "sector": f.get("sector"),
        "industry": f.get("industry"), "currency": f["currency"],
        "market_cap": f.get("market_cap"),
        "ai_score": ai_score, "ai_band": _band(ai_score, AI_BANDS) if ai_score is not None else None,
        "verdict": verdict,
        "confidence": fv.get("confidence") if fv.get("available") else max(10, f["data_quality"] // 2),
        "scores": {
            "financial_health": health, "cash_flow": cashf, "growth": growth,
            "profitability": prof,
            "valuation": {"score": round(vscore) if vscore is not None else None,
                          "upside_pct": fv.get("upside_pct") if fv.get("available") else None},
            "technical": {"score": tech_score},
            "risk": risk,
        },
        "fair_value": fv,
        "value_trap": trap,
        "thesis": {"why_buy": pos[:7], "why_not": neg[:7]},
        "data_quality": f["data_quality"],
        "data_freshness": f["period_label"],
        "key_assumptions": fv.get("assumptions") if fv.get("available") else None,
        "validation_note": ("Scores computed from reported financials and price math. "
                            "Predictive accuracy is under backtest validation - see Track Record."),
        "engine_version": ENGINE_VERSION,
        "source": f["source"],
    }
