/**
 * Central Zustand store for btc_simulator frontend.
 * Handles all app state: market, trade, bots, UI, playback.
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type {
  Candle,
  Position,
  Stats,
  TradeRecord,
  Bot,
  Indicators,
  EquityCurve,
  TabId,
  IndicatorToggles,
  Timeframe,
  SpeedPreset,
  ConnectionStatus,
  WsEvent,
  LlmBotMeta,
  SandboxReport,
} from '../types';
import { api } from '../api/client';
import { wsClient } from '../api/wsClient';

// ─── State Shape ──────────────────────────────────────────────────────────────

interface AppState {
  // Connection
  connectionStatus: ConnectionStatus;
  isMockMode: boolean;
  sessionId: string | null;
  datasetInfo: string;

  // UI
  activeTab: TabId;
  indicators: IndicatorToggles;

  // Playback
  isPlaying: boolean;
  timeframe: Timeframe;
  speedMs: number;
  speedPreset: SpeedPreset;

  // Market
  candles: Candle[];
  currentCandle: Candle | null;
  marketIndex: number;
  chartIndicators: Indicators;
  equityCurve: EquityCurve;

  // Trade
  balanceUsdt: number;
  availableBalance: number;
  position: Position | null;
  stats: Stats;
  tradeHistory: TradeRecord[];

  // Bots
  bots: Bot[];
  botLogs: string[];

  // LLM Bots
  llmBots: LlmBotMeta[];
  lastBotTestReport: { botId: string; report: SandboxReport } | null;

  // Loading flags
  isLoadingMarket: boolean;
  isLoadingTrade: boolean;
}

// ─── Action Shape ─────────────────────────────────────────────────────────────

interface AppActions {
  // Init
  initialize(): Promise<void>;
  loadSession(params: { source: 'csv' | 'yfinance' | 'ccxt' | 'mock'; startDate?: string; endDate?: string; csvPath?: string }): Promise<{ ok: boolean }>;

  // UI
  setActiveTab(tab: TabId): void;
  toggleIndicator(key: keyof IndicatorToggles): void;

  // Playback
  play(): Promise<void>;
  pause(): Promise<void>;
  step(): Promise<void>;
  fastForward(batchSize?: number): Promise<void>;
  setTimeframe(tf: Timeframe): Promise<void>;
  setSpeed(preset?: SpeedPreset, speedMs?: number): Promise<void>;

  // Market refresh
  refreshMarket(): Promise<void>;
  refreshTrade(): Promise<void>;

  // Trade actions
  openTrade(params: {
    direction: 'long' | 'short';
    marginUsdt: number;
    leverage: number;
    stopLoss?: number;
    takeProfit?: number;
  }): Promise<{ success: boolean; message: string }>;
  closeTrade(): Promise<{ closed: boolean }>;
  closeTradePartial(fraction: number): Promise<{ partial: boolean }>;
  updateTrade(params: { stopLoss?: number; takeProfit?: number }): Promise<{ success: boolean }>;

  // Bots
  refreshBots(): Promise<void>;
  toggleBot(name: string, enabled: boolean): Promise<void>;
  refreshLogs(): Promise<void>;

  // LLM Bots
  refreshLlmBots(): Promise<void>;
  generateLlmBot(payload: {
    name: string;
    timeframe: Timeframe;
    description: string;
    constraints?: Record<string, string>;
  }): Promise<{ ok: boolean; botId?: string; error?: string; raw?: string }>;
  testLlmBot(payload: { botId: string; maxSteps?: number; timeoutSec?: number }): Promise<{
    ok: boolean;
    report?: SandboxReport;
    error?: string;
  }>;

  // WebSocket handler
  handleWsEvent(event: WsEvent): void;

  // Connection
  setConnectionStatus(status: ConnectionStatus): void;
}

// ─── Default State ────────────────────────────────────────────────────────────

const defaultStats: Stats = {
  win_rate_pct: 0,
  total_pnl: 0,
  max_drawdown: 0,
  total_trades: 0,
  total_commission: 0,
  total_return_pct: 0,
  sharpe_ratio: 0,
};

// ─── Store ────────────────────────────────────────────────────────────────────

export const useAppStore = create<AppState & AppActions>()(
  subscribeWithSelector((set, get) => ({
    // ─ Initial State ───────────────────────────────────────────────────────
    connectionStatus: 'connecting',
    isMockMode: wsClient.isMock,
    sessionId: null,
    datasetInfo: '—',

    activeTab: 'chart',
    indicators: {
      volume: true,
      rsi: false,
      macd: false,
      ema20: true,
      ema50: true,
      equity: false,
    },

    isPlaying: false,
    timeframe: '1m',
    speedMs: 100,
    speedPreset: '10x',

    candles: [],
    currentCandle: null,
    marketIndex: 0,
    chartIndicators: {},
    equityCurve: { x: [], y: [] },

    balanceUsdt: 0,
    availableBalance: 0,
    position: null,
    stats: defaultStats,
    tradeHistory: [],

    bots: [],
    botLogs: [],
    llmBots: [],
    lastBotTestReport: null,

    isLoadingMarket: false,
    isLoadingTrade: false,

    // ─ Actions ─────────────────────────────────────────────────────────────

    async initialize() {
      try {
        // Load session info
        const session = await api.getSession();
        set({
          sessionId: session.sessionId,
          timeframe: (session.playback.timeframe as Timeframe) ?? '1m',
          speedMs: session.playback.speedMs ?? 100,
          speedPreset: (session.playback.preset as SpeedPreset) ?? '10x',
          datasetInfo: `${session.dataset.source.toUpperCase()} | ${session.dataset.start?.slice(0, 10) ?? '?'} → ${session.dataset.end?.slice(0, 10) ?? '?'}`,
        });

        // Load market + trade state
        await Promise.all([get().refreshMarket(), get().refreshTrade()]);

        // Connect WebSocket
        wsClient.connect();
        wsClient.onStatus((status) => {
          get().setConnectionStatus(
            status === 'connected'
              ? 'connected'
              : status === 'error'
              ? 'error'
              : 'disconnected'
          );
        });
        wsClient.onEvent((ev) => get().handleWsEvent(ev));

        // In mock mode, mark as connected right away
        if (wsClient.isMock) {
          set({ connectionStatus: 'connected' });
        }

        // Bots & logs
        await Promise.all([get().refreshBots(), get().refreshLogs(), get().refreshLlmBots()]);
      } catch (err) {
        console.error('[Store] initialize error:', err);
        set({ connectionStatus: 'error' });
      }
    },

    async loadSession(params) {
      const res = await api.loadSession({
        source: params.source,
        startDate: params.startDate,
        endDate: params.endDate,
        csvPath: params.csvPath,
      });
      // After loading, refresh everything so UI matches the new dataset
      await get().initialize();
      return res;
    },

    setActiveTab(tab) {
      set({ activeTab: tab });
    },

    toggleIndicator(key) {
      set((s) => ({
        indicators: { ...s.indicators, [key]: !s.indicators[key] },
      }));
    },

    // Playback
    async play() {
      await api.play();
      set({ isPlaying: true });
    },
    async pause() {
      await api.pause();
      set({ isPlaying: false });
    },
    async step() {
      await api.step();
      await get().refreshMarket();
    },
    async fastForward(batchSize?: number) {
      await api.fastForward(batchSize);
      await get().refreshMarket();
      await get().refreshTrade();
    },
    async setTimeframe(tf) {
      await api.setTimeframe(tf);
      set({ timeframe: tf });
      await get().refreshMarket();
    },
    async setSpeed(preset, speedMs) {
      await api.setSpeed({ preset, speedMs });
      if (preset) set({ speedPreset: preset });
      if (speedMs !== undefined) set({ speedMs });
    },

    // Market
    async refreshMarket() {
      set({ isLoadingMarket: true });
      try {
        const state = await api.getMarketState();
        set({
          candles: state.displayCandles,
          currentCandle: state.currentCandle,
          marketIndex: state.index,
          chartIndicators: state.indicators ?? {},
          equityCurve: state.equity ?? { x: [], y: [] },
        });
      } catch (err) {
        console.error('[Store] refreshMarket error:', err);
      } finally {
        set({ isLoadingMarket: false });
      }
    },

    async refreshTrade() {
      set({ isLoadingTrade: true });
      try {
        const state = await api.getTradeState();
        set({
          balanceUsdt: state.balanceUsdt,
          availableBalance: state.availableBalance,
          position: state.position,
          stats: state.stats,
          tradeHistory: state.tradeHistory,
        });
      } catch (err) {
        console.error('[Store] refreshTrade error:', err);
      } finally {
        set({ isLoadingTrade: false });
      }
    },

    // Trade actions
    async openTrade(params) {
      const currentPrice = get().currentCandle?.close ?? 0;
      const res = await api.openTrade({
        direction: params.direction,
        entryPrice: currentPrice,
        marginUsdt: params.marginUsdt,
        leverage: params.leverage,
        stopLoss: params.stopLoss,
        takeProfit: params.takeProfit,
        openedBy: 'Manuel',
      });
      if (res.success && res.position) {
        set({ position: res.position });
      }
      return { success: res.success, message: res.message };
    },

    async closeTrade() {
      const currentPrice = get().currentCandle?.close ?? 0;
      const res = await api.closeTrade(currentPrice);
      if (res.closed) {
        await get().refreshTrade();
      }
      return { closed: res.closed };
    },

    async closeTradePartial(fraction) {
      const currentPrice = get().currentCandle?.close ?? 0;
      const res = await api.closeTradePartial({ exitPrice: currentPrice, fraction });
      if (res.partial) {
        await get().refreshTrade();
        await get().refreshMarket();
      }
      return { partial: res.partial };
    },

    async updateTrade(params) {
      const res = await api.updateTrade(params);
      if (res.success && res.position) {
        set({ position: res.position });
      }
      return { success: res.success };
    },

    // Bots
    async refreshBots() {
      const res = await api.getBots();
      set({ bots: res.bots });
    },
    async toggleBot(name, enabled) {
      await api.toggleBot(name, enabled);
      set((s) => ({
        bots: s.bots.map((b) => (b.name === name ? { ...b, enabled } : b)),
      }));
    },
    async refreshLogs() {
      const res = await api.getLogs();
      set({ botLogs: res.botLogs });
    },

    // LLM bots
    async refreshLlmBots() {
      const res = await api.getLlmBots();
      set({ llmBots: res.bots });
    },

    async generateLlmBot(payload) {
      const res = await api.generateLlmBot(payload);
      if (res.ok) {
        await Promise.all([get().refreshBots(), get().refreshLlmBots()]);
      }
      return { ok: !!res.ok, botId: res.botId, error: res.error, raw: res.raw };
    },

    async testLlmBot(payload) {
      const res = await api.testLlmBot(payload);
      if (res.ok && res.report) {
        set({ lastBotTestReport: { botId: payload.botId, report: res.report as SandboxReport } });
        await get().refreshTrade();
        await get().refreshMarket();
        await get().refreshLlmBots();
      }
      return res;
    },

    // WebSocket events
    handleWsEvent(event) {
      switch (event.type) {
        case 'candle':
          set((s) => {
            const candles = [...s.candles];
            // Replace last if same timestamp, else push
            if (candles.length > 0 && candles[candles.length - 1].time === event.candle.time) {
              candles[candles.length - 1] = event.candle;
            } else {
              candles.push(event.candle);
              if (candles.length > 500) candles.shift();
            }
            return {
              candles,
              currentCandle: event.candle,
              marketIndex: event.index,
            };
          });
          break;
        case 'stats':
          set({
            stats: event.stats,
            balanceUsdt: event.balanceUsdt,
            position: event.position,
          });
          break;
        case 'tradeClosed':
          set((s) => ({
            tradeHistory: [...s.tradeHistory, event.record],
            position: null,
          }));
          get().refreshTrade();
          break;
        case 'log':
          set((s) => ({
            botLogs: [...s.botLogs.slice(-199), event.message],
          }));
          break;
        case 'botGenerated':
          get().refreshBots();
          get().refreshLlmBots();
          break;
        case 'botTestReport':
          set({ lastBotTestReport: { botId: event.botId, report: event.report as SandboxReport } });
          get().refreshLlmBots();
          break;
        case 'tfClose':
          // Refresh on timeframe close
          get().refreshMarket();
          break;
      }
    },

    setConnectionStatus(status) {
      set({ connectionStatus: status });
    },
  }))
);

export default useAppStore;
