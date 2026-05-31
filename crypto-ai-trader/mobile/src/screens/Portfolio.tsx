import React, { useState, useEffect } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator,
} from "react-native";
import { api } from "../services/api";
import { useStore } from "../store";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

type Tab = "paper" | "binance" | "okx" | "hyperliquid";

export const PortfolioScreen: React.FC = () => {
  const { agentStatus } = useStore();
  const [activeTab, setActiveTab] = useState<Tab>("paper");
  const [portfolio, setPortfolio] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPortfolio = async () => {
    setLoading(true);
    try {
      const res = await api.getPortfolio(activeTab);
      setPortfolio(res.data);
    } catch (e) {
      setPortfolio(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolio();
  }, [activeTab]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchPortfolio();
    setRefreshing(false);
  };

  const tabs: Tab[] = ["paper", "binance", "okx", "hyperliquid"];

  const renderPaperBalance = () => {
    const balance = agentStatus.paper_balance;
    const positions = agentStatus.positions || [];
    const total = Object.entries(balance).reduce((sum, [asset, amount]) => {
      return sum + (asset === "USDT" ? amount : 0);
    }, 0);

    return (
      <View>
        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Paper Portfolio</Text>
          <Text style={styles.summaryValue}>${total.toLocaleString("en-US", { maximumFractionDigits: 2 })}</Text>
          <Text style={styles.summaryNote}>Simulated trading - no real money</Text>
        </View>

        <Text style={styles.sectionTitle}>Balances</Text>
        {Object.entries(balance).map(([asset, amount]) => (
          <View key={asset} style={styles.balanceRow}>
            <View style={styles.assetBadge}>
              <Text style={styles.assetBadgeText}>{asset.substring(0, 2)}</Text>
            </View>
            <Text style={styles.assetName}>{asset}</Text>
            <Text style={styles.assetAmount}>{(amount as number).toLocaleString("en-US", { maximumFractionDigits: 6 })}</Text>
          </View>
        ))}

        {positions.length > 0 && (
          <>
            <Text style={[styles.sectionTitle, { marginTop: spacing.md }]}>Open Positions</Text>
            {positions.map((pos: any, i: number) => (
              <View key={i} style={styles.posCard}>
                <View style={styles.posHeader}>
                  <Text style={styles.posSymbol}>{pos.symbol}</Text>
                  <View style={[styles.posTypeBadge, pos.strategy === "futures" ? styles.futureBadge : styles.spotBadge]}>
                    <Text style={styles.posTypeText}>{pos.strategy?.toUpperCase()}</Text>
                  </View>
                </View>
                <View style={styles.posGrid}>
                  <PosItem label="Side" value={pos.side?.toUpperCase()} color={pos.side === "buy" ? colors.success : colors.danger} />
                  <PosItem label="Size" value={pos.size} />
                  <PosItem label="Entry" value={`$${pos.entry_price}`} />
                  <PosItem label="Leverage" value={`${pos.leverage}x`} />
                  {pos.take_profit && <PosItem label="Take Profit" value={`$${pos.take_profit}`} color={colors.success} />}
                  {pos.stop_loss && <PosItem label="Stop Loss" value={`$${pos.stop_loss}`} color={colors.danger} />}
                </View>
              </View>
            ))}
          </>
        )}

        {positions.length === 0 && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>No open positions</Text>
            <Text style={styles.emptySubtext}>Start the AI agent to begin trading</Text>
          </View>
        )}
      </View>
    );
  };

  const renderExchangePortfolio = () => {
    if (loading) return <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.xl }} />;
    if (!portfolio) return (
      <View style={styles.emptyState}>
        <Text style={styles.emptyText}>Unable to load</Text>
        <Text style={styles.emptySubtext}>Configure API keys in Wallet settings</Text>
      </View>
    );

    const balance = portfolio.balance || {};
    const positions = portfolio.positions || [];

    return (
      <View>
        <Text style={styles.sectionTitle}>Balances</Text>
        {Object.entries(balance).length === 0 ? (
          <Text style={styles.emptySubtext}>No balances found</Text>
        ) : (
          Object.entries(balance).map(([asset, info]: [string, any]) => (
            <View key={asset} style={styles.balanceRow}>
              <View style={styles.assetBadge}>
                <Text style={styles.assetBadgeText}>{asset.substring(0, 2)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.assetName}>{asset}</Text>
                <Text style={styles.assetSub}>Available: {info.free?.toFixed(6)}</Text>
              </View>
              <Text style={styles.assetAmount}>{info.total?.toFixed(6)}</Text>
            </View>
          ))
        )}

        {positions.length > 0 && (
          <>
            <Text style={[styles.sectionTitle, { marginTop: spacing.md }]}>Live Positions</Text>
            {positions.map((pos: any, i: number) => (
              <View key={i} style={styles.posCard}>
                <View style={styles.posHeader}>
                  <Text style={styles.posSymbol}>{pos.symbol}</Text>
                  <Text style={[styles.pnlText, (pos.unrealized_pnl || 0) >= 0 ? styles.profitText : styles.lossText]}>
                    {(pos.unrealized_pnl || 0) >= 0 ? "+" : ""}${(pos.unrealized_pnl || 0).toFixed(2)}
                  </Text>
                </View>
                <View style={styles.posGrid}>
                  <PosItem label="Side" value={pos.side?.toUpperCase()} color={pos.side === "long" ? colors.success : colors.danger} />
                  <PosItem label="Size" value={pos.size} />
                  <PosItem label="Entry" value={`$${pos.entry_price}`} />
                  <PosItem label="Mark" value={`$${pos.mark_price}`} />
                  <PosItem label="Leverage" value={`${pos.leverage}x`} />
                </View>
              </View>
            ))}
          </>
        )}
      </View>
    );
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <Text style={styles.title}>Portfolio</Text>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabRow}>
        {tabs.map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab === "paper" ? "Paper" : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {activeTab === "paper" ? renderPaperBalance() : renderExchangePortfolio()}
    </ScrollView>
  );
};

const PosItem = ({ label, value, color }: any) => (
  <View style={{ width: "50%", paddingVertical: 2 }}>
    <Text style={{ color: colors.textMuted, fontSize: fontSize.xs }}>{label}</Text>
    <Text style={{ color: color || colors.text, fontWeight: "600", fontSize: fontSize.sm }}>{value}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  title: { color: colors.text, fontSize: fontSize.xxl, fontWeight: "800", marginBottom: spacing.md },
  tabRow: { marginBottom: spacing.md },
  tab: {
    paddingHorizontal: spacing.md, paddingVertical: spacing.sm,
    borderRadius: borderRadius.full, borderWidth: 1,
    borderColor: colors.border, marginRight: spacing.sm,
    backgroundColor: colors.surface,
  },
  tabActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  tabText: { color: colors.textSecondary, fontSize: fontSize.sm, fontWeight: "600" },
  tabTextActive: { color: colors.text },
  summaryCard: {
    backgroundColor: colors.card, borderRadius: borderRadius.lg,
    padding: spacing.lg, alignItems: "center",
    marginBottom: spacing.md, borderWidth: 1, borderColor: colors.border,
  },
  summaryLabel: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.xs },
  summaryValue: { color: colors.text, fontSize: fontSize.xxxl, fontWeight: "800" },
  summaryNote: { color: colors.textMuted, fontSize: fontSize.xs, marginTop: spacing.xs },
  sectionTitle: { color: colors.text, fontWeight: "700", fontSize: fontSize.lg, marginBottom: spacing.sm },
  balanceRow: {
    flexDirection: "row", alignItems: "center", gap: spacing.sm,
    paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  assetBadge: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: colors.primary + "20", alignItems: "center", justifyContent: "center",
  },
  assetBadgeText: { color: colors.primary, fontWeight: "700", fontSize: fontSize.xs },
  assetName: { color: colors.text, fontWeight: "600", fontSize: fontSize.md },
  assetSub: { color: colors.textMuted, fontSize: fontSize.xs },
  assetAmount: { color: colors.text, fontWeight: "700", fontSize: fontSize.md },
  posCard: {
    backgroundColor: colors.card, borderRadius: borderRadius.md,
    padding: spacing.md, marginBottom: spacing.sm,
    borderWidth: 1, borderColor: colors.border,
  },
  posHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.sm },
  posSymbol: { color: colors.text, fontWeight: "700", fontSize: fontSize.md },
  posGrid: { flexDirection: "row", flexWrap: "wrap" },
  posTypeBadge: { paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: borderRadius.sm },
  spotBadge: { backgroundColor: colors.primary + "30" },
  futureBadge: { backgroundColor: colors.accent + "30" },
  posTypeText: { fontSize: fontSize.xs, color: colors.text, fontWeight: "700" },
  pnlText: { fontWeight: "700", fontSize: fontSize.md },
  profitText: { color: colors.success },
  lossText: { color: colors.danger },
  emptyState: { alignItems: "center", paddingVertical: spacing.xxl },
  emptyText: { color: colors.textSecondary, fontSize: fontSize.lg, fontWeight: "600" },
  emptySubtext: { color: colors.textMuted, fontSize: fontSize.sm, marginTop: spacing.xs },
});
