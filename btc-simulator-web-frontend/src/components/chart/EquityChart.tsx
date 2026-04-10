/**
 * EquityChart — renders equity curve as a lightweight-charts Area chart.
 */

import { useEffect, useRef } from 'react';
import { createChart, IChartApi, AreaSeries, ISeriesApi } from 'lightweight-charts';
import type { EquityCurve } from '../../types';

interface EquityChartProps {
  equity: EquityCurve;
}

const CHART_LAYOUT = { background: { color: '#0f0f11' }, textColor: '#a1a1aa' };
const CHART_GRID = { vertLines: { color: '#18181b' }, horzLines: { color: '#18181b' } };

export function EquityChart({ equity }: EquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: CHART_LAYOUT,
      grid: CHART_GRID,
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      timeScale: { visible: true, borderColor: '#27272a' },
      rightPriceScale: { borderColor: '#27272a' },
    });
    chartRef.current = chart;

    seriesRef.current = chart.addSeries(AreaSeries, {
      lineColor: '#10b981',
      topColor: 'rgba(16,185,129,0.3)',
      bottomColor: 'rgba(16,185,129,0)',
      lineWidth: 2,
      priceLineVisible: false,
    });

    const ro = new ResizeObserver(() => {
      if (containerRef.current)
        chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || equity.x.length === 0) return;
    const data = equity.x
      .map((x, i) => ({
        time: x as unknown as import('lightweight-charts').Time,
        value: equity.y[i],
      }))
      .sort((a, b) => (a.time as unknown as number) - (b.time as unknown as number));
    try {
      seriesRef.current.setData(data);
    } catch (err) {
      console.warn('[EquityChart] setData error:', err);
    }
  }, [equity]);

  return (
    <div className="flex flex-col h-full">
      <div className="text-xs text-zinc-500 font-mono px-2 py-1">Equity Eğrisi</div>
      <div ref={containerRef} className="flex-1 min-h-0 w-full" />
    </div>
  );
}
