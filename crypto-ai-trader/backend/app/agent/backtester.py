"""
Backtesting engine for crypto trading strategies.

Runs simulated trades against historical OHLCV data using the same technical
indicators as market_analyzer.py (RSI, MACD, EMA, Bollinger Bands, ATR).
No AI/Claude calls — signals are generated purely from indicator logic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import ta

from app.agent.market_analyzer import compute_indicators


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BacktestTrade:
    """Represents a single closed trade in the backtest."""
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    side: str          # "long" | "short"
    size: float        # in quote currency (USDT)
    pnl: float         # realised P&L in quote currency after fees
    pnl_pct: float     # percentage of size
    exit_reason: str   # "tp" | "sl" | "signal" | "end_of_data"
    leverage: float = 1.0


@dataclass
class BacktestResult:
    """Aggregated metrics returned after a complete backtest run."""
    strategy: str
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    profit_factor: float
    avg_trade_pct: float
    final_capital: float
    initial_capital: float
    trades: List[BacktestTrade] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

def _build_indicator_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all indicator series across the full OHLCV DataFrame and attach
    them as columns so we can iterate row-by-row in O(1) per bar.
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    df = df.copy()

    # EMAs
    df["ema9"]  = ta.trend.EMAIndicator(close, 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(close, 21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close, 50).ema_indicator()

    # MACD
    _macd = ta.trend.MACD(close)
    df["macd"]      = _macd.macd()
    df["macd_sig"]  = _macd.macd_signal()
    df["macd_hist"] = _macd.macd_diff()

    # RSI
    df["rsi"] = ta.momentum.RSIIndicator(close, 14).rsi()

    # Bollinger Bands
    _bb = ta.volatility.BollingerBands(close, 20, 2)
    df["bb_upper"] = _bb.bollinger_hband()
    df["bb_lower"] = _bb.bollinger_lband()
    df["bb_mid"]   = _bb.bollinger_mavg()

    # ATR
    df["atr"] = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()

    return df


def _spot_signal(row: pd.Series, prev_row: pd.Series) -> Optional[str]:
    """
    Spot strategy entry signal.

    Buy when:
      - EMA9 > EMA21 > EMA50  (bullish alignment)
      - RSI in [35, 65]        (not over-extended)
      - MACD histogram crosses above zero (momentum confirmation)

    Sell / exit when the trend breaks (EMA9 < EMA21) or RSI > 70.
    """
    if pd.isna(row["ema50"]) or pd.isna(row["macd_hist"]):
        return None

    bullish = row["ema9"] > row["ema21"] > row["ema50"]
    rsi_ok   = 35 < row["rsi"] < 65
    macd_cross_up = row["macd_hist"] > 0 and (pd.isna(prev_row["macd_hist"]) or prev_row["macd_hist"] <= 0)

    if bullish and rsi_ok and macd_cross_up:
        return "buy"

    bearish_exit = row["ema9"] < row["ema21"]
    rsi_overbought = row["rsi"] > 70

    if bearish_exit or rsi_overbought:
        return "sell"

    return None


def _futures_signal(row: pd.Series, prev_row: pd.Series) -> Optional[str]:
    """
    Futures / perpetual strategy signals (long and short).

    Long when:
      - EMA9 > EMA21 (short-term bullish)
      - MACD histogram crosses above zero
      - RSI < 65

    Short when:
      - EMA9 < EMA21 (short-term bearish)
      - MACD histogram crosses below zero
      - RSI > 35

    Exit on opposite signal or RSI extremes.
    """
    if pd.isna(row["ema21"]) or pd.isna(row["macd_hist"]):
        return None

    prev_hist = prev_row["macd_hist"] if not pd.isna(prev_row["macd_hist"]) else 0.0

    long_signal  = (row["ema9"] > row["ema21"]
                    and row["macd_hist"] > 0
                    and prev_hist <= 0
                    and row["rsi"] < 65)

    short_signal = (row["ema9"] < row["ema21"]
                    and row["macd_hist"] < 0
                    and prev_hist >= 0
                    and row["rsi"] > 35)

    if long_signal:
        return "long"
    if short_signal:
        return "short"

    return None


def _grid_signals(
    df: pd.DataFrame,
    params: dict,
) -> List[Tuple[int, str, float]]:
    """
    Grid strategy: place virtual buy/sell orders at fixed price levels.

    Returns a list of (bar_index, side, fill_price) representing fills as
    price crosses grid levels during the simulation.  The grid is initialised
    once and level orders flip each time they are hit.
    """
    upper      = params.get("upper_price", 0.0)
    lower      = params.get("lower_price", 0.0)
    grid_count = int(params.get("grid_count", 10))

    if upper <= lower or grid_count < 2:
        return []

    levels = np.linspace(lower, upper, grid_count + 1)
    # Track which side each level is waiting for: True = waiting to buy, False = waiting to sell
    waiting_buy = np.ones(len(levels), dtype=bool)

    # Seed: levels below the initial price are waiting to buy; above are selling
    initial_price = df["close"].iloc[0]
    for i, lvl in enumerate(levels):
        waiting_buy[i] = lvl < initial_price

    fills: List[Tuple[int, str, float]] = []

    for idx in range(1, len(df)):
        lo = df["low"].iloc[idx]
        hi = df["high"].iloc[idx]

        for i, lvl in enumerate(levels):
            if waiting_buy[i] and lo <= lvl <= hi:
                fills.append((idx, "buy", lvl))
                waiting_buy[i] = False        # now waiting to sell at this level
            elif not waiting_buy[i] and lo <= lvl <= hi:
                fills.append((idx, "sell", lvl))
                waiting_buy[i] = True         # now waiting to buy again

    return fills


# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """
    Engine that simulates trading strategies on historical OHLCV data.

    Usage::

        engine = BacktestEngine()
        result = await engine.run_backtest(ohlcv, "spot", {
            "initial_capital": 10000,
            "risk_per_trade": 0.02,
            "tp_atr_mult": 2.0,
            "sl_atr_mult": 1.0,
            "leverage": 1,
            "fee_rate": 0.001,
        })
    """

    # Default fee rate (0.1 % taker on most exchanges)
    DEFAULT_FEE_RATE: float = 0.001

    async def run_backtest(
        self,
        ohlcv: List[dict],
        strategy: str,
        params: dict,
    ) -> BacktestResult:
        """
        Run a backtest on OHLCV data.

        Parameters
        ----------
        ohlcv:
            List of candle dicts with keys: timestamp, open, high, low, close, volume.
            Minimum 60 candles required (to warm-up indicators).
        strategy:
            One of "spot", "grid", "futures".
        params:
            Dict of optional parameters:
            - initial_capital (float): Starting USDT balance.  Default 10 000.
            - risk_per_trade (float): Fraction of capital risked per trade.  Default 0.02.
            - tp_atr_mult (float): ATR multiplier for take-profit.  Default 2.0.
            - sl_atr_mult (float): ATR multiplier for stop-loss.  Default 1.0.
            - leverage (int): Leverage for futures.  Default 1 for spot/grid, 3 for futures.
            - fee_rate (float): Taker fee fraction.  Default 0.001.
            - grid_count (int): Number of grid levels (grid only).  Default 10.

        Returns
        -------
        BacktestResult
            Aggregated performance metrics plus the list of individual trades.
        """
        strategy = strategy.lower()
        if strategy not in ("spot", "grid", "futures"):
            raise ValueError(f"Unknown strategy '{strategy}'. Choose spot, grid, or futures.")

        if len(ohlcv) < 60:
            raise ValueError("Need at least 60 candles to run a meaningful backtest.")

        initial_capital: float = float(params.get("initial_capital", 10_000.0))
        risk_per_trade:  float = float(params.get("risk_per_trade", 0.02))
        tp_atr_mult:     float = float(params.get("tp_atr_mult", 2.0))
        sl_atr_mult:     float = float(params.get("sl_atr_mult", 1.0))
        fee_rate:        float = float(params.get("fee_rate", self.DEFAULT_FEE_RATE))
        leverage:        int   = int(params.get("leverage", 3 if strategy == "futures" else 1))

        df = pd.DataFrame(ohlcv)
        df = _build_indicator_series(df)

        if strategy == "grid":
            trades = self._run_grid(df, params, initial_capital, fee_rate)
        elif strategy == "spot":
            trades = self._run_spot(df, initial_capital, risk_per_trade,
                                    tp_atr_mult, sl_atr_mult, fee_rate)
        else:  # futures
            trades = self._run_futures(df, initial_capital, risk_per_trade,
                                       tp_atr_mult, sl_atr_mult, fee_rate, leverage)

        return self._compute_metrics(trades, initial_capital, strategy)

    # ------------------------------------------------------------------
    # Strategy simulators
    # ------------------------------------------------------------------

    def _run_spot(
        self,
        df: pd.DataFrame,
        initial_capital: float,
        risk_per_trade: float,
        tp_atr_mult: float,
        sl_atr_mult: float,
        fee_rate: float,
    ) -> List[BacktestTrade]:
        """
        Spot strategy: long-only, one position at a time.
        Entry/exit driven by EMA/MACD/RSI signals.
        TP and SL sized via ATR.
        """
        trades: List[BacktestTrade] = []
        capital = initial_capital
        position: Optional[dict] = None   # open position state

        for i in range(1, len(df)):
            row      = df.iloc[i]
            prev_row = df.iloc[i - 1]
            price    = row["close"]
            atr      = row["atr"] if not pd.isna(row["atr"]) else price * 0.01

            # ---- Manage open position ----
            if position is not None:
                tp = position["tp"]
                sl = position["sl"]

                # Check SL / TP using high/low of the bar (conservative: SL first)
                hit_sl = df.iloc[i]["low"] <= sl
                hit_tp = df.iloc[i]["high"] >= tp

                if hit_sl:
                    exit_price  = sl
                    exit_reason = "sl"
                elif hit_tp:
                    exit_price  = tp
                    exit_reason = "tp"
                else:
                    # Check for signal-based exit
                    sig = _spot_signal(row, prev_row)
                    if sig == "sell":
                        exit_price  = price
                        exit_reason = "signal"
                    else:
                        continue  # hold

                # Close position
                trade, capital = self._close_long(
                    position, i, exit_price, exit_reason, capital, fee_rate
                )
                trades.append(trade)
                position = None
                continue

            # ---- Look for entry ----
            sig = _spot_signal(row, prev_row)
            if sig == "buy" and not pd.isna(atr):
                sl_price = price - atr * sl_atr_mult
                tp_price = price + atr * tp_atr_mult
                if sl_price >= price:
                    continue  # degenerate, skip

                # Risk-based position sizing
                risk_amount = capital * risk_per_trade
                stop_dist   = price - sl_price
                size_coins  = risk_amount / stop_dist
                size_usdt   = size_coins * price
                size_usdt   = min(size_usdt, capital * 0.10)  # cap at 10 % of capital

                if size_usdt <= 0 or size_usdt > capital:
                    continue

                fee_in  = size_usdt * fee_rate
                capital -= size_usdt + fee_in

                position = {
                    "entry_index": i,
                    "entry_price": price,
                    "size_usdt":   size_usdt,
                    "size_coins":  size_usdt / price,
                    "tp": tp_price,
                    "sl": sl_price,
                }

        # Close any open position at the last bar
        if position is not None:
            last_price = df["close"].iloc[-1]
            trade, capital = self._close_long(
                position, len(df) - 1, last_price, "end_of_data", capital, fee_rate
            )
            trades.append(trade)

        return trades

    def _run_futures(
        self,
        df: pd.DataFrame,
        initial_capital: float,
        risk_per_trade: float,
        tp_atr_mult: float,
        sl_atr_mult: float,
        fee_rate: float,
        leverage: int,
    ) -> List[BacktestTrade]:
        """
        Futures strategy: long and short, one position at a time.
        Entry/exit driven by EMA/MACD cross signals.
        TP and SL sized via ATR.  Liquidation guard applied.
        """
        trades: List[BacktestTrade] = []
        capital  = initial_capital
        position: Optional[dict] = None

        for i in range(1, len(df)):
            row      = df.iloc[i]
            prev_row = df.iloc[i - 1]
            price    = row["close"]
            atr      = row["atr"] if not pd.isna(row["atr"]) else price * 0.01

            if position is not None:
                tp   = position["tp"]
                sl   = position["sl"]
                side = position["side"]
                lo   = df.iloc[i]["low"]
                hi   = df.iloc[i]["high"]

                if side == "long":
                    hit_sl = lo <= sl
                    hit_tp = hi >= tp
                else:  # short
                    hit_sl = hi >= sl
                    hit_tp = lo <= tp

                if hit_sl:
                    exit_price  = sl
                    exit_reason = "sl"
                elif hit_tp:
                    exit_price  = tp
                    exit_reason = "tp"
                else:
                    # Signal-based exit or reversal
                    sig = _futures_signal(row, prev_row)
                    flip = (side == "long" and sig == "short") or \
                           (side == "short" and sig == "long")
                    if flip:
                        exit_price  = price
                        exit_reason = "signal"
                    else:
                        continue  # hold

                trade, capital = self._close_futures(
                    position, i, exit_price, exit_reason, capital, fee_rate
                )
                trades.append(trade)
                position = None
                # Fall through to check for new entry this same bar (reversal)

            # ---- Look for entry ----
            sig = _futures_signal(row, prev_row)
            if sig in ("long", "short") and not pd.isna(atr):
                if sig == "long":
                    sl_price = price - atr * sl_atr_mult
                    tp_price = price + atr * tp_atr_mult
                else:
                    sl_price = price + atr * sl_atr_mult
                    tp_price = price - atr * tp_atr_mult

                # Margin required
                risk_amount  = capital * risk_per_trade
                stop_dist    = abs(price - sl_price)
                if stop_dist == 0:
                    continue
                size_coins   = risk_amount * leverage / stop_dist
                margin_used  = (size_coins * price) / leverage
                margin_used  = min(margin_used, capital * 0.10)

                if margin_used <= 0 or margin_used > capital:
                    continue

                fee_in  = size_coins * price * fee_rate
                capital -= margin_used + fee_in

                position = {
                    "entry_index": i,
                    "entry_price": price,
                    "side":        sig,
                    "size_coins":  size_coins,
                    "margin_used": margin_used,
                    "tp": tp_price,
                    "sl": sl_price,
                    "leverage":    leverage,
                }

        # Close at end of data
        if position is not None:
            last_price = df["close"].iloc[-1]
            trade, capital = self._close_futures(
                position, len(df) - 1, last_price, "end_of_data", capital, fee_rate
            )
            trades.append(trade)

        return trades

    def _run_grid(
        self,
        df: pd.DataFrame,
        params: dict,
        initial_capital: float,
        fee_rate: float,
    ) -> List[BacktestTrade]:
        """
        Grid strategy: place static buy/sell orders at equidistant price levels.

        Grid boundaries are derived from the data if not provided in params:
        - upper_price / lower_price: use a ±10 % band around the first close.
        - grid_count: number of intervals (default 10).

        Pairs up fills: each buy fill is matched with the next sell fill at a
        higher level to produce a round-trip trade.  Unpaired buys at the end
        are closed at the last bar's close.
        """
        grid_count = int(params.get("grid_count", 10))
        first_close = df["close"].iloc[0]

        # Auto-derive range if not provided
        upper = float(params.get("upper_price", first_close * 1.10))
        lower = float(params.get("lower_price", first_close * 0.90))
        if upper <= lower:
            upper = first_close * 1.10
            lower = first_close * 0.90

        grid_params = {
            "upper_price": upper,
            "lower_price": lower,
            "grid_count":  grid_count,
        }

        per_grid_usdt = initial_capital / grid_count
        fills = _grid_signals(df, grid_params)

        trades: List[BacktestTrade] = []
        capital = initial_capital

        # Match buys with subsequent sells (FIFO queue per level)
        open_buys: List[dict] = []   # stack of unmatched buy fills

        for (bar_idx, side, fill_price) in fills:
            if side == "buy":
                fee_in = per_grid_usdt * fee_rate
                if capital >= per_grid_usdt + fee_in:
                    capital -= per_grid_usdt + fee_in
                    open_buys.append({
                        "entry_index": bar_idx,
                        "entry_price": fill_price,
                        "size_usdt":   per_grid_usdt,
                        "size_coins":  per_grid_usdt / fill_price,
                    })
            elif side == "sell" and open_buys:
                buy = open_buys.pop(0)
                proceeds   = buy["size_coins"] * fill_price
                fee_out    = proceeds * fee_rate
                net        = proceeds - fee_out
                pnl        = net - buy["size_usdt"]
                pnl_pct    = pnl / buy["size_usdt"] * 100
                capital   += net

                trades.append(BacktestTrade(
                    entry_index  = buy["entry_index"],
                    exit_index   = bar_idx,
                    entry_price  = buy["entry_price"],
                    exit_price   = fill_price,
                    side         = "long",
                    size         = buy["size_usdt"],
                    pnl          = pnl,
                    pnl_pct      = pnl_pct,
                    exit_reason  = "tp",   # grid sell = profit target
                    leverage     = 1.0,
                ))

        # Close any remaining open buys at the last price
        last_price = df["close"].iloc[-1]
        for buy in open_buys:
            proceeds  = buy["size_coins"] * last_price
            fee_out   = proceeds * fee_rate
            net       = proceeds - fee_out
            pnl       = net - buy["size_usdt"]
            pnl_pct   = pnl / buy["size_usdt"] * 100
            capital  += net

            trades.append(BacktestTrade(
                entry_index  = buy["entry_index"],
                exit_index   = len(df) - 1,
                entry_price  = buy["entry_price"],
                exit_price   = last_price,
                side         = "long",
                size         = buy["size_usdt"],
                pnl          = pnl,
                pnl_pct      = pnl_pct,
                exit_reason  = "end_of_data",
                leverage     = 1.0,
            ))

        return trades

    # ------------------------------------------------------------------
    # Trade closing helpers
    # ------------------------------------------------------------------

    def _close_long(
        self,
        position: dict,
        exit_index: int,
        exit_price: float,
        exit_reason: str,
        capital: float,
        fee_rate: float,
    ) -> Tuple[BacktestTrade, float]:
        """Close a spot long position and return the trade + updated capital."""
        proceeds = position["size_coins"] * exit_price
        fee_out  = proceeds * fee_rate
        net      = proceeds - fee_out
        capital += net

        pnl     = net - position["size_usdt"]
        pnl_pct = pnl / position["size_usdt"] * 100

        trade = BacktestTrade(
            entry_index = position["entry_index"],
            exit_index  = exit_index,
            entry_price = position["entry_price"],
            exit_price  = exit_price,
            side        = "long",
            size        = position["size_usdt"],
            pnl         = pnl,
            pnl_pct     = pnl_pct,
            exit_reason = exit_reason,
            leverage    = 1.0,
        )
        return trade, capital

    def _close_futures(
        self,
        position: dict,
        exit_index: int,
        exit_price: float,
        exit_reason: str,
        capital: float,
        fee_rate: float,
    ) -> Tuple[BacktestTrade, float]:
        """Close a futures position (long or short) and return trade + updated capital."""
        side       = position["side"]
        lev        = position["leverage"]
        entry      = position["entry_price"]
        coins      = position["size_coins"]
        margin     = position["margin_used"]

        if side == "long":
            raw_pnl = (exit_price - entry) * coins
        else:
            raw_pnl = (entry - exit_price) * coins

        fee_out  = coins * exit_price * fee_rate
        net_pnl  = raw_pnl - fee_out

        # Guard: can't lose more than the margin
        net_pnl  = max(net_pnl, -margin)

        capital += margin + net_pnl
        capital  = max(capital, 0.0)

        pnl_pct  = net_pnl / margin * 100 if margin > 0 else 0.0

        trade = BacktestTrade(
            entry_index = position["entry_index"],
            exit_index  = exit_index,
            entry_price = entry,
            exit_price  = exit_price,
            side        = side,
            size        = margin,
            pnl         = net_pnl,
            pnl_pct     = pnl_pct,
            exit_reason = exit_reason,
            leverage    = float(lev),
        )
        return trade, capital

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _compute_metrics(
        self,
        trades: List[BacktestTrade],
        initial_capital: float,
        strategy: str,
    ) -> BacktestResult:
        """Compute aggregated performance metrics from a list of closed trades."""

        if not trades:
            return BacktestResult(
                strategy        = strategy,
                total_return_pct= 0.0,
                max_drawdown_pct= 0.0,
                sharpe_ratio    = 0.0,
                win_rate        = 0.0,
                total_trades    = 0,
                profit_factor   = 0.0,
                avg_trade_pct   = 0.0,
                final_capital   = initial_capital,
                initial_capital = initial_capital,
                trades          = [],
            )

        # Rebuild equity curve from trade sequence
        equity = initial_capital
        equity_curve: List[float] = [initial_capital]
        for t in trades:
            equity += t.pnl
            equity_curve.append(equity)

        final_capital    = equity
        total_return_pct = (final_capital - initial_capital) / initial_capital * 100

        # Max drawdown (peak-to-trough on equity curve)
        eq_arr = np.array(equity_curve, dtype=float)
        peak   = np.maximum.accumulate(eq_arr)
        dd     = (eq_arr - peak) / peak * 100
        max_drawdown_pct = float(abs(dd.min()))

        # Win rate
        wins     = [t for t in trades if t.pnl > 0]
        losses   = [t for t in trades if t.pnl <= 0]
        win_rate = len(wins) / len(trades) * 100

        # Profit factor (gross profit / gross loss)
        gross_profit = sum(t.pnl for t in wins)
        gross_loss   = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
        if profit_factor == float("inf") and gross_profit == 0:
            profit_factor = 0.0

        # Average trade return %
        avg_trade_pct = sum(t.pnl_pct for t in trades) / len(trades)

        # Sharpe ratio (annualised, based on per-trade returns; assumes ~252 trading days)
        # Use trade pnl_pct as individual returns
        returns = np.array([t.pnl_pct for t in trades], dtype=float)
        if len(returns) > 1 and returns.std() > 0:
            # Approximate: assume each trade averages 1 day, annualise by sqrt(252)
            sharpe_ratio = float(returns.mean() / returns.std() * math.sqrt(252))
        else:
            sharpe_ratio = 0.0

        return BacktestResult(
            strategy         = strategy,
            total_return_pct = round(total_return_pct, 4),
            max_drawdown_pct = round(max_drawdown_pct, 4),
            sharpe_ratio     = round(sharpe_ratio, 4),
            win_rate         = round(win_rate, 2),
            total_trades     = len(trades),
            profit_factor    = round(profit_factor, 4),
            avg_trade_pct    = round(avg_trade_pct, 4),
            final_capital    = round(final_capital, 2),
            initial_capital  = round(initial_capital, 2),
            trades           = trades,
        )
