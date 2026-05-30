import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
} from "react-native";
import { api } from "../services/api";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

type BacktestStrategy = "spot" | "grid" | "futures";
type Exchange = "binance" | "okx" | "hyperliquid" | "paper";
type DayOption = 7 | 30 | 90;

interface BacktestResult {
  return_pct: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  total_trades: number;
  sharpe_ratio: number;
}

const STRATEGIES: BacktestStrategy[] = ["spot", "grid", "futures"];
const EXCHANGES: Exchange[] = ["binance", "okx", "hyperliquid", "paper"];
const DAY_OPTIONS: DayOption[] = [7, 30, 90];

export const BacktestScreen: React.FC = () => {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [strategy, setStrategy] = useState<BacktestStrategy>("spot");
  const [days, setDays] = useState<DayOption>(30);
  const [capital, setCapital] = useState("10000");
  const [exchange, setExchange] = useState<Exchange>("binance");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);

  const handleSubmit = async () => {
    const capitalNum = parseFloat(capital);
    if (!symbol.trim()) {
      return Alert.alert("Validation", "Please enter a symbol (e.g. BTC/USDT)");
    }
    if (!capital || isNaN(capitalNum) || capitalNum <= 0) {
      return Alert.alert("Validation", "Please enter a valid capital amount");
    }

    setLoading(true);
    setResult(null);

    try {
      const res = await api.runBacktest({
        symbol: symbol.toUpperCase().trim(),
        strategy,
        days,
        capital: capitalNum,
        exchange,
      });
      setResult(res.data);
    } catch (e: any) {
      Alert.alert("Error", e?.response?.data?.detail || e.message || "Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  const returnColor =
    result && result.return_pct >= 0 ? colors.success : colors.danger;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Backtest</Text>

      {/* Exchange */}
      <Text style={styles.label}>Exchange</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.chipRow}
      >
        {EXCHANGES.map((ex) => (
          <TouchableOpacity
            key={ex}
            style={[styles.chip, exchange === ex && styles.chipActive]}
            onPress={() => setExchange(ex)}
          >
            <Text
              style={[
                styles.chipText,
                exchange === ex && styles.chipTextActive,
              ]}
            >
              {ex.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Symbol */}
      <Text style={styles.label}>Symbol</Text>
      <TextInput
        style={styles.input}
        value={symbol}
        onChangeText={(t) => setSymbol(t.toUpperCase())}
        placeholder="e.g. BTC/USDT"
        placeholderTextColor={colors.textMuted}
        autoCapitalize="characters"
      />

      {/* Strategy */}
      <Text style={styles.label}>Strategy</Text>
      <View style={styles.chipRow}>
        {STRATEGIES.map((s) => (
          <TouchableOpacity
            key={s}
            style={[styles.chip, strategy === s && styles.chipActive]}
            onPress={() => setStrategy(s)}
          >
            <Text
              style={[
                styles.chipText,
                strategy === s && styles.chipTextActive,
              ]}
            >
              {s.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Days */}
      <Text style={styles.label}>Lookback Period</Text>
      <View style={styles.chipRow}>
        {DAY_OPTIONS.map((d) => (
          <TouchableOpacity
            key={d}
            style={[styles.chip, days === d && styles.chipActive]}
            onPress={() => setDays(d)}
          >
            <Text
              style={[styles.chipText, days === d && styles.chipTextActive]}
            >
              {d} days
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Capital */}
      <Text style={styles.label}>Starting Capital (USDT)</Text>
      <TextInput
        style={styles.input}
        value={capital}
        onChangeText={setCapital}
        keyboardType="numeric"
        placeholder="10000"
        placeholderTextColor={colors.textMuted}
      />

      {/* Submit */}
      <TouchableOpacity
        style={[styles.submitBtn, loading && styles.submitBtnDisabled]}
        onPress={handleSubmit}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color={colors.text} />
        ) : (
          <Text style={styles.submitBtnText}>Run Backtest</Text>
        )}
      </TouchableOpacity>

      {/* Results */}
      {result && (
        <View style={styles.resultsCard}>
          <Text style={styles.resultsTitle}>Results</Text>

          <View style={styles.returnRow}>
            <Text style={styles.returnLabel}>Total Return</Text>
            <Text style={[styles.returnValue, { color: returnColor }]}>
              {result.return_pct >= 0 ? "+" : ""}
              {result.return_pct.toFixed(2)}%
            </Text>
          </View>

          <View style={styles.divider} />

          <MetricRow
            label="Max Drawdown"
            value={`${result.max_drawdown_pct.toFixed(2)}%`}
            color={colors.danger}
          />
          <MetricRow
            label="Win Rate"
            value={`${result.win_rate_pct.toFixed(1)}%`}
            color={
              result.win_rate_pct >= 50 ? colors.success : colors.warning
            }
          />
          <MetricRow
            label="Total Trades"
            value={result.total_trades.toString()}
          />
          <MetricRow
            label="Sharpe Ratio"
            value={result.sharpe_ratio.toFixed(2)}
            color={
              result.sharpe_ratio >= 1
                ? colors.success
                : result.sharpe_ratio >= 0
                ? colors.warning
                : colors.danger
            }
          />

          <View style={styles.paramsRow}>
            <Text style={styles.paramsText}>
              {symbol} · {strategy.toUpperCase()} · {days}d · ${parseFloat(capital).toLocaleString()} · {exchange.toUpperCase()}
            </Text>
          </View>
        </View>
      )}
    </ScrollView>
  );
};

const MetricRow = ({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) => (
  <View style={metricStyles.row}>
    <Text style={metricStyles.label}>{label}</Text>
    <Text style={[metricStyles.value, color ? { color } : undefined]}>
      {value}
    </Text>
  </View>
);

const metricStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.xs,
  },
  label: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
  },
  value: {
    color: colors.text,
    fontWeight: "700",
    fontSize: fontSize.sm,
  },
});

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },

  title: {
    color: colors.text,
    fontSize: fontSize.xxl,
    fontWeight: "800",
    marginBottom: spacing.md,
  },

  label: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
    marginBottom: spacing.xs,
    marginTop: spacing.sm,
  },

  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },

  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginRight: spacing.sm,
    marginBottom: spacing.xs,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: fontSize.sm, fontWeight: "600" },
  chipTextActive: { color: colors.text },

  input: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    color: colors.text,
    fontSize: fontSize.md,
    borderWidth: 1,
    borderColor: colors.border,
  },

  submitBtn: {
    backgroundColor: colors.accent,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    alignItems: "center",
    marginTop: spacing.lg,
  },
  submitBtnDisabled: { opacity: 0.6 },
  submitBtnText: { color: colors.text, fontWeight: "700", fontSize: fontSize.md },

  resultsCard: {
    marginTop: spacing.lg,
    backgroundColor: colors.card,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  resultsTitle: {
    color: colors.text,
    fontSize: fontSize.lg,
    fontWeight: "800",
    marginBottom: spacing.md,
  },

  returnRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  returnLabel: {
    color: colors.textSecondary,
    fontSize: fontSize.md,
  },
  returnValue: {
    fontSize: fontSize.xxxl,
    fontWeight: "800",
  },

  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.sm,
  },

  paramsRow: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  paramsText: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
    textAlign: "center",
  },
});
