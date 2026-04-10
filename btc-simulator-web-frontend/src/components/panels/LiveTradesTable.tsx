/**
 * LiveTradesTable — shows open position live PnL
 * and recent closed trades in a compact table.
 */

import { useAppStore } from '../../store/useAppStore';
import { fmt } from '../../utils/format';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { TrendingUp, TrendingDown } from 'lucide-react';

export function LiveTradesTable() {
  const { position, tradeHistory, currentCandle } = useAppStore();
  const currentPrice = currentCandle?.close ?? 0;

  // Recent 10 closed trades
  const recentTrades = [...tradeHistory].reverse().slice(0, 10);

  const livePnl = position
    ? (() => {
        const diff =
          position.direction === 'long'
            ? currentPrice - position.entry_price
            : position.entry_price - currentPrice;
        return (diff / position.entry_price) * position.margin_usdt * position.leverage;
      })()
    : null;

  return (
    <Card title="Canlı İşlemler" noPad>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800">
              {['Kaynak', 'Yön', 'Giriş', 'SL', 'TP', 'PnL %', 'Durum'].map((h) => (
                <th
                  key={h}
                  className="text-left px-3 py-2 text-zinc-500 font-medium uppercase tracking-wide"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {position && (
              <tr className="border-b border-zinc-800/50 bg-sky-950/10">
                <td className="px-3 py-2 text-zinc-300">{position.opened_by}</td>
                <td className="px-3 py-2">
                  <Badge variant={position.direction === 'long' ? 'green' : 'red'}>
                    {position.direction === 'long' ? (
                      <TrendingUp size={10} className="mr-1" />
                    ) : (
                      <TrendingDown size={10} className="mr-1" />
                    )}
                    {position.direction.toUpperCase()}
                  </Badge>
                </td>
                <td className="px-3 py-2 font-mono text-zinc-200">
                  {fmt.usdt(position.entry_price)}
                </td>
                <td className="px-3 py-2 font-mono text-rose-400">
                  {position.stop_loss ? fmt.usdt(position.stop_loss) : '—'}
                </td>
                <td className="px-3 py-2 font-mono text-emerald-400">
                  {position.take_profit ? fmt.usdt(position.take_profit) : '—'}
                </td>
                <td
                  className={`px-3 py-2 font-mono font-semibold ${
                    (livePnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {livePnl != null
                    ? fmt.pct((livePnl / position.margin_usdt) * 100)
                    : '—'}
                </td>
                <td className="px-3 py-2">
                  <Badge variant="blue">Açık</Badge>
                </td>
              </tr>
            )}

            {recentTrades.map((t, i) => (
              <tr
                key={i}
                className="border-b border-zinc-800/30 hover:bg-zinc-800/30 transition-colors"
              >
                <td className="px-3 py-2 text-zinc-400">{t.tetikleyici}</td>
                <td className="px-3 py-2">
                  <Badge variant={t.yon === 'Long' ? 'green' : 'red'}>
                    {t.yon === 'Long' ? (
                      <TrendingUp size={10} className="mr-1" />
                    ) : (
                      <TrendingDown size={10} className="mr-1" />
                    )}
                    {t.yon}
                  </Badge>
                </td>
                <td className="px-3 py-2 font-mono text-zinc-300">
                  {fmt.usdt(t.giris_fiyat)}
                </td>
                <td className="px-3 py-2 font-mono text-zinc-500">—</td>
                <td className="px-3 py-2 font-mono text-zinc-500">—</td>
                <td
                  className={`px-3 py-2 font-mono font-semibold ${
                    t.roe_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {fmt.pct(t.roe_pct)}
                </td>
                <td className="px-3 py-2">
                  <Badge variant={t.pnl >= 0 ? 'green' : 'red'}>
                    {t.kapanis_sebebi}
                  </Badge>
                </td>
              </tr>
            ))}

            {!position && recentTrades.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-zinc-600 text-xs">
                  Henüz açık veya kapalı işlem yok
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
