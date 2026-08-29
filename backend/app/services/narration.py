"""Narration layer.

The LLM receives ONLY the computed facts JSON and must return four short
labeled blocks (the reel-presenter structure): pattern, why, confirmation,
invalidation. A deterministic verifier then checks every number in the
narration against the fact set — any sentence containing a number we did
not compute is removed. If Ollama is offline, a template narration built
purely from the facts is returned instead, so Analyze always works.
"""
from __future__ import annotations

import json
import re

from .llm.base import LLMUnavailable, get_llm

_SECTIONS = ("pattern", "why", "confirmation", "invalidation")

_SYSTEM = (
    "You are a chart analyst narrating a swing-trade setup, like a presenter "
    "walking through an annotated chart. You are given a JSON of computed "
    "facts. Respond with ONLY a JSON object with keys 'pattern', 'why', "
    "'confirmation', 'invalidation' — each value 1-2 short sentences, plain "
    "language, confident but honest. HARD RULES: use ONLY numbers that appear "
    "in the facts JSON, never invent or derive new numbers, never give "
    "financial advice, refer to levels by their computed values. If the setup "
    "state is 'no_clean_setup' or 'downtrend', say plainly that there is no "
    "clean long setup right now and what would need to change."
)


def _allowed_numbers(payload: dict) -> set[str]:
    """Every numeric token that legitimately exists in the computed facts,
    in a few common formats (2dp, 1dp, int, thousands-separated)."""
    allowed: set[str] = set()

    def add(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            for s in (f"{x:.2f}", f"{x:.1f}", f"{x:.0f}", str(x),
                      f"{x:,.2f}", f"{x:,.0f}"):
                allowed.add(s.rstrip("0").rstrip(".") if "." in s else s)
                allowed.add(s)
        elif isinstance(x, dict):
            for v in x.values():
                add(v)
        elif isinstance(x, list):
            for v in x:
                add(v)

    add(payload)
    # Common analytics vocabulary that is not "data"
    allowed.update({"1", "2", "14", "20", "50", "200", "100"})
    return allowed


_NUM_RE = re.compile(r"\d[\d,]*\.?\d*")


def _verify(text: str, allowed: set[str]) -> tuple[str, int]:
    """Remove sentences containing numbers not in the allowed set."""
    removed = 0
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        nums = _NUM_RE.findall(sentence)
        ok = all(
            n in allowed or n.replace(",", "") in allowed
            or (n.replace(",", "").rstrip("0").rstrip(".") if "." in n else n) in allowed
            for n in nums
        )
        if ok:
            kept.append(sentence)
        else:
            removed += 1
    return " ".join(kept), removed


def _fallback(payload: dict) -> dict:
    """Deterministic narration from facts — used when the LLM is offline.
    Every number here is read straight from the payload."""
    s = payload["setup"]
    ind = payload["indicators"]
    state = s["state"].replace("_", " ")
    plan = s["plan"]
    if not plan and s["state"] == "strong_uptrend_extended":
        w = s.get("watch") or {}
        sup = w.get("nearest_support")
        swing_low = w.get("recent_swing_low")
        sup_txt = (f"the {sup['price_low']}\u2013{sup['price_high']} support zone" if sup
                   else (f"the recent swing low near {swing_low}" if swing_low else "the nearest support"))
        sma = w.get("sma20")
        return {
            "pattern": f"Strong established uptrend, but price is extended \u2014 last at {ind['last_close']}, stretched above its base.",
            "why": "Chasing an extended move buys at the point of maximum risk; the trend is healthy, the entry is not.",
            "confirmation": f"A controlled pullback that holds {sup_txt}" + (f" or the 20 SMA around {sma}" if sma else "") + " builds the next clean entry.",
            "invalidation": "A high-volume break below the nearest support zone would end the extension thesis entirely.",
        }
    if not plan:
        return {
            "pattern": f"Current state: {state}. No clean long setup on this chart right now.",
            "why": "The structure does not offer a level with an acceptable risk-reward at the moment.",
            "confirmation": "A decisive close above a multi-touch resistance zone with above-average volume would change the picture.",
            "invalidation": "Until then, patience is the position.",
        }
    return {
        "pattern": f"Detected state: {state}, bias {s['bias']}, with price last at {ind['last_close']}.",
        "why": f"The plan keys off the marked zone: entry {plan['entry_low']}–{plan['entry_high']}, protective stop {plan['stop_loss']}.",
        "confirmation": f"Volume ratio {ind['volume_ratio']}x vs the 20-bar average; targets sit at {plan['target1']} and {plan['target2']} ({plan['risk_reward']}:1 to the first).",
        "invalidation": f"A close back below {plan['stop_loss']} invalidates the setup.",
    }


def narrate(payload: dict) -> tuple[dict, dict]:
    """Returns (narration_dict, verification_report)."""
    allowed = _allowed_numbers(payload)
    try:
        llm = get_llm()
        raw = llm.chat([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(
                {"setup": payload["setup"], "indicators": payload["indicators"],
                 "zones": payload["zones"]}, ensure_ascii=False)},
        ])
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        narration, removed_total = {}, 0
        for key in _SECTIONS:
            text = str(parsed.get(key, "")).strip()
            clean, removed = _verify(text, allowed)
            narration[key] = clean or "—"
            removed_total += removed
        status = "verified" if removed_total == 0 else "edited"
        return narration, {"status": status, "unsupported_sentences_removed": removed_total,
                           "provider": llm.provider_name}
    except (LLMUnavailable, json.JSONDecodeError, ValueError) as exc:
        return _fallback(payload), {
            "status": "template_fallback",
            "detail": f"Local AI unavailable or returned invalid JSON ({type(exc).__name__}); "
                      "narration generated deterministically from computed facts.",
        }
