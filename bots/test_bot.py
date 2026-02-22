# -*- coding: utf-8 -*-
"""
Örnek test botu: 15m timeframe, RSI + EMA hızlı strateji.
Sermaye %5 marjin, 5x kaldıraç, TP %1, SL %2.
"""

from typing import Dict, Any, List, Optional

import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None


class TestBot15m:
    """15 dakikalık mumlara göre sinyal üreten test botu."""

    name = "TestBot_15m"
    timeframe = "15m"

    def __init__(self, trading_engine: Any):
        self._engine = trading_engine
        self._history_15m: List[Dict[str, Any]] = []

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        """15m mum tamamlandığında çağrılır. Sinyal üretip pozisyon açar."""
        if timeframe != self.timeframe:
            return
        self._history_15m.append(candle.copy())
        if len(self._history_15m) < 20:
            return
        try:
            if ta is None:
                return
            close_series = pd.Series([c["close"] for c in self._history_15m])
            rsi = ta.rsi(close_series, length=14)
            if rsi is None or len(rsi) < 2:
                return
            rsi_last = float(rsi.iloc[-1]) if hasattr(rsi, "iloc") else float(rsi[-1])
            rsi_prev = float(rsi.iloc[-2]) if hasattr(rsi, "iloc") else float(rsi[-2])
            price = candle["close"]
            pos = self._engine.get_position()
            if pos is not None:
                return
            balance = self._engine.get_balance_usdt()
            margin = balance * 0.5 # %5 marjinli hali eskiden 0.05 ti
            if margin < 10:
                return
            leverage = 5.0
            if rsi_last < 35 and rsi_prev >= 35:
                tp = price * 1.01
                sl = price * 0.98
                r = self._engine.open_long(
                    entry_price=price,
                    margin_usdt=margin,
                    leverage=leverage,
                    stop_loss=sl,
                    take_profit=tp,
                    opened_by=self.name,
                )
            elif rsi_last > 65 and rsi_prev <= 65:
                tp = price * 0.99
                sl = price * 1.02
                r = self._engine.open_short(
                    entry_price=price,
                    margin_usdt=margin,
                    leverage=leverage,
                    stop_loss=sl,
                    take_profit=tp,
                    opened_by=self.name,
                )
        except Exception:
            pass
