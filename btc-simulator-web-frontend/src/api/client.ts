/**
 * Typed API client for the btc_simulator Python backend.
 * Base URL is driven by VITE_API_BASE_URL env variable.
 * When VITE_MOCK_MODE=true, all calls are intercepted and served
 * from the local mock handlers — no network needed.
 */

import type {
  SessionResponse,
  MarketStateResponse,
  TradeStateResponse,
  OpenTradeRequest,
  OpenTradeResponse,
  CloseTradeResponse,
  BotsResponse,
  LogsResponse,
  LlmBotsResponse,
  Timeframe,
  SpeedPreset,
} from '../types';
import { mockHandlers } from './mock';

// ─── Config ───────────────────────────────────────────────────────────────────

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';
const MOCK_ENV = (import.meta.env.VITE_MOCK_MODE as string | undefined)?.toLowerCase();
const IS_MOCK =
  MOCK_ENV === 'true'
    ? true
    : MOCK_ENV === 'false'
    ? false
    : import.meta.env.DEV; // default: mock in dev unless explicitly disabled

// ─── Fetch Helper ─────────────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options?: RequestInit,
  body?: unknown
): Promise<T> {
  const init: RequestInit = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} failed [${res.status}]: ${text}`);
  }
  return res.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>(path, { method: 'GET' });
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST' }, body);

// ─── API Methods ──────────────────────────────────────────────────────────────

export const api = {
  // Session
  getSession(): Promise<SessionResponse> {
    if (IS_MOCK) return Promise.resolve(mockHandlers.getSession());
    return get('/session');
  },

  loadSession(payload: {
    startDate?: string;
    endDate?: string;
    source: string;
    csvPath?: string;
  }): Promise<{ ok: boolean }> {
    if (IS_MOCK) return Promise.resolve({ ok: true });
    return post('/session/load', payload);
  },

  // Playback
  play(): Promise<void> {
    if (IS_MOCK) return Promise.resolve();
    return post('/playback/play');
  },

  pause(): Promise<void> {
    if (IS_MOCK) return Promise.resolve();
    return post('/playback/pause');
  },

  step(): Promise<void> {
    if (IS_MOCK) return Promise.resolve();
    return post('/playback/step');
  },

  fastForward(batchSize?: number): Promise<void> {
    if (IS_MOCK) return Promise.resolve();
    return post('/playback/fast-forward', { batchSize });
  },

  setTimeframe(timeframe: Timeframe): Promise<void> {
    if (IS_MOCK) return Promise.resolve();
    return post('/playback/timeframe', { timeframe });
  },

  setSpeed(payload: { preset?: SpeedPreset; speedMs?: number }): Promise<void> {
    if (IS_MOCK) return Promise.resolve();
    return post('/playback/speed', payload);
  },

  // Market
  getMarketState(): Promise<MarketStateResponse> {
    if (IS_MOCK) return Promise.resolve(mockHandlers.getMarketState());
    return get('/market/state');
  },

  // Trade
  getTradeState(): Promise<TradeStateResponse> {
    if (IS_MOCK) return Promise.resolve(mockHandlers.getTradeState());
    return get('/trade/state');
  },

  openTrade(payload: OpenTradeRequest): Promise<OpenTradeResponse> {
    if (IS_MOCK) {
      return Promise.resolve(
        mockHandlers.openTrade({
          direction: payload.direction,
          marginUsdt: payload.marginUsdt,
          leverage: payload.leverage,
          stopLoss: payload.stopLoss,
          takeProfit: payload.takeProfit,
        })
      );
    }
    return post('/trade/open', payload);
  },

  closeTrade(exitPrice: number): Promise<CloseTradeResponse> {
    if (IS_MOCK) return Promise.resolve(mockHandlers.closeTrade());
    return post('/trade/close', { exitPrice });
  },

  closeTradePartial(payload: { exitPrice: number; fraction: number }): Promise<{
    partial: boolean;
    record?: import('../types').TradeRecord;
    position?: import('../types').Position;
  }> {
    if (IS_MOCK) return Promise.resolve({ partial: false });
    return post('/trade/close-partial', payload);
  },

  updateTrade(payload: { stopLoss?: number; takeProfit?: number }): Promise<{
    success: boolean;
    position: import('../types').Position;
  }> {
    if (IS_MOCK) {
      const pos = mockHandlers.getTradeState().position;
      if (!pos) return Promise.reject(new Error('No position'));
      return Promise.resolve({ success: true, position: pos });
    }
    return post('/trade/update', payload);
  },

  // Bots
  getBots(): Promise<BotsResponse> {
    if (IS_MOCK) return Promise.resolve(mockHandlers.getBots());
    return get('/bots');
  },

  toggleBot(name: string, enabled: boolean): Promise<{ success: boolean }> {
    if (IS_MOCK) return Promise.resolve(mockHandlers.toggleBot(name, enabled));
    return post('/bots/toggle', { name, enabled });
  },

  // Logs
  getLogs(): Promise<LogsResponse> {
    if (IS_MOCK) return Promise.resolve(mockHandlers.getLogs());
    return get('/logs');
  },

  // ─── LLM Bots ───────────────────────────────────────────────────────────
  getLlmBots(): Promise<LlmBotsResponse> {
    if (IS_MOCK) return Promise.resolve({ bots: [] });
    return get('/llm/bots');
  },

  generateLlmBot(payload: {
    name: string;
    timeframe: string;
    description: string;
  }): Promise<{ ok: boolean; botId?: string; path?: string; compileOk?: boolean; error?: string }> {
    if (IS_MOCK) return Promise.resolve({ ok: false, error: 'Mock mode: LLM disabled' });
    return post('/llm/bots/generate', payload);
  },

  testLlmBot(payload: {
    botId: string;
    maxSteps?: number;
    timeoutSec?: number;
  }): Promise<{ ok: boolean; report?: unknown; error?: string }> {
    if (IS_MOCK) return Promise.resolve({ ok: false, error: 'Mock mode: LLM disabled' });
    return post('/llm/bots/test', payload);
  },
};

export default api;
