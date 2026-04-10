/**
 * StatsCards — win rate, total PnL, max DD, trades, commission,
 * total return, sharpe ratio.
 */

import { TrendingUp, TrendingDown, Target, BarChart2, Zap, DollarSign, Activity } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import { fmt } from '../../utils/format';

interface StatCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: string;
  sub?: string;
}

function StatCard({ label, value, icon, color, sub }: StatCardProps) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col gap-2 hover:border-zinc-700 transition-colors">
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-500 font-medium uppercase tracking-wide">{label}</span>
        <div className={`p-1.5 rounded-lg ${color}`}>{icon}</div>
      </div>
      <div className="text-xl font-bold font-mono text-zinc-100">{value}</div>
      {sub && <div className="text-xs text-zinc-500">{sub}</div>}
    </div>
  );
}

export function StatsCards() {
  const { stats } = useAppStore();

  const cards: StatCardProps[] = [
    {
      label: 'Kazanma Oranı',
      value: `${stats.win_rate_pct.toFixed(1)}%`,
      icon: <Target size={14} />,
      color: 'bg-emerald-500/20 text-emerald-400',
      sub: `${stats.total_trades} işlemden`,
    },
    {
      label: 'Toplam PnL',
      value: fmt.pnl(stats.total_pnl),
      icon: <DollarSign size={14} />,
      color:
        stats.total_pnl >= 0
          ? 'bg-emerald-500/20 text-emerald-400'
          : 'bg-rose-500/20 text-rose-400',
    },
    {
      label: 'Maks. Drawdown',
      value: `${stats.max_drawdown.toFixed(2)}%`,
      icon: <TrendingDown size={14} />,
      color: 'bg-rose-500/20 text-rose-400',
    },
    {
      label: 'Toplam İşlem',
      value: stats.total_trades.toString(),
      icon: <BarChart2 size={14} />,
      color: 'bg-sky-500/20 text-sky-400',
    },
    {
      label: 'Toplam Komisyon',
      value: fmt.usdt(stats.total_commission),
      icon: <Zap size={14} />,
      color: 'bg-amber-500/20 text-amber-400',
    },
    {
      label: 'Toplam Getiri',
      value: fmt.pct(stats.total_return_pct),
      icon: <TrendingUp size={14} />,
      color:
        stats.total_return_pct >= 0
          ? 'bg-emerald-500/20 text-emerald-400'
          : 'bg-rose-500/20 text-rose-400',
    },
    {
      label: 'Sharpe Oranı',
      value: stats.sharpe_ratio.toFixed(2),
      icon: <Activity size={14} />,
      color:
        stats.sharpe_ratio >= 1
          ? 'bg-emerald-500/20 text-emerald-400'
          : stats.sharpe_ratio >= 0
          ? 'bg-amber-500/20 text-amber-400'
          : 'bg-rose-500/20 text-rose-400',
      sub: stats.sharpe_ratio >= 1 ? 'İyi' : stats.sharpe_ratio >= 0 ? 'Orta' : 'Zayıf',
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3">
      {cards.map((c) => (
        <StatCard key={c.label} {...c} />
      ))}
    </div>
  );
}
