# -*- coding: utf-8 -*-
"""
The Executioner — Trend + RSI pullback + hacim onayı + ATR tabanlı SL/TP.
EMA 200/50 trend filtresi; RSI(14) pullback girişi; hacim ortalamasının %120'si; SL=1.5*ATR, TP=2.5*ATR.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from trading_engine import TradingEngine
    from data_engine import DataEngine

try:
    import pandas_ta as ta
except ImportError:
    ta = None

# Sabitler (overfitting’den kaçınmak için tek yerde)
EMA_FAST = 50
EMA_SLOW = 200
RSI_LEN = 14
RSI_OVERSOLD = 40
RSI_OVERBOUGHT = 60
ATR_LEN = 14
VOL_LOOKBACK = 10
VOL_MIN_RATIO = 1.20  # Giriş mumu hacmi >= %120 * son 10 mum ortalaması
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.5
MIN_BARS_FOR_INDICATORS = 201  # EMA200 + 1 bar
MARGIN_PCT_OF_BALANCE = 0.05
LEVERAGE = 5
MIN_MARGIN_USDT = 10.0


class ExecutionerBot:
    """
    Trend filtresi (EMA 200/50) + RSI pullback girişi + hacim onayı + dinamik ATR SL/TP.
    Sadece tamamlanmış mumlarda karar verir; tek açık pozisyon kuralına uyar.
    """

    name = "The Executioner"
    timeframe = "15m"

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine = trading_engine
        self._data_engine = data_engine
        self._last_log_ts: Optional[str] = None

    def _log(self, msg: str) -> None:
        """UI Bot Loglarına yazar (trading_engine üzerinden)."""
        try:
            self._engine.log_message(f"[{self.name}] {msg}")
        except Exception:
            pass

    def _safe_float(self, x: Any, default: float = 0.0) -> float:
        try:
            v = float(x)
            return v if pd.notna(v) and abs(v) < 1e15 else default
        except (TypeError, ValueError):
            return default

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        """Tamamlanan TF mumunda trend + pullback + hacim kontrolü; uygunsa pozisyon açar."""
        if timeframe != self.timeframe or ta is None:
            return
        if self._engine.get_position() is not None:
            return

        df = self._data_engine.get_completed_tf_candles(timeframe) if self._data_engine else None
        if df is None or len(df) < MIN_BARS_FOR_INDICATORS:
            return

        try:
            close = df["close"].astype(float)
            high = df["high"].astype(float)
            low = df["low"].astype(float)
            volume = df["volume"].astype(float)
        except Exception as e:
            self._log(f"Hata: veri dönüşümü — {e}")
            return

        try:
            # İndikatörler (son iki bar için RSI gerekli)
            ema50 = ta.ema(close, length=EMA_FAST)
            ema200 = ta.ema(close, length=EMA_SLOW)
            rsi = ta.rsi(close, length=RSI_LEN)
            atr = ta.atr(high, low, close, length=ATR_LEN)

            if ema50 is None or ema200 is None or rsi is None or atr is None:
                return
            if len(close) < 2 or pd.isna(ema200.iloc[-1]) or pd.isna(ema50.iloc[-1]):
                return

            price = self._safe_float(candle.get("close", close.iloc[-1]))
            ema200_curr = self._safe_float(ema200.iloc[-1])
            ema50_curr = self._safe_float(ema50.iloc[-1])
            rsi_curr = self._safe_float(rsi.iloc[-1], 50.0)
            rsi_prev = self._safe_float(rsi.iloc[-2], 50.0)
            atr_curr = self._safe_float(atr.iloc[-1])

            if atr_curr <= 0 or pd.isna(atr.iloc[-1]):
                return

            # Trend: Fiyat EMA200’e göre (talep: altında sadece SHORT, üstünde sadece LONG)
            trend_up = price > ema200_curr
            trend_down = price < ema200_curr

            # Hacim onayı: giriş mumu hacmi >= son 10 mum ort. * 1.20
            vol_curr = self._safe_float(candle.get("volume", volume.iloc[-1] if len(volume) > 0 else 0))
            if len(volume) >= VOL_LOOKBACK:
                vol_avg = float(volume.iloc[-VOL_LOOKBACK:].mean())
                if vol_avg <= 0 or vol_curr < VOL_MIN_RATIO * vol_avg:
                    return
            else:
                return

            # Giriş sinyalleri (pullback)
            long_signal = (
                trend_up
                and rsi_prev < RSI_OVERSOLD
                and rsi_curr > rsi_prev
            )
            short_signal = (
                trend_down
                and rsi_prev > RSI_OVERBOUGHT
                and rsi_curr < rsi_prev
            )

            if not long_signal and not short_signal:
                return

            # Marjin: bakiye yüzdesi, minimum kontrol
            available = self._engine.get_available_balance()
            margin = max(MIN_MARGIN_USDT, available * MARGIN_PCT_OF_BALANCE)
            if margin > available or margin < MIN_MARGIN_USDT:
                self._log("Yetersiz bakiye veya minimum marjin sağlanamadı.")
                return

            if long_signal:
                sl_price = price - SL_ATR_MULT * atr_curr
                tp_price = price + TP_ATR_MULT * atr_curr
                if sl_price >= price or tp_price <= price:
                    return
                res = self._engine.open_long(
                    entry_price=price,
                    margin_usdt=margin,
                    leverage=LEVERAGE,
                    stop_loss=sl_price,
                    take_profit=tp_price,
                    opened_by=self.name,
                )
                if res.get("success"):
                    self._log(
                        f"LONG açıldı @ {price:.2f} | SL={sl_price:.2f} TP={tp_price:.2f} | "
                        f"ATR={atr_curr:.2f} RSI={rsi_curr:.1f}"
                    )
                else:
                    self._log(f"LONG açılamadı: {res.get('message', '')}")
                return

            if short_signal:
                sl_price = price + SL_ATR_MULT * atr_curr
                tp_price = price - TP_ATR_MULT * atr_curr
                if sl_price <= price or tp_price >= price:
                    return
                res = self._engine.open_short(
                    entry_price=price,
                    margin_usdt=margin,
                    leverage=LEVERAGE,
                    stop_loss=sl_price,
                    take_profit=tp_price,
                    opened_by=self.name,
                )
                if res.get("success"):
                    self._log(
                        f"SHORT açıldı @ {price:.2f} | SL={sl_price:.2f} TP={tp_price:.2f} | "
                        f"ATR={atr_curr:.2f} RSI={rsi_curr:.1f}"
                    )
                else:
                    self._log(f"SHORT açılamadı: {res.get('message', '')}")
        except Exception as e:
            self._log(f"Hata: {e}")
