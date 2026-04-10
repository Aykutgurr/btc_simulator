# -*- coding: utf-8 -*-
"""
MTF AOI + MSB Bot: HTF (W/D/4H) çoğunluk, günlük AOI (3+ temas), 15m gövde kapanışı MSB, sabit SL/TP.
"""

from typing import Any, Dict, TYPE_CHECKING

from .msb_mtf_logic import LOOKBACK_DAYS_DEFAULT, evaluate_msb_mtf

if TYPE_CHECKING:
    from trading_engine import TradingEngine
    from data_engine import DataEngine

MARGIN_PCT_OF_BALANCE = 0.05
LEVERAGE = 5
MIN_MARGIN_USDT = 10.0


class MSB_MTF_Bot:
    name = "MSB_MTF_AOI"
    timeframe = "15m"

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine = trading_engine
        self._data_engine = data_engine
        self._warned_short_data = False

    def _log(self, msg: str) -> None:
        try:
            self._engine.log_message(f"[{self.name}] {msg}")
        except Exception:
            pass

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe:
            return
        if self._engine.get_position() is not None:
            return
        if self._data_engine is None:
            return

        df_1m = self._data_engine.get_all_1m_for_indicators()
        if df_1m is None or len(df_1m) < 500:
            if not self._warned_short_data and df_1m is not None and len(df_1m) > 0:
                self._warned_short_data = True
                self._log("Yetersiz 1m geçmiş: HTF/AOI için daha uzun tarih aralığı önerilir.")
            return

        span_days = max(1, (df_1m.index[-1] - df_1m.index[0]).days)
        if span_days < 120:
            if not self._warned_short_data:
                self._warned_short_data = True
                self._log(f"Veri ~{span_days} gün: HTF oylaması ve AOI zayıf kalabilir.")

        sig = evaluate_msb_mtf(df_1m, lookback_days=min(LOOKBACK_DAYS_DEFAULT, max(90, span_days)))
        if sig is None:
            return

        entry = float(sig["entry"])
        sl = float(sig["stop_loss"])
        tp = float(sig["take_profit"])
        direction = sig["direction"]
        if entry <= 0:
            return

        available = self._engine.get_available_balance()
        margin = max(MIN_MARGIN_USDT, available * MARGIN_PCT_OF_BALANCE)
        if margin > available or margin < MIN_MARGIN_USDT:
            self._log("Yetersiz bakiye veya minimum marjin sağlanamadı.")
            return

        if direction == "short":
            res = self._engine.open_short(
                entry_price=entry,
                margin_usdt=margin,
                leverage=LEVERAGE,
                stop_loss=sl,
                take_profit=tp,
                opened_by=self.name,
            )
            if res.get("success"):
                self._log(f"SHORT @ {entry:.2f} | SL={sl:.2f} TP={tp:.2f} | MSB+AOI+HTF")
            else:
                self._log(f"SHORT açılamadı: {res.get('message', '')}")
        elif direction == "long":
            res = self._engine.open_long(
                entry_price=entry,
                margin_usdt=margin,
                leverage=LEVERAGE,
                stop_loss=sl,
                take_profit=tp,
                opened_by=self.name,
            )
            if res.get("success"):
                self._log(f"LONG @ {entry:.2f} | SL={sl:.2f} TP={tp:.2f} | MSB+AOI+HTF")
            else:
                self._log(f"LONG açılamadı: {res.get('message', '')}")
