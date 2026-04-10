/**
 * FuturesPanel — leverage, margin, SL/TP inputs + Long/Short/Close buttons.
 * Shows open position summary if active.
 */

import { useState, useCallback } from 'react';
import { TrendingUp, TrendingDown, X, AlertTriangle, DollarSign } from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { useAppStore } from '../../store/useAppStore';
import { fmt } from '../../utils/format';

export function FuturesPanel() {
  const { position, balanceUsdt, availableBalance, currentCandle, openTrade, closeTrade, updateTrade, closeTradePartial } =
    useAppStore();

  const [leverage, setLeverage] = useState(10);
  const [marginUsdt, setMarginUsdt] = useState('100');
  const [stopLoss, setStopLoss] = useState('');
  const [takeProfit, setTakeProfit] = useState('');
  const [isOpening, setIsOpening] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  const currentPrice = currentCandle?.close ?? 0;

  const handleOpen = useCallback(
    async (direction: 'long' | 'short') => {
      setIsOpening(true);
      setFeedback(null);
      try {
        const res = await openTrade({
          direction,
          marginUsdt: Number(marginUsdt),
          leverage,
          stopLoss: stopLoss ? Number(stopLoss) : undefined,
          takeProfit: takeProfit ? Number(takeProfit) : undefined,
        });
        setFeedback({ type: res.success ? 'success' : 'error', msg: res.message });
        if (res.success) {
          setStopLoss('');
          setTakeProfit('');
        }
      } catch (err) {
        setFeedback({ type: 'error', msg: String(err) });
      } finally {
        setIsOpening(false);
      }
    },
    [openTrade, marginUsdt, leverage, stopLoss, takeProfit]
  );

  const handleClose = useCallback(async () => {
    setIsClosing(true);
    setFeedback(null);
    try {
      const res = await closeTrade();
      setFeedback({
        type: res.closed ? 'success' : 'error',
        msg: res.closed ? 'Pozisyon kapatıldı.' : 'Kapatma başarısız.',
      });
    } catch (err) {
      setFeedback({ type: 'error', msg: String(err) });
    } finally {
      setIsClosing(false);
    }
  }, [closeTrade]);

  const handleUpdate = useCallback(async () => {
    if (!position) return;
    setIsUpdating(true);
    setFeedback(null);
    try {
      const res = await updateTrade({
        stopLoss: stopLoss ? Number(stopLoss) : undefined,
        takeProfit: takeProfit ? Number(takeProfit) : undefined,
      });
      setFeedback({ type: res.success ? 'success' : 'error', msg: res.success ? 'SL/TP güncellendi.' : 'Güncelleme başarısız.' });
    } catch (err) {
      setFeedback({ type: 'error', msg: String(err) });
    } finally {
      setIsUpdating(false);
    }
  }, [updateTrade, stopLoss, takeProfit, position]);

  const handleClosePartial = useCallback(async (fraction: number) => {
    setIsClosing(true);
    setFeedback(null);
    try {
      const res = await closeTradePartial(fraction);
      setFeedback({
        type: res.partial ? 'success' : 'error',
        msg: res.partial ? `Kısmi kapatma (${Math.round(fraction * 100)}%) yapıldı.` : 'Kısmi kapatma başarısız.',
      });
    } catch (err) {
      setFeedback({ type: 'error', msg: String(err) });
    } finally {
      setIsClosing(false);
    }
  }, [closeTradePartial]);

  // Live PnL calculation
  const livePnl = position
    ? (() => {
        const diff =
          position.direction === 'long'
            ? currentPrice - position.entry_price
            : position.entry_price - currentPrice;
        return (diff / position.entry_price) * position.margin_usdt * position.leverage;
      })()
    : null;

  const liveRoe = position && livePnl != null
    ? (livePnl / position.margin_usdt) * 100
    : null;

  const LEVERAGES = [1, 2, 5, 10, 20, 25, 50, 75, 100];

  return (
    <div className="flex flex-col gap-3 h-full overflow-y-auto p-1">
      {/* Balance info */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-zinc-800/60 rounded-lg p-3 border border-zinc-700/50">
          <div className="text-xs text-zinc-500 mb-1">Toplam Bakiye</div>
          <div className="text-sm font-bold text-zinc-100 font-mono">{fmt.usdt(balanceUsdt)}</div>
        </div>
        <div className="bg-zinc-800/60 rounded-lg p-3 border border-zinc-700/50">
          <div className="text-xs text-zinc-500 mb-1">Kullanılabilir</div>
          <div className="text-sm font-bold text-emerald-400 font-mono">{fmt.usdt(availableBalance)}</div>
        </div>
      </div>

      {/* Open Position card */}
      {position && (
        <Card className="border-sky-800/50 bg-sky-950/20">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Badge variant={position.direction === 'long' ? 'green' : 'red'}>
                {position.direction === 'long' ? (
                  <TrendingUp size={10} className="mr-1" />
                ) : (
                  <TrendingDown size={10} className="mr-1" />
                )}
                {position.direction.toUpperCase()}
              </Badge>
              <Badge variant="blue">{position.leverage}x</Badge>
              <span className="text-xs text-zinc-500">{position.opened_by}</span>
            </div>
            <div
              className={`text-sm font-bold font-mono ${
                (livePnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {fmt.pnl(livePnl)}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <span className="text-zinc-500">Giriş:</span>
              <span className="ml-2 text-zinc-200 font-mono">{fmt.usdt(position.entry_price)}</span>
            </div>
            <div>
              <span className="text-zinc-500">Anlık:</span>
              <span className="ml-2 text-zinc-200 font-mono">{fmt.usdt(currentPrice)}</span>
            </div>
            <div>
              <span className="text-zinc-500">Marjin:</span>
              <span className="ml-2 text-zinc-200 font-mono">{fmt.usdt(position.margin_usdt)}</span>
            </div>
            <div>
              <span className="text-zinc-500">ROE:</span>
              <span
                className={`ml-2 font-mono font-semibold ${
                  (liveRoe ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {liveRoe != null ? fmt.pct(liveRoe) : '—'}
              </span>
            </div>
            <div>
              <span className="text-zinc-500">SL:</span>
              <span className="ml-2 font-mono text-rose-400">
                {position.stop_loss ? fmt.usdt(position.stop_loss) : '—'}
              </span>
            </div>
            <div>
              <span className="text-zinc-500">TP:</span>
              <span className="ml-2 font-mono text-emerald-400">
                {position.take_profit ? fmt.usdt(position.take_profit) : '—'}
              </span>
            </div>
            <div className="col-span-2">
              <span className="text-zinc-500">Likidasyon:</span>
              <span className="ml-2 font-mono text-amber-400">{fmt.usdt(position.liquidation_price)}</span>
            </div>
          </div>

          <Button
            variant="danger"
            size="sm"
            className="w-full mt-3"
            onClick={handleClose}
            isLoading={isClosing}
            leftIcon={<X size={13} />}
          >
            Market Kapat
          </Button>

          <div className="grid grid-cols-2 gap-2 mt-2">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => handleClosePartial(0.5)}
              isLoading={isClosing}
            >
              %50 Kapat
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => handleClosePartial(0.25)}
              isLoading={isClosing}
            >
              %25 Kapat
            </Button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <Input
              label="SL (Güncelle)"
              type="number"
              placeholder="Opsiyonel"
              value={stopLoss}
              onChange={(e) => setStopLoss(e.target.value)}
              leftAddon={<AlertTriangle size={10} className="text-rose-400" />}
            />
            <Input
              label="TP (Güncelle)"
              type="number"
              placeholder="Opsiyonel"
              value={takeProfit}
              onChange={(e) => setTakeProfit(e.target.value)}
              leftAddon={<TrendingUp size={10} className="text-emerald-400" />}
            />
          </div>

          <Button
            variant="ghost"
            size="sm"
            className="w-full mt-2"
            onClick={handleUpdate}
            isLoading={isUpdating}
          >
            SL/TP Güncelle
          </Button>
        </Card>
      )}

      {/* Trade form */}
      {!position && (
        <Card title="Pozisyon Aç" titleRight={
          <span className="text-xs font-mono text-sky-400">{fmt.usdt(currentPrice)}</span>
        }>
          {/* Leverage */}
          <div className="mb-4">
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2 block">
              Kaldıraç — {leverage}x
            </label>
            <div className="flex flex-wrap gap-1">
              {LEVERAGES.map((l) => (
                <button
                  key={l}
                  onClick={() => setLeverage(l)}
                  className={`px-2 py-1 text-xs rounded font-mono transition-all ${
                    leverage === l
                      ? 'bg-sky-600 text-white'
                      : 'bg-zinc-700 text-zinc-400 hover:bg-zinc-600'
                  }`}
                >
                  {l}x
                </button>
              ))}
            </div>
          </div>

          {/* Margin */}
          <div className="mb-3">
            <Input
              label="Marjin (USDT)"
              type="number"
              min="1"
              step="10"
              value={marginUsdt}
              onChange={(e) => setMarginUsdt(e.target.value)}
              leftAddon={<DollarSign size={12} />}
              rightAddon="USDT"
              hint={`Pozisyon: ${fmt.usdt(Number(marginUsdt) * leverage)}`}
            />
          </div>

          {/* SL / TP */}
          <div className="grid grid-cols-2 gap-2 mb-4">
            <Input
              label="Stop Loss"
              type="number"
              placeholder="Opsiyonel"
              value={stopLoss}
              onChange={(e) => setStopLoss(e.target.value)}
              leftAddon={<AlertTriangle size={10} className="text-rose-400" />}
            />
            <Input
              label="Take Profit"
              type="number"
              placeholder="Opsiyonel"
              value={takeProfit}
              onChange={(e) => setTakeProfit(e.target.value)}
              leftAddon={<TrendingUp size={10} className="text-emerald-400" />}
            />
          </div>

          {/* Open buttons */}
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="success"
              size="md"
              className="w-full"
              onClick={() => handleOpen('long')}
              isLoading={isOpening}
              leftIcon={<TrendingUp size={14} />}
            >
              Long Aç
            </Button>
            <Button
              variant="danger"
              size="md"
              className="w-full"
              onClick={() => handleOpen('short')}
              isLoading={isOpening}
              leftIcon={<TrendingDown size={14} />}
            >
              Short Aç
            </Button>
          </div>
        </Card>
      )}

      {/* Feedback */}
      {feedback && (
        <div
          className={`text-xs px-3 py-2 rounded-lg border ${
            feedback.type === 'success'
              ? 'bg-emerald-900/30 border-emerald-700/50 text-emerald-400'
              : 'bg-rose-900/30 border-rose-700/50 text-rose-400'
          }`}
        >
          {feedback.msg}
        </div>
      )}
    </div>
  );
}
