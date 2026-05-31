/**
 * Push notification setup for trade alerts.
 * Uses @react-native-firebase/messaging for FCM.
 *
 * Setup steps:
 * 1. Create Firebase project at console.firebase.google.com
 * 2. npm install @react-native-firebase/app @react-native-firebase/messaging
 * 3. Download google-services.json (Android) and GoogleService-Info.plist (iOS)
 * 4. Follow platform-specific setup at rnfirebase.io
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import { api } from "./api";

const FCM_TOKEN_KEY = "fcm_device_token";

export interface TradeNotification {
  type: "trade" | "pnl" | "risk" | "agent_status";
  title: string;
  body: string;
  data?: Record<string, string>;
}

/**
 * Request permission and get FCM token.
 * Call once on app startup.
 */
export async function setupNotifications(): Promise<string | null> {
  try {
    // Dynamic import so the app doesn't crash without Firebase installed
    const messaging = await import("@react-native-firebase/messaging")
      .then((m) => m.default())
      .catch(() => null);

    if (!messaging) {
      console.log("[Notifications] Firebase not configured. Install @react-native-firebase/messaging");
      return null;
    }

    const authStatus = await messaging.requestPermission();
    const enabled =
      authStatus === 1 || // AUTHORIZED
      authStatus === 2;   // PROVISIONAL

    if (!enabled) return null;

    const token = await messaging.getToken();
    await AsyncStorage.setItem(FCM_TOKEN_KEY, token);

    // Register token with backend
    await registerTokenWithBackend(token);

    // Handle foreground messages
    messaging.onMessage(async (remoteMessage) => {
      handleForegroundMessage(remoteMessage);
    });

    // Handle background/quit tap navigation
    messaging.onNotificationOpenedApp((remoteMessage) => {
      console.log("[Notifications] Opened from background:", remoteMessage);
    });

    return token;
  } catch (error) {
    console.error("[Notifications] Setup error:", error);
    return null;
  }
}

async function registerTokenWithBackend(token: string): Promise<void> {
  try {
    const storedToken = await AsyncStorage.getItem(FCM_TOKEN_KEY);
    if (storedToken === token) return; // Already registered
    // POST to /api/v1/notifications/register
    await fetch(`${(await import("../store")).useStore.getState().backendUrl}/api/v1/notifications/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
  } catch {}
}

function handleForegroundMessage(message: any): void {
  const { notification, data } = message;
  if (!notification) return;
  console.log("[Notification]", notification.title, notification.body, data);
  // In production: show an in-app banner using a toast library
  // e.g. Toast.show({ text1: notification.title, text2: notification.body })
}

export async function getStoredToken(): Promise<string | null> {
  return AsyncStorage.getItem(FCM_TOKEN_KEY);
}
