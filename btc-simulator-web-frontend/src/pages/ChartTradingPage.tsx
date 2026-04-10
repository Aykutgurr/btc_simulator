/**
 * Tab 1: Chart & Trading
 * Layout: controls top bar, candlestick chart (center), futures panel (right side).
 */

import { useAppStore } from '../store/useAppStore';
import { ControlsPanel } from '../components/panels/ControlsPanel';
import { CandlestickChart } from '../components/chart/CandlestickChart';
import { EquityChart } from '../components/chart/EquityChart';
import { FuturesPanel } from '../components/panels/FuturesPanel';
import { LiveTradesTable } from '../components/panels/LiveTradesTable';

export function ChartTradingPage() {
  const { candles, chartIndicators, indicators, tradeHistory, currentCandle, equityCurve } =
    useAppStore();

  const currentPrice = currentCandle?.close;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Top controls bar */}
      <ControlsPanel />

      {/* Main content area */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Chart area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden p-2 gap-2">
          {/* Candlestick */}
          <div className="flex-1 min-h-0" style={{ minHeight: 300 }}>
            <CandlestickChart
              candles={candles}
              indicators={chartIndicators}
              indicatorToggles={indicators}
              tradeHistory={tradeHistory}
              currentPrice={currentPrice}
            />
          </div>

          {/* Equity curve (optional) */}
          {indicators.equity && equityCurve.x.length > 0 && (
            <div className="h-40 bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
              <EquityChart equity={equityCurve} />
            </div>
          )}

          {/* Live trades table */}
          <LiveTradesTable />
        </div>

        {/* Right sidebar — Futures Panel */}
        <div className="w-80 flex-shrink-0 border-l border-zinc-800 overflow-y-auto p-2">
          <FuturesPanel />
        </div>
      </div>
    </div>
  );
}
