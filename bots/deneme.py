# -*- coding: utf-8 -*-
"""
Deneme: Hacim + EMA200 + RSI ile giriş, hibrit çıkış (kısmi → breakeven → trailing).
15m timeframe; indikatörler: EMA 200, RSI 14, ATR 14, Hacim SMA 10.
"""

import traceback
from collections import deque
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np

try:
    import pandas_ta as ta
except ImportError:
    ta = None

from .para_makinasi1 import _ema, _rsi, _atr


MAX_HISTORY_15M = 200


def _volume_sma(series: pd.Series, length: int = 10) -> pd.Series:
    return series.rolling(window=length, min_periods=length).mean()


class AykutunSagTassagi:
    """
    Giriş: Hacim > Hacim SMA 10; Long: Fiyat > EMA200 ve RSI > 50; Short: Fiyat < EMA200 ve RSI < 50.
    Risk: 1.5 * ATR SL. Hibrit çıkış: +%5 kârda %50 kısmi → SL breakeven → +%5 üstü trailing %1.
    """

    name = "deneme"
    timeframe = "15m"

    MIN_BARS_15M = 201

    # Hibrit çıkış fazları
    PHASE_1 = 1   # Kâr +%5 olunca %50 kapat
    PHASE_2 = 2   # SL breakeven'e çekildi
    PHASE_3 = 3   # Trailing stop aktif (%1 mesafe)

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine = trading_engine
        self._data_engine = data_engine
        self._history_15m: deque = deque(maxlen=MAX_HISTORY_15M)
        self._phase: int = 0
        self._trailing_stop_level: Optional[float] = None

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        try:
            self._on_timeframe_candle_impl(timeframe, candle)
        except Exception:
            self._engine.log_message(traceback.format_exc())

    def _on_timeframe_candle_impl(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe:
            return
        # Tarih listesini max 200 mumda tut
        self._history_15m.append(candle.copy())
        self._handle_hybrid_exit(candle["close"])
        pos = self._engine.get_position()
        if pos is not None:
            return
        df_15m, indicators = self._get_15m_indicators()
        if df_15m is None or indicators is None or len(df_15m) < self.MIN_BARS_15M:
            return
        self._try_open_position(candle, df_15m, indicators)

    def _get_15m_indicators(self) -> tuple:
        df_1m = self._data_engine.get_all_1m_for_indicators() if self._data_engine else None
        if df_1m is None or len(df_1m) < 100:
            return None, None
        if not pd.api.types.is_datetime64_any_dtype(df_1m.index):
            df_1m = df_1m.copy()
            df_1m.index = pd.to_datetime(df_1m.index, errors="coerce")
            df_1m = df_1m[df_1m.index.notna()]
        agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        df_15m = df_1m.resample("15min").agg(agg).dropna(how="all")
        if len(df_15m) < self.MIN_BARS_15M:
            return df_15m, None
        close = df_15m["close"].astype(float)
        high = df_15m["high"].astype(float)
        low = df_15m["low"].astype(float)
        volume = df_15m["volume"].astype(float)
        ema200 = _ema(close, 200)
        rsi = _rsi(close, 14)
        atr = _atr(high, low, close, 14)
        vol_sma10 = _volume_sma(volume, 10)
        if rsi is None or atr is None or ema200.isna().iloc[-1]:
            return df_15m, None
        if pd.isna(vol_sma10.iloc[-1]):
            return df_15m, None
        indicators = {
            "ema200": ema200,
            "rsi": rsi,
            "atr": atr,
            "volume_sma10": vol_sma10,
        }
        return df_15m, indicators

    def _try_open_position(
        self,
        candle: Dict[str, Any],
        df_15m: pd.DataFrame,
        indicators: Dict[str, pd.Series],
    ) -> None:
        ema200 = indicators["ema200"]
        rsi = indicators["rsi"]
        atr = indicators["atr"]
        vol_sma10 = indicators["volume_sma10"]
        n = len(df_15m)
        price = float(candle["close"])
        volume_last = float(candle.get("volume", 0) or df_15m["volume"].iloc[-1])
        vol_sma_last = float(vol_sma10.iloc[-1])
        if volume_last <= vol_sma_last:
            return
        ema_last = float(ema200.iloc[-1])
        rsi_last = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        atr_last = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else price * 0.01
        balance = self._engine.get_balance_usdt()
        margin = balance * 0.05
        if margin < 10:
            return
        leverage = 5.0
        # Long: Fiyat > EMA 200 ve RSI > 50
        if price > ema_last and rsi_last > 50:
            sl_price = price - 1.5 * atr_last
            self._phase = self.PHASE_1
            self._trailing_stop_level = None
            self._engine.open_long(
                entry_price=price,
                margin_usdt=margin,
                leverage=leverage,
                stop_loss=sl_price,
                take_profit=None,
                opened_by=self.name,
            )
            return
        # Short: Fiyat < EMA 200 ve RSI < 50
        if price < ema_last and rsi_last < 50:
            sl_price = price + 1.5 * atr_last
            self._phase = self.PHASE_1
            self._trailing_stop_level = None
            self._engine.open_short(
                entry_price=price,
                margin_usdt=margin,
                leverage=leverage,
                stop_loss=sl_price,
                take_profit=None,
                opened_by=self.name,
            )

    def _handle_hybrid_exit(self, current_price: float) -> None:
        pos = self._engine.get_position()
        if pos is None or pos.get("opened_by") != self.name:
            self._phase = 0
            self._trailing_stop_level = None
            return
        entry = pos["entry_price"]
        direction = pos["direction"]

        if direction == "long":
            pnl_pct = (current_price - entry) / entry * 100.0
            if self._phase == self.PHASE_1 and pnl_pct >= 5.0:
                r = self._engine.close_partial(current_price, fraction=0.5)
                if r.get("partial"):
                    self._phase = self.PHASE_2
                    pos_rem = r.get("position") or self._engine.get_position()
                    if pos_rem and pos_rem.get("position_size_btc"):
                        m = pos_rem["margin_usdt"]
                        s = pos_rem["position_size_btc"]
                        e = pos_rem["entry_price"]
                        lv = pos_rem["leverage"]
                        be = e + (m * lv * self._engine.COMMISSION_RATE) / s
                        self._engine.update_position_parameters(new_sl=be, new_tp=None)
                return
            if self._phase == self.PHASE_2 and pnl_pct >= 5.0:
                self._phase = self.PHASE_3
            if self._phase == self.PHASE_3:
                self._trailing_stop_level = max(
                    self._trailing_stop_level or 0,
                    current_price * 0.99,
                )
                if current_price <= self._trailing_stop_level:
                    self._engine.close_position(current_price)
                    self._phase = 0
                    self._trailing_stop_level = None
        else:
            pnl_pct = (entry - current_price) / entry * 100.0
            if self._phase == self.PHASE_1 and pnl_pct >= 5.0:
                r = self._engine.close_partial(current_price, fraction=0.5)
                if r.get("partial"):
                    self._phase = self.PHASE_2
                    pos_rem = r.get("position") or self._engine.get_position()
                    if pos_rem and pos_rem.get("position_size_btc"):
                        m = pos_rem["margin_usdt"]
                        s = pos_rem["position_size_btc"]
                        e = pos_rem["entry_price"]
                        lv = pos_rem["leverage"]
                        be = e - (m * lv * self._engine.COMMISSION_RATE) / s
                        self._engine.update_position_parameters(new_sl=be, new_tp=None)
                return
            if self._phase == self.PHASE_2 and pnl_pct >= 5.0:
                self._phase = self.PHASE_3
            if self._phase == self.PHASE_3:
                self._trailing_stop_level = min(
                    self._trailing_stop_level or float("inf"),
                    current_price * 1.01,
                )
                if current_price >= self._trailing_stop_level:
                    self._engine.close_position(current_price)
                    self._phase = 0
                    self._trailing_stop_level = None
