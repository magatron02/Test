from sqlalchemy import Column, String, Float, Integer, DateTime, Enum, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum
import uuid

Base = declarative_base()


class TradeType(str, enum.Enum):
    SPOT = "spot"
    GRID = "grid"
    FUTURES = "futures"
    PERPETUAL = "perpetual"


class TradeSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    LIQUIDATED = "liquidated"


class Exchange(str, enum.Enum):
    BINANCE = "binance"
    OKX = "okx"
    HYPERLIQUID = "hyperliquid"
    PAPER = "paper"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    exchange = Column(Enum(Exchange), nullable=False)
    trade_type = Column(Enum(TradeType), nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(Enum(TradeSide), nullable=False)
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)

    entry_price = Column(Float)
    exit_price = Column(Float)
    quantity = Column(Float, nullable=False)
    leverage = Column(Integer, default=1)

    take_profit = Column(Float)
    stop_loss = Column(Float)

    realized_pnl = Column(Float, default=0)
    unrealized_pnl = Column(Float, default=0)
    fee = Column(Float, default=0)

    ai_reasoning = Column(String)
    ai_confidence = Column(Float)
    market_data_snapshot = Column(JSON)

    exchange_order_id = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    closed_at = Column(DateTime)


class GridConfig(Base):
    __tablename__ = "grid_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    exchange = Column(Enum(Exchange), nullable=False)
    symbol = Column(String, nullable=False)
    upper_price = Column(Float, nullable=False)
    lower_price = Column(Float, nullable=False)
    grid_count = Column(Integer, nullable=False)
    investment_amount = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    total_profit = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())


class Portfolio(Base):
    __tablename__ = "portfolio"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    exchange = Column(Enum(Exchange), nullable=False)
    asset = Column(String, nullable=False)
    balance = Column(Float, default=0)
    available = Column(Float, default=0)
    locked = Column(Float, default=0)
    usd_value = Column(Float, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AgentConfig(Base):
    __tablename__ = "agent_config"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    is_running = Column(Boolean, default=False)
    selected_exchanges = Column(JSON, default=list)
    enabled_strategies = Column(JSON, default=list)
    risk_level = Column(String, default="medium")  # low, medium, high
    max_position_size_pct = Column(Float, default=0.05)
    max_drawdown_pct = Column(Float, default=0.15)
    default_leverage = Column(Integer, default=3)
    watchlist = Column(JSON, default=list)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
