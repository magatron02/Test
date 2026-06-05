"""Async retry with exponential backoff for transient exchange/network errors."""
import asyncio
import functools
import logging
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)

# ccxt raises these on transient issues; import lazily so the module never hard-fails
def _transient_errors() -> Tuple[Type[Exception], ...]:
    errs = [asyncio.TimeoutError, ConnectionError, OSError]
    try:
        import ccxt
        errs += [ccxt.NetworkError, ccxt.RequestTimeout, ccxt.ExchangeNotAvailable,
                 ccxt.DDoSProtection, ccxt.RateLimitExceeded]
    except Exception:
        pass
    return tuple(errs)


def with_retry(max_attempts: int = 4, base_delay: float = 1.0, max_delay: float = 16.0):
    """Decorator: retry an async function on transient errors with exponential backoff.

    Delays: base_delay * 2**(attempt-1), capped at max_delay (1s, 2s, 4s, 8s, ...).
    Non-transient exceptions (e.g. ccxt.InsufficientFunds, ccxt.InvalidOrder,
    ccxt.AuthenticationError) are re-raised immediately — never retried, since
    retrying a bad order is dangerous.
    """
    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            transient = _transient_errors()
            # Non-retryable: auth, insufficient funds, invalid order
            non_retryable = tuple()
            try:
                import ccxt
                non_retryable = (ccxt.AuthenticationError, ccxt.InsufficientFunds,
                                 ccxt.InvalidOrder, ccxt.PermissionDenied)
            except Exception:
                pass
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except non_retryable:
                    raise  # never retry these — fail fast
                except transient as e:
                    last_exc = e
                    if attempt >= max_attempts:
                        break
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning("%s failed (attempt %d/%d): %s — retrying in %.1fs",
                                   fn.__name__, attempt, max_attempts, e, delay)
                    await asyncio.sleep(delay)
            logger.error("%s exhausted %d attempts: %s", fn.__name__, max_attempts, last_exc)
            raise last_exc
        return wrapper
    return decorator
