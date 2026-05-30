import React, { useState } from "react";
import { useStore } from "../store";
import { Settings, Save, RefreshCw } from "lucide-react";
import clsx from "clsx";

const RISK_LEVELS = ["conservative", "moderate", "aggressive"] as const;

export default function SettingsPage() {
  const { riskLevel, setRiskLevel, portfolioValue, setPortfolioValue } = useStore();
  const [capital, setCapital] = useState(String(portfolioValue));
  const [saved, setSaved] = useState(false);

  const save = () => {
    const v = Number(capital);
    if (!isNaN(v) && v > 0) setPortfolioValue(v);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="p-6 space-y-6 max-w-2xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-sm text-muted mt-1">Configure the AI trading agent</p>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Settings size={15} /> Risk Profile
        </h2>
        <p className="text-xs text-muted">Controls position sizing, leverage limits, and stop-loss tightness.</p>
        <div className="grid grid-cols-3 gap-3">
          {RISK_LEVELS.map(level => (
            <button
              key={level}
              onClick={() => setRiskLevel(level)}
              className={clsx(
                "py-3 rounded-xl font-bold text-sm capitalize transition-all border",
                riskLevel === level
                  ? level === "conservative" ? "bg-success/20 border-success text-success"
                    : level === "moderate" ? "bg-primary/20 border-primary text-primary"
                    : "bg-danger/20 border-danger text-danger"
                  : "border-border text-muted hover:text-white"
              )}
            >{level}</button>
          ))}
        </div>
        <div className="text-xs text-muted bg-surface border border-border rounded-xl p-3">
          {riskLevel === "conservative" && "Max 1-3% risk per trade. Tight stop-losses. Prioritizes capital preservation."}
          {riskLevel === "moderate" && "Max 3-7% risk per trade. Balanced approach with moderate stop-losses."}
          {riskLevel === "aggressive" && "Max 7-15% risk per trade. Higher leverage allowed. Larger potential returns and losses."}
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold text-white">Paper Capital</h2>
        <p className="text-xs text-muted">Reference value used for P&L calculations and position sizing.</p>
        <div className="flex gap-3">
          <input
            type="number"
            value={capital}
            onChange={e => setCapital(e.target.value)}
            className="flex-1 bg-surface border border-border rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-primary"
            placeholder="10000"
          />
          <span className="flex items-center text-sm text-muted font-bold">USDT</span>
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold text-white">Agent Configuration</h2>
        <div className="space-y-2 text-xs">
          {[
            { label: "Model", value: "claude-sonnet-4-6" },
            { label: "Scan Interval", value: "60 minutes" },
            { label: "Exchanges", value: "Demo (Binance / OKX / Hyperliquid)" },
            { label: "Mode", value: "Paper Trading" },
            { label: "Strategies", value: "Spot, Grid, Futures, Perpetual" },
          ].map(({ label, value }) => (
            <div key={label} className="flex justify-between bg-surface border border-border rounded-xl px-3 py-2">
              <span className="text-muted">{label}</span>
              <span className="text-white font-mono">{value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold text-white">API Keys</h2>
        <p className="text-xs text-muted">
          Set real API keys in <span className="font-mono text-primary">backend/.env</span> to enable live trading.
          Currently running in <span className="text-success font-semibold">Demo Mode</span> — all data is simulated.
        </p>
        <div className="text-xs bg-surface border border-border rounded-xl p-3 font-mono text-muted space-y-1">
          <div>BINANCE_API_KEY=your_key</div>
          <div>BINANCE_SECRET=your_secret</div>
          <div>OKX_API_KEY=your_key</div>
          <div>ANTHROPIC_API_KEY=your_key</div>
          <div>USE_DEMO_MODE=false</div>
        </div>
      </div>

      <button
        onClick={save}
        className={clsx(
          "w-full py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all",
          saved ? "bg-success text-white" : "bg-primary hover:bg-primary/80 text-white"
        )}
      >
        {saved ? <><RefreshCw size={15} /> Saved!</> : <><Save size={15} /> Save Settings</>}
      </button>
    </div>
  );
}
