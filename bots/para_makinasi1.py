# -*- coding: utf-8 -*-
"""
Para Makinası 1: Trend takip + dinamik risk yönetimi (EMA 200, RSI, ATR).
15m mum tamamlandığında tetiklenir; 1m veriyi 15min resample ile indikatör hesaplar.
"""

from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np

try:
    import pandas_ta as ta
except ImportError:
    ta = None


def _ema(series: pd.Series, length: int) -> pd.Series:
    """EMA hesaplar (pandas_ta yoksa ewm fallback)."""
    if ta is not None:
        s = ta.ema(series, length=length)
        if s is not None and not s.dropna().empty:
            return s
    return series.ewm(span=length, adjust=False).mean()


def _rsi(series: pd.Series, length: int = 14) -> Optional[pd.Series]:
    """RSI(14) hesaplar."""
    if ta is not None:
        s = ta.rsi(series, length=length)
        if s is not None and not s.dropna().empty:
            return s
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(span=length, adjust=False).mean()
    avg_loss = loss.ewm(span=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> Optional[pd.Series]:
    """ATR(14) hesaplar."""
    if ta is not None:
        s = ta.atr(high, low, close, length=length)
        if s is not None and not s.dropna().empty:
            return s
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=length, adjust=False).mean()


class ParaMakinasi1:
    """
    Trend takip + triple confirmation (EMA200, RSI, önceki mum high/low).
    Initial SL: 1.5 * ATR. Trailing: %1.5 kârda aktif, %0.5 mesafe.
    """

    name = "Para Makinası 1"
    timeframe = "15m"

    # Minimum 15m bar sayısı (EMA200 için)
    MIN_BARS_15M = 201

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine = trading_engine
        self._data_engine = data_engine
        self._trailing_active: bool = False
        self._trailing_stop_level: Optional[float] = None

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe:
            return
        try:
            self._handle_trailing_stop(candle["close"])
            pos = self._engine.get_position()
            if pos is not None:
                return
            df_15m, indicators = self._get_15m_indicators()
            if df_15m is None or indicators is None or len(df_15m) < self.MIN_BARS_15M:
                return
            self._try_open_position(candle, df_15m, indicators)
        except Exception:
            pass

    def _get_15m_indicators(self) -> tuple:
        """1m veriyi alır, 15min resample eder, EMA200/RSI/ATR hesaplar. (df_15m, dict) veya (None, None)."""
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
        ema200 = _ema(close, 200)
        rsi = _rsi(close, 14)
        atr = _atr(high, low, close, 14)
        if rsi is None or atr is None or ema200.isna().iloc[-1]:
            return df_15m, None
        indicators = {
            "ema200": ema200,
            "rsi": rsi,
            "atr": atr,
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
        n = len(df_15m)
        price = float(candle["close"])
        ema_last = float(ema200.iloc[-1])
        rsi_last = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        atr_last = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else price * 0.01
        prev_high = float(df_15m["high"].iloc[-2]) if n >= 2 else 0.0
        prev_low = float(df_15m["low"].iloc[-2]) if n >= 2 else float("inf")

        balance = self._engine.get_balance_usdt()
        margin = balance * 0.05
        if margin < 10:
            return
        leverage = 5.0

        # Long: fiyat > EMA200, RSI > 50, close > prev_15m_high
        if price > ema_last and rsi_last > 50 and price > prev_high:
            sl_price = price - 1.5 * atr_last
            self._trailing_active = False
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
        # Short: fiyat < EMA200, RSI < 50, close < prev_15m_low
        if price < ema_last and rsi_last < 50 and price < prev_low:
            sl_price = price + 1.5 * atr_last
            self._trailing_active = False
            self._trailing_stop_level = None
            self._engine.open_short(
                entry_price=price,
                margin_usdt=margin,
                leverage=leverage,
                stop_loss=sl_price,
                take_profit=None,
                opened_by=self.name,
            )

    def _handle_trailing_stop(self, current_price: float) -> None:
        """Pozisyon bizimse: %1.5 kârda trailing aktif, %0.5 mesafe; seviyeyi güncelle / gerekirse kapat."""
        pos = self._engine.get_position()
        if pos is None or pos.get("opened_by") != self.name:
            self._trailing_active = False
            self._trailing_stop_level = None
            return
        entry = pos["entry_price"]
        direction = pos["direction"]
        if direction == "long":
            pnl_pct = (current_price - entry) / entry * 100.0
            if pnl_pct >= 1.5:
                self._trailing_active = True
                new_level = current_price * 0.995
                if self._trailing_stop_level is None:
                    self._trailing_stop_level = new_level
                else:
                    self._trailing_stop_level = max(self._trailing_stop_level, new_level)
                if current_price <= self._trailing_stop_level:
                    self._engine.close_position(current_price)
                    self._trailing_stop_level = None
                    self._trailing_active = False
        else:
            pnl_pct = (entry - current_price) / entry * 100.0
            if pnl_pct >= 1.5:
                self._trailing_active = True
                new_level = current_price * 1.005
                if self._trailing_stop_level is None:
                    self._trailing_stop_level = new_level
                else:
                    self._trailing_stop_level = min(self._trailing_stop_level, new_level)
                if current_price >= self._trailing_stop_level:
                    self._engine.close_position(current_price)
                    self._trailing_stop_level = None
                    self._trailing_active = False
