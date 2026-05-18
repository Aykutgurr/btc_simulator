import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { useAppStore } from '../../store/useAppStore';
import type { SandboxReport } from '../../types';
import { fmt } from '../../utils/format';

export function BotTestReport() {
  const { lastBotTestReport } = useAppStore();
  if (!lastBotTestReport) return null;

  const report = lastBotTestReport.report;
  const ok = !!report?.ok;
  const stats = report?.stats;
  const steps = report?.steps;
  const sample = report?.tradeHistorySample ?? [];

  return (
    <Card
      title="LLM Bot Test Raporu"
      titleRight={<Badge variant={ok ? 'green' : 'red'}>{ok ? 'OK' : 'FAIL'}</Badge>}
    >
      <div className="text-xs text-zinc-500 mb-2">
        Bot: <span className="text-zinc-300 font-mono">{lastBotTestReport.botId}</span>
      </div>

      {!ok && report?.error && (
        <div className="mb-3 text-xs px-3 py-2 rounded-lg border bg-rose-900/30 border-rose-700/50 text-rose-300">
          {report.error}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="bg-zinc-800/40 border border-zinc-700/40 rounded-lg p-3">
          <div className="text-zinc-500 mb-1">Steps</div>
          <div className="text-zinc-100 font-mono font-semibold">{steps ?? '—'}</div>
        </div>
        <div className="bg-zinc-800/40 border border-zinc-700/40 rounded-lg p-3">
          <div className="text-zinc-500 mb-1">Trades</div>
          <div className="text-zinc-100 font-mono font-semibold">{stats?.total_trades ?? '—'}</div>
        </div>
        <div className="bg-zinc-800/40 border border-zinc-700/40 rounded-lg p-3">
          <div className="text-zinc-500 mb-1">Win Rate</div>
          <div className="text-zinc-100 font-mono font-semibold">
            {typeof stats?.win_rate_pct === 'number' ? `${stats.win_rate_pct.toFixed(1)}%` : '—'}
          </div>
        </div>
        <div className="bg-zinc-800/40 border border-zinc-700/40 rounded-lg p-3">
          <div className="text-zinc-500 mb-1">Total PnL</div>
          <div className="text-zinc-100 font-mono font-semibold">
            {typeof stats?.total_pnl === 'number' ? stats.total_pnl.toFixed(2) : '—'}
          </div>
        </div>
      </div>

      {sample.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <div className="text-xs font-semibold text-zinc-400 mb-2">Örnek işlemler</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-700">
                {['Tarih', 'Yön', 'Giriş', 'Çıkış', 'PnL', 'ROE%'].map((h) => (
                  <th key={h} className="text-left py-1.5 pr-3 text-zinc-500 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sample.slice(-10).map((t, i) => (
                <tr key={i} className="border-b border-zinc-700/30">
                  <td className="py-1.5 pr-3 text-zinc-400">{t.tarih}</td>
                  <td className="py-1.5 pr-3 text-zinc-300">{t.yon}</td>
                  <td className="py-1.5 pr-3 font-mono text-zinc-300">{fmt.usdt(t.giris_fiyat)}</td>
                  <td className="py-1.5 pr-3 font-mono text-zinc-300">{fmt.usdt(t.cikis_fiyat)}</td>
                  <td
                    className={`py-1.5 pr-3 font-mono font-semibold ${
                      t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {fmt.pnl(t.pnl)}
                  </td>
                  <td className="py-1.5 font-mono text-zinc-400">{fmt.pct(t.roe_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!!report?.logsTail?.length && (
        <div className="mt-3">
          <div className="text-xs font-semibold text-zinc-400 mb-2">Son Loglar</div>
          <pre className="text-xs bg-zinc-950 border border-zinc-800 rounded-lg p-3 max-h-48 overflow-auto text-zinc-300">
            {report.logsTail.slice(-50).join('\n')}
          </pre>
        </div>
      )}
    </Card>
  );
}
