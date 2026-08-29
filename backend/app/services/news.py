"""Newsroom service.

Real headlines only: fetched from RSS feeds, never written or rewritten by
an LLM. A story is CONFIRMED when materially-similar headlines appear from
2+ distinct sources (or it comes from an official feed), else UNVERIFIED.
Per-feed failures degrade gracefully and are reported in the payload.
"""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone

import feedparser

from .market_data import _source_block

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL_SECONDS = 300

MARKET_FEEDS = [
    ("Google News · India Markets",
     "https://news.google.com/rss/search?q=indian+stock+market&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Google News · Global Markets",
     "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en"),
    ("Economic Times Markets",
     "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Moneycontrol Markets",
     "https://www.moneycontrol.com/rss/marketsnews.xml"),
    ("LiveMint Markets",
     "https://www.livemint.com/rss/markets"),
]

_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "as", "at",
         "by", "with", "is", "are", "its", "it", "s", "amid", "after", "over"}


def _norm_tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if w not in _STOP and len(w) > 1}


def _similar(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    return inter / len(a | b) >= 0.55 or inter >= min(len(a), len(b)) * 0.8


def _entry_source(entry, feed_name: str) -> str:
    src = getattr(entry, "source", None)
    if src is not None and getattr(src, "title", None):
        return src.title
    # Google News titles end with " - Publisher"
    title = entry.get("title", "")
    if " - " in title:
        candidate = title.rsplit(" - ", 1)[1].strip()
        if 2 < len(candidate) < 60:
            return candidate
    return feed_name


def _entry_time(entry) -> str | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = entry.get(attr)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).isoformat(timespec="seconds")
    return None


def _fetch_feeds(feeds: list[tuple[str, str]]) -> tuple[list[dict], list[str], list[str]]:
    items, ok, failed = [], [], []
    for feed_name, url in feeds:
        try:
            parsed = feedparser.parse(url)
            entries = parsed.get("entries") or []
            if not entries:
                failed.append(feed_name)
                continue
            ok.append(feed_name)
            for e in entries[:25]:
                title = (e.get("title") or "").strip()
                link = e.get("link") or ""
                if not title or not link:
                    continue
                clean_title = title.rsplit(" - ", 1)[0].strip() if " - " in title else title
                items.append({
                    "id": hashlib.sha1(link.encode()).hexdigest()[:12],
                    "title": clean_title,
                    "url": link,
                    "source_name": _entry_source(e, feed_name),
                    "feed": feed_name,
                    "published_at": _entry_time(e),
                })
        except Exception:
            failed.append(feed_name)
    return items, ok, failed


def _corroborate(items: list[dict]) -> list[dict]:
    """Group near-identical headlines; CONFIRMED = 2+ distinct sources."""
    groups: list[dict] = []
    for it in items:
        toks = _norm_tokens(it["title"])
        placed = False
        for g in groups:
            if _similar(toks, g["tokens"]):
                g["members"].append(it)
                g["tokens"] |= toks
                placed = True
                break
        if not placed:
            groups.append({"tokens": toks, "members": [it]})

    out = []
    for g in groups:
        sources = sorted({m["source_name"] for m in g["members"]})
        lead = max(g["members"], key=lambda m: m["published_at"] or "")
        out.append({
            **lead,
            "confirmed": len(sources) >= 2,
            "corroborated_by": sources,
        })
    out.sort(key=lambda x: x["published_at"] or "", reverse=True)
    return out


def _cached(key: str, builder):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL_SECONDS:
        return hit[1]
    data = builder()
    _CACHE[key] = (now, data)
    return data


def _company_name(symbol: str) -> str:
    from . import markets  # lazy: avoids circular import
    for seg in markets.SEGMENTS.values():
        if symbol in seg["symbols"]:
            return seg["symbols"][symbol]
    return re.sub(r"\.(NS|BO)$", "", symbol.upper()).replace("-", " ")


def get_market_news() -> dict:
    def build():
        items, ok, failed = _fetch_feeds(MARKET_FEEDS)
        stories = _corroborate(items)[:40]
        return {
            "items": stories,
            "feeds_ok": ok,
            "feeds_failed": failed,
            "confirmed_count": sum(1 for s in stories if s["confirmed"]),
            "source": _source_block("") | {
                "provider": f"{len(ok)} RSS feeds (headlines are real articles, never AI-written)",
                "note": (f"Feeds unreachable: {', '.join(failed)}" if failed else None),
            },
        }
    return _cached("market", build)


def get_symbol_news(symbol: str) -> dict:
    symbol = symbol.upper().strip()

    def build():
        name = _company_name(symbol)
        q = name.replace("&", "and").replace(" ", "+")
        feeds = [
            (f"Google News · {name}",
             f"https://news.google.com/rss/search?q=%22{q}%22+stock&hl=en-IN&gl=IN&ceid=IN:en"),
        ]
        items, ok, failed = _fetch_feeds(feeds)
        stories = _corroborate(items)[:20]
        return {
            "symbol": symbol,
            "query_name": name,
            "items": stories,
            "feeds_ok": ok,
            "feeds_failed": failed,
            "source": _source_block(symbol) | {
                "provider": "Google News RSS (original publishers linked)",
            },
        }
    return _cached(f"sym:{symbol}", build)
