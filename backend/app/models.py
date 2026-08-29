from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TradePlan(Base):
    """Every generated setup is stored so the platform can grade itself
    later (Phase 2 roadmap: the public accuracy scorecard)."""
    __tablename__ = "trade_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    symbol = Column(String(24), index=True, nullable=False)
    interval = Column(String(8), nullable=False)
    setup_state = Column(String(48), nullable=False)
    entry_low = Column(Float)
    entry_high = Column(Float)
    stop_loss = Column(Float)
    target1 = Column(Float)
    target2 = Column(Float)
    risk_reward = Column(Float)
    confidence = Column(Integer)
    status = Column(String(16), default="open")  # open | hit_t1 | hit_t2 | stopped | expired
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(80), default="New chat")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True, nullable=False)
    role = Column(String(12), nullable=False)  # user | ai | scan
    content = Column(String(12000), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    broker = Column(String(24), default="unknown")
    symbol_raw = Column(String(64), nullable=False)
    symbol = Column(String(24))          # resolved Yahoo symbol, may be null
    name = Column(String(120))
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    ltp_imported = Column(Float)         # LTP from the file, if present
    imported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    broker = Column(String(24), default="unknown")
    symbol_raw = Column(String(64), nullable=False)
    symbol = Column(String(24))
    name = Column(String(120))
    side = Column(String(4), nullable=False)   # BUY | SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    trade_date = Column(DateTime)
    imported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class WatchItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    symbol = Column(String(24), nullable=False)
    name = Column(String(120))
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    symbol = Column(String(24), nullable=False)
    price = Column(Float, nullable=False)
    direction = Column(String(6), nullable=False)  # above | below
    status = Column(String(12), default="active")  # active | triggered
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    triggered_at = Column(DateTime)
    triggered_price = Column(Float)


class Thesis(Base):
    """A saved investment thesis = a snapshot of the computed research report.
    The Thesis Monitor recomputes the report later and diffs it against this
    snapshot - health drops only when the NUMBERS that justified the thesis
    actually weaken. Pure math, fully explainable."""
    __tablename__ = "theses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    symbol = Column(String(24), index=True, nullable=False)
    name = Column(String(120))
    note = Column(String(2000))                 # the user's own words
    snapshot = Column(String(12000), nullable=False)  # JSON research snapshot
    last_health = Column(Float)
    last_changes = Column(String(6000))         # JSON list of diff lines
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_checked_at = Column(DateTime)
