/**
 * ControlsPanel — timeframe, play/pause/step/ff controls,
 * speed presets, ms slider, indicator toggles.
 */

import { useCallback } from 'react';
import {
  Play,
  Pause,
  SkipForward,
  FastForward,
  BarChart2,
  TrendingUp,
  Activity,
  LineChart,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { Slider } from '../ui/Input';
import { useAppStore } from '../../store/useAppStore';
import type { Timeframe, SpeedPreset, IndicatorToggles } from '../../types';
import { clsn } from '../../utils/format';

const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '4h'];
const SPEED_PRESETS: SpeedPreset[] = ['1x', '10x', '100x', 'Max Hız'];

const INDICATOR_CONFIG: { key: keyof IndicatorToggles; label: string; icon: React.ReactNode }[] = [
  { key: 'volume', label: 'Vol', icon: <BarChart2 size={12} /> },
  { key: 'rsi', label: 'RSI', icon: <Activity size={12} /> },
  { key: 'macd', label: 'MACD', icon: <TrendingUp size={12} /> },
  { key: 'ema20', label: 'EMA20', icon: <LineChart size={12} /> },
  { key: 'ema50', label: 'EMA50', icon: <LineChart size={12} /> },
  { key: 'equity', label: 'Equity', icon: <TrendingUp size={12} /> },
];

export function ControlsPanel() {
  const {
    isPlaying,
    timeframe,
    speedMs,
    speedPreset,
    indicators,
    play,
    pause,
    step,
    fastForward,
    setTimeframe,
    setSpeed,
    toggleIndicator,
  } = useAppStore();

  const handlePlayPause = useCallback(() => {
    if (isPlaying) pause();
    else play();
  }, [isPlaying, play, pause]);

  const handleSpeedMs = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = Number(e.target.value);
      setSpeed(undefined, val);
    },
    [setSpeed]
  );

  return (
    <div className="flex flex-wrap items-center gap-2 px-3 py-2 bg-zinc-900 border-b border-zinc-800">
      {/* Timeframe */}
      <div className="flex items-center gap-1">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => setTimeframe(tf)}
            className={clsn(
              'px-2.5 py-1 text-xs font-semibold rounded transition-all',
              timeframe === tf
                ? 'bg-sky-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200'
            )}
          >
            {tf}
          </button>
        ))}
      </div>

      <div className="w-px h-6 bg-zinc-700" />

      {/* Playback controls */}
      <div className="flex items-center gap-1">
        <Button
          variant={isPlaying ? 'warning' : 'success'}
          size="sm"
          onClick={handlePlayPause}
          leftIcon={isPlaying ? <Pause size={13} /> : <Play size={13} />}
        >
          {isPlaying ? 'Duraklat' : 'Oynat'}
        </Button>
        <Button variant="ghost" size="sm" onClick={step} leftIcon={<SkipForward size={13} />}>
          Adım
        </Button>
        <Button variant="ghost" size="sm" onClick={fastForward} leftIcon={<FastForward size={13} />}>
          Hızlı
        </Button>
      </div>

      <div className="w-px h-6 bg-zinc-700" />

      {/* Speed presets */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-zinc-500 mr-1">Hız:</span>
        {SPEED_PRESETS.map((p) => (
          <button
            key={p}
            onClick={() => setSpeed(p, undefined)}
            className={clsn(
              'px-2 py-1 text-xs font-mono rounded transition-all',
              speedPreset === p
                ? 'bg-sky-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
            )}
          >
            {p}
          </button>
        ))}
      </div>

      {/* MS slider */}
      <div className="flex items-center gap-2 min-w-[120px]">
        <Slider
          min={10}
          max={2000}
          step={10}
          value={speedMs}
          onChange={handleSpeedMs}
          valueLabel={`${speedMs}ms`}
        />
      </div>

      <div className="w-px h-6 bg-zinc-700" />

      {/* Indicator toggles */}
      <div className="flex items-center gap-1 flex-wrap">
        <span className="text-xs text-zinc-500 mr-1">İndikatör:</span>
        {INDICATOR_CONFIG.map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => toggleIndicator(key)}
            className={clsn(
              'flex items-center gap-1 px-2 py-1 text-xs rounded border transition-all',
              indicators[key]
                ? 'bg-sky-600/20 text-sky-400 border-sky-600/50'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700 hover:text-zinc-300'
            )}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
