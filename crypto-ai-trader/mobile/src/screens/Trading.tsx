import React, { useState } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, ActivityIndicator,
} from "react-native";
import { api } from "../services/api";
import { useStore } from "../store";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

type Strategy = "spot" | "futures" | "perpetual" | "grid";
type Exchange = "binance" | "okx" | "hyperliquid" | "paper";

export const TradingScreen: React.FC = () => {
  const { agentConfig } = useStore();
  const [strategy, setStrategy] = useState<Strategy>("spot");
  const [exchange, setExchange] = useState<Exchange>("binance");
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"ai" | "manual" | "grid">("ai");

  // Manual order
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [amount, setAmount] = useState("");
  const [price, setPrice] = useState("");
  const [leverage, setLeverage] = useState("3");

  // Grid
  const [investment, setInvestment] = useState("1000");
  const [gridCount, setGridCount] = useState("10");
  const [gridResult, setGridResult] = useState<any>(null);

  const handleAIAnalyze = async () => {
    setLoading(true);
    setAnalysis(null);
    try {
      const res = await api.analyzeAndDecide(
        exchange, symbol, agentConfig.portfolioValue, agentConfig.riskLevel
      );
      setAnalysis(res.data);
    } catch (e: any) {
      Alert.alert("Error", e.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleManualTrade = async () => {
    if (!amount) return Alert.alert("Error", "Enter amount");
    setLoading(true);
    try {
      const res = await api.manualTrade({
        exchange,
        symbol,
        side,
        amount: parseFloat(amount),
        price: price ? parseFloat(price) : undefined,
        leverage: parseInt(leverage),
        strategy,
      });
      Alert.alert("Order Placed", JSON.stringify(res.data, null, 2));
    } catch (e: any) {
      Alert.alert("Error", e.message || "Order failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGridSetup = async () => {
    setLoading(true);
    setGridResult(null);
    try {
      const res = await api.setupGrid({
        exchange,
        symbol,
        investment: parseFloat(investment),
        grid_count: parseInt(gridCount),
      });
      setGridResult(res.data);
    } catch (e: any) {
      Alert.alert("Error", e.message || "Grid setup failed");
    } finally {
      setLoading(false);
    }
  };

  const strategies: Strategy[] = ["spot", "futures", "perpetual", "grid"];
  const exchanges: Exchange[] = ["binance", "okx", "hyperliquid", "paper"];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Trading Terminal</Text>

      <Text style={styles.label}>Exchange</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow}>
        {exchanges.map((ex) => (
          <TouchableOpacity
            key={ex}
            style={[styles.chip, exchange === ex && styles.chipActive]}
            onPress={() => setExchange(ex)}
          >
            <Text style={[styles.chipText, exchange === ex && styles.chipTextActive]}>
              {ex.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={styles.label}>Strategy</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow}>
        {strategies.map((s) => (
          <TouchableOpacity
            key={s}
            style={[styles.chip, strategy === s && styles.chipActive]}
            onPress={() => setStrategy(s)}
          >
            <Text style={[styles.chipText, strategy === s && styles.chipTextActive]}>
              {s.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={styles.label}>Symbol</Text>
      <TextInput
        style={styles.input}
        value={symbol}
        onChangeText={(t) => setSymbol(t.toUpperCase())}
        placeholder="e.g. BTC/USDT"
        placeholderTextColor={colors.textMuted}
        autoCapitalize="characters"
      />

      <View style={styles.tabRow}>
        {(["ai", "manual", "grid"] as const).map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab === "ai" ? "AI Analysis" : tab === "manual" ? "Manual" : "Grid Setup"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {activeTab === "ai" && (
        <View style={styles.panel}>
          <Text style={styles.panelDesc}>
            AI will analyze {symbol} on {exchange} and suggest a trade with entry, TP, SL, and reasoning.
          </Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={handleAIAnalyze} disabled={loading}>
            {loading ? <ActivityIndicator color={colors.text} /> : <Text style={styles.primaryBtnText}>Analyze with AI</Text>}
          </TouchableOpacity>

          {analysis && (
            <View style={styles.analysisCard}>
              <View style={styles.decisionHeader}>
                <Text style={styles.decisionAction}>{analysis.decision?.action?.toUpperCase()}</Text>
                <View style={[styles.confBadge, { backgroundColor: analysis.decision?.confidence > 0.7 ? colors.success + "30" : colors.warning + "30" }]}>
                  <Text style={{ color: analysis.decision?.confidence > 0.7 ? colors.success : colors.warning, fontWeight: "700" }}>
                    {(analysis.decision?.confidence * 100).toFixed(0)}%
                  </Text>
                </View>
              </View>

              <Text style={styles.reasoning}>{analysis.decision?.reasoning}</Text>

              {analysis.decision?.action !== "hold" && (
                <View style={styles.levels}>
                  <LevelRow label="Entry" value={analysis.decision?.entry_price} />
                  <LevelRow label="Take Profit" value={analysis.decision?.take_profit} color={colors.success} />
                  <LevelRow label="Stop Loss" value={analysis.decision?.stop_loss} color={colors.danger} />
                  <LevelRow label="R:R Ratio" value={analysis.decision?.risk_reward_ratio} suffix="x" />
                </View>
              )}

              {analysis.decision?.key_signals && (
                <View style={styles.signals}>
                  {analysis.decision.key_signals.map((s: string, i: number) => (
                    <View key={i} style={styles.signalBadge}>
                      <Text style={styles.signalText}>{s}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}
        </View>
      )}

      {activeTab === "manual" && (
        <View style={styles.panel}>
          <View style={styles.sideRow}>
            <TouchableOpacity
              style={[styles.sideBtn, side === "buy" && styles.buyBtn]}
              onPress={() => setSide("buy")}
            >
              <Text style={styles.sideBtnText}>BUY / LONG</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.sideBtn, side === "sell" && styles.sellBtn]}
              onPress={() => setSide("sell")}
            >
              <Text style={styles.sideBtnText}>SELL / SHORT</Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.label}>Amount</Text>
          <TextInput
            style={styles.input}
            value={amount}
            onChangeText={setAmount}
            keyboardType="numeric"
            placeholder="0.001"
            placeholderTextColor={colors.textMuted}
          />

          <Text style={styles.label}>Price (leave empty for market)</Text>
          <TextInput
            style={styles.input}
            value={price}
            onChangeText={setPrice}
            keyboardType="numeric"
            placeholder="Market price"
            placeholderTextColor={colors.textMuted}
          />

          {(strategy === "futures" || strategy === "perpetual") && (
            <>
              <Text style={styles.label}>Leverage</Text>
              <TextInput
                style={styles.input}
                value={leverage}
                onChangeText={setLeverage}
                keyboardType="numeric"
                placeholder="3"
                placeholderTextColor={colors.textMuted}
              />
            </>
          )}

          <TouchableOpacity
            style={[styles.primaryBtn, side === "sell" && styles.sellPrimaryBtn]}
            onPress={handleManualTrade}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color={colors.text} />
            ) : (
              <Text style={styles.primaryBtnText}>{side === "buy" ? "Place Buy Order" : "Place Sell Order"}</Text>
            )}
          </TouchableOpacity>
        </View>
      )}

      {activeTab === "grid" && (
        <View style={styles.panel}>
          <Text style={styles.panelDesc}>
            Grid trading automatically buys low and sells high within a price range.
          </Text>

          <Text style={styles.label}>Investment (USDT)</Text>
          <TextInput
            style={styles.input}
            value={investment}
            onChangeText={setInvestment}
            keyboardType="numeric"
            placeholder="1000"
            placeholderTextColor={colors.textMuted}
          />

          <Text style={styles.label}>Number of Grids</Text>
          <TextInput
            style={styles.input}
            value={gridCount}
            onChangeText={setGridCount}
            keyboardType="numeric"
            placeholder="10"
            placeholderTextColor={colors.textMuted}
          />

          <TouchableOpacity style={styles.primaryBtn} onPress={handleGridSetup} disabled={loading}>
            {loading ? <ActivityIndicator color={colors.text} /> : <Text style={styles.primaryBtnText}>Calculate Grid</Text>}
          </TouchableOpacity>

          {gridResult && (
            <View style={styles.gridResult}>
              <Text style={styles.gridTitle}>Grid Parameters</Text>
              <LevelRow label="Current Price" value={gridResult.current_price} prefix="$" />
              <LevelRow label="Upper Range" value={gridResult.grid_params?.upper_price} prefix="$" color={colors.success} />
              <LevelRow label="Lower Range" value={gridResult.grid_params?.lower_price} prefix="$" color={colors.danger} />
              <LevelRow label="Grid Spacing" value={gridResult.grid_params?.grid_spacing} prefix="$" />
              <LevelRow label="Per Grid" value={gridResult.grid_params?.per_grid_investment} prefix="$" />
              <LevelRow label="Est. Daily Profit" value={gridResult.grid_params?.estimated_daily_profit_pct} suffix="%" color={colors.success} />
            </View>
          )}
        </View>
      )}
    </ScrollView>
  );
};

const LevelRow = ({ label, value, color, prefix = "", suffix = "" }: any) => (
  <View style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 }}>
    <Text style={{ color: colors.textSecondary, fontSize: fontSize.sm }}>{label}</Text>
    <Text style={{ color: color || colors.text, fontWeight: "600", fontSize: fontSize.sm }}>
      {prefix}{typeof value === "number" ? value.toLocaleString("en-US", { maximumFractionDigits: 4 }) : value || "-"}{suffix}
    </Text>
  </View>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  title: { color: colors.text, fontSize: fontSize.xxl, fontWeight: "800", marginBottom: spacing.md },
  label: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.xs, marginTop: spacing.sm },
  chipRow: { marginBottom: spacing.sm },
  chip: {
    paddingHorizontal: spacing.md, paddingVertical: spacing.xs,
    borderRadius: borderRadius.full, borderWidth: 1,
    borderColor: colors.border, marginRight: spacing.sm,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: fontSize.sm, fontWeight: "600" },
  chipTextActive: { color: colors.text },
  input: {
    backgroundColor: colors.card, borderRadius: borderRadius.md,
    padding: spacing.sm, color: colors.text, fontSize: fontSize.md,
    borderWidth: 1, borderColor: colors.border,
  },
  tabRow: {
    flexDirection: "row", marginVertical: spacing.md,
    backgroundColor: colors.surface, borderRadius: borderRadius.md, padding: 4,
  },
  tab: { flex: 1, paddingVertical: spacing.sm, borderRadius: borderRadius.sm, alignItems: "center" },
  tabActive: { backgroundColor: colors.card },
  tabText: { color: colors.textMuted, fontSize: fontSize.sm },
  tabTextActive: { color: colors.text, fontWeight: "700" },
  panel: { backgroundColor: colors.card, borderRadius: borderRadius.lg, padding: spacing.md, borderWidth: 1, borderColor: colors.border },
  panelDesc: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.md, lineHeight: 20 },
  primaryBtn: {
    backgroundColor: colors.primary, borderRadius: borderRadius.md,
    padding: spacing.md, alignItems: "center", marginTop: spacing.md,
  },
  primaryBtnText: { color: colors.text, fontWeight: "700", fontSize: fontSize.md },
  sellPrimaryBtn: { backgroundColor: colors.danger },
  analysisCard: { marginTop: spacing.md, padding: spacing.md, backgroundColor: colors.surface, borderRadius: borderRadius.md },
  decisionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.sm },
  decisionAction: { color: colors.text, fontWeight: "800", fontSize: fontSize.xl },
  confBadge: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: borderRadius.sm },
  reasoning: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.md, lineHeight: 20 },
  levels: { borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm },
  signals: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginTop: spacing.sm },
  signalBadge: { backgroundColor: colors.primary + "20", paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: borderRadius.sm },
  signalText: { color: colors.primary, fontSize: fontSize.xs, fontWeight: "600" },
  sideRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.sm },
  sideBtn: {
    flex: 1, padding: spacing.sm, borderRadius: borderRadius.md,
    alignItems: "center", backgroundColor: colors.surface,
    borderWidth: 1, borderColor: colors.border,
  },
  buyBtn: { backgroundColor: colors.success + "30", borderColor: colors.success },
  sellBtn: { backgroundColor: colors.danger + "30", borderColor: colors.danger },
  sideBtnText: { color: colors.text, fontWeight: "700", fontSize: fontSize.sm },
  gridResult: { marginTop: spacing.md, padding: spacing.md, backgroundColor: colors.surface, borderRadius: borderRadius.md },
  gridTitle: { color: colors.text, fontWeight: "700", fontSize: fontSize.md, marginBottom: spacing.sm },
});
