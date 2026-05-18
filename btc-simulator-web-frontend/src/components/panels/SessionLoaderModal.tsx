import { useMemo, useState } from 'react';
import { X, Database } from 'lucide-react';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { useAppStore } from '../../store/useAppStore';
import { clsn } from '../../utils/format';

export type SessionSource = 'csv' | 'yfinance' | 'ccxt' | 'mock';

const SOURCE_OPTIONS: { value: SessionSource; label: string; hint?: string }[] = [
  { value: 'csv', label: 'CSV' },
  { value: 'yfinance', label: 'YFinance' },
  { value: 'ccxt', label: 'Binance (CCXT)', hint: 'BTC/USDT 1m' },
  { value: 'mock', label: 'Mock (demo)', hint: '~800 bar' },
];

const SOURCE_TITLES: Record<SessionSource, string> = {
  csv: 'CSV',
  yfinance: 'yfinance (BTC-USD)',
  ccxt: 'Binance CCXT',
  mock: 'Mock veri',
};

function isoDate(d: Date) {
  return d.toISOString().slice(0, 10);
}

export function SessionLoaderModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { loadSession, datasetInfo } = useAppStore();
  const [source, setSource] = useState<SessionSource>('csv');
  const [startDate, setStartDate] = useState<string>(() => isoDate(new Date(Date.now() - 7 * 24 * 3600 * 1000)));
  const [endDate, setEndDate] = useState<string>(() => isoDate(new Date()));
  const [csvPath, setCsvPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const showDateRange = source !== 'mock';
  const canCsvPath = source === 'csv';
  const title = SOURCE_TITLES[source];
  const loadingHint = useMemo(() => {
    if (source === 'ccxt') return 'Binance 1m verisi cekiliyor...';
    if (source === 'yfinance') return 'YFinance verisi cekiliyor...';
    if (source === 'mock') return 'Mock veri uretiliyor...';
    return 'Yukleniyor...';
  }, [source]);

  if (!open) return null;

  async function submit() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await loadSession({
        source,
        startDate: showDateRange && startDate ? new Date(startDate).toISOString() : undefined,
        endDate: showDateRange && endDate ? new Date(endDate).toISOString() : undefined,
        csvPath: csvPath || undefined,
      });
      if (!res.ok) {
        const msgs: Record<SessionSource, string> = {
          csv: 'CSV yolu veya tarih araligini kontrol edin.',
          yfinance: 'Tarih araligi / internet erisimini kontrol edin.',
          ccxt: 'Tarih araligi / Binance erisimini kontrol edin.',
          mock: 'Mock yukleme basarisiz.',
        };
        setError(`Yükleme başarısız. ${msgs[source]}`);
        return;
      }
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-xl">
          <Card
            title="Veri / Session Yukle"
            titleRight={
              <Button variant="ghost" size="sm" onClick={onClose} leftIcon={<X size={13} />}>
                Kapat
              </Button>
            }
          >
            <div className="flex items-start justify-between gap-3 mb-4">
              <div>
                <div className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  <Database size={16} className="text-sky-400" />
                  Kaynak sec
                </div>
                <div className="text-xs text-zinc-500 mt-0.5">Su an: {datasetInfo}</div>
              </div>
              <Badge variant="blue">{title}</Badge>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-4">
              {SOURCE_OPTIONS.map(({ value, label, hint }) => (
                <button
                  key={value}
                  onClick={() => setSource(value)}
                  className={clsn(
                    'px-3 py-2 rounded-lg border text-xs font-semibold transition-colors text-left',
                    source === value
                      ? 'bg-sky-600/20 text-sky-300 border-sky-600/40'
                      : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:bg-zinc-800 hover:text-zinc-200'
                  )}
                >
                  <div>{label}</div>
                  {hint && <div className="text-[10px] font-normal opacity-70 mt-0.5">{hint}</div>}
                </button>
              ))}
            </div>

            {showDateRange && (
              <div className="grid grid-cols-2 gap-3 mb-4">
                <Input label="Baslangic (YYYY-MM-DD)" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                <Input label="Bitis (YYYY-MM-DD)" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
            )}

            {source === 'mock' && (
              <p className="text-xs text-zinc-500 mb-4">
                Demo icin sentetik ~800 adet 1 dakikalik mum uretilir; tarih filtresi uygulanmaz.
              </p>
            )}

            {canCsvPath && (
              <div className="mb-4">
                <Input
                  label="CSV Path (opsiyonel)"
                  placeholder="Boş bırak: data/btc_ohlcv.csv aranır"
                  value={csvPath}
                  onChange={(e) => setCsvPath(e.target.value)}
                  hint="CSV kolonları: timestamp/date/datetime/time + open/high/low/close (+volume opsiyonel)"
                />
              </div>
            )}

            {error && (
              <div className="mb-3 text-xs px-3 py-2 rounded-lg border bg-rose-900/30 border-rose-700/50 text-rose-300">
                {error}
              </div>
            )}

            <div className="flex items-center justify-between gap-2">
              {isLoading && <span className="text-xs text-zinc-500">{loadingHint}</span>}
              <div className="flex items-center gap-2 ml-auto">
                <Button variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
                  Iptal
                </Button>
                <Button variant="primary" size="sm" onClick={submit} isLoading={isLoading}>
                  Yukle
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
