import React from "react";
import { useStore } from "../store";
import {
  Zap, TrendingUp, Briefcase, FlaskConical, Settings, Wifi, WifiOff,
} from "lucide-react";
import clsx from "clsx";

const NAV = [
  { id: "dashboard", label: "Dashboard",  Icon: Zap },
  { id: "trade",     label: "Trade",      Icon: TrendingUp },
  { id: "portfolio", label: "Portfolio",  Icon: Briefcase },
  { id: "backtest",  label: "Backtest",   Icon: FlaskConical },
  { id: "settings",  label: "Settings",   Icon: Settings },
];

export default function Sidebar() {
  const { activePage, setPage, connected, agentRunning } = useStore();

  return (
    <aside className="w-60 bg-surface border-r border-border flex flex-col shrink-0">
      {/* Logo */}
      <div className="p-6 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center">
            <Zap size={18} className="text-primary" />
          </div>
          <div>
            <div className="text-sm font-bold text-white leading-none">CryptoAI</div>
            <div className="text-xs text-muted">Trader</div>
          </div>
        </div>
      </div>

      {/* Agent Status */}
      <div className="mx-4 mt-4 rounded-xl bg-card border border-border p-3">
        <div className="flex items-center gap-2 mb-1">
          <div className={clsx("w-2 h-2 rounded-full", agentRunning ? "bg-success pulse" : "bg-muted")} />
          <span className="text-xs font-semibold text-white">AI Agent</span>
        </div>
        <span className={clsx("text-xs", agentRunning ? "text-success" : "text-muted")}>
          {agentRunning ? "Trading active" : "Paused"}
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 mt-2">
        {NAV.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => setPage(id)}
            className={clsx(
              "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all",
              activePage === id
                ? "bg-primary/15 text-primary"
                : "text-muted hover:text-white hover:bg-white/5"
            )}
          >
            <Icon size={17} />
            {label}
          </button>
        ))}
      </nav>

      {/* Connection */}
      <div className="p-4 border-t border-border">
        <div className={clsx("flex items-center gap-2 text-xs", connected ? "text-success" : "text-danger")}>
          {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
          {connected ? "Connected to backend" : "Backend offline"}
        </div>
        <div className="text-xs text-muted mt-1">localhost:8000</div>
      </div>
    </aside>
  );
}
