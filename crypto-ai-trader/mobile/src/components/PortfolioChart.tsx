import React from "react";
import { View, Text, StyleSheet, Dimensions } from "react-native";
import { LineChart } from "react-native-chart-kit";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

const { width: SCREEN_WIDTH } = Dimensions.get("window");

interface PortfolioChartProps {
  totalValue: number;
  dailyPnl: number;
  totalPnl: number;
  chartData?: number[];
}

export const PortfolioChart: React.FC<PortfolioChartProps> = ({
  totalValue,
  dailyPnl,
  totalPnl,
  chartData = [10000, 10050, 10120, 10090, 10180, 10250, 10310],
}) => {
  const isPositiveDay = dailyPnl >= 0;
  const isPositiveTotal = totalPnl >= 0;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.label}>Portfolio Value</Text>
          <Text style={styles.value}>
            ${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </Text>
        </View>
        <View style={styles.pnlContainer}>
          <View style={styles.pnlRow}>
            <Text style={styles.pnlLabel}>Daily</Text>
            <Text style={[styles.pnlValue, isPositiveDay ? styles.positive : styles.negative]}>
              {isPositiveDay ? "+" : ""}{dailyPnl.toFixed(2)}%
            </Text>
          </View>
          <View style={styles.pnlRow}>
            <Text style={styles.pnlLabel}>Total</Text>
            <Text style={[styles.pnlValue, isPositiveTotal ? styles.positive : styles.negative]}>
              {isPositiveTotal ? "+" : ""}{totalPnl.toFixed(2)}%
            </Text>
          </View>
        </View>
      </View>

      <LineChart
        data={{
          labels: [],
          datasets: [{ data: chartData }],
        }}
        width={SCREEN_WIDTH - spacing.md * 2}
        height={120}
        chartConfig={{
          backgroundColor: colors.card,
          backgroundGradientFrom: colors.card,
          backgroundGradientTo: colors.card,
          decimalPlaces: 0,
          color: (opacity = 1) => `rgba(59, 130, 246, ${opacity})`,
          labelColor: () => colors.textMuted,
          style: { borderRadius: borderRadius.md },
          propsForDots: { r: "0" },
        }}
        bezier
        style={styles.chart}
        withVerticalLabels={false}
        withHorizontalLabels={false}
        withDots={false}
        withShadow={false}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacing.sm,
  },
  label: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
    marginBottom: 4,
  },
  value: {
    color: colors.text,
    fontWeight: "800",
    fontSize: fontSize.xxl,
  },
  pnlContainer: {
    alignItems: "flex-end",
  },
  pnlRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: 2,
  },
  pnlLabel: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
  },
  pnlValue: {
    fontWeight: "700",
    fontSize: fontSize.sm,
  },
  positive: {
    color: colors.success,
  },
  negative: {
    color: colors.danger,
  },
  chart: {
    marginLeft: -spacing.md,
    marginRight: -spacing.md,
  },
});
