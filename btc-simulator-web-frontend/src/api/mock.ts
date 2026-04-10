/**
 * Mock data generator for development / demo mode.
 * When VITE_MOCK_MODE=true (or no backend is reachable) these helpers
 * produce realistic-looking BTC futures data so the UI renders fully.
 */

import type {
  Candle,
  Position,
  Stats,
  TradeRecord,
  Bot,
  SessionResponse,
  MarketStateResponse,
  TradeStateResponse,
  BotsResponse,
  LogsResponse,
} from '../types';

// ─── Candle Generator ─────────────────────────────────────────────────────────

function generateCandles(count = 200): Candle[] {
  const candles: Candle[] = [];
  let price = 65_000 + Math.random() * 5_000;
  const now = Date.now();
  const MINUTE = 60_000;

  for (let i = count; i >= 0; i--) {
    const ts = new Date(now - i * MINUTE);
    const open = price;
    const change = (Math.random() - 0.48) * 300;
    const high = open + Math.abs(change) + Math.random() * 150;
    const low = open - Math.abs(change) - Math.random() * 150;
    const close = open + change;
    price = close;

    candles.push({
      time: ts.toISOString(),
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume: parseFloat((Math.random() * 50 + 5).toFixed(4)),
    });
  }
  return candles;
}

// ─── Indicator Generator ──────────────────────────────────────────────────────

function generateRSI(count: number): number[] {
  return Array.from({ length: count }, (_, i) =>
    parseFloat((30 + 40 * Math.abs(Math.sin(i / 14))).toFixed(2))
  );
}

function generateMACD(count: number) {
  return {
    macd: Array.from({ length: count }, (_, i) =>
      parseFloat(((Math.random() - 0.5) * 200 * Math.sin(i / 20)).toFixed(2))
    ),
    signal: Array.from({ length: count }, (_, i) =>
      parseFloat(((Math.random() - 0.5) * 150 * Math.sin(i / 20 + 0.5)).toFixed(2))
    ),
  };
}

function generateEMA(candles: Candle[], period: number): number[] {
  const k = 2 / (period + 1);
  const ema: number[] = [];
  candles.forEach((c, i) => {
    if (i === 0) ema.push(c.close);
    else ema.push(parseFloat((c.close * k + ema[i - 1] * (1 - k)).toFixed(2)));
  });
  return ema;
}

// ─── Trade History ────────────────────────────────────────────────────────────

const CLOSE_REASONS = ['TP', 'SL', 'Manuel', 'Likidasyon'];
const TRIGGERS = ['Bot-RSI', 'Bot-MACD', 'Manuel', 'Bot-EMA'];
const DIRECTIONS = ['Long', 'Short'];

function generateTradeHistory(count = 30): TradeRecord[] {
  const records: TradeRecord[] = [];
  let balance = 10_000;
  const now = Date.now();

  for (let i = count; i >= 0; i--) {
    const entry = 60_000 + Math.random() * 10_000;
    const exit = entry + (Math.random() - 0.45) * 2_000;
    const margin = 100 + Math.floor(Math.random() * 400);
    const leverage = [5, 10, 20, 50][Math.floor(Math.random() * 4)];
    const yon = DIRECTIONS[Math.floor(Math.random() * 2)];
    const pnl_raw = yon === 'Long' ? exit - entry : entry - exit;
    const pnl = parseFloat(((pnl_raw / entry) * margin * leverage).toFixed(2));
    const commission = parseFloat((margin * 0.0004).toFixed(4));
    const roe_pct = parseFloat(((pnl / margin) * 100).toFixed(2));
    balance += pnl - commission;

    const entryTime = new Date(now - i * 3_600_000);
    const exitTime = new Date(entryTime.getTime() + Math.random() * 3_600_000);

    records.push({
      tarih: exitTime.toLocaleDateString('tr-TR'),
      yon,
      giris_fiyat: parseFloat(entry.toFixed(2)),
      cikis_fiyat: parseFloat(exit.toFixed(2)),
      marjin: margin,
      pnl,
      roe_pct,
      kapanis_sebebi: CLOSE_REASONS[Math.floor(Math.random() * CLOSE_REASONS.length)],
      tetikleyici: TRIGGERS[Math.floor(Math.random() * TRIGGERS.length)],
      komisyon: commission,
      bakiye: parseFloat(balance.toFixed(2)),
      entry_time: entryTime.toISOString(),
      exit_time: exitTime.toISOString(),
    });
  }
  return records;
}

// ─── Stats ────────────────────────────────────────────────────────────────────

function generateStats(trades: TradeRecord[]): Stats {
  const wins = trades.filter((t) => t.pnl > 0).length;
  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
  const totalCommission = trades.reduce((s, t) => s + t.komisyon, 0);
  const initBalance = 10_000;

  return {
    win_rate_pct: trades.length > 0 ? parseFloat(((wins / trades.length) * 100).toFixed(1)) : 0,
    total_pnl: parseFloat(totalPnl.toFixed(2)),
    max_drawdown: parseFloat((Math.random() * 15 + 5).toFixed(2)),
    total_trades: trades.length,
    total_commission: parseFloat(totalCommission.toFixed(4)),
    total_return_pct: parseFloat(((totalPnl / initBalance) * 100).toFixed(2)),
    sharpe_ratio: parseFloat((Math.random() * 2.5 - 0.5).toFixed(2)),
  };
}

// ─── Equity Curve ─────────────────────────────────────────────────────────────

function generateEquity(trades: TradeRecord[]): { x: number[]; y: number[] } {
  const x: number[] = [];
  const y: number[] = [];
  trades.forEach((t, i) => {
    x.push(i);
    y.push(t.bakiye);
  });
  return { x, y };
}

// ─── Bots ─────────────────────────────────────────────────────────────────────

const MOCK_BOTS: Bot[] = [
  { name: 'RSI-Bot', timeframe: '1m', enabled: true },
  { name: 'MACD-Bot', timeframe: '5m', enabled: false },
  { name: 'EMA-Cross', timeframe: '15m', enabled: true },
  { name: 'Trend-Follow', timeframe: '1h', enabled: false },
  { name: 'Scalper-v2', timeframe: '1m', enabled: false },
];

// ─── Log Messages ─────────────────────────────────────────────────────────────

function generateLogs(count = 50): string[] {
  const templates = [
    '[RSI-Bot] RSI=28.4 → Long sinyal, giriş: $64,320',
    '[MACD-Bot] MACD kesişimi yok, bekleniyor...',
    '[EMA-Cross] EMA20 > EMA50 → Long açıldı',
    '[RSI-Bot] TP tetiklendi → PnL: +$142.30',
    '[Trend-Follow] ATR filtresi geçilemedi, sinyal atlandı',
    '[MACD-Bot] Short sinyal üretildi: $65,110',
    '[Scalper-v2] SL tetiklendi → PnL: -$48.20',
    '[RSI-Bot] RSI=72.1 → Short sinyal',
    '[EMA-Cross] EMA sıkışması, pozisyon açılmadı',
    '[MACD-Bot] Histogram pozitif, long sinyal bekleniyor',
  ];

  const logs: string[] = [];
  const now = Date.now();
  for (let i = count; i >= 0; i--) {
    const ts = new Date(now - i * 45_000);
    const msg = templates[Math.floor(Math.random() * templates.length)];
    logs.push(`[${ts.toLocaleTimeString('tr-TR')}] ${msg}`);
  }
  return logs;
}

// ─── Public Mock State ────────────────────────────────────────────────────────

// Build once so data is consistent across mock calls
const CANDLES = generateCandles(200);
const TRADES = generateTradeHistory(30);
const STATS = generateStats(TRADES);
const EQUITY = generateEquity(TRADES);
const RSI = generateRSI(CANDLES.length);
const MACD = generateMACD(CANDLES.length);
const EMA20 = generateEMA(CANDLES, 20);
const EMA50 = generateEMA(CANDLES, 50);

let mockBalance = TRADES.length > 0 ? TRADES[TRADES.length - 1].bakiye : 10_000;
let mockPosition: Position | null = null;
let mockBots: Bot[] = [...MOCK_BOTS];
let mockLogs: string[] = generateLogs(50);
let mockTradeHistory: TradeRecord[] = [...TRADES];

// ─── Mock API Handlers ────────────────────────────────────────────────────────

export const mockHandlers = {
  getSession(): SessionResponse {
    return {
      sessionId: 'mock-session-001',
      dataset: {
        source: 'mock',
        start: CANDLES[0].time,
        end: CANDLES[CANDLES.length - 1].time,
      },
      playback: { timeframe: '1m', speedMs: 100, preset: '10x' },
      connection: { ws: false },
    };
  },

  getMarketState(): MarketStateResponse {
    return {
      index: CANDLES.length - 1,
      currentCandle: CANDLES[CANDLES.length - 1],
      displayCandles: CANDLES,
      indicators: { rsi: RSI, macd: MACD, ema20: EMA20, ema50: EMA50 },
      equity: EQUITY,
    };
  },

  getTradeState(): TradeStateResponse {
    return {
      balanceUsdt: mockBalance,
      availableBalance: mockBalance - (mockPosition ? mockPosition.margin_usdt : 0),
      position: mockPosition,
      stats: STATS,
      tradeHistory: mockTradeHistory,
    };
  },

  openTrade(req: {
    direction: 'long' | 'short';
    marginUsdt: number;
    leverage: number;
    stopLoss?: number;
    takeProfit?: number;
  }): { success: boolean; message: string; position?: Position } {
    if (mockPosition) {
      return { success: false, message: 'Zaten açık bir pozisyon var.' };
    }
    const currentPrice = CANDLES[CANDLES.length - 1].close;
    const liqDist = (1 / req.leverage) * currentPrice;
    mockPosition = {
      direction: req.direction,
      entry_price: currentPrice,
      leverage: req.leverage,
      margin_usdt: req.marginUsdt,
      liquidation_price:
        req.direction === 'long'
          ? parseFloat((currentPrice - liqDist).toFixed(2))
          : parseFloat((currentPrice + liqDist).toFixed(2)),
      stop_loss: req.stopLoss ?? null,
      take_profit: req.takeProfit ?? null,
      opened_by: 'Manuel',
      entry_time: new Date().toISOString(),
    };
    mockBalance -= req.marginUsdt;
    return { success: true, message: 'Pozisyon açıldı.', position: mockPosition };
  },

  closeTrade(): { closed: boolean; record?: TradeRecord } {
    if (!mockPosition) return { closed: false };
    const exitPrice = CANDLES[CANDLES.length - 1].close;
    const pnl_raw =
      mockPosition.direction === 'long'
        ? exitPrice - mockPosition.entry_price
        : mockPosition.entry_price - exitPrice;
    const pnl = parseFloat(
      ((pnl_raw / mockPosition.entry_price) * mockPosition.margin_usdt * mockPosition.leverage).toFixed(2)
    );
    const commission = parseFloat((mockPosition.margin_usdt * 0.0004).toFixed(4));
    const roe_pct = parseFloat(((pnl / mockPosition.margin_usdt) * 100).toFixed(2));
    mockBalance += mockPosition.margin_usdt + pnl - commission;

    const record: TradeRecord = {
      tarih: new Date().toLocaleDateString('tr-TR'),
      yon: mockPosition.direction === 'long' ? 'Long' : 'Short',
      giris_fiyat: mockPosition.entry_price,
      cikis_fiyat: exitPrice,
      marjin: mockPosition.margin_usdt,
      pnl,
      roe_pct,
      kapanis_sebebi: 'Manuel',
      tetikleyici: 'Manuel',
      komisyon: commission,
      bakiye: parseFloat(mockBalance.toFixed(2)),
      entry_time: mockPosition.entry_time,
      exit_time: new Date().toISOString(),
    };
    mockTradeHistory.push(record);
    mockPosition = null;
    return { closed: true, record };
  },

  getBots(): BotsResponse {
    return { bots: mockBots };
  },

  toggleBot(name: string, enabled: boolean) {
    mockBots = mockBots.map((b) => (b.name === name ? { ...b, enabled } : b));
    return { success: true };
  },

  getLogs(): LogsResponse {
    return { botLogs: mockLogs };
  },

  pushLog(message: string) {
    mockLogs = [...mockLogs.slice(-199), `[${new Date().toLocaleTimeString('tr-TR')}] ${message}`];
  },
};

export type MockHandlers = typeof mockHandlers;
