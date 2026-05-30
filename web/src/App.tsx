import React, { useEffect } from "react";
import { useStore } from "./store";
import { ws } from "./services/ws";
import { api } from "./services/api";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import TradePage from "./pages/Trade";
import PortfolioPage from "./pages/Portfolio";
import BacktestPage from "./pages/Backtest";
import SettingsPage from "./pages/Settings";

export default function App() {
  const { activePage, setPrices, setAgentStatus } = useStore();

  useEffect(() => {
    ws.connect();
    ws.on("prices", (d) => setPrices(d as any));
    ws.on("agent_status", (d) => setAgentStatus(d as any));

    const poll = setInterval(async () => {
      try {
        const r = await api.getAgentStatus();
        setAgentStatus(r.data);
      } catch {}
    }, 10000);

    return () => {
      ws.disconnect();
      clearInterval(poll);
    };
  }, []);

  const pages: Record<string, React.ReactNode> = {
    dashboard: <Dashboard />,
    trade:     <TradePage />,
    portfolio: <PortfolioPage />,
    backtest:  <BacktestPage />,
    settings:  <SettingsPage />,
  };

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="fade-in">{pages[activePage] ?? <Dashboard />}</div>
      </main>
    </div>
  );
}
