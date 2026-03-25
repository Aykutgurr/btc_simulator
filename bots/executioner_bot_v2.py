# -*- coding: utf-8 -*-
"""
The Executioner v2 — Backtest iyileştirmeli sürüm.
- TP 4.0*ATR, hacim %110, marjin %2.
- Golden/Death Cross (EMA50 vs EMA200) ile trend teyidi.
- Trailing: TP yarısına (2*ATR) gelince SL break-even'a çekilir.
- Komisyon beklenen kârın %20'sinden fazlaysa işleme girilmez.
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

# Parametreler (backtest sonuçlarına göre güncellendi)
EMA_FAST = 50
EMA_SLOW = 200
RSI_LEN = 14
RSI_OVERSOLD = 40
RSI_OVERBOUGHT = 60
ATR_LEN = 14
VOL_LOOKBACK = 10
VOL_MIN_RATIO = 1.10  # Giriş mumu hacmi >= %110 * son 10 mum ortalaması
SL_ATR_MULT = 1.5
TP_ATR_MULT = 4.0  # Trendden maksimum kar
TRAIL_TRIGGER_ATR_MULT = 2.0  # TP'nin yarısı (4*ATR/2) — bu seviyede SL break-even'a çekilir
MIN_BARS_FOR_INDICATORS = 201
MARGIN_PCT_OF_BALANCE = 0.02  # %2 — düşük win-rate için daha güvenli
LEVERAGE = 5
MIN_MARGIN_USDT = 10.0
COMMISSION_MAX_PCT_OF_EXPECTED_PROFIT = 0.20  # Komisyon beklenen brüt kârın %20'sini geçmemeli

# Break-even: round-trip komisyonu karşılayan fiyat (engine COMMISSION_RATE = 0.001, açılış+kapanış)
COMMISSION_RATE_ROUND_TRIP = 0.002  # 2 * 0.001


class ExecutionerBotV2:
    """
    Executioner v2: Daha sıkı trend filtresi (EMA50/200 cross), düşük marjin,
    trailing break-even, komisyon/kar oranı kontrolü.
    """

    name = "The Executioner v2"
    timeframe = "15m"

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine = trading_engine
        self._data_engine = data_engine

    def _log(self, msg: str) -> None:
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

    def _try_trailing_stop(self, candle: Dict[str, Any]) -> None:
        """
        Açık pozisyon bizimse ve fiyat TP'nin yarısına (2*ATR) ulaştıysa,
        Stop-Loss'u break-even (giriş + komisyon) seviyesine çek.
        """
        pos = self._engine.get_position()
        if pos is None or pos.get("opened_by") != self.name:
            return
        entry = self._safe_float(pos.get("entry_price"))
        current_sl = pos.get("stop_loss")
        if entry <= 0:
            return

        df = self._data_engine.get_completed_tf_candles(self.timeframe) if self._data_engine else None
        if df is None or len(df) < ATR_LEN + 5:
            return
        try:
            high = df["high"].astype(float)
            low = df["low"].astype(float)
            close = df["close"].astype(float)
        except Exception:
            return
        atr_series = ta.atr(high, low, close, length=ATR_LEN) if ta else None
        if atr_series is None or len(atr_series) < 1 or pd.isna(atr_series.iloc[-1]):
            return
        atr_curr = self._safe_float(atr_series.iloc[-1])
        if atr_curr <= 0:
            return

        price = self._safe_float(candle.get("close"))
        # Break-even: round-trip komisyonu karşılayan fiyat
        be_long = entry * (1.0 + COMMISSION_RATE_ROUND_TRIP)
        be_short = entry * (1.0 - COMMISSION_RATE_ROUND_TRIP)
        trigger_dist = TRAIL_TRIGGER_ATR_MULT * atr_curr

        if pos["direction"] == "long":
            if price >= entry + trigger_dist:
                # Mevcut SL zaten break-even veya daha iyiyse dokunma
                if current_sl is not None and current_sl >= be_long:
                    return
                res = self._engine.update_position_parameters(new_sl=be_long)
                if res.get("success"):
                    self._log(f"Trailing: LONG SL break-even'a çekildi @ {be_long:.2f}")
        else:
            if price <= entry - trigger_dist:
                if current_sl is not None and current_sl <= be_short:
                    return
                res = self._engine.update_position_parameters(new_sl=be_short)
                if res.get("success"):
                    self._log(f"Trailing: SHORT SL break-even'a çekildi @ {be_short:.2f}")

    def _commission_ok_for_trade(
        self,
        entry: float,
        tp_price: float,
        margin: float,
        is_long: bool,
    ) -> bool:
        """
        Komisyon maliyeti beklenen brüt kârın %20'sinden fazlaysa False döner.
        """
        notional = margin * LEVERAGE
        commission = 2.0 * notional * getattr(
            self._engine, "COMMISSION_RATE", 0.001
        )
        size_btc = notional / entry if entry > 0 else 0
        if size_btc <= 0:
            return False
        if is_long:
            expected_gross = (tp_price - entry) * size_btc
        else:
            expected_gross = (entry - tp_price) * size_btc
        if expected_gross <= 0:
            return False
        return commission <= COMMISSION_MAX_PCT_OF_EXPECTED_PROFIT * expected_gross

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe or ta is None:
            return

        # Önce kendi açtığımız pozisyonda trailing stop (break-even) kontrolü
        self._try_trailing_stop(candle)

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

            trend_up = price > ema200_curr
            trend_down = price < ema200_curr
            # Golden Cross / Death Cross: trend gücü teyidi
            golden_cross = ema50_curr > ema200_curr
            death_cross = ema50_curr < ema200_curr

            vol_curr = self._safe_float(candle.get("volume", volume.iloc[-1] if len(volume) > 0 else 0))
            if len(volume) >= VOL_LOOKBACK:
                vol_avg = float(volume.iloc[-VOL_LOOKBACK:].mean())
                if vol_avg <= 0 or vol_curr < VOL_MIN_RATIO * vol_avg:
                    return
            else:
                return

            long_signal = (
                trend_up
                and golden_cross  # EMA50 > EMA200
                and rsi_prev < RSI_OVERSOLD
                and rsi_curr > rsi_prev
            )
            short_signal = (
                trend_down
                and death_cross  # EMA50 < EMA200
                and rsi_prev > RSI_OVERBOUGHT
                and rsi_curr < rsi_prev
            )

            if not long_signal and not short_signal:
                return

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
                if not self._commission_ok_for_trade(price, tp_price, margin, is_long=True):
                    self._log("LONG iptal: Komisyon beklenen kârın %20'sinden fazla.")
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
                if not self._commission_ok_for_trade(price, tp_price, margin, is_long=False):
                    self._log("SHORT iptal: Komisyon beklenen kârın %20'sinden fazla.")
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
