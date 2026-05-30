from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "CryptoAI Trader"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Claude AI
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    # Binance
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET_KEY: str = ""
    BINANCE_TESTNET: bool = True

    # OKX
    OKX_API_KEY: str = ""
    OKX_SECRET_KEY: str = ""
    OKX_PASSPHRASE: str = ""
    OKX_TESTNET: bool = True

    # Hyperliquid
    HYPERLIQUID_PRIVATE_KEY: str = ""
    HYPERLIQUID_TESTNET: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./trading.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # Trading defaults
    MAX_POSITION_SIZE_PCT: float = 0.05  # 5% of portfolio per trade
    MAX_DRAWDOWN_PCT: float = 0.15       # 15% max drawdown
    DEFAULT_LEVERAGE: int = 3
    MAX_LEVERAGE: int = 10

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
