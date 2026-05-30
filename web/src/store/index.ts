import { create } from "zustand";

export interface Ticker { symbol: string; price: number; change_24h: number; volume: number }
export interface Position { symbol: string; side: string; size: number; entry_price: number; take_profit?: number; stop_loss?: number; leverage: number; strategy: string }

interface Store {
  prices: Record<string, Ticker>;
  setPrices: (p: Record<string, Ticker>) => void;

  agentRunning: boolean;
  paperBalance: Record<string, number>;
  positions: Position[];
  setAgentStatus: (s: { is_running: boolean; paper_balance: Record<string, number>; positions?: Position[] }) => void;

  activePage: string;
  setPage: (p: string) => void;

  connected: boolean;
  setConnected: (v: boolean) => void;

  riskLevel: string;
  setRiskLevel: (v: string) => void;

  watchlist: string[];
  portfolioValue: number;
  setPortfolioValue: (v: number) => void;
  usePaper: boolean;
}

export const useStore = create<Store>((set) => ({
  prices: {},
  setPrices: (prices) => set({ prices }),

  agentRunning: false,
  paperBalance: { USDT: 10000 },
  positions: [],
  setAgentStatus: (s) => set({ agentRunning: s.is_running, paperBalance: s.paper_balance, positions: s.positions ?? [] }),

  activePage: "dashboard",
  setPage: (activePage) => set({ activePage }),

  connected: false,
  setConnected: (connected) => set({ connected }),

  riskLevel: "moderate",
  setRiskLevel: (riskLevel) => set({ riskLevel }),

  watchlist: ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT"],
  portfolioValue: 10000,
  setPortfolioValue: (portfolioValue) => set({ portfolioValue }),
  usePaper: true,
}));
