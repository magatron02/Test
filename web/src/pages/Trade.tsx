import React, { useState } from "react";
import { api } from "../services/api";
import { useStore } from "../store";
import { TrendingUp, TrendingDown, Zap, Grid, RefreshCw } from "lucide-react";
import clsx from "clsx";

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT"];
const STRATEGIES = ["spot", "grid", "futures", "perpetual"] as const;

type Strategy = typeof STRATEGIES[number];

export default function TradePage() {
  const { prices, riskLevel } = useStore();
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [strategy, setStrategy] = useState<Strategy>("spot");
  const [amount, setAmount] = useState("");
  const [leverage, setLeverage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  const currentPrice = prices[symbol]?.price ?? 0;
  const change = prices[symbol]?.change_24h ?? 0;

  const handleTrade = async () => {
    if (!amount || isNaN(Number(amount))) { setError("Enter a valid amount"); return; }
    setLoading(true); setError(""); setResult(null);
    try {
      const r = await api.placeTrade({
        exchange: "demo",
        symbol,
        side,
        amount: Number(amount),
        strategy,
        leverage: strategy === "futures" || strategy === "perpetual" ? leverage : 1,
        use_paper: true,
      });
      setResult(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Trade failed");
    }
    setLoading(false);
  };

  const handleAnalyze = async () => {
    setLoading(true); setError(""); setResult(null);
    try {
      const r = await api.analyzeMarket({ symbol, exchange: "demo" });
      setResult(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Analysis failed");
    }
    setLoading(false);
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white">Trade</h1>
        <p className="text-sm text-muted mt-1">Paper trading — no real funds at risk</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Order Form */}
        <div className="col-span-2 bg-card border border-border rounded-2xl p-5 space-y-4">
          {/* Symbol & price */}
          <div className="flex items-center justify-between">
            <select
              value={symbol}
              onChange={e => setSymbol(e.target.value)}
              className="bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-primary"
            >
              {SYMBOLS.map(s => <option key={s}>{s}</option>)}
            </select>
            <div className="text-right">
              <div className="text-lg font-bold text-white">${currentPrice.toLocaleString("en-US", { maximumFractionDigits: 2 })}</div>
              <div className={clsx("text-xs", change >= 0 ? "text-success" : "text-danger")}>
                {change >= 0 ? "+" : ""}{change.toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Strategy */}
          <div>
            <label className="text-xs text-muted mb-2 block">Strategy</label>
            <div className="grid grid-cols-4 gap-2">
              {STRATEGIES.map(s => (
                <button
                  key={s}
                  onClick={() => setStrategy(s)}
                  className={clsx(
                    "py-2 rounded-xl text-xs font-bold capitalize transition-all",
                    strategy === s ? "bg-primary text-white" : "bg-surface text-muted hover:text-white"
                  )}
                >{s}</button>
              ))}
            </div>
          </div>

          {/* Buy / Sell */}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setSide("buy")}
              className={clsx("py-2.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all",
                side === "buy" ? "bg-success text-white" : "bg-surface text-muted hover:text-white")}
            >
              <TrendingUp size={14} /> Buy / Long
            </button>
            <button
              onClick={() => setSide("sell")}
              className={clsx("py-2.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all",
                side === "sell" ? "bg-danger text-white" : "bg-surface text-muted hover:text-white")}
            >
              <TrendingDown size={14} /> Sell / Short
            </button>
          </div>

          {/* Amount */}
          <div>
            <label className="text-xs text-muted mb-1 block">Amount (USDT)</label>
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              placeholder="100"
              className="w-full bg-surface border border-border rounded-xl px-4 py-2.5 text-sm text-white placeholder-muted focus:outline-none focus:border-primary"
            />
          </div>

          {/* Leverage (futures/perp only) */}
          {(strategy === "futures" || strategy === "perpetual") && (
            <div>
              <label className="text-xs text-muted mb-1 block">Leverage: {leverage}x</label>
              <input
                type="range" min={1} max={20} value={leverage}
                onChange={e => setLeverage(Number(e.target.value))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-xs text-muted mt-1">
                <span>1x</span><span>5x</span><span>10x</span><span>20x</span>
              </div>
            </div>
          )}

          {error && <div className="text-xs text-danger bg-danger/10 rounded-xl px-3 py-2">{error}</div>}

          {result && (
            <div className="text-xs bg-surface border border-border rounded-xl px-3 py-2 space-y-1">
              {Object.entries(result).slice(0, 8).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-muted capitalize">{k.replace(/_/g, " ")}</span>
                  <span className="text-white font-mono">{String(v)}</span>
                </div>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="py-2.5 rounded-xl font-bold text-sm bg-surface border border-border text-white hover:bg-white/5 flex items-center justify-center gap-2 transition-all"
            >
              {loading ? <RefreshCw size={14} className="animate-spin" /> : <><Zap size={14} /> AI Analyze</>}
            </button>
            <button
              onClick={handleTrade}
              disabled={loading}
              className={clsx(
                "py-2.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all",
                side === "buy" ? "bg-success hover:bg-success/80" : "bg-danger hover:bg-danger/80"
              )}
            >
              {loading ? <RefreshCw size={14} className="animate-spin" /> : <><Grid size={14} /> Place Order</>}
            </button>
          </div>
        </div>

        {/* Quick info panel */}
        <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
          <h3 className="text-sm font-bold text-white">Market Info</h3>
          {SYMBOLS.map(sym => {
            const d = prices[sym];
            const isUp = (d?.change_24h ?? 0) >= 0;
            return (
              <button
                key={sym}
                onClick={() => setSymbol(sym)}
                className={clsx(
                  "w-full flex items-center justify-between text-xs rounded-xl px-2 py-1.5 transition-colors",
                  symbol === sym ? "bg-primary/20 text-primary" : "hover:bg-white/5 text-muted"
                )}
              >
                <span className="font-bold text-white">{sym.split("/")[0]}</span>
                <span className={isUp ? "text-success" : "text-danger"}>
                  {isUp ? "+" : ""}{(d?.change_24h ?? 0).toFixed(2)}%
                </span>
              </button>
            );
          })}
          <div className="border-t border-border pt-3 text-xs text-muted space-y-1">
            <div>Risk Level: <span className="text-white capitalize">{riskLevel}</span></div>
            <div>Mode: <span className="text-success">Paper</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}
