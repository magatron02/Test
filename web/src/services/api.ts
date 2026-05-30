import axios from "axios";

const client = axios.create({ baseURL: "/api/v1", timeout: 30000 });

export const api = {
  health:         ()                              => client.get("/health"),
  getPrices:      (symbols: string[])             => client.get("/prices", { params: { symbols: symbols.join(",") } }),
  getAgentStatus: ()                              => client.get("/agent/status"),
  startAgent:     (cfg: object)                   => client.post("/agent/start", cfg),
  stopAgent:      ()                              => client.post("/agent/stop"),
  analyzeMarket:  (params: { symbol: string; exchange: string }) =>
    client.post("/agent/analyze", null, { params: { exchange: params.exchange, symbol: params.symbol, portfolio_value: 10000, risk_level: "moderate" } }),
  placeTrade:     (params: object)                => client.post("/trade/manual", params),
  getMarket:      (exchange: string, symbol: string) => client.get(`/market/${exchange}/${encodeURIComponent(symbol)}`),
  runBacktest:    (params: object)                => client.post("/backtest", params),
  gridSetup:      (params: object)                => client.post("/grid/setup", params),
  getPortfolio:   (exchange: string)              => client.get(`/portfolio/${exchange}`),
};
