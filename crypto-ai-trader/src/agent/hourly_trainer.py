"""
Hourly real-data training task.

Every hour:
  1. Fetch 200 × 1h candles per symbol from Binance public API (no key needed)
  2. Compute indicators via existing market_analyzer.analyze()
  3. Label each candle with look-ahead: if close[i+LOOKAHEAD] > close[i] * (1+THRESH) → BUY win
  4. Bulk-insert labelled TrainingRecord rows (skip duplicates by candle timestamp)
  5. Call AITrainer.train() to refresh RandomForest model
  6. Broadcast status via WebSocket
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional

import aiohttp

from ..core.config import settings
from ..core.database import SessionLocal, TrainingRecord
from ..exchanges.base import OHLCV

logger = logging.getLogger(__name__)

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
INTERVAL       = "1h"
LIMIT          = 200   # candles per symbol per run
LOOKAHEAD      = 3     # candles ahead for label
THRESHOLD      = 0.004 # 0.4% move → meaningful signal

_SOURCE_TAG = "hourly_real"   # marks records from this trainer


class HourlyTrainer:
    def __init__(self, trainer, broadcast_fn=None):
        self._trainer   = trainer
        self._broadcast = broadcast_fn
        self._task: Optional[asyncio.Task] = None
        self.status = {
            "running":          False,
            "last_run":         None,
            "last_samples":     0,
            "total_samples":    0,
            "model_accuracy":   None,
            "symbols_ok":       [],
            "error":            None,
            "next_run_in":      3600,
        }

    # ── public ───────────────────────────────────────────────────────────
    def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("HourlyTrainer started — first run in ~5 s")

    def stop(self):
        if self._task:
            self._task.cancel()
        self.status["running"] = False

    async def run_now(self) -> dict:
        """Force an immediate training run (callable from API)."""
        return await self._run_once()

    # ── internals ────────────────────────────────────────────────────────
    async def _loop(self):
        await asyncio.sleep(5)          # brief delay on startup
        while True:
            await self._run_once()
            # count down for next run
            interval = settings.get("ai", "hourly_train_interval", default=3600)
            self.status["next_run_in"] = interval
            for remaining in range(interval, 0, -10):
                self.status["next_run_in"] = remaining
                await asyncio.sleep(10)

    async def _run_once(self) -> dict:
        self.status["running"] = True
        self.status["error"]   = None
        symbols = settings.symbols
        added_total = 0
        ok_syms = []

        logger.info(f"HourlyTrainer: fetching {INTERVAL} data for {symbols}")

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                for sym in symbols:
                    try:
                        candles = await self._fetch_klines(session, sym)
                        if len(candles) < LOOKAHEAD + 10:
                            continue
                        added = self._label_and_store(sym, candles)
                        added_total += added
                        ok_syms.append(sym)
                        logger.info(f"  {sym}: {len(candles)} candles → {added} new records")
                    except Exception as e:
                        logger.warning(f"  {sym}: fetch failed — {e}")

            # retrain if we got new samples
            accuracy = None
            if added_total > 0:
                ok = self._trainer.train()
                accuracy = self._trainer.stats.get("accuracy")
                logger.info(
                    f"HourlyTrainer: retrained — added={added_total} acc={accuracy}"
                )
            else:
                logger.info("HourlyTrainer: no new samples, skipping retrain")
                accuracy = self._trainer.stats.get("accuracy")

            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.status.update({
                "running":        False,
                "last_run":       now,
                "last_samples":   added_total,
                "total_samples":  self._count_real_records(),
                "model_accuracy": accuracy,
                "symbols_ok":     ok_syms,
            })

            await self._emit("hourly_train_done", {
                "last_run":       now,
                "last_samples":   added_total,
                "total_samples":  self.status["total_samples"],
                "model_accuracy": accuracy,
                "symbols":        ok_syms,
            })
            return dict(self.status)

        except Exception as e:
            logger.error(f"HourlyTrainer error: {e}")
            self.status["running"] = False
            self.status["error"]   = str(e)
            return dict(self.status)

    async def _fetch_klines(self, session: aiohttp.ClientSession, symbol: str) -> List[OHLCV]:
        binance_sym = symbol.replace("/", "")
        params = {"symbol": binance_sym, "interval": INTERVAL, "limit": LIMIT}
        async with session.get(BINANCE_KLINES, params=params) as resp:
            resp.raise_for_status()
            raw = await resp.json()

        candles = []
        for row in raw:
            ts = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).replace(tzinfo=None)
            candles.append(OHLCV(
                timestamp=ts,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            ))
        return candles

    def _label_and_store(self, symbol: str, candles: List[OHLCV]) -> int:
        from .market_analyzer import analyze

        added = 0
        db = SessionLocal()
        try:
            # build set of existing candle hashes to skip duplicates
            existing = {
                r.features.get("_ts_hash")
                for r in db.query(TrainingRecord.features)
                          .filter(TrainingRecord.symbol == symbol,
                                  TrainingRecord.action == _SOURCE_TAG)
                          .all()
                if r.features and r.features.get("_ts_hash")
            }

            labelable = candles[:-LOOKAHEAD]   # exclude last N (no future yet)
            for i, candle in enumerate(labelable):
                ts_hash = hashlib.md5(
                    f"{symbol}_{candle.timestamp.isoformat()}".encode()
                ).hexdigest()
                if ts_hash in existing:
                    continue

                # use all candles up to i+1 for indicator calculation
                window = candles[: i + 1]
                if len(window) < 30:
                    continue

                price    = candle.close
                change   = (candle.close - candles[0].close) / candles[0].close * 100
                analysis = analyze(symbol, window, price, change)

                # look-ahead label
                future_close = candles[i + LOOKAHEAD].close
                pct_change   = (future_close - price) / price

                if pct_change > THRESHOLD:
                    label, outcome = 1,  pct_change * 100
                elif pct_change < -THRESHOLD:
                    label, outcome = 0, pct_change * 100
                else:
                    continue   # inside dead-zone — skip ambiguous candle

                features = dict(analysis.features)
                features["_ts_hash"] = ts_hash   # dedup key

                record = TrainingRecord(
                    symbol=symbol,
                    features=features,
                    action=_SOURCE_TAG,   # marks real-data source
                    outcome=outcome,
                    label=label,
                    trade_id=None,
                )
                db.add(record)
                existing.add(ts_hash)
                added += 1

            db.commit()
        finally:
            db.close()
        return added

    def _count_real_records(self) -> int:
        db = SessionLocal()
        try:
            return db.query(TrainingRecord).filter(
                TrainingRecord.label.isnot(None)
            ).count()
        finally:
            db.close()

    async def _emit(self, event: str, data: dict):
        if self._broadcast:
            try:
                await self._broadcast(event, data)
            except Exception:
                pass
