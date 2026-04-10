/**
 * WebSocket client for the btc_simulator live stream.
 * Connects to VITE_WS_URL (default: ws://localhost:8000/ws).
 * Exposes an event emitter pattern so store subscribers can react.
 */

import type { WsEvent } from '../types';

type WsHandler = (event: WsEvent) => void;
type StatusHandler = (status: 'connected' | 'disconnected' | 'error') => void;

const WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/ws';
const MOCK_ENV = (import.meta.env.VITE_MOCK_MODE as string | undefined)?.toLowerCase();
const IS_MOCK =
  MOCK_ENV === 'true'
    ? true
    : MOCK_ENV === 'false'
    ? false
    : import.meta.env.DEV; // default: mock in dev unless explicitly disabled

class WsClient {
  private ws: WebSocket | null = null;
  private handlers: Set<WsHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = false;

  connect() {
    if (IS_MOCK) {
      // In mock mode we simulate the WS with no actual connection.
      // The store can call simulateEvent() for testing.
      console.info('[WsClient] Mock mode — no WebSocket connection.');
      return;
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    this.shouldReconnect = true;
    this._open();
  }

  private _open() {
    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        console.info('[WsClient] Connected to', WS_URL);
        this._emitStatus('connected');
      };

      this.ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data as string) as WsEvent;
          this.handlers.forEach((h) => h(data));
        } catch {
          console.warn('[WsClient] Failed to parse message:', ev.data);
        }
      };

      this.ws.onerror = () => {
        console.error('[WsClient] WebSocket error');
        this._emitStatus('error');
      };

      this.ws.onclose = () => {
        console.warn('[WsClient] Disconnected');
        this._emitStatus('disconnected');
        if (this.shouldReconnect) {
          this.reconnectTimer = setTimeout(() => this._open(), 3_000);
        }
      };
    } catch (err) {
      console.error('[WsClient] Could not create WebSocket:', err);
      this._emitStatus('error');
    }
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  /** Subscribe to incoming WS events */
  onEvent(handler: WsHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  /** Subscribe to connection status changes */
  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  private _emitStatus(status: 'connected' | 'disconnected' | 'error') {
    this.statusHandlers.forEach((h) => h(status));
  }

  /** Inject a synthetic event (useful for mock/testing) */
  simulateEvent(event: WsEvent) {
    this.handlers.forEach((h) => h(event));
  }

  get isMock() {
    return IS_MOCK;
  }
}

export const wsClient = new WsClient();
export default wsClient;
