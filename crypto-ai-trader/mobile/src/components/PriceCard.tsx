import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

interface PriceCardProps {
  symbol: string;
  price: number;
  change24h: number;
  volume?: number;
  onPress?: () => void;
}

export const PriceCard: React.FC<PriceCardProps> = ({
  symbol,
  price,
  change24h,
  volume,
  onPress,
}) => {
  const isPositive = change24h >= 0;
  const baseAsset = symbol.split("/")[0];

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.8}>
      <View style={styles.left}>
        <View style={styles.iconBadge}>
          <Text style={styles.iconText}>{baseAsset.substring(0, 2)}</Text>
        </View>
        <View>
          <Text style={styles.symbol}>{baseAsset}</Text>
          <Text style={styles.pair}>{symbol.split("/")[1]}</Text>
        </View>
      </View>
      <View style={styles.right}>
        <Text style={styles.price}>${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: price < 1 ? 6 : 2 })}</Text>
        <View style={[styles.changeBadge, isPositive ? styles.positive : styles.negative]}>
          <Text style={[styles.change, isPositive ? styles.positiveText : styles.negativeText]}>
            {isPositive ? "+" : ""}{change24h?.toFixed(2)}%
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  left: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  iconBadge: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary + "30",
    alignItems: "center",
    justifyContent: "center",
  },
  iconText: {
    color: colors.primary,
    fontWeight: "700",
    fontSize: fontSize.sm,
  },
  symbol: {
    color: colors.text,
    fontWeight: "700",
    fontSize: fontSize.md,
  },
  pair: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
  },
  right: {
    alignItems: "flex-end",
  },
  price: {
    color: colors.text,
    fontWeight: "700",
    fontSize: fontSize.md,
  },
  changeBadge: {
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginTop: 4,
  },
  positive: {
    backgroundColor: colors.success + "20",
  },
  negative: {
    backgroundColor: colors.danger + "20",
  },
  change: {
    fontSize: fontSize.xs,
    fontWeight: "600",
  },
  positiveText: {
    color: colors.success,
  },
  negativeText: {
    color: colors.danger,
  },
});
