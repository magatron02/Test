/**
 * WalletConnect v2 integration via @walletconnect/modal-react-native
 *
 * Setup steps:
 * 1. Get a project ID from cloud.walletconnect.com (free)
 * 2. npm install @walletconnect/modal-react-native @walletconnect/modal
 * 3. npm install @react-native-async-storage/async-storage
 *    react-native-get-random-values @ethersproject/shims
 * 4. In index.js add BEFORE everything else:
 *      import 'react-native-get-random-values'
 *      import '@ethersproject/shims'
 * 5. Wrap App in <WalletConnectModal> — see AppWithWalletConnect below
 */

import { useStore } from "../store";

export const WALLETCONNECT_PROJECT_ID = "YOUR_PROJECT_ID_FROM_CLOUD_WALLETCONNECT_COM";

export const walletConnectConfig = {
  projectId: WALLETCONNECT_PROJECT_ID,
  providerMetadata: {
    name: "CryptoAI Trader",
    description: "AI-powered crypto trading agent",
    url: "https://your-app-domain.com",
    icons: ["https://your-app-domain.com/icon.png"],
    redirect: {
      native: "cryptoaitrader://",
      universal: "https://your-app-domain.com",
    },
  },
};

/**
 * Sign a message using WalletConnect session.
 * Used for Hyperliquid order signing.
 */
export async function signMessage(message: string): Promise<string | null> {
  try {
    const { walletAddress } = useStore.getState();
    if (!walletAddress) throw new Error("No wallet connected");

    // Dynamic import to avoid crash when not installed
    const { useWalletConnectModal } = await import("@walletconnect/modal-react-native");
    // This must be called inside a React component — use the hook in your component instead.
    // Here we export the hook reference for documentation purposes.
    console.log("[WalletConnect] Use useWalletConnectModal hook in your component to call provider.request()");
    return null;
  } catch (e) {
    console.error("[WalletConnect] Sign error:", e);
    return null;
  }
}

/**
 * Usage example inside a React component:
 *
 * ```tsx
 * import { useWalletConnectModal } from '@walletconnect/modal-react-native';
 *
 * const MyComponent = () => {
 *   const { open, isConnected, address, provider } = useWalletConnectModal();
 *
 *   const connect = () => open();
 *
 *   const signOrder = async (orderData: string) => {
 *     if (!provider) return;
 *     const signature = await provider.request({
 *       method: 'personal_sign',
 *       params: [orderData, address],
 *     });
 *     return signature;
 *   };
 *
 *   return (
 *     <Button title={isConnected ? address : 'Connect Wallet'} onPress={connect} />
 *   );
 * };
 * ```
 */

/**
 * App wrapper with WalletConnect provider — add to App.tsx:
 *
 * ```tsx
 * import { WalletConnectModal } from '@walletconnect/modal-react-native';
 * import { walletConnectConfig } from './src/services/walletconnect';
 *
 * export default function App() {
 *   return (
 *     <>
 *       <AppNavigator />
 *       <WalletConnectModal
 *         projectId={walletConnectConfig.projectId}
 *         providerMetadata={walletConnectConfig.providerMetadata}
 *       />
 *     </>
 *   );
 * }
 * ```
 */
