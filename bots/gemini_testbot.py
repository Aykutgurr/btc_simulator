# -*- coding: utf-8 -*-
"""
Gemini_TestBot: MFI + OBV/OBV_EMA + ADX ile giriş.
Long: ADX < 25, MFI < 30, OBV > OBV_EMA. Short: ADX < 25, MFI > 70, OBV < OBV_EMA.
TP %0.5, SL %1, Kaldıraç 10x.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None


LEVERAGE = 10
TP_PCT = 0.005   # %0.5
SL_PCT = 0.01    # %1
MARGIN_PCT = 0.10  # Bakiye %10 marjin (10x = %100 risk)
MIN_BARS_WARMUP = 25  # MFI(14), OBV_EMA(20), ADX(14) için


def _compute_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """MFI, OBV, OBV_EMA, ADX hesaplar."""
    if ta is None or df is None or len(df) < MIN_BARS_WARMUP:
        return None
    high = df["high"]
    low = df["low"]
    close = df["close"]
    volume = df["volume"]
    out = pd.DataFrame(index=df.index)

    mfi = ta.mfi(high, low, close, volume, length=14)
    if mfi is not None:
        out["mfi"] = mfi

    obv = ta.obv(close, volume)
    if obv is not None:
        out["obv"] = obv
        obv_ema = ta.ema(obv, length=20)
        if obv_ema is not None:
            out["obv_ema"] = obv_ema

    adx_df = ta.adx(high, low, close, length=14)
    if adx_df is not None and isinstance(adx_df, pd.DataFrame):
        adx_col = [c for c in adx_df.columns if "ADX" in c.upper()]
        if adx_col:
            out["adx"] = adx_df[adx_col[0]]
        else:
            out["adx"] = adx_df.iloc[:, 0]
    elif adx_df is not None:
        out["adx"] = adx_df

    if "mfi" not in out.columns or "obv" not in out.columns or "obv_ema" not in out.columns or "adx" not in out.columns:
        return None
    return out


class Gemini_TestBot:
    """
    BTC Flow Sniper mantığı: MFI + OBV/OBV_EMA + ADX.
    - Long: ADX < 25, MFI < 30, OBV > OBV_EMA. TP %0.5, SL %1.
    - Short: ADX < 25, MFI > 70, OBV < OBV_EMA. TP %0.5, SL %1.
    - Kaldıraç 10x.
    """

    name = "Gemini_TestBot"
    timeframe = "15m"

    def __init__(self, trading_engine: Any) -> None:
        self._engine = trading_engine
        self._history_15m: List[Dict[str, Any]] = []

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe:
            return
        if ta is None:
            return
        self._history_15m.append(candle.copy())
        if len(self._history_15m) < MIN_BARS_WARMUP:
            return
        pos = self._engine.get_position()
        if pos is not None:
            return

        try:
            df = pd.DataFrame(self._history_15m)
            df = df[["open", "high", "low", "close", "volume"]].astype(float)
            ind = _compute_indicators(df)
            if ind is None or ind.empty:
                return
            last = ind.iloc[-1]
            mfi = last.get("mfi")
            obv = last.get("obv")
            obv_ema = last.get("obv_ema")
            adx = last.get("adx")
            if pd.isna(mfi) or pd.isna(obv) or pd.isna(obv_ema) or pd.isna(adx):
                return
            if adx >= 25:
                return

            price = float(candle["close"])
            balance = self._engine.get_balance_usdt()
            margin = balance * MARGIN_PCT
            if margin < 10:
                return

            long_in = mfi < 30 and obv > obv_ema
            short_in = mfi > 70 and obv < obv_ema

            if long_in:
                tp_price = price * (1 + TP_PCT)
                sl_price = price * (1 - SL_PCT)
                if sl_price > 0 and tp_price > price:
                    self._engine.open_long(
                        entry_price=price,
                        margin_usdt=margin,
                        leverage=LEVERAGE,
                        stop_loss=sl_price,
                        take_profit=tp_price,
                        opened_by=self.name,
                    )
            elif short_in:
                tp_price = price * (1 - TP_PCT)
                sl_price = price * (1 + SL_PCT)
                if tp_price > 0 and sl_price > price:
                    self._engine.open_short(
                        entry_price=price,
                        margin_usdt=margin,
                        leverage=LEVERAGE,
                        stop_loss=sl_price,
                        take_profit=tp_price,
                        opened_by=self.name,
                    )
        except Exception:
            pass
