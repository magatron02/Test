import { useStore } from "../store";

type MessageHandler = (data: any) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  connect() {
    const url = useStore.getState().backendUrl.replace("http", "ws");
    this.ws = new WebSocket(`${url}/ws`);

    this.ws.onopen = () => {
      useStore.getState().setConnected(true);
      this.subscribeToDefaults();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const handlers = this.handlers.get(msg.type) || [];
        handlers.forEach((h) => h(msg.data));
      } catch {}
    };

    this.ws.onclose = () => {
      useStore.getState().setConnected(false);
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private subscribeToDefaults() {
    this.send({
      type: "subscribe_prices",
      symbols: ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT"],
    });
    this.send({ type: "subscribe_agent" });
  }

  send(data: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  on(type: string, handler: MessageHandler) {
    const existing = this.handlers.get(type) || [];
    this.handlers.set(type, [...existing, handler]);
  }

  off(type: string, handler: MessageHandler) {
    const existing = this.handlers.get(type) || [];
    this.handlers.set(type, existing.filter((h) => h !== handler));
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}

export const wsService = new WebSocketService();
