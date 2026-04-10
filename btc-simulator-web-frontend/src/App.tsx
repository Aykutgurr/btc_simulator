import { useEffect, useState, type ReactNode } from 'react';
import { Activity, Bot, ScrollText, Database } from 'lucide-react';
import { useAppStore } from './store/useAppStore';
import { Badge } from './components/ui/Badge';
import { Button } from './components/ui/Button';
import { clsn } from './utils/format';
import { ChartTradingPage } from './pages/ChartTradingPage';
import { BotsStatsPage } from './pages/BotsStatsPage';
import { TradeLogPage } from './pages/TradeLogPage';
import { SessionLoaderModal } from './components/panels/SessionLoaderModal';

function ConnectionBadge() {
  const { connectionStatus, isMockMode } = useAppStore();

  const variant =
    connectionStatus === 'connected'
      ? 'green'
      : connectionStatus === 'connecting'
      ? 'yellow'
      : connectionStatus === 'error'
      ? 'red'
      : 'gray';

  const label =
    connectionStatus === 'connected'
      ? 'Connected'
      : connectionStatus === 'connecting'
      ? 'Connecting'
      : connectionStatus === 'error'
      ? 'Error'
      : 'Disconnected';

  return (
    <div className="flex items-center gap-2">
      <Badge variant={variant}>{label}</Badge>
      {isMockMode && <Badge variant="purple">Mock</Badge>}
    </div>
  );
}

function Tabs() {
  const { activeTab, setActiveTab } = useAppStore();

  const tabBtn = (id: 'chart' | 'bots' | 'log', label: string, icon: ReactNode) => (
    <button
      key={id}
      onClick={() => setActiveTab(id)}
      className={clsn(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-semibold transition-colors border',
        activeTab === id
          ? 'bg-sky-600/20 text-sky-300 border-sky-600/40'
          : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:bg-zinc-800 hover:text-zinc-200'
      )}
    >
      {icon}
      {label}
    </button>
  );

  return (
    <div className="flex items-center gap-2">
      {tabBtn('chart', 'Grafik & İşlem', <Activity size={16} />)}
      {tabBtn('bots', 'Botlar & İstatistikler', <Bot size={16} />)}
      {tabBtn('log', 'İşlem Logu', <ScrollText size={16} />)}
    </div>
  );
}

export default function App() {
  const { initialize, activeTab, datasetInfo } = useAppStore();
  const [sessionOpen, setSessionOpen] = useState(false);

  useEffect(() => {
    initialize();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-10 bg-zinc-950/80 backdrop-blur border-b border-zinc-800">
        <div className="px-4 py-3 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-indigo-900/30" />
              <div className="min-w-0">
                <div className="text-sm font-bold tracking-tight">BTC Simulator</div>
                <div className="text-xs text-zinc-500 truncate">{datasetInfo}</div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Tabs />
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSessionOpen(true)}
              leftIcon={<Database size={14} />}
            >
              Veri
            </Button>
            <ConnectionBadge />
          </div>
        </div>
      </header>

      <main className="h-[calc(100vh-64px)]">
        {activeTab === 'chart' && <ChartTradingPage />}
        {activeTab === 'bots' && <BotsStatsPage />}
        {activeTab === 'log' && <TradeLogPage />}
      </main>

      <SessionLoaderModal open={sessionOpen} onClose={() => setSessionOpen(false)} />
    </div>
  );
}
