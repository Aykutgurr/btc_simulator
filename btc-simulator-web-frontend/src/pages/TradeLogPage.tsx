import { useEffect, useMemo, useState } from 'react';
import { Download, RefreshCw, Search } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { fmt, downloadCSV } from '../utils/format';
import type { TradeRecord } from '../types';

const HEADERS: { key: keyof TradeRecord | 'actions'; label: string; className?: string }[] = [
  { key: 'tarih', label: 'Tarih' },
  { key: 'yon', label: 'Yön' },
  { key: 'giris_fiyat', label: 'Giriş' },
  { key: 'cikis_fiyat', label: 'Çıkış' },
  { key: 'marjin', label: 'Marjin' },
  { key: 'pnl', label: 'PnL' },
  { key: 'roe_pct', label: 'ROE %' },
  { key: 'kapanis_sebebi', label: 'Kapanış' },
  { key: 'tetikleyici', label: 'Tetikleyici' },
  { key: 'komisyon', label: 'Komisyon' },
  { key: 'bakiye', label: 'Bakiye' },
];

function toCsvRows(trades: TradeRecord[]) {
  return trades.map((t) => ({
    tarih: t.tarih,
    yon: t.yon,
    giris_fiyat: t.giris_fiyat,
    cikis_fiyat: t.cikis_fiyat,
    marjin: t.marjin,
    pnl: t.pnl,
    roe_pct: t.roe_pct,
    kapanis_sebebi: t.kapanis_sebebi,
    tetikleyici: t.tetikleyici,
    komisyon: t.komisyon,
    bakiye: t.bakiye,
    entry_time: t.entry_time ?? '',
    exit_time: t.exit_time ?? '',
  }));
}

export function TradeLogPage() {
  const { tradeHistory, refreshTrade } = useAppStore();
  const [query, setQuery] = useState('');

  useEffect(() => {
    refreshTrade();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tradeHistory;
    return tradeHistory.filter((t) => {
      const hay = [
        t.tarih,
        t.yon,
        t.kapanis_sebebi,
        t.tetikleyici,
        String(t.giris_fiyat),
        String(t.cikis_fiyat),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(q);
    });
  }, [tradeHistory, query]);

  const exportCsv = () => {
    const rows = toCsvRows(filtered);
    downloadCSV(rows, `trade_log_${new Date().toISOString().slice(0, 10)}.csv`);
  };

  return (
    <div className="h-full overflow-hidden p-4">
      <Card
        title="İşlem Logu"
        titleRight={
          <div className="flex items-center gap-2">
            <div className="hidden md:flex items-center gap-2 bg-zinc-950 border border-zinc-800 rounded-md px-2 py-1.5">
              <Search size={14} className="text-zinc-600" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ara (bot, sebep, yön, tarih...)"
                className="bg-transparent text-xs outline-none placeholder:text-zinc-600 w-72"
              />
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refreshTrade()}
              leftIcon={<RefreshCw size={13} />}
            >
              Yenile
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={exportCsv}
              leftIcon={<Download size={13} />}
              disabled={filtered.length === 0}
            >
              CSV
            </Button>
          </div>
        }
        noPad
      >
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-800">
                {HEADERS.map((h) => (
                  <th
                    key={h.label}
                    className="text-left px-3 py-2 text-zinc-500 font-medium uppercase tracking-wide whitespace-nowrap"
                  >
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered
                .slice()
                .reverse()
                .map((t, i) => (
                  <tr
                    key={`${t.tarih}-${i}`}
                    className="border-b border-zinc-800/30 hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="px-3 py-2 text-zinc-400 whitespace-nowrap">
                      {t.exit_time ? fmt.datetime(t.exit_time) : t.tarih}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <Badge variant={t.yon === 'Long' ? 'green' : 'red'}>{t.yon}</Badge>
                    </td>
                    <td className="px-3 py-2 font-mono text-zinc-200 whitespace-nowrap">
                      {fmt.usdt(t.giris_fiyat)}
                    </td>
                    <td className="px-3 py-2 font-mono text-zinc-200 whitespace-nowrap">
                      {fmt.usdt(t.cikis_fiyat)}
                    </td>
                    <td className="px-3 py-2 font-mono text-zinc-300 whitespace-nowrap">
                      {fmt.usdt(t.marjin)}
                    </td>
                    <td
                      className={`px-3 py-2 font-mono font-semibold whitespace-nowrap ${
                        t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {fmt.pnl(t.pnl)}
                    </td>
                    <td
                      className={`px-3 py-2 font-mono whitespace-nowrap ${
                        t.roe_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {fmt.pct(t.roe_pct)}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <Badge variant={t.pnl >= 0 ? 'green' : 'red'}>{t.kapanis_sebebi}</Badge>
                    </td>
                    <td className="px-3 py-2 text-zinc-400 whitespace-nowrap">{t.tetikleyici}</td>
                    <td className="px-3 py-2 font-mono text-amber-400 whitespace-nowrap">
                      {fmt.usdt(t.komisyon)}
                    </td>
                    <td className="px-3 py-2 font-mono text-zinc-200 whitespace-nowrap">
                      {fmt.usdt(t.bakiye)}
                    </td>
                  </tr>
                ))}

              {filtered.length === 0 && (
                <tr>
                  <td colSpan={HEADERS.length} className="px-3 py-10 text-center text-zinc-600">
                    Kayıt bulunamadı.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

