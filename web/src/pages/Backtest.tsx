import React, { useState } from "react";
import { api } from "../services/api";
import { FlaskConical, RefreshCw, TrendingUp, TrendingDown } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import clsx from "clsx";

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT"];
const STRATEGIES = ["spot", "grid", "futures"] as const;
const TIMEFRAMES = ["1h", "4h", "1d"];
const PERIODS = [
  { label: "1 Week", days: 7 },
  { label: "1 Month", days: 30 },
  { label: "3 Months", days: 90 },
];

export default function BacktestPage() {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [strategy, setStrategy] = useState("spot");
  const [timeframe, setTimeframe] = useState("1h");
  const [days, setDays] = useState(30);
  const [initialCapital, setInitialCapital] = useState("10000");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  const runBacktest = async () => {
    setLoading(true); setError(""); setResult(null);
    try {
      const r = await api.runBacktest({
        symbol,
        exchange: "demo",
        strategy,
        timeframe,
        limit: days * (timeframe === "1d" ? 1 : timeframe === "4h" ? 6 : 24),
        initial_capital: Number(initialCapital),
        params: {},
      });
      setResult(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Backtest failed");
    }
    setLoading(false);
  };

  const metrics = result ? [
    { label: "Total Return", value: `${result.total_return_pct >= 0 ? "+" : ""}${result.total_return_pct?.toFixed(2)}%`, positive: result.total_return_pct >= 0 },
    { label: "Max Drawdown", value: `-${result.max_drawdown_pct?.toFixed(2)}%`, positive: false },
    { label: "Sharpe Ratio", value: result.sharpe_ratio?.toFixed(3), positive: result.sharpe_ratio >= 1 },
    { label: "Win Rate", value: `${(result.win_rate * 100)?.toFixed(1)}%`, positive: result.win_rate >= 0.5 },
    { label: "Total Trades", value: String(result.total_trades), positive: true },
    { label: "Profit Factor", value: result.profit_factor?.toFixed(2), positive: result.profit_factor >= 1 },
  ] : [];

  const chartData = result?.equity_curve
    ? result.equity_curve.map((v: number, i: number) => ({ i, equity: v }))
    : [];

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white">Backtest</h1>
        <p className="text-sm text-muted mt-1">Simulate strategies on historical data</p>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-muted mb-1 block">Symbol</label>
            <select value={symbol} onChange={e => setSymbol(e.target.value)}
              className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-primary">
              {SYMBOLS.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted mb-1 block">Initial Capital (USDT)</label>
            <input type="number" value={initialCapital} onChange={e => setInitialCapital(e.target.value)}
              className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-primary" />
          </div>
        </div>

        <div>
          <label className="text-xs text-muted mb-2 block">Strategy</label>
          <div className="flex gap-2">
            {STRATEGIES.map(s => (
              <button key={s} onClick={() => setStrategy(s)}
                className={clsx("px-4 py-2 rounded-xl text-xs font-bold capitalize transition-all",
                  strategy === s ? "bg-primary text-white" : "bg-surface text-muted hover:text-white")}>
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-muted mb-2 block">Timeframe</label>
            <div className="flex gap-2">
              {TIMEFRAMES.map(tf => (
                <button key={tf} onClick={() => setTimeframe(tf)}
                  className={clsx("px-3 py-2 rounded-xl text-xs font-bold transition-all",
                    timeframe === tf ? "bg-primary text-white" : "bg-surface text-muted hover:text-white")}>
                  {tf}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-muted mb-2 block">Period</label>
            <div className="flex gap-2">
              {PERIODS.map(p => (
                <button key={p.days} onClick={() => setDays(p.days)}
                  className={clsx("px-3 py-2 rounded-xl text-xs font-bold transition-all",
                    days === p.days ? "bg-primary text-white" : "bg-surface text-muted hover:text-white")}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && <div className="text-xs text-danger bg-danger/10 rounded-xl px-3 py-2">{error}</div>}

        <button onClick={runBacktest} disabled={loading}
          className="w-full py-3 rounded-xl font-bold bg-primary hover:bg-primary/80 flex items-center justify-center gap-2 transition-all">
          {loading ? <RefreshCw size={15} className="animate-spin" /> : <><FlaskConical size={15} /> Run Backtest</>}
        </button>
      </div>

      {result && (
        <>
          <div className="grid grid-cols-3 gap-3">
            {metrics.map(({ label, value, positive }) => (
              <div key={label} className="bg-card border border-border rounded-2xl p-4">
                <p className="text-xs text-muted mb-1">{label}</p>
                <p className={clsx("text-xl font-black", positive ? "text-success" : "text-danger")}>{value}</p>
              </div>
            ))}
          </div>

          {chartData.length > 1 && (
            <div className="bg-card border border-border rounded-2xl p-5">
              <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                {result.total_return_pct >= 0 ? <TrendingUp size={15} className="text-success" /> : <TrendingDown size={15} className="text-danger" />}
                Equity Curve
              </h2>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#252D40" />
                  <XAxis dataKey="i" hide />
                  <YAxis domain={["auto", "auto"]} stroke="#4B5563" tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <Tooltip
                    contentStyle={{ background: "#1A2235", border: "1px solid #252D40", borderRadius: 8 }}
                    formatter={(v: number) => [`$${v.toLocaleString("en-US", { minimumFractionDigits: 2 })}`, "Equity"]}
                  />
                  <Line type="monotone" dataKey="equity"
                    stroke={result.total_return_pct >= 0 ? "#22C55E" : "#EF4444"}
                    strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="bg-card border border-border rounded-2xl p-5 text-xs text-muted space-y-1">
            <div className="font-bold text-white mb-2">Strategy: <span className="text-primary capitalize">{strategy}</span> — {symbol} — {timeframe} — {days}d</div>
            <div>Initial: <span className="text-white">${Number(initialCapital).toLocaleString()}</span></div>
            <div>Final: <span className="text-white">${result.final_capital?.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span></div>
            <div>Avg Trade: <span className={result.avg_trade_pct >= 0 ? "text-success" : "text-danger"}>{result.avg_trade_pct?.toFixed(3)}%</span></div>
          </div>
        </>
      )}
    </div>
  );
}
