/**
 * Tab 2: Bots & Stats
 */

import { useEffect } from 'react';
import { RefreshCw } from 'lucide-react';
import { StatsCards } from '../components/panels/StatsCards';
import { BotsManager } from '../components/panels/BotsManager';
import { BotLogViewer } from '../components/panels/BotLogViewer';
import { EquityChart } from '../components/chart/EquityChart';
import { BotTestReport } from '../components/panels/BotTestReport';
import { Button } from '../components/ui/Button';
import { useAppStore } from '../store/useAppStore';

export function BotsStatsPage() {
  const { refreshBots, refreshLogs, refreshTrade, equityCurve } = useAppStore();

  useEffect(() => {
    refreshBots();
    refreshLogs();
    refreshTrade();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full">
      {/* Stats header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-zinc-100">Botlar & İstatistikler</h2>
          <p className="text-xs text-zinc-500 mt-0.5">Tüm botların performans özeti</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => { refreshBots(); refreshLogs(); refreshTrade(); }}
          leftIcon={<RefreshCw size={13} />}
        >
          Yenile
        </Button>
      </div>

      {/* Stats cards */}
      <StatsCards />

      {/* Equity curve */}
      {equityCurve.x.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden" style={{ height: 200 }}>
          <EquityChart equity={equityCurve} />
        </div>
      )}

      {/* Two-column: bots manager + log viewer */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BotsManager />
        <BotLogViewer />
      </div>

      <BotTestReport />

      {/* Bot stats tree (per-bot breakdown) */}
      <BotStatsTree />
    </div>
  );
}

// ─── Bot Stats Tree ───────────────────────────────────────────────────────────

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '../components/ui/Badge';
import { fmt } from '../utils/format';
import type { Bot } from '../types';

function BotStatsTree() {
  const { bots, tradeHistory } = useAppStore();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggle = (name: string) =>
    setExpanded((p) => ({ ...p, [name]: !p[name] }));

  // Build per-bot stats from tradeHistory (using tetikleyici as source)
  function botStats(bot: Bot) {
    const trades = tradeHistory.filter((t) => t.tetikleyici.includes(bot.name.split('-')[0]));
    if (trades.length === 0) return null;
    const wins = trades.filter((t) => t.pnl > 0).length;
    const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
    const commission = trades.reduce((s, t) => s + t.komisyon, 0);
    return {
      total: trades.length,
      wins,
      losses: trades.length - wins,
      winRate: ((wins / trades.length) * 100).toFixed(1),
      totalPnl,
      commission,
      trades,
    };
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800">
        <span className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Bot Bazlı İstatistikler</span>
      </div>
      <div className="divide-y divide-zinc-800">
        {bots.map((bot) => {
          const stats = botStats(bot);
          const isOpen = expanded[bot.name];
          return (
            <div key={bot.name}>
              <button
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-zinc-800/40 transition-colors text-left"
                onClick={() => toggle(bot.name)}
              >
                <div className="flex items-center gap-3">
                  {isOpen ? <ChevronDown size={14} className="text-zinc-500" /> : <ChevronRight size={14} className="text-zinc-500" />}
                  <span className="text-sm font-medium text-zinc-200">{bot.name}</span>
                  <Badge variant="blue">{bot.timeframe}</Badge>
                  <Badge variant={bot.enabled ? 'green' : 'gray'}>{bot.enabled ? 'Aktif' : 'Pasif'}</Badge>
                </div>
                {stats ? (
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-zinc-500">{stats.total} işlem</span>
                    <span className={stats.totalPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                      {fmt.pnl(stats.totalPnl)}
                    </span>
                    <span className="text-zinc-500">%{stats.winRate} kazan</span>
                  </div>
                ) : (
                  <span className="text-xs text-zinc-600">Veri yok</span>
                )}
              </button>

              {isOpen && stats && (
                <div className="bg-zinc-800/30 px-8 py-3">
                  <div className="grid grid-cols-3 gap-4 mb-3">
                    <div className="text-xs">
                      <div className="text-zinc-500 mb-1">Toplam İşlem</div>
                      <div className="text-zinc-200 font-mono font-semibold">{stats.total}</div>
                    </div>
                    <div className="text-xs">
                      <div className="text-zinc-500 mb-1">Kazanılan / Kaybedilen</div>
                      <div className="font-mono">
                        <span className="text-emerald-400">{stats.wins}</span>
                        <span className="text-zinc-500"> / </span>
                        <span className="text-rose-400">{stats.losses}</span>
                      </div>
                    </div>
                    <div className="text-xs">
                      <div className="text-zinc-500 mb-1">Komisyon</div>
                      <div className="text-amber-400 font-mono font-semibold">{fmt.usdt(stats.commission)}</div>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-zinc-700">
                          {['Tarih', 'Yön', 'Giriş', 'Çıkış', 'PnL', 'ROE%', 'Sebep'].map((h) => (
                            <th key={h} className="text-left py-1.5 pr-3 text-zinc-500 font-medium">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {stats.trades.slice(-5).map((t, i) => (
                          <tr key={i} className="border-b border-zinc-700/30">
                            <td className="py-1.5 pr-3 text-zinc-400">{t.tarih}</td>
                            <td className="py-1.5 pr-3">
                              <Badge variant={t.yon === 'Long' ? 'green' : 'red'}>{t.yon}</Badge>
                            </td>
                            <td className="py-1.5 pr-3 font-mono text-zinc-300">{fmt.usdt(t.giris_fiyat)}</td>
                            <td className="py-1.5 pr-3 font-mono text-zinc-300">{fmt.usdt(t.cikis_fiyat)}</td>
                            <td className={`py-1.5 pr-3 font-mono font-semibold ${t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {fmt.pnl(t.pnl)}
                            </td>
                            <td className={`py-1.5 pr-3 font-mono ${t.roe_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {fmt.pct(t.roe_pct)}
                            </td>
                            <td className="py-1.5 text-zinc-500">{t.kapanis_sebebi}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {bots.length === 0 && (
          <div className="px-4 py-6 text-center text-zinc-600 text-sm">Bot bulunamadı</div>
        )}
      </div>
    </div>
  );
}
