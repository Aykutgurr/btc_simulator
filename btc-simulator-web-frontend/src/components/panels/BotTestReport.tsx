import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { useAppStore } from '../../store/useAppStore';

export function BotTestReport() {
  const { lastBotTestReport } = useAppStore();
  if (!lastBotTestReport) return null;

  const report = lastBotTestReport.report as any;
  const ok = !!report?.ok;
  const stats = report?.stats;
  const steps = report?.steps;

  return (
    <Card
      title="LLM Bot Test Raporu"
      titleRight={<Badge variant={ok ? 'green' : 'red'}>{ok ? 'OK' : 'FAIL'}</Badge>}
    >
      <div className="text-xs text-zinc-500 mb-2">
        Bot: <span className="text-zinc-300 font-mono">{lastBotTestReport.botId}</span>
      </div>

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

