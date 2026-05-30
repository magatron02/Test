import axios from "axios";
import { useStore } from "../store";

const getClient = () => {
  const url = useStore.getState().backendUrl;
  return axios.create({
    baseURL: `${url}/api/v1`,
    timeout: 30000,
    headers: { "Content-Type": "application/json" },
  });
};

export const api = {
  health: () => getClient().get("/health"),

  getPrices: (symbols: string[]) =>
    getClient().get("/prices", { params: { symbols: symbols.join(",") } }),

  getMarketData: (exchange: string, symbol: string) =>
    getClient().get(`/market/${exchange}/${symbol}`),

  analyzeAndDecide: (exchange: string, symbol: string, portfolioValue: number, riskLevel: string) =>
    getClient().post("/agent/analyze", null, {
      params: { exchange, symbol, portfolio_value: portfolioValue, risk_level: riskLevel },
    }),

  startAgent: (config: {
    watchlist: string[];
    exchanges: string[];
    risk_level: string;
    portfolio_value: number;
    use_paper: boolean;
    interval_minutes: number;
  }) => getClient().post("/agent/start", config),

  stopAgent: () => getClient().post("/agent/stop"),

  getAgentStatus: () => getClient().get("/agent/status"),

  getPortfolio: (exchange: string) => getClient().get(`/portfolio/${exchange}`),

  setupGrid: (params: {
    exchange: string;
    symbol: string;
    investment: number;
    grid_count: number;
    upper_price?: number;
    lower_price?: number;
  }) => getClient().post("/grid/setup", params),

  manualTrade: (params: {
    exchange: string;
    symbol: string;
    side: string;
    amount: number;
    price?: number;
    leverage?: number;
    strategy?: string;
  }) => getClient().post("/trade/manual", params),
};
