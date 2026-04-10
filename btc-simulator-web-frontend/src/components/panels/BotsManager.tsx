/**
 * BotsManager — bot list with enable/disable checkboxes.
 */

import { useCallback, useState } from 'react';
import { Bot, Cpu, Clock } from 'lucide-react';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { useAppStore } from '../../store/useAppStore';
import { clsn } from '../../utils/format';
import { LlmBotBuilderModal } from './LlmBotBuilderModal';

export function BotsManager() {
  const { bots, toggleBot } = useAppStore();
  const [open, setOpen] = useState(false);

  const handleToggle = useCallback(
    (name: string, enabled: boolean) => {
      toggleBot(name, !enabled);
    },
    [toggleBot]
  );

  const enabledCount = bots.filter((b) => b.enabled).length;

  return (
    <Card
      title="Bot Yöneticisi"
      titleRight={
        <div className="flex items-center gap-2">
          <Badge variant={enabledCount > 0 ? 'green' : 'gray'}>
            {enabledCount}/{bots.length} Aktif
          </Badge>
          <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
            Yeni Bot Üret
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-2">
        {bots.length === 0 && (
          <div className="text-center py-6 text-zinc-600 text-sm">Bot bulunamadı</div>
        )}
        {bots.map((bot) => (
          <div
            key={bot.name}
            className={clsn(
              'flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer',
              bot.enabled
                ? 'bg-emerald-950/20 border-emerald-800/40 hover:bg-emerald-950/30'
                : 'bg-zinc-800/40 border-zinc-700/40 hover:bg-zinc-800/60'
            )}
            onClick={() => handleToggle(bot.name, bot.enabled)}
          >
            <div className="flex items-center gap-3">
              {/* Toggle */}
              <div
                className={clsn(
                  'w-10 h-5 rounded-full relative transition-colors flex-shrink-0',
                  bot.enabled ? 'bg-emerald-500' : 'bg-zinc-600'
                )}
              >
                <div
                  className={clsn(
                    'absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all',
                    bot.enabled ? 'left-5' : 'left-0.5'
                  )}
                />
              </div>

              <div className="flex items-center gap-2">
                <div className={clsn('p-1.5 rounded-lg', bot.enabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-700 text-zinc-500')}>
                  <Cpu size={14} />
                </div>
                <div>
                  <div className="text-sm font-semibold text-zinc-200">{bot.name}</div>
                  <div className="flex items-center gap-1 text-xs text-zinc-500">
                    <Clock size={10} />
                    <span>{bot.timeframe}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant={bot.enabled ? 'green' : 'gray'}>
                {bot.enabled ? 'Aktif' : 'Pasif'}
              </Badge>
              <Bot size={14} className={bot.enabled ? 'text-emerald-400' : 'text-zinc-600'} />
            </div>
          </div>
        ))}
      </div>

      <LlmBotBuilderModal open={open} onClose={() => setOpen(false)} />
    </Card>
  );
}
