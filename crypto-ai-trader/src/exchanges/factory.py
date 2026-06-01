"""Exchange factory — single source of truth for picking demo vs live.

Live exchange clients (ccxt-based) are imported lazily so that demo mode
never needs ccxt loaded, and a missing optional dependency for one exchange
can't break the others.
"""
import importlib
import logging
from typing import Optional, Tuple

from .base import BaseExchange
from .demo_client import DemoExchange
from ..core.config import settings

logger = logging.getLogger(__name__)

# name -> (relative module, class). Order = fallback preference.
LIVE_EXCHANGES = {
    "binance":    (".binance_client",    "BinanceExchange"),
    "binance_th": (".binance_th_client", "BinanceTHExchange"),
    "bitkub":     (".bitkub_client",     "BitkubExchange"),
    "okx":        (".okx_client",        "OKXExchange"),
}


class LiveExchangeError(Exception):
    """Raised when live mode is requested but cannot be satisfied."""


def _load(name: str) -> BaseExchange:
    mod_path, cls_name = LIVE_EXCHANGES[name]
    mod = importlib.import_module(mod_path, package=__package__)
    return getattr(mod, cls_name)()


def has_credentials(name: str) -> bool:
    """True when the named exchange has the API credentials it needs."""
    cfg = settings.get("exchanges", name) or {}
    if not cfg.get("api_key") or not cfg.get("api_secret"):
        return False
    if name == "okx" and not cfg.get("passphrase"):
        return False
    return True


def resolve_live_exchange() -> Optional[str]:
    """Pick which live exchange to use.

    Preference: the explicitly chosen ``exchanges.active`` (when enabled and
    keyed), otherwise the first enabled+keyed exchange in LIVE_EXCHANGES order.
    Returns None when nothing is configured for live trading.
    """
    active = settings.get("exchanges", "active", default="")
    if active in LIVE_EXCHANGES:
        cfg = settings.get("exchanges", active) or {}
        if cfg.get("enabled") and has_credentials(active):
            return active
    for name in LIVE_EXCHANGES:
        cfg = settings.get("exchanges", name) or {}
        if cfg.get("enabled") and has_credentials(name):
            return name
    return None


def create_exchange(mode: Optional[str] = None) -> Tuple[BaseExchange, str]:
    """Build the exchange for ``mode`` (defaults to settings.trading_mode).

    Lenient: falls back to demo if live is requested but misconfigured, so the
    app always starts. Returns ``(exchange, name)``.
    """
    mode = mode or settings.trading_mode
    if mode != "live":
        return DemoExchange(), "demo"

    name = resolve_live_exchange()
    if not name:
        logger.warning("Live mode requested but no exchange is configured — falling back to demo")
        return DemoExchange(), "demo"
    try:
        ex = _load(name)
        logger.info(f"Live exchange ready: {name}")
        return ex, name
    except Exception as e:
        logger.error(f"Failed to initialize live exchange '{name}': {e} — falling back to demo")
        return DemoExchange(), "demo"


def create_live_exchange_strict() -> Tuple[BaseExchange, str]:
    """Build a live exchange or raise LiveExchangeError.

    Used by the explicit demo→live swap so the user gets a precise reason
    instead of a silent demo fallback.
    """
    name = resolve_live_exchange()
    if not name:
        raise LiveExchangeError(
            "No live exchange configured. Enable an exchange and add API key + secret "
            "in Settings, then switch to Live Mode."
        )
    try:
        return _load(name), name
    except Exception as e:
        raise LiveExchangeError(f"Failed to initialize '{name}': {e}")
