import { useCallback, useState } from 'react';
import { FlaskConical, Sparkles, Clock } from 'lucide-react';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { useAppStore } from '../../store/useAppStore';
import type { LlmBotMeta, SandboxReport } from '../../types';
import { clsn } from '../../utils/format';

function lastTestSummary(lastTest?: SandboxReport | null): { label: string; variant: 'green' | 'red' | 'gray' } {
  if (!lastTest) return { label: 'Test yok', variant: 'gray' };
  if (!lastTest.ok) return { label: 'FAIL', variant: 'red' };
  const trades = lastTest.stats?.total_trades ?? 0;
  return { label: `OK · ${trades} işlem`, variant: 'green' };
}

export function LlmBotsPanel() {
  const { llmBots, bots, toggleBot, testLlmBot, refreshLlmBots } = useAppStore();
  const [testingId, setTestingId] = useState<string | null>(null);

  const isBotEnabled = useCallback(
    (meta: LlmBotMeta) => bots.find((b) => b.name === meta.name)?.enabled ?? meta.enabled ?? false,
    [bots]
  );

  const handleToggle = useCallback(
    (meta: LlmBotMeta) => {
      const enabled = isBotEnabled(meta);
      toggleBot(meta.name, !enabled);
    },
    [isBotEnabled, toggleBot]
  );

  const handleTest = useCallback(
    async (botId: string) => {
      setTestingId(botId);
      try {
        await testLlmBot({ botId, maxSteps: 5000, timeoutSec: 30 });
        await refreshLlmBots();
      } finally {
        setTestingId(null);
      }
    },
    [testLlmBot, refreshLlmBots]
  );

  return (
    <Card
      title="Üretilmiş LLM Botları"
      titleRight={
        <Badge variant="purple">
          <Sparkles size={10} className="mr-1 inline" />
          {llmBots.length}
        </Badge>
      }
    >
      {llmBots.length === 0 ? (
        <div className="text-center py-6 text-zinc-600 text-sm">
          Henüz üretilmiş bot yok. &quot;Yeni Bot Üret&quot; ile oluşturabilirsiniz.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {llmBots.map((meta) => {
            const enabled = isBotEnabled(meta);
            const testBadge = lastTestSummary(meta.lastTest);
            return (
              <div
                key={meta.id}
                className={clsn(
                  'flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl border',
                  enabled
                    ? 'bg-violet-950/20 border-violet-800/40'
                    : 'bg-zinc-800/40 border-zinc-700/40'
                )}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-zinc-200 truncate">{meta.name}</span>
                    <Badge variant="blue">{meta.timeframe}</Badge>
                    <Badge variant={testBadge.variant}>{testBadge.label}</Badge>
                    {meta.lastTest?.steps != null && (
                      <span className="text-xs text-zinc-500 font-mono">{meta.lastTest.steps} adım</span>
                    )}
                  </div>
                  <div className="text-xs text-zinc-500 font-mono mt-1 truncate">{meta.id}</div>
                  {meta.createdAt && (
                    <div className="flex items-center gap-1 text-xs text-zinc-600 mt-0.5">
                      <Clock size={10} />
                      {meta.createdAt.slice(0, 19).replace('T', ' ')}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => handleToggle(meta)}
                    className={clsn(
                      'px-2.5 py-1 text-xs rounded-md border font-semibold transition-colors',
                      enabled
                        ? 'bg-emerald-600/20 text-emerald-400 border-emerald-700/50'
                        : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                    )}
                  >
                    {enabled ? 'Aktif' : 'Pasif'}
                  </button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleTest(meta.id)}
                    isLoading={testingId === meta.id}
                    leftIcon={<FlaskConical size={12} />}
                  >
                    Test Et
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
