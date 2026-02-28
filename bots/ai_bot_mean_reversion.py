# -*- coding: utf-8 -*-
"""
AIBot_MeanReversion: Rapor tabanlı ortalama geri dönüş (mean reversion) test botu.
RSI + BB %B ile aşırı alım/satım, ADX < 25 yatay piyasa filtresi, ATR tabanlı SL/TP,
Kısmi Kelly pozisyon boyutlandırma (max %20).
"""

from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None


# Sabit risk oranı (backtest başında Kelly için yeterli veri yok)
DEFAULT_MARGIN_PCT = 0.03  # %3 (daha muhafazakâr)
KELLY_FRACTION = 0.5  # Yarım Kelly
MAX_MARGIN_PCT = 0.20  # Rapor 2: %20 üst sınır
MIN_BARS_WARMUP = 30  # BB(20) + RSI/ADX/ATR(14) için
KELLY_LOOKBACK = 50    # Son N işlemden win rate / payoff
# test4: R:R 0.91 idi; TP yükselterek R:R ~1.5 (break-even WR ~%40)
ATR_SL_MULT = 2.0
ATR_TP_MULT = 3.0   # 2.5 -> 3.0
LEVERAGE = 5.0
# Giriş: test2 (çok işlem) ile test3 (6 işlem) arası orta yol
RSI_OVERSOLD = 35    # Long: RSI < 35 (klasik aşırı satım)
RSI_OVERBOUGHT = 65  # Short: RSI > 65 (klasik aşırı alım)
BBP_LONG_MAX = 0.0   # Long: BB %B <= 0 (bandın altı veya üst sınırı)
BBP_SHORT_MIN = 1.0  # Short: BB %B >= 1 (bandın üstü veya alt sınırı)
ADX_MAX_SIDEWAYS = 25  # ADX < 25 yatay piyasa (daha fazla fırsat)
COOLDOWN_BARS = 1      # Son açılıştan sonra 1 mum bekle (çift girişi azalt)


def _compute_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """RSI, BB %B, ATR, ADX hesaplar. pandas_ta gerekli."""
    if ta is None or df is None or len(df) < MIN_BARS_WARMUP:
        return None
    high = df["high"]
    low = df["low"]
    close = df["close"]
    out = pd.DataFrame(index=df.index)

    rsi = ta.rsi(close, length=14)
    if rsi is not None:
        out["rsi"] = rsi

    bbands = ta.bbands(close, length=20, std=2)
    if bbands is not None and isinstance(bbands, pd.DataFrame):
        bbp_col = [c for c in bbands.columns if "BBP" in c.upper()]
        if bbp_col:
            out["bbp"] = bbands[bbp_col[0]]
        else:
            # %%B = (close - lower) / (upper - lower)
            lower_col = [c for c in bbands.columns if "L" in c.upper() and "BB" in c][:1]
            upper_col = [c for c in bbands.columns if "U" in c.upper() and "BB" in c][:1]
            if lower_col and upper_col:
                out["bbp"] = (close - bbands[lower_col[0]]) / (
                    bbands[upper_col[0]] - bbands[lower_col[0]].replace(0, pd.NA)
                )
            else:
                out["bbp"] = bbands.iloc[:, -1]

    atr = ta.atr(high, low, close, length=14)
    if atr is not None:
        out["atr"] = atr

    adx_df = ta.adx(high, low, close, length=14)
    if adx_df is not None:
        if isinstance(adx_df, pd.DataFrame):
            adx_col = [c for c in adx_df.columns if "ADX" in c.upper()]
            out["adx"] = adx_df[adx_col[0]] if adx_col else adx_df.iloc[:, 0]
        else:
            out["adx"] = adx_df

    return out if "rsi" in out.columns and "bbp" in out.columns and "atr" in out.columns and "adx" in out.columns else None


def _half_kelly_margin_pct(history: List[Dict[str, Any]]) -> Optional[float]:
    """
    Son KELLY_LOOKBACK işlemden Yarım Kelly ile marjin yüzdesi hesaplar.
    f* = (p*b - q) / b; p=win rate, q=1-p, b=avg_win/avg_loss. Cap %20.
    """
    if not history or len(history) < 10:
        return None
    recent = history[-KELLY_LOOKBACK:]
    wins = [r for r in recent if r.get("pnl", r.get("pnl_net", 0)) > 0]
    losses = [r for r in recent if r.get("pnl", r.get("pnl_net", 0)) < 0]
    n = len(recent)
    p = len(wins) / n if n else 0
    q = 1 - p
    if not losses:
        b = 2.0  # conservative
    else:
        avg_win = sum(r.get("pnl", r.get("pnl_net", 0)) for r in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(r.get("pnl", r.get("pnl_net", 0)) for r in losses) / len(losses))
        b = (avg_win / avg_loss) if avg_loss > 0 else 2.0
    if b <= 0:
        return None
    f_star = (p * b - q) / b
    if f_star <= 0:
        return None
    half = KELLY_FRACTION * f_star
    return min(half, MAX_MARGIN_PCT)


class AIBot_MeanReversion:
    """
    Ortalama geri dönüş (mean reversion) botu.
    - Long: RSI < 35, BB %B <= 0, ADX < 25
    - Short: RSI > 65, BB %B >= 1, ADX < 25
    - SL/TP: ATR(14) ile 2xATR / 3xATR (R:R ~1.5)
    - Cooldown: 1 mum. Pozisyon: %3 veya Yarım Kelly (max %20).
    """

    name = "AIBot_MeanReversion"
    timeframe = "15m"

    def __init__(self, trading_engine: Any) -> None:
        self._engine = trading_engine
        self._history_15m: List[Dict[str, Any]] = []
        self._last_open_bar_index: Optional[int] = None  # Cooldown: son açılışın bar indeksi

    def _margin_pct(self) -> float:
        """Marjin için kullanılacak bakiye yüzdesi (Kısmi Kelly veya sabit)."""
        history = self._engine.get_trade_history()
        # Sadece bu botun işlemleri için filtre (tetikleyici veya opened_by)
        bot_trades = [r for r in history if r.get("tetikleyici") == self.name or r.get("opened_by") == self.name]
        kelly_pct = _half_kelly_margin_pct(bot_trades)
        if kelly_pct is not None and kelly_pct > 0:
            return min(max(kelly_pct, 0.01), MAX_MARGIN_PCT)
        return DEFAULT_MARGIN_PCT

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
            rsi = last.get("rsi")
            bbp = last.get("bbp")
            atr = last.get("atr")
            adx = last.get("adx")
            if pd.isna(rsi) or pd.isna(bbp) or pd.isna(atr) or pd.isna(adx):
                return
            # Yatay piyasa filtresi (rapor 2)
            if adx >= ADX_MAX_SIDEWAYS:
                return

            # Cooldown: son açılıştan sonra en az COOLDOWN_BARS mum bekle
            if self._last_open_bar_index is not None:
                if len(self._history_15m) - self._last_open_bar_index < COOLDOWN_BARS:
                    return

            price = float(candle["close"])
            if atr <= 0:
                return
            balance = self._engine.get_balance_usdt()
            margin_pct = self._margin_pct()
            margin = balance * margin_pct
            if margin < 10:
                return

            # Long: aşırı satım (RSI + BB %B)
            if rsi < RSI_OVERSOLD and bbp < BBP_LONG_MAX:
                sl = price - ATR_SL_MULT * atr
                tp = price + ATR_TP_MULT * atr
                if sl > 0 and tp > price:
                    self._last_open_bar_index = len(self._history_15m)
                    self._engine.open_long(
                        entry_price=price,
                        margin_usdt=margin,
                        leverage=LEVERAGE,
                        stop_loss=sl,
                        take_profit=tp,
                        opened_by=self.name,
                    )
                return
            # Short: aşırı alım (RSI + BB %B)
            if rsi > RSI_OVERBOUGHT and bbp > BBP_SHORT_MIN:
                sl = price + ATR_SL_MULT * atr
                tp = price - ATR_TP_MULT * atr
                if tp > 0 and tp < price:
                    self._last_open_bar_index = len(self._history_15m)
                    self._engine.open_short(
                        entry_price=price,
                        margin_usdt=margin,
                        leverage=LEVERAGE,
                        stop_loss=sl,
                        take_profit=tp,
                        opened_by=self.name,
                    )
        except Exception:
            pass
