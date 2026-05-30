import React, { useState } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Switch, Alert,
} from "react-native";
import { useStore } from "../store";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

const RISK_LEVELS = [
  { id: "low", label: "Conservative", desc: "1% risk per trade, max 5x leverage", color: colors.success },
  { id: "medium", label: "Moderate", desc: "2% risk per trade, max 10x leverage", color: colors.warning },
  { id: "high", label: "Aggressive", desc: "4% risk per trade, higher returns & risk", color: colors.danger },
];

const INTERVALS = [
  { label: "15 min", value: 15 },
  { label: "30 min", value: 30 },
  { label: "1 hour", value: 60 },
  { label: "4 hours", value: 240 },
];

export const SettingsScreen: React.FC = () => {
  const { agentConfig, setAgentConfig, backendUrl, setBackendUrl } = useStore();
  const [urlInput, setUrlInput] = useState(backendUrl);
  const [newSymbol, setNewSymbol] = useState("");

  const toggleExchange = (ex: string) => {
    const current = agentConfig.exchanges;
    const updated = current.includes(ex)
      ? current.filter((e) => e !== ex)
      : [...current, ex];
    if (updated.length === 0) return Alert.alert("Error", "At least one exchange must be selected");
    setAgentConfig({ exchanges: updated });
  };

  const addSymbol = () => {
    const sym = newSymbol.toUpperCase().trim();
    if (!sym) return;
    if (!sym.includes("/")) {
      Alert.alert("Format", "Use format like BTC/USDT");
      return;
    }
    if (agentConfig.watchlist.includes(sym)) return;
    setAgentConfig({ watchlist: [...agentConfig.watchlist, sym] });
    setNewSymbol("");
  };

  const removeSymbol = (sym: string) => {
    setAgentConfig({ watchlist: agentConfig.watchlist.filter((s) => s !== sym) });
  };

  const saveBackendUrl = () => {
    setBackendUrl(urlInput);
    Alert.alert("Saved", "Backend URL updated");
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Settings</Text>

      <Section title="Backend Server">
        <Text style={styles.label}>Server URL</Text>
        <View style={styles.urlRow}>
          <TextInput
            style={[styles.input, { flex: 1 }]}
            value={urlInput}
            onChangeText={setUrlInput}
            placeholder="http://your-server:8000"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
          />
          <TouchableOpacity style={styles.saveUrlBtn} onPress={saveBackendUrl}>
            <Text style={styles.saveUrlText}>Save</Text>
          </TouchableOpacity>
        </View>
      </Section>

      <Section title="Risk Level">
        {RISK_LEVELS.map((r) => (
          <TouchableOpacity
            key={r.id}
            style={[styles.riskCard, agentConfig.riskLevel === r.id && { borderColor: r.color }]}
            onPress={() => setAgentConfig({ riskLevel: r.id })}
          >
            <View style={styles.riskHeader}>
              <View style={[styles.riskDot, { backgroundColor: r.color }]} />
              <Text style={styles.riskLabel}>{r.label}</Text>
              {agentConfig.riskLevel === r.id && (
                <View style={[styles.activeBadge, { backgroundColor: r.color + "30" }]}>
                  <Text style={[styles.activeText, { color: r.color }]}>Active</Text>
                </View>
              )}
            </View>
            <Text style={styles.riskDesc}>{r.desc}</Text>
          </TouchableOpacity>
        ))}
      </Section>

      <Section title="Exchanges">
        {["binance", "okx", "hyperliquid"].map((ex) => (
          <View key={ex} style={styles.switchRow}>
            <Text style={styles.switchLabel}>{ex.charAt(0).toUpperCase() + ex.slice(1)}</Text>
            <Switch
              value={agentConfig.exchanges.includes(ex)}
              onValueChange={() => toggleExchange(ex)}
              trackColor={{ false: colors.border, true: colors.primary + "80" }}
              thumbColor={agentConfig.exchanges.includes(ex) ? colors.primary : colors.textMuted}
            />
          </View>
        ))}
      </Section>

      <Section title="Analysis Interval">
        <View style={styles.chipRow}>
          {INTERVALS.map((interval) => (
            <TouchableOpacity
              key={interval.value}
              style={[styles.chip, agentConfig.intervalMinutes === interval.value && styles.chipActive]}
              onPress={() => setAgentConfig({ intervalMinutes: interval.value })}
            >
              <Text style={[styles.chipText, agentConfig.intervalMinutes === interval.value && styles.chipTextActive]}>
                {interval.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </Section>

      <Section title="Paper Trading">
        <View style={styles.switchRow}>
          <View>
            <Text style={styles.switchLabel}>Paper Mode</Text>
            <Text style={styles.switchDesc}>Trade with simulated money (recommended for testing)</Text>
          </View>
          <Switch
            value={agentConfig.usePaper}
            onValueChange={(v) => setAgentConfig({ usePaper: v })}
            trackColor={{ false: colors.border, true: colors.primary + "80" }}
            thumbColor={agentConfig.usePaper ? colors.primary : colors.textMuted}
          />
        </View>

        <Text style={styles.label}>Portfolio Value (USDT)</Text>
        <TextInput
          style={styles.input}
          value={agentConfig.portfolioValue.toString()}
          onChangeText={(v) => setAgentConfig({ portfolioValue: parseFloat(v) || 10000 })}
          keyboardType="numeric"
          placeholderTextColor={colors.textMuted}
        />
      </Section>

      <Section title="Watchlist">
        <View style={styles.addRow}>
          <TextInput
            style={[styles.input, { flex: 1 }]}
            value={newSymbol}
            onChangeText={setNewSymbol}
            placeholder="BTC/USDT"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="characters"
          />
          <TouchableOpacity style={styles.addBtn} onPress={addSymbol}>
            <Text style={styles.addBtnText}>+</Text>
          </TouchableOpacity>
        </View>

        {agentConfig.watchlist.map((sym) => (
          <View key={sym} style={styles.symbolRow}>
            <Text style={styles.symbolText}>{sym}</Text>
            <TouchableOpacity onPress={() => removeSymbol(sym)}>
              <Text style={styles.removeText}>Remove</Text>
            </TouchableOpacity>
          </View>
        ))}
      </Section>

      {!agentConfig.usePaper && (
        <View style={styles.warningCard}>
          <Text style={styles.warningTitle}>⚠️ Live Trading Active</Text>
          <Text style={styles.warningText}>
            Live trading uses real money. Ensure your exchange API keys are configured and you understand the risks. The AI agent makes decisions based on technical analysis — past performance does not guarantee future results.
          </Text>
        </View>
      )}
    </ScrollView>
  );
};

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <View style={sectionStyles.container}>
    <Text style={sectionStyles.title}>{title}</Text>
    <View style={sectionStyles.card}>{children}</View>
  </View>
);

const sectionStyles = StyleSheet.create({
  container: { marginBottom: spacing.lg },
  title: { color: colors.textSecondary, fontSize: fontSize.sm, fontWeight: "700", marginBottom: spacing.sm, textTransform: "uppercase", letterSpacing: 1 },
  card: { backgroundColor: colors.card, borderRadius: borderRadius.lg, padding: spacing.md, borderWidth: 1, borderColor: colors.border },
});

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  title: { color: colors.text, fontSize: fontSize.xxl, fontWeight: "800", marginBottom: spacing.lg },
  label: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.xs, marginTop: spacing.sm },
  input: {
    backgroundColor: colors.surface, borderRadius: borderRadius.md,
    padding: spacing.sm, color: colors.text,
    borderWidth: 1, borderColor: colors.border,
  },
  urlRow: { flexDirection: "row", gap: spacing.sm, alignItems: "center" },
  saveUrlBtn: { backgroundColor: colors.primary, padding: spacing.sm, borderRadius: borderRadius.md },
  saveUrlText: { color: colors.text, fontWeight: "700", fontSize: fontSize.sm },
  riskCard: {
    backgroundColor: colors.surface, borderRadius: borderRadius.md,
    padding: spacing.md, marginBottom: spacing.sm,
    borderWidth: 1, borderColor: colors.border,
  },
  riskHeader: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: 4 },
  riskDot: { width: 10, height: 10, borderRadius: 5 },
  riskLabel: { color: colors.text, fontWeight: "700", fontSize: fontSize.md, flex: 1 },
  activeBadge: { paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: borderRadius.sm },
  activeText: { fontSize: fontSize.xs, fontWeight: "700" },
  riskDesc: { color: colors.textMuted, fontSize: fontSize.xs },
  switchRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: spacing.sm },
  switchLabel: { color: colors.text, fontSize: fontSize.md, fontWeight: "600" },
  switchDesc: { color: colors.textMuted, fontSize: fontSize.xs, marginTop: 2, maxWidth: "80%" },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: {
    paddingHorizontal: spacing.md, paddingVertical: spacing.xs,
    borderRadius: borderRadius.full, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: fontSize.sm, fontWeight: "600" },
  chipTextActive: { color: colors.text },
  addRow: { flexDirection: "row", gap: spacing.sm, alignItems: "center", marginBottom: spacing.sm },
  addBtn: {
    backgroundColor: colors.primary, width: 40, height: 40,
    borderRadius: borderRadius.md, alignItems: "center", justifyContent: "center",
  },
  addBtnText: { color: colors.text, fontSize: fontSize.xl, fontWeight: "700" },
  symbolRow: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", paddingVertical: spacing.sm,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  symbolText: { color: colors.text, fontWeight: "600" },
  removeText: { color: colors.danger, fontSize: fontSize.sm },
  warningCard: {
    backgroundColor: colors.danger + "15", borderRadius: borderRadius.md,
    padding: spacing.md, borderWidth: 1, borderColor: colors.danger + "40",
    marginTop: spacing.sm,
  },
  warningTitle: { color: colors.danger, fontWeight: "700", marginBottom: spacing.xs },
  warningText: { color: colors.textSecondary, fontSize: fontSize.xs, lineHeight: 18 },
});
