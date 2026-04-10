/**
 * BotLogViewer — scrollable log viewer for bot messages.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { RefreshCw, Trash2, ChevronDown } from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { useAppStore } from '../../store/useAppStore';

export function BotLogViewer() {
  const { botLogs, refreshLogs } = useAppStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState('');

  // Auto-scroll on new logs
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [botLogs, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollTop + clientHeight >= scrollHeight - 20);
  }, []);

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      setAutoScroll(true);
    }
  };

  const filteredLogs = filter
    ? botLogs.filter((l) => l.toLowerCase().includes(filter.toLowerCase()))
    : botLogs;

  const colorize = (line: string) => {
    if (line.includes('TP') || line.includes('uzun') || line.includes('Long') || line.includes('+')) {
      return 'text-emerald-400';
    }
    if (line.includes('SL') || line.includes('Short') || line.includes('Likidasyon')) {
      return 'text-rose-400';
    }
    if (line.includes('bekleniyor') || line.includes('yok') || line.includes('Pasif')) {
      return 'text-zinc-500';
    }
    return 'text-zinc-300';
  };

  return (
    <Card
      title="Bot Logları"
      titleRight={
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Filtrele..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-sky-500 w-28"
          />
          <Button variant="ghost" size="xs" onClick={refreshLogs} leftIcon={<RefreshCw size={11} />}>
            Yenile
          </Button>
        </div>
      }
      noPad
    >
      <div className="relative">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-64 overflow-y-auto p-3 font-mono text-xs leading-5 space-y-0.5"
        >
          {filteredLogs.length === 0 && (
            <div className="text-zinc-600 text-center py-4">
              {filter ? 'Eşleşen log bulunamadı' : 'Henüz log yok'}
            </div>
          )}
          {filteredLogs.map((line, i) => (
            <div key={i} className={colorize(line)}>
              {line}
            </div>
          ))}
        </div>

        {/* Scroll to bottom button */}
        {!autoScroll && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-3 right-3 bg-sky-600 hover:bg-sky-500 text-white rounded-full p-1.5 shadow-lg transition-all"
          >
            <ChevronDown size={14} />
          </button>
        )}
      </div>

      <div className="flex items-center justify-between px-3 py-2 border-t border-zinc-800">
        <span className="text-xs text-zinc-500">{filteredLogs.length} log satırı</span>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-zinc-500 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-3 h-3 accent-sky-500"
            />
            Otomatik Kaydır
          </label>
          <Button
            variant="ghost"
            size="xs"
            leftIcon={<Trash2 size={11} />}
            onClick={() => useAppStore.setState({ botLogs: [] })}
          >
            Temizle
          </Button>
        </div>
      </div>
    </Card>
  );
}
