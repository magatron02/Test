import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { useStore } from "../store";
import { api } from "../services/api";
import { wsService } from "../services/websocket";
import { PriceCard } from "../components/PriceCard";
import { AgentStatusCard } from "../components/AgentStatusCard";
import { PortfolioChart } from "../components/PortfolioChart";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

const WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"];

export const DashboardScreen: React.FC = () => {
  const {
    prices, setPrices,
    agentStatus, setAgentStatus,
    agentConfig,
    totalValue, dailyPnl, totalPnl,
    isConnected,
  } = useStore();

  const [refreshing, setRefreshing] = useState(false);
  const [agentLoading, setAgentLoading] = useState(false);

  useEffect(() => {
    wsService.connect();

    const handlePrices = (data: any) => {
      setPrices(data);
    };
    const handleStatus = (data: any) => {
      setAgentStatus(data);
    };

    wsService.on("prices", handlePrices);
    wsService.on("agent_status", handleStatus);

    return () => {
      wsService.off("prices", handlePrices);
      wsService.off("agent_status", handleStatus);
    };
  }, []);

  const fetchData = async () => {
    try {
      const [pricesRes, statusRes] = await Promise.all([
        api.getPrices(),
        api.getStatus(),
      ]);
      if (pricesRes.data) setPrices(pricesRes.data);
      if (statusRes.data) setAgentStatus(statusRes.data);
    } catch {}
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, []);

  const handleToggleAgent = async () => {
    setAgentLoading(true);
    try {
      // The backend auto-starts via the startup event.
      // The kill switch is the proper way to halt/resume trading.
      const res = await api.getStatus();
      setAgentStatus(res.data);
    } catch (e) {
      console.error("Status fetch error:", e);
    } finally {
      setAgentLoading(false);
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
      }
    >
      <View style={styles.headerRow}>
        <Text style={styles.greeting}>CryptoAI Trader</Text>
        <View style={[styles.connDot, isConnected ? styles.connActive : styles.connInactive]} />
      </View>

      <PortfolioChart
        totalValue={agentStatus.paper_balance?.USDT || totalValue}
        dailyPnl={dailyPnl}
        totalPnl={totalPnl}
      />

      <AgentStatusCard
        isRunning={agentStatus.is_running}
        openPositions={agentStatus.open_positions}
        paperBalance={agentStatus.paper_balance}
        onToggle={handleToggleAgent}
        loading={agentLoading}
      />

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Market Prices</Text>
        <TouchableOpacity>
          <Text style={styles.seeAll}>See all</Text>
        </TouchableOpacity>
      </View>

      {WATCHLIST.map((symbol) => {
        const data = prices[symbol];
        return (
          <PriceCard
            key={symbol}
            symbol={symbol}
            price={data?.price || 0}
            change24h={data?.change_24h || 0}
            volume={data?.volume}
          />
        );
      })}

      {agentStatus.positions && agentStatus.positions.length > 0 && (
        <>
          <Text style={[styles.sectionTitle, { marginTop: spacing.md }]}>Open Positions</Text>
          {agentStatus.positions.map((pos, i) => (
            <View key={i} style={styles.positionCard}>
              <View style={styles.positionHeader}>
                <Text style={styles.posSymbol}>{pos.symbol}</Text>
                <View style={[styles.sideBadge, pos.side === "buy" || pos.side === "long" ? styles.longBadge : styles.shortBadge]}>
                  <Text style={styles.sideText}>{pos.side.toUpperCase()}</Text>
                </View>
              </View>
              <View style={styles.posStats}>
                <View>
                  <Text style={styles.posLabel}>Entry</Text>
                  <Text style={styles.posValue}>${pos.entry_price}</Text>
                </View>
                <View>
                  <Text style={styles.posLabel}>Size</Text>
                  <Text style={styles.posValue}>{pos.size}</Text>
                </View>
                <View>
                  <Text style={styles.posLabel}>Leverage</Text>
                  <Text style={styles.posValue}>{pos.leverage}x</Text>
                </View>
              </View>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
    paddingTop: spacing.sm,
  },
  greeting: {
    color: colors.text,
    fontSize: fontSize.xl,
    fontWeight: "800",
  },
  connDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  connActive: { backgroundColor: colors.success },
  connInactive: { backgroundColor: colors.danger },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: fontSize.lg,
    fontWeight: "700",
  },
  seeAll: {
    color: colors.primary,
    fontSize: fontSize.sm,
  },
  positionCard: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  positionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  posSymbol: {
    color: colors.text,
    fontWeight: "700",
    fontSize: fontSize.md,
  },
  sideBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  longBadge: { backgroundColor: colors.success + "30" },
  shortBadge: { backgroundColor: colors.danger + "30" },
  sideText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
    color: colors.text,
  },
  posStats: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  posLabel: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
  },
  posValue: {
    color: colors.text,
    fontWeight: "600",
    fontSize: fontSize.sm,
  },
});
