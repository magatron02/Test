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
from .param_optimizer import ParamOptimizer

logger = logging.getLogger(__name__)

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
INTERVAL       = "1h"
LIMIT          = 500   # candles per symbol per run (~20 days backfill)
LOOKAHEAD      = 3     # candles ahead for label
THRESHOLD      = 0.004 # 0.4% move → meaningful signal

_SOURCE_TAG = "hourly_real"   # marks records from this trainer


class HourlyTrainer:
    # Minimum bars needed before a walk-forward optimization run is worthwhile
    _MIN_OPT_BARS = 60
    # Rolling optimization buffer cap per symbol (~33 days of 1h candles)
    _OPT_BUFFER_CAP = 800
    # Hourly grid is intentionally lean: only the dimensions our cheap bar
    # builder can exercise (RSI bands, ATR SL, confidence gate).
    _HOURLY_GRID = {
        "rsi_oversold":   [25, 30, 35],
        "rsi_overbought": [65, 70, 75],
        "atr_sl_mult":    [1.5, 2.0, 2.5],
        "min_confidence": [0.50, 0.55, 0.60, 0.65, 0.70],
    }

    def __init__(self, trainer, broadcast_fn=None, *, trader=None):
        self._trainer   = trainer
        self._trader    = trader   # optional AITrader ref — used to refresh opt params
        self._broadcast = broadcast_fn
        self._task: Optional[asyncio.Task] = None
        self._param_opt = ParamOptimizer(
            grid=self._HOURLY_GRID, n_splits=3, models_dir=settings.models_dir
        )
        # Rolling per-symbol bar buffer for walk-forward optimization. Only newly
        # analyzed candles are appended each run (reusing existing analyze() work),
        # so the buffer fills on the cold-start batch and keeps growing thereafter.
        self._opt_bars: dict = {}
        self.status = {
            "running":          False,
            "last_run":         None,
            "last_samples":     0,
            "total_samples":    0,
            "model_accuracy":   None,
            "symbols_ok":       [],
            "error":            None,
            "next_run_in":      3600,
            "param_opt":        self._param_opt.summary(),
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
                        sym_bars: list = []
                        added = self._label_and_store(sym, candles, bars_out=sym_bars)
                        if sym_bars:
                            buf = self._opt_bars.setdefault(sym, [])
                            buf.extend(sym_bars)
                            if len(buf) > self._OPT_BUFFER_CAP:
                                del buf[: len(buf) - self._OPT_BUFFER_CAP]
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
                "param_opt":      self._param_opt.summary(),
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

    def _maybe_optimize_params(self):
        """Run walk-forward param optimization on the rolling bar buffer (F5.1).

        Optimization is gated behind ``ai.param_optimize`` (default on) and only
        fires once a symbol's rolling buffer holds ``_MIN_OPT_BARS`` analyzed
        candles, so it kicks in after the cold-start batch and re-runs as the
        buffer keeps growing each hour.
        """
        if not settings.get("ai", "param_optimize", default=True):
            return
        if not self._opt_bars:
            return
        sym, bars = max(self._opt_bars.items(), key=lambda kv: len(kv[1]))
        if len(bars) < self._MIN_OPT_BARS:
            logger.debug(
                "HourlyTrainer: skipping param-opt (%s has only %d bars)", sym, len(bars)
            )
            return
        try:
            result = self._param_opt.run(bars)
            logger.info(
                "HourlyTrainer: param-opt on %s (%d bars) → sharpe=%.3f params=%s",
                sym, len(bars), result.get("best_sharpe", 0.0), result.get("best_params"),
            )
            # Propagate newly-saved params to the live trader immediately (F5.1)
            if self._trader is not None and hasattr(self._trader, "_apply_opt_params"):
                try:
                    self._trader._apply_opt_params()
                except Exception as ex:
                    logger.warning("HourlyTrainer: failed to refresh trader opt params — %s", ex)
        except Exception as e:
            logger.warning("HourlyTrainer: param-opt failed — %s", e)

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

    def _label_and_store(
        self, symbol: str, candles: List[OHLCV], bars_out: Optional[list] = None
    ) -> int:
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

                # Collect a bar for walk-forward param optimization (F5.1).
                # Reuses the analysis we already computed — no extra cost.
                if bars_out is not None:
                    feats = analysis.features or {}
                    bars_out.append({
                        "close":             float(price),
                        "rsi":               float(feats.get("rsi", 50.0)),
                        "atr_pct":           float(feats.get("atr_pct", 1.0)) / 100.0,
                        "signal_confidence": float(self._trainer.score(feats)),
                    })

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
