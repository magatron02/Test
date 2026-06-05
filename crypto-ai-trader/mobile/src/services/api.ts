import axios from "axios";
import { useStore } from "../store";

const getClient = () => {
  const url = useStore.getState().backendUrl;
  return axios.create({
    baseURL: `${url}/api`,   // backend prefix is /api (not /api/v1)
    timeout: 30000,
    headers: { "Content-Type": "application/json" },
  });
};

export const api = {
  // ── System ──────────────────────────────────────────────────────────
  health: () => getClient().get("/status"),

  getStatus: () => getClient().get("/status"),

  // ── Prices ──────────────────────────────────────────────────────────
  getPrices: () => getClient().get("/prices"),

  // ── Portfolio ────────────────────────────────────────────────────────
  getPortfolio: () => getClient().get("/portfolio"),

  getPortfolioStats: () => getClient().get("/portfolio/stats"),

  getBalances: () => getClient().get("/balances"),

  getPositions: () => getClient().get("/positions"),

  getHrpWeights: () => getClient().get("/portfolio/hrp"),

  // ── Trading ──────────────────────────────────────────────────────────
  getKillSwitchStatus: () => getClient().get("/trading/kill-switch"),

  activateKillSwitch: () =>
    getClient().post("/trading/kill-switch", null, { params: { action: "activate" } }),

  deactivateKillSwitch: () =>
    getClient().post("/trading/kill-switch", null, { params: { action: "deactivate" } }),

  setDryRun: (enabled: boolean) =>
    getClient().post("/trading/dry-run", null, { params: { enabled } }),

  manualTrade: (params: {
    action: "BUY" | "SELL" | "CLOSE";
    symbol: string;
    amount_usdt?: number;
  }) => getClient().post("/trade/manual", params),

  // ── Analysis ─────────────────────────────────────────────────────────
  getRegimes: () => getClient().get("/regimes"),

  getSentiment: (symbol = "BTC/USDT") =>
    getClient().get("/sentiment", { params: { symbol } }),

  getRiskState: () => getClient().get("/risk"),

  getPatterns: (symbol = "BTC/USDT") =>
    getClient().get("/patterns", { params: { symbol } }),

  getAnalytics: (symbol?: string, days = 30) =>
    getClient().get("/analytics", { params: { symbol, days } }),

  // ── ML ───────────────────────────────────────────────────────────────
  getFeatureImportance: () => getClient().get("/ml/feature-importance"),

  getSizerStats: () => getClient().get("/sizer/stats"),

  // ── Pairs trading ────────────────────────────────────────────────────
  getCointegrationPairs: () => getClient().get("/pairs/cointegration"),

  // ── Backtest ─────────────────────────────────────────────────────────
  runBacktest: (params: {
    symbol?: string;
    days?: number;
    tp_pct?: number;
    sl_pct?: number;
    initial_capital?: number;
  }) => getClient().post("/backtest", params),

  runWalkforward: (params: {
    symbol?: string;
    days?: number;
    folds?: number;
    tp_pct?: number;
    sl_pct?: number;
    initial_capital?: number;
  }) => getClient().get("/backtest/walkforward", { params }),

  // ── Trades ───────────────────────────────────────────────────────────
  getTrades: (limit = 50) =>
    getClient().get("/trades", { params: { limit } }),

  // ── Settings ─────────────────────────────────────────────────────────
  getSettings: () => getClient().get("/settings"),

  updateSettings: (data: Record<string, Record<string, unknown>>) =>
    getClient().post("/settings", data),

  // ── Notifications ─────────────────────────────────────────────────────
  getNotifications: () => getClient().get("/notifications"),

  clearNotifications: () => getClient().delete("/notifications"),
};
