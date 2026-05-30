import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { useStore } from "../store";
import { Briefcase, RefreshCw } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import clsx from "clsx";

const COLORS = ["#3B82F6", "#F7931A", "#627EEA", "#9945FF", "#F0B90B", "#E84142"];

export default function PortfolioPage() {
  const { paperBalance, positions, portfolioValue } = useStore();
  const [portfolio, setPortfolio] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { loadPortfolio(); }, []);

  const loadPortfolio = async () => {
    setLoading(true);
    try {
      const r = await api.getPortfolio("demo");
      setPortfolio(r.data);
    } catch {}
    setLoading(false);
  };

  const balance = paperBalance?.USDT ?? 10000;
  const pnl = balance - portfolioValue;
  const pnlPct = portfolioValue > 0 ? (pnl / portfolioValue) * 100 : 0;

  const pieData = portfolio?.balances
    ? Object.entries(portfolio.balances as Record<string, number>)
        .filter(([, v]) => v > 0.001)
        .map(([k, v]) => ({ name: k, value: Number(v) }))
    : [{ name: "USDT", value: balance }];

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Portfolio</h1>
          <p className="text-sm text-muted mt-1">Paper trading overview</p>
        </div>
        <button
          onClick={loadPortfolio}
          disabled={loading}
          className="flex items-center gap-2 text-xs bg-card border border-border px-3 py-2 rounded-xl text-muted hover:text-white transition-colors"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Balance", value: `$${balance.toLocaleString("en-US", { minimumFractionDigits: 2 })}`, sub: "USDT", color: "text-white" },
          { label: "P&L", value: `${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)}`, sub: `${pnlPct.toFixed(2)}%`, color: pnl >= 0 ? "text-success" : "text-danger" },
          { label: "Open Positions", value: String(positions.length), sub: "active", color: "text-white" },
          { label: "Initial Capital", value: `$${portfolioValue.toLocaleString()}`, sub: "reference", color: "text-muted" },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="bg-card border border-border rounded-2xl p-4">
            <p className="text-xs text-muted mb-1">{label}</p>
            <p className={clsx("text-xl font-black", color)}>{value}</p>
            <p className="text-xs text-muted mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-2xl p-5">
          <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
            <Briefcase size={15} /> Allocation
          </h2>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={2}>
                {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#1A2235", border: "1px solid #252D40", borderRadius: 8 }}
                formatter={(v: number) => [v.toFixed(4), ""]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1 mt-2">
            {pieData.map((d, i) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                  <span className="text-muted">{d.name}</span>
                </div>
                <span className="text-white font-mono">{d.value.toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-card border border-border rounded-2xl p-5">
          <h2 className="text-sm font-bold text-white mb-4">Open Positions</h2>
          {positions.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-muted text-sm">
              <Briefcase size={32} className="mb-2 opacity-40" />
              No open positions
            </div>
          ) : (
            <div className="space-y-2 overflow-y-auto max-h-64">
              {positions.map((pos, i) => {
                const isLong = pos.side === "buy" || pos.side === "long";
                return (
                  <div key={i} className="bg-surface border border-border rounded-xl p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-white text-xs">{pos.symbol}</span>
                      <span className={clsx("text-xs font-bold px-2 py-0.5 rounded-lg", isLong ? "bg-success/20 text-success" : "bg-danger/20 text-danger")}>
                        {pos.side.toUpperCase()}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-1 text-xs text-muted">
                      <span>Entry: <span className="text-white">${pos.entry_price}</span></span>
                      <span>Size: <span className="text-white">{pos.size}</span></span>
                      {pos.take_profit && <span className="text-success">TP: ${pos.take_profit}</span>}
                      {pos.stop_loss && <span className="text-danger">SL: ${pos.stop_loss}</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {portfolio?.balances && (
        <div className="bg-card border border-border rounded-2xl p-5">
          <h2 className="text-sm font-bold text-white mb-3">Wallet Balances</h2>
          <div className="grid grid-cols-4 gap-2">
            {Object.entries(portfolio.balances as Record<string, number>).map(([asset, amount]) => (
              <div key={asset} className="bg-surface border border-border rounded-xl p-3 text-xs">
                <div className="font-bold text-white">{asset}</div>
                <div className="text-muted font-mono mt-0.5">{Number(amount).toFixed(4)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
