import { create } from "zustand";
import AsyncStorage from "@react-native-async-storage/async-storage";

export interface Position {
  symbol: string;
  side: string;
  size: number;
  entry_price: number;
  take_profit?: number;
  stop_loss?: number;
  leverage: number;
  strategy: string;
  unrealized_pnl?: number;
}

export interface Trade {
  id: string;
  symbol: string;
  side: string;
  strategy: string;
  entry_price: number;
  exit_price?: number;
  size: number;
  pnl?: number;
  status: string;
  reasoning: string;
  confidence: number;
  created_at: string;
}

export interface AgentStatus {
  is_running: boolean;
  paper_balance: Record<string, number>;
  open_positions: number;
  positions: Position[];
}

export interface MarketData {
  symbol: string;
  price: number;
  change_24h: number;
  volume: number;
}

export interface AppState {
  // Connection
  backendUrl: string;
  isConnected: boolean;
  setBackendUrl: (url: string) => void;
  setConnected: (v: boolean) => void;

  // Wallet
  walletAddress: string | null;
  walletConnected: boolean;
  setWallet: (address: string | null) => void;

  // Exchange Keys
  exchangeKeys: Record<string, { apiKey: string; secret: string; passphrase?: string }>;
  setExchangeKey: (exchange: string, key: string, secret: string, passphrase?: string) => void;

  // Agent
  agentStatus: AgentStatus;
  setAgentStatus: (status: AgentStatus) => void;

  // Config
  agentConfig: {
    watchlist: string[];
    exchanges: string[];
    riskLevel: string;
    portfolioValue: number;
    usePaper: boolean;
    intervalMinutes: number;
  };
  setAgentConfig: (config: Partial<AppState["agentConfig"]>) => void;

  // Market
  prices: Record<string, MarketData>;
  setPrices: (prices: Record<string, MarketData>) => void;

  // Trades
  recentTrades: Trade[];
  addTrade: (trade: Trade) => void;

  // Portfolio
  totalValue: number;
  dailyPnl: number;
  totalPnl: number;
  setPortfolio: (value: number, dailyPnl: number, totalPnl: number) => void;
}

export const useStore = create<AppState>((set, get) => ({
  backendUrl: "http://localhost:8000",
  isConnected: false,
  setBackendUrl: (url) => {
    set({ backendUrl: url });
    AsyncStorage.setItem("backendUrl", url);
  },
  setConnected: (v) => set({ isConnected: v }),

  walletAddress: null,
  walletConnected: false,
  setWallet: (address) =>
    set({ walletAddress: address, walletConnected: !!address }),

  exchangeKeys: {},
  setExchangeKey: (exchange, apiKey, secret, passphrase) =>
    set((state) => ({
      exchangeKeys: {
        ...state.exchangeKeys,
        [exchange]: { apiKey, secret, passphrase },
      },
    })),

  agentStatus: {
    is_running: false,
    paper_balance: { USDT: 10000 },
    open_positions: 0,
    positions: [],
  },
  setAgentStatus: (status) => set({ agentStatus: status }),

  agentConfig: {
    watchlist: ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    exchanges: ["binance"],
    riskLevel: "medium",
    portfolioValue: 10000,
    usePaper: true,
    intervalMinutes: 60,
  },
  setAgentConfig: (config) =>
    set((state) => ({
      agentConfig: { ...state.agentConfig, ...config },
    })),

  prices: {},
  setPrices: (prices) => set({ prices }),

  recentTrades: [],
  addTrade: (trade) =>
    set((state) => ({
      recentTrades: [trade, ...state.recentTrades].slice(0, 50),
    })),

  totalValue: 10000,
  dailyPnl: 0,
  totalPnl: 0,
  setPortfolio: (totalValue, dailyPnl, totalPnl) =>
    set({ totalValue, dailyPnl, totalPnl }),
}));
