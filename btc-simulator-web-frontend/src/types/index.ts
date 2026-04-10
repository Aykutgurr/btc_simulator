// ─── Core Data Types ──────────────────────────────────────────────────────────

export interface Candle {
  time: string; // ISO or "YYYY-MM-DD HH:mm:ss"
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Position {
  direction: 'long' | 'short';
  entry_price: number;
  leverage: number;
  margin_usdt: number;
  liquidation_price: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  opened_by: string;
  entry_time: string;
}

export interface TradeRecord {
  tarih: string;
  yon: string;
  giris_fiyat: number;
  cikis_fiyat: number;
  marjin: number;
  pnl: number;
  roe_pct: number;
  kapanis_sebebi: string;
  tetikleyici: string;
  komisyon: number;
  bakiye: number;
  entry_time?: string;
  exit_time?: string;
}

export interface Stats {
  win_rate_pct: number;
  total_pnl: number;
  max_drawdown: number;
  total_trades: number;
  total_commission: number;
  total_return_pct: number;
  sharpe_ratio: number;
}

export interface Bot {
  name: string;
  timeframe: string;
  enabled: boolean;
}

// ─── API Response Types ───────────────────────────────────────────────────────

export interface SessionDataset {
  source: string;
  csvPath?: string;
  start: string;
  end: string;
}

export interface SessionPlayback {
  timeframe: string;
  speedMs: number;
  preset: string;
}

export interface SessionConnection {
  ws: boolean;
}

export interface SessionResponse {
  sessionId: string;
  dataset: SessionDataset;
  playback: SessionPlayback;
  connection: SessionConnection;
}

export interface Indicators {
  rsi?: number[];
  macd?: { macd: number[]; signal: number[] };
  ema20?: number[];
  ema50?: number[];
}

export interface EquityCurve {
  x: number[];
  y: number[];
}

export interface MarketStateResponse {
  index: number;
  currentCandle: Candle | null;
  displayCandles: Candle[];
  indicators?: Indicators;
  equity?: EquityCurve;
}

export interface TradeStateResponse {
  balanceUsdt: number;
  availableBalance: number;
  position: Position | null;
  stats: Stats;
  tradeHistory: TradeRecord[];
}

export interface OpenTradeRequest {
  direction: 'long' | 'short';
  entryPrice: number;
  marginUsdt: number;
  leverage: number;
  stopLoss?: number;
  takeProfit?: number;
  openedBy: string;
}

export interface OpenTradeResponse {
  success: boolean;
  message: string;
  position?: Position;
}

export interface CloseTradeResponse {
  closed: boolean;
  record?: TradeRecord;
}

export interface BotsResponse {
  bots: Bot[];
}

export interface LogsResponse {
  botLogs: string[];
}

// ─── LLM Bot Builder Types ────────────────────────────────────────────────────

export interface LlmBotMeta {
  id: string;
  name: string;
  timeframe: string;
  path?: string;
  enabled?: boolean;
  createdAt?: string;
  lastTest?: unknown;
}

export interface LlmBotsResponse {
  bots: LlmBotMeta[];
}

// ─── Playback Types ───────────────────────────────────────────────────────────

export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h';
export type SpeedPreset = '1x' | '10x' | '100x' | 'Max Hız';

// ─── WebSocket Event Types ────────────────────────────────────────────────────

export type WsEventType =
  | 'candle'
  | 'tfClose'
  | 'tradeClosed'
  | 'stats'
  | 'log'
  | 'botGenerated'
  | 'botTestReport';

export interface WsCandleEvent {
  type: 'candle';
  candle: Candle;
  index: number;
}

export interface WsTfCloseEvent {
  type: 'tfClose';
  timeframe: string;
  candle: Candle;
}

export interface WsTradeClosedEvent {
  type: 'tradeClosed';
  record: TradeRecord;
}

export interface WsStatsEvent {
  type: 'stats';
  stats: Stats;
  balanceUsdt: number;
  position: Position | null;
}

export interface WsLogEvent {
  type: 'log';
  message: string;
}

export interface WsBotGeneratedEvent {
  type: 'botGenerated';
  botId: string;
  name: string;
  timeframe: string;
}

export interface WsBotTestReportEvent {
  type: 'botTestReport';
  botId: string;
  report: unknown;
}

export type WsEvent =
  | WsCandleEvent
  | WsTfCloseEvent
  | WsTradeClosedEvent
  | WsStatsEvent
  | WsLogEvent
  | WsBotGeneratedEvent
  | WsBotTestReportEvent;

// ─── UI State Types ───────────────────────────────────────────────────────────

export type TabId = 'chart' | 'bots' | 'log';

export interface IndicatorToggles {
  volume: boolean;
  rsi: boolean;
  macd: boolean;
  ema20: boolean;
  ema50: boolean;
  equity: boolean;
}

export type ConnectionStatus = 'connected' | 'disconnected' | 'connecting' | 'error';
