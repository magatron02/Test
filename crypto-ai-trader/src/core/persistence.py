"""
Atomic file persistence helpers.

Crash-safe writes: serialise to a temp file in the same directory, fsync, then
``os.replace()`` onto the target — an atomic rename on POSIX and Windows. A crash
mid-write leaves the previous good file intact instead of a truncated one.

Used for runtime state, RL bandit pickles, and position-sizer stats so a power
loss / kill -9 never corrupts persisted learning.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def _atomic_write(path: Path, write_fn: Callable[[Any], None], mode: str) -> bool:
    """Write via a temp file in the same dir, then atomically replace `path`."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, mode) as fh:
                write_fn(fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)   # atomic
            return True
        finally:
            # Clean up the temp file if replace never happened (exception path)
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    except Exception as exc:
        logger.warning("Atomic write to %s failed: %s", path, exc)
        return False


def atomic_write_json(path: Path, data: Any) -> bool:
    """Atomically serialise `data` to `path` as JSON (default=str for datetimes)."""
    return _atomic_write(path, lambda fh: json.dump(data, fh, indent=2, default=str), "w")


def atomic_write_pickle(path: Path, data: Any) -> bool:
    """Atomically pickle `data` to `path`."""
    return _atomic_write(path, lambda fh: pickle.dump(data, fh), "wb")


def safe_read_json(path: Path) -> Optional[Any]:
    """Read JSON from `path`; return None on missing/corrupt file (never raises)."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception as exc:
        logger.warning("Could not read JSON %s — %s", path, exc)
        return None
