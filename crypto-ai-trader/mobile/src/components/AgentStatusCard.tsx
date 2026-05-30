import React from "react";
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from "react-native";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

interface AgentStatusCardProps {
  isRunning: boolean;
  openPositions: number;
  paperBalance: Record<string, number>;
  onToggle: () => void;
  loading?: boolean;
}

export const AgentStatusCard: React.FC<AgentStatusCardProps> = ({
  isRunning,
  openPositions,
  paperBalance,
  onToggle,
  loading,
}) => {
  const usdtBalance = paperBalance?.USDT || 0;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <View style={[styles.statusDot, isRunning ? styles.dotActive : styles.dotInactive]} />
          <Text style={styles.title}>AI Trading Agent</Text>
        </View>
        <TouchableOpacity
          style={[styles.toggleBtn, isRunning ? styles.stopBtn : styles.startBtn]}
          onPress={onToggle}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color={colors.text} size="small" />
          ) : (
            <Text style={styles.toggleText}>{isRunning ? "Stop" : "Start"}</Text>
          )}
        </TouchableOpacity>
      </View>

      <Text style={styles.statusText}>
        {isRunning ? "Analyzing markets & trading..." : "Agent paused"}
      </Text>

      <View style={styles.stats}>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Open Positions</Text>
          <Text style={styles.statValue}>{openPositions}</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.stat}>
          <Text style={styles.statLabel}>USDT Balance</Text>
          <Text style={styles.statValue}>${usdtBalance.toLocaleString("en-US", { maximumFractionDigits: 2 })}</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Mode</Text>
          <Text style={[styles.statValue, { color: colors.warning }]}>Paper</Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  dotActive: {
    backgroundColor: colors.success,
    shadowColor: colors.success,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 4,
  },
  dotInactive: {
    backgroundColor: colors.textMuted,
  },
  title: {
    color: colors.text,
    fontWeight: "700",
    fontSize: fontSize.lg,
  },
  toggleBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    minWidth: 70,
    alignItems: "center",
  },
  startBtn: {
    backgroundColor: colors.primary,
  },
  stopBtn: {
    backgroundColor: colors.danger,
  },
  toggleText: {
    color: colors.text,
    fontWeight: "700",
    fontSize: fontSize.sm,
  },
  statusText: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
    marginBottom: spacing.md,
  },
  stats: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
  },
  stat: {
    flex: 1,
    alignItems: "center",
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
    marginBottom: 2,
  },
  statValue: {
    color: colors.text,
    fontWeight: "700",
    fontSize: fontSize.sm,
  },
  divider: {
    width: 1,
    backgroundColor: colors.border,
    marginHorizontal: spacing.xs,
  },
});
