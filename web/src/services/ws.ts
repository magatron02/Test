import { useStore } from "../store";

class WsClient {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, ((d: unknown) => void)[]>();
  private reconnect = true;

  connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws`);

    this.ws.onopen = () => {
      useStore.getState().setConnected(true);
      this.send({ type: "subscribe_prices", symbols: ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","AVAX/USDT"] });
      this.send({ type: "subscribe_agent" });
    };
    this.ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      (this.handlers.get(msg.type) ?? []).forEach((h) => h(msg.data));
    };
    this.ws.onclose = () => {
      useStore.getState().setConnected(false);
      if (this.reconnect) setTimeout(() => this.connect(), 3000);
    };
  }

  send(data: object) { this.ws?.readyState === WebSocket.OPEN && this.ws.send(JSON.stringify(data)); }
  on(type: string, fn: (d: unknown) => void) { this.handlers.set(type, [...(this.handlers.get(type) ?? []), fn]); }
  off(type: string, fn: (d: unknown) => void) { this.handlers.set(type, (this.handlers.get(type) ?? []).filter(h => h !== fn)); }
  disconnect() { this.reconnect = false; this.ws?.close(); }
}

export const ws = new WsClient();
