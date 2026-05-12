import { useMemo, useState } from 'react';
import { X, Database } from 'lucide-react';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { useAppStore } from '../../store/useAppStore';
import { clsn } from '../../utils/format';

type Source = 'csv' | 'yfinance';

const SOURCE_OPTIONS: { value: Source; label: string }[] = [
  { value: 'csv', label: 'CSV' },
  { value: 'yfinance', label: 'YFinance' },
];

function isoDate(d: Date) {
  return d.toISOString().slice(0, 10);
}

export function SessionLoaderModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { loadSession, datasetInfo } = useAppStore();
  const [source, setSource] = useState<Source>('csv');
  const [startDate, setStartDate] = useState<string>(() => isoDate(new Date(Date.now() - 7 * 24 * 3600 * 1000)));
  const [endDate, setEndDate] = useState<string>(() => isoDate(new Date()));
  const [csvPath, setCsvPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canCsvPath = source === 'csv';
  const title = useMemo(() => {
    if (source === 'csv') return 'CSV';
    return 'yfinance (BTC-USD)';
  }, [source]);

  if (!open) return null;

  async function submit() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await loadSession({
        source,
        startDate: startDate ? new Date(startDate).toISOString() : undefined,
        endDate: endDate ? new Date(endDate).toISOString() : undefined,
        csvPath: csvPath || undefined,
      });
      if (!res.ok) {
        setError('Yükleme başarısız. CSV yolu / tarih aralığı / internet erişimini kontrol edin.');
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
            title="Veri / Session Yükle"
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
                  Kaynak seç
                </div>
                <div className="text-xs text-zinc-500 mt-0.5">Şu an: {datasetInfo}</div>
              </div>
              <Badge variant="blue">{title}</Badge>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-4">
              {SOURCE_OPTIONS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setSource(value)}
                  className={clsn(
                    'px-3 py-2 rounded-lg border text-xs font-semibold transition-colors',
                    source === value
                      ? 'bg-sky-600/20 text-sky-300 border-sky-600/40'
                      : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:bg-zinc-800 hover:text-zinc-200'
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <Input label="Başlangıç (YYYY-MM-DD)" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              <Input label="Bitiş (YYYY-MM-DD)" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>

            {canCsvPath && (
              <div className="mb-4">
                <Input
                  label="CSV Path (opsiyonel)"
                  placeholder="Boş bırak: repo kökünde btc_ohlcv.csv aranır"
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

            <div className="flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" onClick={onClose}>
                İptal
              </Button>
              <Button variant="primary" size="sm" onClick={submit} isLoading={isLoading}>
                Yükle
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

