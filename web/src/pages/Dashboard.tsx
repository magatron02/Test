import React, { useEffect, useState } from "react";
import { useStore } from "../store";
import { api } from "../services/api";
import { TrendingUp, TrendingDown, Play, Square, RefreshCw, Activity } from "lucide-react";
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import clsx from "clsx";

const COIN_COLORS: Record<string, string> = {
  BTC: "#F7931A", ETH: "#627EEA", SOL: "#9945FF",
  BNB: "#F0B90B", AVAX: "#E84142",
};

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT"];

export default function Dashboard() {
  const { prices, setPrices, agentRunning, paperBalance, positions, setAgentStatus, portfolioValue, riskLevel } = useStore();
  const [loading, setLoading] = useState(false);
  const [chartData, setChartData] = useState<{ t: string; v: number }[]>([]);

  useEffect(() => {
    loadPrices();
    const iv = setInterval(loadPrices, 5000);
    return () => clearInterval(iv);
  }, []);

  const loadPrices = async () => {
    try {
      const r = await api.getPrices(SYMBOLS);
      setPrices(r.data);
      setChartData(prev => {
        const btc = r.data["BTC/USDT"]?.price ?? 0;
        const next = [...prev, { t: new Date().toLocaleTimeString(), v: btc }].slice(-30);
        return next;
      });
    } catch {}
  };

  const toggleAgent = async () => {
    setLoading(true);
    try {
      if (agentRunning) {
        await api.stopAgent();
      } else {
        await api.startAgent({
          watchlist: SYMBOLS,
          exchanges: ["binance"],
          risk_level: riskLevel,
          portfolio_value: portfolioValue,
          use_paper: true,
          interval_minutes: 60,
        });
      }
      const r = await api.getAgentStatus();
      setAgentStatus(r.data);
    } catch {}
    setLoading(false);
  };

  const balance = paperBalance?.USDT ?? 10000;
  const pnl = balance - portfolioValue;
  const pnlPct = (pnl / portfolioValue) * 100;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-muted mt-1">AI-powered crypto trading — Demo Mode</p>
      </div>

      {/* Portfolio + Agent row */}
      <div className="grid grid-cols-3 gap-4">
        {/* Portfolio Card */}
        <div className="col-span-2 bg-card border border-border rounded-2xl p-5">
          <p className="text-sm text-muted mb-1">Paper Portfolio</p>
          <div className="flex items-end justify-between mb-4">
            <div>
              <span className="text-4xl font-black text-white">
                ${balance.toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </span>
              <span className={clsx("ml-3 text-sm font-semibold", pnl >= 0 ? "text-success" : "text-danger")}>
                {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)} ({pnlPct.toFixed(2)}%)
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted">
              <Activity size={13} />
              {positions.length} positions open
            </div>
          </div>

          {/* BTC mini chart */}
          {chartData.length > 1 && (
            <ResponsiveContainer width="100%" height={80}>
              <LineChart data={chartData}>
                <Line type="monotone" dataKey="v" stroke="#3B82F6" strokeWidth={2} dot={false} />
                <XAxis dataKey="t" hide />
                <Tooltip
                  contentStyle={{ background: "#1A2235", border: "1px solid #252D40", borderRadius: 8 }}
                  labelStyle={{ color: "#94A3B8" }}
                  formatter={(v: number) => [`$${v.toLocaleString()}`, "BTC"]}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Agent Card */}
        <div className={clsx("bg-card border rounded-2xl p-5 flex flex-col", agentRunning ? "border-primary/50" : "border-border")}>
          <div className="flex items-center gap-2 mb-3">
            <div className={clsx("w-2.5 h-2.5 rounded-full", agentRunning ? "bg-success pulse" : "bg-muted")} />
            <span className="font-semibold text-white text-sm">AI Agent</span>
          </div>
          <p className="text-xs text-muted flex-1">
            {agentRunning
              ? "Scanning markets every hour with Claude AI..."
              : "Start to enable automated trading"}
          </p>
          <button
            onClick={toggleAgent}
            disabled={loading}
            className={clsx(
              "mt-4 w-full py-2.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all",
              agentRunning ? "bg-danger hover:bg-danger/80" : "bg-primary hover:bg-primary/80"
            )}
          >
            {loading ? (
              <RefreshCw size={15} className="animate-spin" />
            ) : agentRunning ? (
              <><Square size={14} /> Stop Agent</>
            ) : (
              <><Play size={14} /> Start Agent</>
            )}
          </button>
        </div>
      </div>

      {/* Market Prices */}
      <div>
        <h2 className="text-lg font-bold text-white mb-3">Live Market</h2>
        <div className="grid grid-cols-5 gap-3">
          {SYMBOLS.map((sym) => {
            const data = prices[sym];
            const base = sym.split("/")[0];
            const color = COIN_COLORS[base] ?? "#3B82F6";
            const isUp = (data?.change_24h ?? 0) >= 0;
            return (
              <div key={sym} className="bg-card border border-border rounded-xl p-4 hover:border-primary/40 transition-colors">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-black" style={{ background: color + "25", color }}>
                    {base.slice(0, 2)}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white">{base}</div>
                    <div className="text-xs text-muted">/USDT</div>
                  </div>
                </div>
                <div className="text-sm font-bold text-white">
                  ${(data?.price ?? 0).toLocaleString("en-US", { maximumFractionDigits: data?.price < 10 ? 4 : 2 })}
                </div>
                <div className={clsx("flex items-center gap-1 text-xs mt-1", isUp ? "text-success" : "text-danger")}>
                  {isUp ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                  {isUp ? "+" : ""}{(data?.change_24h ?? 0).toFixed(2)}%
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Open Positions */}
      {positions.length > 0 && (
        <div>
          <h2 className="text-lg font-bold text-white mb-3">Open Positions</h2>
          <div className="space-y-2">
            {positions.map((pos, i) => {
              const isLong = pos.side === "buy" || pos.side === "long";
              return (
                <div key={i} className="bg-card border border-border rounded-xl p-4 flex items-center gap-4">
                  <div className="font-bold text-white w-28">{pos.symbol}</div>
                  <div className={clsx("text-xs font-bold px-2 py-1 rounded-lg", isLong ? "bg-success/20 text-success" : "bg-danger/20 text-danger")}>
                    {pos.side.toUpperCase()} {pos.leverage > 1 ? `${pos.leverage}x` : ""}
                  </div>
                  <div className="text-sm text-muted">Entry: <span className="text-white">${pos.entry_price}</span></div>
                  <div className="text-sm text-muted">Size: <span className="text-white">{pos.size}</span></div>
                  {pos.take_profit && <div className="text-sm text-success">TP: ${pos.take_profit}</div>}
                  {pos.stop_loss && <div className="text-sm text-danger">SL: ${pos.stop_loss}</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
