from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import (
    Column, DateTime, Float, Integer, JSON, String, Text, create_engine
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

DB_PATH = settings.data_dir / "trades.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True)
    side = Column(String(10))        # BUY | SELL
    price = Column(Float)
    amount = Column(Float)
    cost = Column(Float)             # price * amount
    mode = Column(String(10))        # demo | live
    exchange = Column(String(20))
    strategy = Column(String(30))
    ai_model = Column(String(30))
    confidence = Column(Float)
    reasoning = Column(Text)
    journal = Column(Text, nullable=True)  # user-written note/review for this trade
    status = Column(String(20), default="open")  # open | closed | cancelled
    close_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    indicators = Column(JSON, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


class Portfolio(Base):
    __tablename__ = "portfolio_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    mode = Column(String(10))
    exchange = Column(String(20))
    total_value_usdt = Column(Float)
    cash_usdt = Column(Float)
    positions = Column(JSON)         # {symbol: {amount, avg_price, value}}
    pnl_today = Column(Float, default=0.0)
    pnl_total = Column(Float, default=0.0)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)


class TrainingRecord(Base):
    __tablename__ = "training_records"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20))
    features = Column(JSON)          # indicator values at decision time
    action = Column(String(10))      # BUY | SELL | HOLD
    outcome = Column(Float)          # pnl_pct (filled after trade closes)
    label = Column(Integer, nullable=True)  # 1=profitable, 0=loss (filled later)
    trade_id = Column(Integer, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class PriceAlert(Base):
    __tablename__ = "price_alerts"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True)
    condition = Column(String(10))            # "above" | "below"
    target_price = Column(Float)
    note = Column(String(200), nullable=True)
    active = Column(Boolean, default=True)
    repeat = Column(Boolean, default=False)   # False = one-shot (auto-disable after firing)
    triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PriceCache(Base):
    __tablename__ = "price_cache"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True)
    price = Column(Float)
    change_24h = Column(Float)
    volume_24h = Column(Float)
    high_24h = Column(Float)
    low_24h = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(Integer, primary_key=True, index=True)
    version = Column(Integer, index=True)
    cv_accuracy = Column(Float)           # cross-val accuracy (train set)
    val_accuracy = Column(Float)          # held-out validation accuracy
    training_samples = Column(Integer)
    val_samples = Column(Integer)
    win_rate = Column(Float, nullable=True)
    feature_importances = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    kept = Column(Boolean, default=True)  # False = rejected (worse than prev best)
    notes = Column(String(300), nullable=True)
    saved_at = Column(DateTime, default=datetime.utcnow, index=True)


def _ensure_columns():
    """Add columns introduced by newer versions to existing tables.

    SQLAlchemy's create_all() creates missing tables but never ALTERs existing
    ones, so an upgraded install keeps its old schema. We add any missing
    column in-place — this is additive only and never drops or rewrites data,
    so the user's trade history stays intact.
    """
    from sqlalchemy import inspect, text
    expected = {
        "trades": {"journal": "TEXT"},
    }
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in expected.items():
            if table not in existing_tables:
                continue  # create_all() will build it fresh with all columns
            have = {c["name"] for c in insp.get_columns(table)}
            for col, sql_type in cols.items():
                if col not in have:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {sql_type}'))


def init_db():
    Base.metadata.create_all(engine)
    _ensure_columns()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
