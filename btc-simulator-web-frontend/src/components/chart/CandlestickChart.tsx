/**
 * CandlestickChart — lightweight-charts v5 wrapper.
 * Renders: candlesticks, EMA20/50 overlays, buy/sell markers,
 * optional volume sub-histogram, RSI + MACD sub-charts.
 */

import { useEffect, useRef, useCallback } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  LineData,
  HistogramData,
  Time,
  CrosshairMode,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  createSeriesMarkers,
  ISeriesMarkersPluginApi,
  SeriesMarker,
} from 'lightweight-charts';
import type { Candle, Indicators, TradeRecord } from '../../types';
import type { IndicatorToggles } from '../../types';

interface CandlestickChartProps {
  candles: Candle[];
  indicators: Indicators;
  indicatorToggles: IndicatorToggles;
  tradeHistory: TradeRecord[];
  currentPrice?: number;
}

function toTime(iso: string): Time {
  return Math.floor(new Date(iso).getTime() / 1000) as unknown as Time;
}

function candlesToLwc(candles: Candle[]): CandlestickData[] {
  const seen = new Set<number>();
  return candles
    .filter((c) => c.time)
    .map((c) => ({
      time: toTime(c.time),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    .filter((d) => {
      const t = d.time as unknown as number;
      if (seen.has(t)) return false;
      seen.add(t);
      return true;
    })
    .sort((a, b) => (a.time as unknown as number) - (b.time as unknown as number));
}

function buildLineData(candles: Candle[], values: number[]): LineData[] {
  const seen = new Set<number>();
  return candles
    .slice(0, values.length)
    .map((c, i) => ({ time: toTime(c.time), value: values[i] }))
    .filter((d) => {
      const t = d.time as unknown as number;
      if (seen.has(t)) return false;
      seen.add(t);
      return true;
    })
    .sort((a, b) => (a.time as unknown as number) - (b.time as unknown as number));
}

function buildVolumeData(candles: Candle[]): HistogramData[] {
  const seen = new Set<number>();
  return candles
    .filter((c) => c.time)
    .map((c) => ({
      time: toTime(c.time),
      value: c.volume,
      color: c.close >= c.open ? 'rgba(16,185,129,0.4)' : 'rgba(244,63,94,0.4)',
    }))
    .filter((d) => {
      const t = d.time as unknown as number;
      if (seen.has(t)) return false;
      seen.add(t);
      return true;
    })
    .sort((a, b) => (a.time as unknown as number) - (b.time as unknown as number));
}

const CHART_LAYOUT = { background: { color: '#0f0f11' }, textColor: '#a1a1aa' };
const CHART_GRID = { vertLines: { color: '#18181b' }, horzLines: { color: '#18181b' } };

export function CandlestickChart({
  candles,
  indicators,
  indicatorToggles,
  tradeHistory,
  currentPrice,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rsiContainerRef = useRef<HTMLDivElement>(null);
  const macdContainerRef = useRef<HTMLDivElement>(null);

  const mainChartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const macdChartRef = useRef<IChartApi | null>(null);

  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const ema20SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ema50SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const macdLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<'Line'> | null>(null);
  const macdHistRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  const buildMarkers = useCallback((trades: TradeRecord[]): SeriesMarker<Time>[] => {
    const markers: SeriesMarker<Time>[] = [];
    trades.forEach((t) => {
      if (t.entry_time) {
        markers.push({
          time: toTime(t.entry_time),
          position: t.yon === 'Long' ? 'belowBar' : 'aboveBar',
          color: t.yon === 'Long' ? '#10b981' : '#f43f5e',
          shape: t.yon === 'Long' ? 'arrowUp' : 'arrowDown',
          text: t.yon,
        });
      }
      if (t.exit_time) {
        markers.push({
          time: toTime(t.exit_time),
          position: t.yon === 'Long' ? 'aboveBar' : 'belowBar',
          color: t.pnl >= 0 ? '#10b981' : '#f43f5e',
          shape: 'circle',
          text: t.pnl >= 0 ? `+$${t.pnl.toFixed(0)}` : `-$${Math.abs(t.pnl).toFixed(0)}`,
        });
      }
    });
    return markers.sort(
      (a, b) => (a.time as unknown as number) - (b.time as unknown as number)
    );
  }, []);

  // ── Init ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const sharedOptions = {
      layout: CHART_LAYOUT,
      grid: CHART_GRID,
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#27272a' },
      rightPriceScale: { borderColor: '#27272a' },
    };

    // Main chart
    const mainChart = createChart(containerRef.current, {
      ...sharedOptions,
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });
    mainChartRef.current = mainChart;

    // Candlestick
    const candleSeries = mainChart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#f43f5e',
      borderUpColor: '#10b981',
      borderDownColor: '#f43f5e',
      wickUpColor: '#10b981',
      wickDownColor: '#f43f5e',
    });
    candleSeriesRef.current = candleSeries;

    // Markers plugin
    markersPluginRef.current = createSeriesMarkers(candleSeries, []);

    // Volume
    const volumeSeries = mainChart.addSeries(HistogramSeries, {
      priceScaleId: 'vol',
      priceFormat: { type: 'volume' },
    });
    mainChart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    volumeSeriesRef.current = volumeSeries;

    // EMA20
    ema20SeriesRef.current = mainChart.addSeries(LineSeries, {
      color: '#f59e0b',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    // EMA50
    ema50SeriesRef.current = mainChart.addSeries(LineSeries, {
      color: '#8b5cf6',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    // RSI chart
    if (rsiContainerRef.current) {
      const rsiChart = createChart(rsiContainerRef.current, {
        ...sharedOptions,
        width: rsiContainerRef.current.clientWidth,
        height: rsiContainerRef.current.clientHeight,
        timeScale: { ...sharedOptions.timeScale, visible: false },
      });
      rsiChartRef.current = rsiChart;

      mainChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) rsiChart.timeScale().setVisibleLogicalRange(range);
      });
      rsiChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) mainChart.timeScale().setVisibleLogicalRange(range);
      });

      rsiSeriesRef.current = rsiChart.addSeries(LineSeries, {
        color: '#38bdf8',
        lineWidth: 2,
        priceLineVisible: false,
      });
    }

    // MACD chart
    if (macdContainerRef.current) {
      const macdChart = createChart(macdContainerRef.current, {
        ...sharedOptions,
        width: macdContainerRef.current.clientWidth,
        height: macdContainerRef.current.clientHeight,
        timeScale: { ...sharedOptions.timeScale, visible: false },
      });
      macdChartRef.current = macdChart;

      mainChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) macdChart.timeScale().setVisibleLogicalRange(range);
      });
      macdChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) mainChart.timeScale().setVisibleLogicalRange(range);
      });

      macdLineRef.current = macdChart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 2, priceLineVisible: false });
      macdSignalRef.current = macdChart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 2, priceLineVisible: false });
      macdHistRef.current = macdChart.addSeries(HistogramSeries, { priceScaleId: 'right', priceLineVisible: false });
    }

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current)
        mainChart.applyOptions({ width: containerRef.current.clientWidth });
      if (rsiContainerRef.current)
        rsiChartRef.current?.applyOptions({ width: rsiContainerRef.current.clientWidth });
      if (macdContainerRef.current)
        macdChartRef.current?.applyOptions({ width: macdContainerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      mainChart.remove();
      rsiChartRef.current?.remove();
      macdChartRef.current?.remove();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Update data ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return;

    try {
      const lwcData = candlesToLwc(candles);
      candleSeriesRef.current.setData(lwcData);

      volumeSeriesRef.current?.setData(buildVolumeData(candles));

      if (indicators.ema20) ema20SeriesRef.current?.setData(buildLineData(candles, indicators.ema20));
      if (indicators.ema50) ema50SeriesRef.current?.setData(buildLineData(candles, indicators.ema50));
      if (indicators.rsi) rsiSeriesRef.current?.setData(buildLineData(candles, indicators.rsi));

      if (indicators.macd) {
        macdLineRef.current?.setData(buildLineData(candles, indicators.macd.macd));
        macdSignalRef.current?.setData(buildLineData(candles, indicators.macd.signal));

        const seen = new Set<number>();
        const histData = candles
          .slice(0, indicators.macd.macd.length)
          .map((c, i) => {
            const val = indicators.macd!.macd[i] - indicators.macd!.signal[i];
            return {
              time: toTime(c.time),
              value: val,
              color: val >= 0 ? 'rgba(16,185,129,0.6)' : 'rgba(244,63,94,0.6)',
            };
          })
          .filter((d) => {
            const t = d.time as unknown as number;
            if (seen.has(t)) return false;
            seen.add(t);
            return true;
          })
          .sort((a, b) => (a.time as unknown as number) - (b.time as unknown as number));
        macdHistRef.current?.setData(histData);
      }

      // Markers
      if (markersPluginRef.current) {
        markersPluginRef.current.setMarkers(buildMarkers(tradeHistory));
      }

      mainChartRef.current?.timeScale().scrollToRealTime();
    } catch (err) {
      console.warn('[Chart] setData error:', err);
    }
  }, [candles, indicators, tradeHistory, buildMarkers]);

  // ── Toggle visibility ─────────────────────────────────────────────────────
  useEffect(() => { volumeSeriesRef.current?.applyOptions({ visible: indicatorToggles.volume }); }, [indicatorToggles.volume]);
  useEffect(() => { ema20SeriesRef.current?.applyOptions({ visible: indicatorToggles.ema20 }); }, [indicatorToggles.ema20]);
  useEffect(() => { ema50SeriesRef.current?.applyOptions({ visible: indicatorToggles.ema50 }); }, [indicatorToggles.ema50]);

  return (
    <div className="flex flex-col h-full w-full gap-0.5">
      {/* Main candlestick */}
      <div ref={containerRef} className="flex-1 min-h-0 w-full rounded-lg overflow-hidden" style={{ minHeight: 180 }} />

      {/* RSI */}
      {indicatorToggles.rsi && (
        <div className="w-full relative border-t border-zinc-800" style={{ height: 90 }}>
          <span className="absolute top-1 left-2 z-10 text-xs text-zinc-500 font-mono pointer-events-none">RSI(14)</span>
          <div ref={rsiContainerRef} className="w-full h-full rounded-b-lg overflow-hidden" />
        </div>
      )}

      {/* MACD */}
      {indicatorToggles.macd && (
        <div className="w-full relative border-t border-zinc-800" style={{ height: 90 }}>
          <span className="absolute top-1 left-2 z-10 text-xs text-zinc-500 font-mono pointer-events-none">MACD(12,26,9)</span>
          <div ref={macdContainerRef} className="w-full h-full rounded-b-lg overflow-hidden" />
        </div>
      )}

      {/* Live price */}
      {currentPrice != null && (
        <div className="flex items-center justify-end gap-2 px-2 py-1">
          <span className="text-zinc-500 text-xs">Anlık:</span>
          <span className="text-emerald-400 font-mono font-bold text-sm">
            ${currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
      )}
    </div>
  );
}
