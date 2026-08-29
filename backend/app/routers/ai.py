import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import ChatMessage, Conversation, User
from ..services.llm.base import LLMUnavailable, get_llm
from ..services.market_data import search_symbols

router = APIRouter(prefix="/api/ai", tags=["ai"])

# ---------------------------------------------------------------- intents

_ANALYZE_RE = re.compile(r"\b(analy[sz]e|analysis|analyse|setup|levels|breakout|targets?)\b", re.I)
_THIS_RE = re.compile(r"\b(this|current)\s+(stock|chart|share|scrip|symbol|one)\b", re.I)
_SCAN_RE = re.compile(
    r"\b(scan|screen(er)?|which stocks?|what stocks?|suggest .*stocks?|best stocks?|"
    r"top (stocks?|picks?|setups?)|stocks? .*(bullish|to buy|to watch|for swing)|"
    r"bullish .*stocks?)\b", re.I)
_STOPWORDS = {
    "analyze", "analyse", "analysis", "please", "give", "show", "find", "check",
    "stock", "share", "chart", "swing", "trade", "trading", "setup", "levels",
    "target", "targets", "breakout", "for", "the", "of", "me", "my", "a", "an",
    "next", "this", "that", "week", "weeks", "month", "months", "term", "short",
    "long", "on", "in", "and", "do", "can", "you", "u", "its", "it", "current",
}


def detect_analyze_intent(message: str) -> str | None:
    if not _ANALYZE_RE.search(message):
        return None
    words = re.findall(r"[A-Za-z][A-Za-z0-9.&-]*", message)
    tokens = [w for w in words if w.lower() not in _STOPWORDS]
    if not tokens:
        return None
    query = " ".join(tokens[:3])
    try:
        results = search_symbols(query)["results"]
    except Exception:
        return None
    if not results:
        return None
    for r in results:
        if r["symbol"] and r["symbol"].upper() == query.upper():
            return r["symbol"]
    for r in results:
        if r["symbol"] and r["symbol"].endswith((".NS", ".BO")):
            return r["symbol"]
    return results[0]["symbol"]


def detect_scan_segment(message: str) -> str | None:
    if not _SCAN_RE.search(message):
        return None
    m = message.lower()
    if "small" in m:
        return "india_small"
    if "mid" in m:
        return "india_mid"
    if re.search(r"\bus\b|american|nasdaq|s&p", m):
        return "us"
    return "india_large"


SYSTEM_PROMPT = (
    "You are SwingLens AI - a sharp, friendly markets mentor living inside a "
    "stock research platform. Match the user's language and energy; be warm, "
    "clear, and genuinely engaging. Formatting: short paragraphs, **bold** the "
    "key idea, use a compact bulleted list only when comparing or listing "
    "things, and reach for a vivid analogy when it truly helps a beginner. "
    "Length: as short as the question allows; never pad.\n\n"
    "GROUNDING (hard rules): a CONTEXT block may accompany the question with "
    "the chart symbol, the latest computed analysis, real fetched news "
    "headlines, and possibly last_scan (a ranked market scan our engine "
    "computed). You may cite ONLY numbers and stock names that literally "
    "appear in CONTEXT. NEVER name or recommend a stock that is not in "
    "CONTEXT - if asked to pick stocks and no scan is present, tell the user "
    "to run the scanner (they can just ask 'scan the market'). Never invent "
    "news - reference only provided titles, noting confirmed vs unverified.\n\n"
    "You explain concepts and strategies (buy-the-dip, breakout trading, "
    "position sizing, rotation...) masterfully at any level, in general terms "
    "or applied to the CONTEXT facts. You never give personal financial "
    "advice - you teach, interpret computed facts, and let the person decide. "
    "Everything is research and education."
)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context: dict | None = None
    conversation_id: int | None = None


# ------------------------------------------------------------- persistence

def _get_conversation(db: Session, user: User, conv_id: int | None, first_msg: str) -> Conversation:
    if conv_id:
        conv = db.get(Conversation, conv_id)
        if conv and conv.user_id == user.id:
            return conv
    title = (first_msg.strip().replace("\n", " ")[:60]) or "New chat"
    conv = Conversation(user_id=user.id, title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _save(db: Session, conv: Conversation, role: str, content: str):
    db.add(ChatMessage(conversation_id=conv.id, role=role, content=content[:12000]))
    db.commit()


def _history_for_llm(db: Session, conv: Conversation, limit: int = 12) -> list[dict]:
    rows = (db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conv.id, ChatMessage.role.in_(("user", "ai")))
            .order_by(ChatMessage.created_at.desc()).limit(limit).all())
    return [{"role": "assistant" if r.role == "ai" else "user", "content": r.content}
            for r in reversed(rows)]


# ------------------------------------------------------------------ routes

@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ctx = body.context or {}
    conv = _get_conversation(db, user, body.conversation_id, body.message)
    _save(db, conv, "user", body.message)

    def reply_with(payload: dict) -> dict:
        _save(db, conv, "ai", payload["reply"])
        return payload | {"conversation_id": conv.id}

    # Market scan request -> the engine picks stocks, never the LLM.
    segment = detect_scan_segment(body.message)
    if segment:
        return reply_with({
            "reply": "On it - scanning the whole universe with the real engine (pivots, "
                     "zones, breakout states, volume, confidence). Results card incoming; "
                     "ask me anything about them once it lands.",
            "provider": "intent-router",
            "action": {"type": "scan", "segment": segment},
        })

    if _ANALYZE_RE.search(body.message) and _THIS_RE.search(body.message) and ctx.get("symbol"):
        sym = ctx["symbol"]
        return reply_with({
            "reply": f"Running the full analysis for {sym} - marking the levels and building the setup card now.",
            "provider": "intent-router",
            "action": {"type": "analyze", "symbol": sym},
        })

    symbol = detect_analyze_intent(body.message)
    if symbol:
        return reply_with({
            "reply": f"Running the full analysis for {symbol} - loading the chart, "
                     f"marking the levels, and building the setup card now.",
            "provider": "intent-router",
            "action": {"type": "analyze", "symbol": symbol},
        })

    llm = get_llm()
    user_content = body.message
    if ctx:
        trimmed = json.dumps(ctx, ensure_ascii=False)[:5000]
        user_content = f"CONTEXT (cite only numbers and names present here):\n{trimmed}\n\nUSER: {body.message}"
    messages = ([{"role": "system", "content": SYSTEM_PROMPT}]
                + _history_for_llm(db, conv)[:-1]
                + [{"role": "user", "content": user_content}])
    try:
        reply = llm.chat(messages)
    except LLMUnavailable as exc:
        raise HTTPException(503, {"message": exc.message, "hint": exc.hint})
    return reply_with({"reply": reply, "provider": llm.provider_name, "action": None})


@router.get("/conversations")
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(Conversation).filter(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc()).limit(50).all())
    return [{"id": r.id, "title": r.title, "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/conversations/{conv_id}/messages")
def conversation_messages(conv_id: int, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found.")
    rows = (db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id)
            .order_by(ChatMessage.created_at.asc()).limit(200).all())
    return [{"role": r.role, "content": r.content, "created_at": r.created_at.isoformat()} for r in rows]


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found.")
    db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id).delete()
    db.delete(conv)
    db.commit()
    return {"deleted": conv_id}


@router.get("/status")
def status(user: User = Depends(get_current_user)):
    try:
        return get_llm().status()
    except LLMUnavailable as exc:
        return {"online": False, "detail": exc.message}
