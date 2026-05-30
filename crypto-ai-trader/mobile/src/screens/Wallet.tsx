import React, { useState } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  Alert, TextInput, Modal,
} from "react-native";
import { useStore } from "../store";
import { colors, spacing, fontSize, borderRadius } from "../utils/theme";

export const WalletScreen: React.FC = () => {
  const { walletAddress, walletConnected, setWallet, exchangeKeys, setExchangeKey } = useStore();
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [selectedExchange, setSelectedExchange] = useState("binance");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");

  const exchanges = [
    { id: "binance", name: "Binance", color: "#F0B90B", description: "Spot + Futures" },
    { id: "okx", name: "OKX", color: "#00AEEF", description: "Spot + Perpetual" },
    { id: "hyperliquid", name: "Hyperliquid", color: "#00FF88", description: "DeFi Perpetual" },
  ];

  const handleConnectWalletConnect = () => {
    Alert.alert(
      "WalletConnect",
      "WalletConnect integration requires native setup. Add @walletconnect/modal-react-native to your project and configure your project ID from cloud.walletconnect.com",
      [{ text: "OK" }]
    );
  };

  const handleSaveKeys = () => {
    if (!apiKey || !apiSecret) {
      return Alert.alert("Error", "Please enter API key and secret");
    }
    setExchangeKey(selectedExchange, apiKey, apiSecret, passphrase || undefined);
    setShowKeyModal(false);
    setApiKey("");
    setApiSecret("");
    setPassphrase("");
    Alert.alert("Saved", `${selectedExchange.toUpperCase()} API keys saved securely`);
  };

  const hasKeys = (exchangeId: string) => !!exchangeKeys[exchangeId]?.apiKey;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Wallet & Accounts</Text>

      <View style={styles.walletCard}>
        <Text style={styles.cardTitle}>Crypto Wallet</Text>
        {walletConnected ? (
          <View>
            <View style={styles.addressRow}>
              <View style={styles.statusDot} />
              <Text style={styles.address}>
                {walletAddress?.substring(0, 6)}...{walletAddress?.slice(-4)}
              </Text>
            </View>
            <View style={styles.walletActions}>
              <TouchableOpacity style={styles.walletBtn}>
                <Text style={styles.walletBtnText}>Receive</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.walletBtn, styles.disconnectBtn]} onPress={() => setWallet(null)}>
                <Text style={[styles.walletBtnText, { color: colors.danger }]}>Disconnect</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View>
            <Text style={styles.walletDesc}>
              Connect your crypto wallet via WalletConnect to enable on-chain features and Hyperliquid trading.
            </Text>
            <TouchableOpacity style={styles.connectBtn} onPress={handleConnectWalletConnect}>
              <Text style={styles.connectBtnText}>Connect Wallet</Text>
            </TouchableOpacity>

            <View style={styles.separator} />
            <Text style={styles.orText}>or use demo wallet</Text>
            <TouchableOpacity
              style={[styles.connectBtn, { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }]}
              onPress={() => setWallet("0x" + "a".repeat(40))}
            >
              <Text style={[styles.connectBtnText, { color: colors.text }]}>Use Demo Address</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      <Text style={[styles.title, { marginTop: spacing.lg }]}>Exchange Accounts</Text>
      <Text style={styles.subtitle}>Add your exchange API keys to enable automated trading.</Text>

      {exchanges.map((ex) => (
        <View key={ex.id} style={styles.exchangeCard}>
          <View style={styles.exchangeHeader}>
            <View style={[styles.exchangeDot, { backgroundColor: ex.color }]} />
            <View style={{ flex: 1 }}>
              <Text style={styles.exchangeName}>{ex.name}</Text>
              <Text style={styles.exchangeDesc}>{ex.description}</Text>
            </View>
            {hasKeys(ex.id) ? (
              <View style={styles.connectedBadge}>
                <Text style={styles.connectedText}>Connected</Text>
              </View>
            ) : (
              <TouchableOpacity
                style={styles.addKeyBtn}
                onPress={() => {
                  setSelectedExchange(ex.id);
                  setShowKeyModal(true);
                }}
              >
                <Text style={styles.addKeyText}>+ Add Keys</Text>
              </TouchableOpacity>
            )}
          </View>

          {hasKeys(ex.id) && (
            <View style={styles.keyInfo}>
              <Text style={styles.keyLabel}>API Key</Text>
              <Text style={styles.keyValue}>
                {exchangeKeys[ex.id].apiKey.substring(0, 8)}...{exchangeKeys[ex.id].apiKey.slice(-4)}
              </Text>
              <TouchableOpacity
                onPress={() => {
                  setSelectedExchange(ex.id);
                  setShowKeyModal(true);
                }}
              >
                <Text style={styles.editText}>Edit</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      ))}

      <View style={styles.securityNote}>
        <Text style={styles.securityTitle}>Security Note</Text>
        <Text style={styles.securityText}>
          API keys are stored locally on your device using encrypted storage. For maximum security, create API keys with "Trade Only" permission and disable withdrawal access.
        </Text>
      </View>

      <Modal visible={showKeyModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>{selectedExchange.toUpperCase()} API Keys</Text>

            <Text style={styles.label}>API Key</Text>
            <TextInput
              style={styles.input}
              value={apiKey}
              onChangeText={setApiKey}
              placeholder="Enter API key"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
              autoCapitalize="none"
            />

            <Text style={styles.label}>Secret Key</Text>
            <TextInput
              style={styles.input}
              value={apiSecret}
              onChangeText={setApiSecret}
              placeholder="Enter secret key"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
              autoCapitalize="none"
            />

            {selectedExchange === "okx" && (
              <>
                <Text style={styles.label}>Passphrase</Text>
                <TextInput
                  style={styles.input}
                  value={passphrase}
                  onChangeText={setPassphrase}
                  placeholder="OKX passphrase"
                  placeholderTextColor={colors.textMuted}
                  secureTextEntry
                  autoCapitalize="none"
                />
              </>
            )}

            {selectedExchange === "hyperliquid" && (
              <Text style={styles.hlNote}>
                Hyperliquid uses your wallet private key. Connect via WalletConnect above for on-chain signing.
              </Text>
            )}

            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setShowKeyModal(false)}>
                <Text style={styles.cancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={handleSaveKeys}>
                <Text style={styles.saveText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  title: { color: colors.text, fontSize: fontSize.xl, fontWeight: "800", marginBottom: spacing.sm },
  subtitle: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.md },
  walletCard: {
    backgroundColor: colors.card, borderRadius: borderRadius.lg,
    padding: spacing.md, borderWidth: 1, borderColor: colors.border,
    marginBottom: spacing.md,
  },
  cardTitle: { color: colors.text, fontWeight: "700", fontSize: fontSize.lg, marginBottom: spacing.sm },
  addressRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  statusDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.success },
  address: { color: colors.text, fontWeight: "600", fontSize: fontSize.md },
  walletDesc: { color: colors.textSecondary, fontSize: fontSize.sm, lineHeight: 20, marginBottom: spacing.md },
  connectBtn: {
    backgroundColor: colors.primary, borderRadius: borderRadius.md,
    padding: spacing.md, alignItems: "center",
  },
  connectBtnText: { color: colors.text, fontWeight: "700", fontSize: fontSize.md },
  separator: { height: 1, backgroundColor: colors.border, marginVertical: spacing.md },
  orText: { color: colors.textMuted, fontSize: fontSize.sm, textAlign: "center", marginBottom: spacing.sm },
  walletActions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
  walletBtn: {
    flex: 1, padding: spacing.sm, borderRadius: borderRadius.md,
    backgroundColor: colors.surface, alignItems: "center",
    borderWidth: 1, borderColor: colors.border,
  },
  walletBtnText: { color: colors.text, fontWeight: "600", fontSize: fontSize.sm },
  disconnectBtn: { borderColor: colors.danger },
  exchangeCard: {
    backgroundColor: colors.card, borderRadius: borderRadius.md,
    padding: spacing.md, marginBottom: spacing.sm,
    borderWidth: 1, borderColor: colors.border,
  },
  exchangeHeader: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  exchangeDot: { width: 12, height: 12, borderRadius: 6 },
  exchangeName: { color: colors.text, fontWeight: "700", fontSize: fontSize.md },
  exchangeDesc: { color: colors.textMuted, fontSize: fontSize.xs },
  connectedBadge: {
    backgroundColor: colors.success + "20",
    paddingHorizontal: spacing.sm, paddingVertical: 4,
    borderRadius: borderRadius.sm,
  },
  connectedText: { color: colors.success, fontSize: fontSize.xs, fontWeight: "700" },
  addKeyBtn: {
    backgroundColor: colors.primary + "20",
    paddingHorizontal: spacing.sm, paddingVertical: 4,
    borderRadius: borderRadius.sm,
  },
  addKeyText: { color: colors.primary, fontSize: fontSize.xs, fontWeight: "700" },
  keyInfo: { flexDirection: "row", alignItems: "center", marginTop: spacing.sm, gap: spacing.sm },
  keyLabel: { color: colors.textMuted, fontSize: fontSize.xs },
  keyValue: { color: colors.text, fontSize: fontSize.xs, flex: 1 },
  editText: { color: colors.primary, fontSize: fontSize.xs },
  securityNote: {
    backgroundColor: colors.warning + "10", borderRadius: borderRadius.md,
    padding: spacing.md, borderWidth: 1, borderColor: colors.warning + "40",
    marginTop: spacing.md,
  },
  securityTitle: { color: colors.warning, fontWeight: "700", fontSize: fontSize.sm, marginBottom: spacing.xs },
  securityText: { color: colors.textSecondary, fontSize: fontSize.xs, lineHeight: 18 },
  modalOverlay: { flex: 1, backgroundColor: "#000a", justifyContent: "flex-end" },
  modalCard: {
    backgroundColor: colors.surface, borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl, padding: spacing.lg,
  },
  modalTitle: { color: colors.text, fontWeight: "800", fontSize: fontSize.xl, marginBottom: spacing.md },
  label: { color: colors.textSecondary, fontSize: fontSize.sm, marginBottom: spacing.xs, marginTop: spacing.sm },
  input: {
    backgroundColor: colors.card, borderRadius: borderRadius.md,
    padding: spacing.sm, color: colors.text,
    borderWidth: 1, borderColor: colors.border,
  },
  hlNote: { color: colors.warning, fontSize: fontSize.xs, marginTop: spacing.sm, lineHeight: 18 },
  modalButtons: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg },
  cancelBtn: { flex: 1, padding: spacing.md, borderRadius: borderRadius.md, alignItems: "center", backgroundColor: colors.card },
  cancelText: { color: colors.textSecondary, fontWeight: "700" },
  saveBtn: { flex: 1, padding: spacing.md, borderRadius: borderRadius.md, alignItems: "center", backgroundColor: colors.primary },
  saveText: { color: colors.text, fontWeight: "700" },
});
