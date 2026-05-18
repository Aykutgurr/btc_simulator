import { useMemo, useState, useCallback } from 'react';
import { X, Sparkles, FlaskConical } from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { useAppStore } from '../../store/useAppStore';
import type { Timeframe } from '../../types';
import { clsn } from '../../utils/format';

const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '4h'];

export function LlmBotBuilderModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { generateLlmBot, testLlmBot } = useAppStore();
  const [name, setName] = useState('');
  const [timeframe, setTimeframe] = useState<Timeframe>('15m');
  const [description, setDescription] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [generatedBotId, setGeneratedBotId] = useState<string | null>(null);
  const [constraintsText, setConstraintsText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [errorRaw, setErrorRaw] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const canSubmit = useMemo(() => name.trim().length >= 3 && description.trim().length >= 10, [name, description]);

  const parseConstraints = useCallback((): Record<string, string> | undefined => {
    const lines = constraintsText
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length === 0) return undefined;
    const out: Record<string, string> = {};
    for (const line of lines) {
      const idx = line.indexOf('=');
      if (idx > 0) {
        out[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
      } else if (line.includes(':')) {
        const [k, ...rest] = line.split(':');
        out[k.trim()] = rest.join(':').trim();
      }
    }
    return Object.keys(out).length > 0 ? out : undefined;
  }, [constraintsText]);

  if (!open) return null;

  async function handleGenerate() {
    setIsGenerating(true);
    setError(null);
    setErrorRaw(null);
    setShowRaw(false);
    setGeneratedBotId(null);
    try {
      const res = await generateLlmBot({
        name: name.trim(),
        timeframe,
        description: description.trim(),
        constraints: parseConstraints(),
      });
      if (!res.ok || !res.botId) {
        setError(res.error ?? 'Üretim başarısız.');
        setErrorRaw(res.raw ?? null);
        return;
      }
      setGeneratedBotId(res.botId);
    } catch (e) {
      setError(String(e));
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleTest() {
    if (!generatedBotId) return;
    setIsTesting(true);
    setError(null);
    try {
      const res = await testLlmBot({ botId: generatedBotId, maxSteps: 5000, timeoutSec: 30 });
      if (!res.ok) {
        setError(res.error ?? 'Test başarısız.');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setIsTesting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl">
          <Card
            title="LLM ile Yeni Bot Üret"
            titleRight={
              <Button variant="ghost" size="sm" onClick={onClose} leftIcon={<X size={13} />}>
                Kapat
              </Button>
            }
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-3">
                <Input
                  label="Bot adı"
                  placeholder="Örn: MyMeanReversion_v1"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  hint="Bot adı unique olmalı; en az 3 karakter."
                />

                <div>
                  <div className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">Timeframe</div>
                  <div className="flex flex-wrap gap-2">
                    {TIMEFRAMES.map((tf) => (
                      <button
                        key={tf}
                        className={clsn(
                          'px-3 py-1.5 rounded-md border text-xs font-semibold',
                          timeframe === tf
                            ? 'bg-sky-600/20 text-sky-300 border-sky-600/40'
                            : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:bg-zinc-800 hover:text-zinc-200'
                        )}
                        onClick={() => setTimeframe(tf)}
                      >
                        {tf}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge variant="purple">Model</Badge>
                  <span className="text-xs text-zinc-500">Ollama — model backend .env (LLM_MODEL)</span>
                </div>

                <div>
                  <div className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
                    Kısıtlar (opsiyonel)
                  </div>
                  <textarea
                    className={clsn(
                      'w-full h-20 bg-zinc-800 border border-zinc-700 rounded-md text-xs text-zinc-100 placeholder-zinc-600',
                      'focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-600 p-2 font-mono'
                    )}
                    placeholder={'max_leverage=10\nonly_long=true'}
                    value={constraintsText}
                    onChange={(e) => setConstraintsText(e.target.value)}
                  />
                  <div className="text-xs text-zinc-600 mt-1">Satır başına key=value veya key: value</div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-xs font-medium text-zinc-400 uppercase tracking-wide">Strateji tarifi</div>
                <textarea
                  className={clsn(
                    'w-full h-40 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-100 placeholder-zinc-600',
                    'focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-600 transition-colors',
                    'p-3'
                  )}
                  placeholder="Kurallar, indikatörler, risk, SL/TP, filtreler..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
                <div className="text-xs text-zinc-500">
                  İpucu: net giriş/çıkış şartları + risk sınırı yazarsan daha iyi sonuç alırsın.
                </div>
              </div>
            </div>

            {error && (
              <div className="mt-4 space-y-2">
                <div className="text-xs px-3 py-2 rounded-lg border bg-rose-900/30 border-rose-700/50 text-rose-300">
                  {error}
                </div>
                {errorRaw && (
                  <div>
                    <button
                      type="button"
                      className="text-xs text-zinc-500 hover:text-zinc-300 underline"
                      onClick={() => setShowRaw((v) => !v)}
                    >
                      {showRaw ? 'Ham çıktıyı gizle' : 'Ham LLM çıktısını göster'}
                    </button>
                    {showRaw && (
                      <pre className="mt-2 text-xs bg-zinc-950 border border-zinc-800 rounded-lg p-3 max-h-40 overflow-auto text-zinc-400 whitespace-pre-wrap">
                        {errorRaw}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="mt-4 flex items-center justify-between">
              <div className="text-xs text-zinc-500">
                {generatedBotId ? (
                  <span>
                    Üretildi: <span className="text-zinc-300 font-mono">{generatedBotId}</span>
                  </span>
                ) : (
                  'Önce botu üret, sonra test et.'
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleGenerate}
                  disabled={!canSubmit}
                  isLoading={isGenerating}
                  leftIcon={<Sparkles size={13} />}
                >
                  Üret
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTest}
                  disabled={!generatedBotId}
                  isLoading={isTesting}
                  leftIcon={<FlaskConical size={13} />}
                >
                  Test Et
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

