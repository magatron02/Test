import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, ActivityIndicator, Switch,
} from "react-native";
import { api } from "../services/api";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"];

export const TradingScreen: React.FC = () => {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"controls" | "manual" | "regime">("controls");

  // Kill switch + dry-run state
  const [killed, setKilled] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [controlLoading, setControlLoading] = useState(false);

  // Manual trade
  const [manualAction, setManualAction] = useState<"BUY" | "SELL" | "CLOSE">("BUY");
  const [amountUsdt, setAmountUsdt] = useState("100");

  // Regime data
  const [regimes, setRegimes] = useState<any>({});
  const [sentiment, setSentiment] = useState<any>(null);

  // ── Fetch kill-switch state on mount ──────────────────────────────
  useEffect(() => {
    fetchControlState();
  }, []);

  const fetchControlState = async () => {
    try {
      const res = await api.getKillSwitchStatus();
      setKilled(res.data.killed);
      setDryRun(res.data.dry_run);
    } catch (_) {}
  };

  // ── Kill switch ───────────────────────────────────────────────────
  const handleKillSwitch = async () => {
    const msg = killed
      ? "Resume trading? New trades will be allowed."
      : "Activate kill switch? All new trades will be halted immediately.";
    Alert.alert(killed ? "Resume Trading" : "Kill Switch", msg, [
      { text: "Cancel", style: "cancel" },
      {
        text: killed ? "Resume" : "Halt",
        style: killed ? "default" : "destructive",
        onPress: async () => {
          setControlLoading(true);
          try {
            if (killed) {
              await api.deactivateKillSwitch();
              setKilled(false);
            } else {
              await api.activateKillSwitch();
              setKilled(true);
            }
          } catch (e: any) {
            Alert.alert("Error", e.message);
          } finally {
            setControlLoading(false);
          }
        },
      },
    ]);
  };

  // ── Dry-run toggle ────────────────────────────────────────────────
  const handleDryRunToggle = async (value: boolean) => {
    try {
      await api.setDryRun(value);
      setDryRun(value);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    }
  };

  // ── Manual trade ──────────────────────────────────────────────────
  const handleManualTrade = async () => {
    if (!amountUsdt && manualAction !== "CLOSE")
      return Alert.alert("Error", "Enter USDT amount");
    setLoading(true);
    try {
      const res = await api.manualTrade({
        action: manualAction,
        symbol,
        amount_usdt: parseFloat(amountUsdt) || 0,
      });
      Alert.alert(
        "Order Placed",
        `${manualAction} ${symbol}\nStatus: ${res.data.status || "ok"}`,
      );
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || "Order failed";
      Alert.alert("Error", msg);
    } finally {
      setLoading(false);
    }
  };

  // ── Regime + sentiment ────────────────────────────────────────────
  const fetchRegimes = useCallback(async () => {
    setLoading(true);
    try {
      const [regRes, sentRes] = await Promise.all([
        api.getRegimes(),
        api.getSentiment(symbol),
      ]);
      setRegimes(regRes.data || {});
      setSentiment(sentRes.data);
    } catch (_) {}
    setLoading(false);
  }, [symbol]);

  useEffect(() => {
    if (activeTab === "regime") fetchRegimes();
  }, [activeTab, fetchRegimes]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Trading</Text>

      {/* ── Kill Switch status bar ─────────────────────────────────── */}
      <View style={[styles.statusBar, killed && styles.statusBarKilled]}>
        <Text style={styles.statusText}>
          {killed ? "⛔  TRADING HALTED" : "✅  TRADING ACTIVE"}
        </Text>
        {dryRun && (
          <View style={styles.dryRunBadge}>
            <Text style={styles.dryRunText}>DRY-RUN</Text>
          </View>
        )}
      </View>

      {/* ── Tabs ──────────────────────────────────────────────────── */}
      <View style={styles.tabRow}>
        {(["controls", "manual", "regime"] as const).map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab === "controls" ? "Controls" : tab === "manual" ? "Manual Trade" : "Regime"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Controls tab ──────────────────────────────────────────── */}
      {activeTab === "controls" && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Kill Switch</Text>
          <Text style={styles.hint}>
            Immediately stops all new trades. Existing open positions are not closed.
          </Text>
          <TouchableOpacity
            style={[styles.killBtn, killed && styles.resumeBtn]}
            onPress={handleKillSwitch}
            disabled={controlLoading}
          >
            {controlLoading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.killBtnText}>
                {killed ? "▶  Resume Trading" : "⛔  Activate Kill Switch"}
              </Text>
            )}
          </TouchableOpacity>

          <View style={styles.divider} />

          <Text style={styles.sectionTitle}>Paper Trade (Dry-Run)</Text>
          <Text style={styles.hint}>
            Orders are logged but never sent to the exchange.
          </Text>
          <View style={styles.row}>
            <Text style={styles.label}>Dry-run mode</Text>
            <Switch
              value={dryRun}
              onValueChange={handleDryRunToggle}
              trackColor={{ false: colors.border, true: colors.primary }}
              thumbColor={dryRun ? colors.text : colors.textMuted}
            />
          </View>
        </View>
      )}

      {/* ── Manual Trade tab ──────────────────────────────────────── */}
      {activeTab === "manual" && (
        <View style={styles.card}>
          <Text style={styles.label}>Symbol</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.sm }}>
            {SYMBOLS.map((s) => (
              <TouchableOpacity
                key={s}
                style={[styles.chip, symbol === s && styles.chipActive]}
                onPress={() => setSymbol(s)}
              >
                <Text style={[styles.chipText, symbol === s && styles.chipTextActive]}>{s}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <Text style={styles.label}>Action</Text>
          <View style={styles.actionRow}>
            {(["BUY", "SELL", "CLOSE"] as const).map((a) => (
              <TouchableOpacity
                key={a}
                style={[
                  styles.actionBtn,
                  manualAction === a && (a === "BUY" ? styles.buyActive : a === "SELL" ? styles.sellActive : styles.closeActive),
                ]}
                onPress={() => setManualAction(a)}
              >
                <Text style={[styles.actionText, manualAction === a && styles.actionTextActive]}>{a}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {manualAction !== "CLOSE" && (
            <>
              <Text style={styles.label}>Amount (USDT)</Text>
              <TextInput
                style={styles.input}
                value={amountUsdt}
                onChangeText={setAmountUsdt}
                keyboardType="numeric"
                placeholder="100"
                placeholderTextColor={colors.textMuted}
              />
            </>
          )}

          {dryRun && (
            <View style={styles.dryRunNotice}>
              <Text style={styles.dryRunNoticeText}>
                📄 Dry-run active — order will be logged, not executed
              </Text>
            </View>
          )}

          <TouchableOpacity
            style={[
              styles.primaryBtn,
              manualAction === "SELL" && styles.sellPrimaryBtn,
              manualAction === "CLOSE" && styles.closePrimaryBtn,
            ]}
            onPress={handleManualTrade}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.primaryBtnText}>
                {manualAction} {symbol}
              </Text>
            )}
          </TouchableOpacity>
        </View>
      )}

      {/* ── Regime tab ────────────────────────────────────────────── */}
      {activeTab === "regime" && (
        <View>
          <TouchableOpacity style={styles.refreshBtn} onPress={fetchRegimes} disabled={loading}>
            {loading ? <ActivityIndicator color={colors.primary} /> : <Text style={styles.refreshText}>↻ Refresh</Text>}
          </TouchableOpacity>

          {Object.entries(regimes).map(([sym, data]: any) => (
            <View key={sym} style={styles.card}>
              <Text style={styles.regimeSymbol}>{sym}</Text>
              <View style={styles.row}>
                <Text style={styles.regimeLabel}>Regime</Text>
                <Text style={[styles.regimeValue, { color: regimeColor(data.regime) }]}>
                  {data.regime}
                </Text>
              </View>
              <View style={styles.row}>
                <Text style={styles.regimeLabel}>Confidence</Text>
                <Text style={styles.regimeValue}>{(data.confidence * 100).toFixed(0)}%</Text>
              </View>
              <View style={styles.row}>
                <Text style={styles.regimeLabel}>ADX</Text>
                <Text style={styles.regimeValue}>{data.adx?.toFixed(1)}</Text>
              </View>
            </View>
          ))}

          {sentiment && (
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Market Sentiment — {symbol}</Text>
              <View style={styles.row}>
                <Text style={styles.regimeLabel}>Fear & Greed</Text>
                <Text style={styles.regimeValue}>
                  {sentiment.fear_greed?.value} ({sentiment.fear_greed?.label})
                </Text>
              </View>
              <View style={styles.row}>
                <Text style={styles.regimeLabel}>Trading Bias</Text>
                <Text style={[styles.regimeValue, { color: biasColor(sentiment.fear_greed?.trading_bias) }]}>
                  {sentiment.fear_greed?.trading_bias}
                </Text>
              </View>
              {sentiment.funding_rate?.rate_pct != null && (
                <View style={styles.row}>
                  <Text style={styles.regimeLabel}>Funding Rate</Text>
                  <Text style={styles.regimeValue}>{sentiment.funding_rate.rate_pct?.toFixed(4)}%</Text>
                </View>
              )}
            </View>
          )}
        </View>
      )}
    </ScrollView>
  );
};

function regimeColor(regime: string): string {
  if (!regime) return colors.text;
  if (regime.includes("BULL")) return colors.success;
  if (regime.includes("BEAR") || regime === "CRASH") return colors.danger;
  if (regime === "VOLATILE") return colors.warning;
  return colors.textSecondary;
}

function biasColor(bias: string): string {
  if (!bias) return colors.text;
  if (bias.includes("BUY")) return colors.success;
  if (bias.includes("SELL")) return colors.danger;
  return colors.textSecondary;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  title: { color: colors.text, fontSize: fontSize.xxl, fontWeight: "800", marginBottom: spacing.sm },

  statusBar: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    backgroundColor: colors.success + "18", borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md, paddingVertical: spacing.sm,
    borderWidth: 1, borderColor: colors.success + "40", marginBottom: spacing.md,
  },
  statusBarKilled: {
    backgroundColor: colors.danger + "18", borderColor: colors.danger + "40",
  },
  statusText: { color: colors.text, fontWeight: "700", fontSize: fontSize.sm },
  dryRunBadge: {
    backgroundColor: colors.primary + "30", paddingHorizontal: spacing.sm,
    paddingVertical: 2, borderRadius: borderRadius.sm,
  },
  dryRunText: { color: colors.primary, fontSize: fontSize.xs, fontWeight: "700" },

  tabRow: {
    flexDirection: "row", marginBottom: spacing.md,
    backgroundColor: colors.surface, borderRadius: borderRadius.md, padding: 4,
  },
  tab: { flex: 1, paddingVertical: spacing.sm, borderRadius: borderRadius.sm, alignItems: "center" },
  tabActive: { backgroundColor: colors.card },
  tabText: { color: colors.textMuted, fontSize: fontSize.sm },
  tabTextActive: { color: colors.text, fontWeight: "700" },

  card: {
    backgroundColor: colors.card, borderRadius: borderRadius.lg,
    padding: spacing.md, borderWidth: 1, borderColor: colors.border,
    marginBottom: spacing.md,
  },
  sectionTitle: { color: colors.text, fontWeight: "700", fontSize: fontSize.md, marginBottom: spacing.xs },
  hint: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.md, lineHeight: 20 },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: spacing.md },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 4 },
  label: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.xs },

  killBtn: {
    backgroundColor: colors.danger, borderRadius: borderRadius.md,
    padding: spacing.md, alignItems: "center", marginTop: spacing.sm,
  },
  resumeBtn: { backgroundColor: colors.success },
  killBtnText: { color: "#fff", fontWeight: "700", fontSize: fontSize.md },

  chip: {
    paddingHorizontal: spacing.md, paddingVertical: spacing.xs,
    borderRadius: borderRadius.full, borderWidth: 1,
    borderColor: colors.border, marginRight: spacing.sm,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: fontSize.sm, fontWeight: "600" },
  chipTextActive: { color: colors.text },

  actionRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.sm },
  actionBtn: {
    flex: 1, padding: spacing.sm, borderRadius: borderRadius.md,
    alignItems: "center", backgroundColor: colors.surface,
    borderWidth: 1, borderColor: colors.border,
  },
  buyActive: { backgroundColor: colors.success + "30", borderColor: colors.success },
  sellActive: { backgroundColor: colors.danger + "30", borderColor: colors.danger },
  closeActive: { backgroundColor: colors.primary + "30", borderColor: colors.primary },
  actionText: { color: colors.textMuted, fontWeight: "700", fontSize: fontSize.sm },
  actionTextActive: { color: colors.text },

  input: {
    backgroundColor: colors.surface, borderRadius: borderRadius.md,
    padding: spacing.sm, color: colors.text, fontSize: fontSize.md,
    borderWidth: 1, borderColor: colors.border, marginBottom: spacing.sm,
  },
  dryRunNotice: {
    backgroundColor: colors.primary + "15", borderRadius: borderRadius.sm,
    padding: spacing.sm, marginBottom: spacing.sm,
  },
  dryRunNoticeText: { color: colors.primary, fontSize: fontSize.sm },

  primaryBtn: {
    backgroundColor: colors.success, borderRadius: borderRadius.md,
    padding: spacing.md, alignItems: "center", marginTop: spacing.sm,
  },
  sellPrimaryBtn: { backgroundColor: colors.danger },
  closePrimaryBtn: { backgroundColor: colors.primary },
  primaryBtnText: { color: "#fff", fontWeight: "700", fontSize: fontSize.md },

  refreshBtn: { alignItems: "flex-end", marginBottom: spacing.sm },
  refreshText: { color: colors.primary, fontSize: fontSize.sm, fontWeight: "600" },

  regimeSymbol: { color: colors.text, fontWeight: "700", fontSize: fontSize.md, marginBottom: spacing.xs },
  regimeLabel: { color: colors.textSecondary, fontSize: fontSize.sm },
  regimeValue: { color: colors.text, fontWeight: "600", fontSize: fontSize.sm },
});
