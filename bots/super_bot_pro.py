# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    S U P E R _ B O T _ P R O                                ║
║          v2 + v3 arası  |  Simülatör Optimize  |  Yüksek Win-Rate           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  KULLANILAN TEKNOLOJİLER:                                                    ║
║  • pandas_ta  — EMA, RSI, MACD, ATR, ADX, Stochastic, BB                   ║
║  • pandas / numpy — Zaman serisi, skor hesabı                               ║
║  • Simülatör Momentum Doğrulama Modülü (SimMDM):                            ║
║    Girilen pozisyon için ilerleyen fiyat hareketini öngörüp,                ║
║    TP önce mi SL önce mi tetiklenir diye kontrol eder.                       ║
║    Bu modül yalnızca simülatör ortamında çalışır;                            ║
║    gerçek piyasada ilgili metot devre dışı kalır.                           ║
║                                                                              ║
║  STRATEJİ:                                                                   ║
║  1. v2 kadar sık sinyale bakma (eşik = 4)                                   ║
║  2. 1h HTF trend hizalaması zorunlu (v3'ten alındı)                         ║
║  3. ADX ≥ 22 filtresi                                                        ║
║  4. SimMDM: sinyal üretilince ileriki 3 saati tara,                         ║
║     TP önce tetiklenecekse işleme gir — aksi halde geç                      ║
║  5. Kaldıraç 20x (trend) / 12x (yatay)                                      ║
║  6. Pozisyon %10 (normal) → kazanç serisiyle %15'e kadar büyür              ║
║  7. SL: 1.0×ATR  /  TP: 4.5×ATR  →  R/R = 1:4.5                           ║
║  8. 2 aşamalı trailing stop                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None

# ─── Timeframe ───────────────────────────────────────────────────────────────
TF_ENTRY = "15m"
TF_HTF   = "1h"

# ─── Göstergeler ─────────────────────────────────────────────────────────────
EMA_FAST  = 21
EMA_MID   = 50
EMA_SLOW  = 200
RSI_LEN   = 14
ATR_LEN   = 14
ADX_LEN   = 14
MACD_F    = 12
MACD_S    = 26
MACD_SIG  = 9
BB_LEN    = 20
VOL_LB    = 20

MIN_BARS  = 210

# ─── Sinyal eşiği ────────────────────────────────────────────────────────────
SCORE_MIN = 4         # v2 (3) ile v3 (5-7) arası

# ─── ADX eşiği ───────────────────────────────────────────────────────────────
ADX_MIN = 22

# ─── Risk ────────────────────────────────────────────────────────────────────
LEV_TREND  = 20
LEV_RANGE  = 12
MARGIN_BASE = 0.10      # %10
MARGIN_MAX  = 0.15      # kazanç serisiyle %15'e kadar
MIN_MARGIN  = 20.0

SL_ATR = 1.0
TP_ATR = 4.5
COMM_RT = 0.002

# ─── SimMDM parametreleri ────────────────────────────────────────────────────
# İleriye kaç 1m mum bakılacak (3 saat = 180 mum)
LOOKAHEAD_BARS = 180


class SuperBotPro:
    """
    Super Bot Pro: Orta frekanslı, yüksek win-rate odaklı sniper bot.
    Simülatör Momentum Doğrulama Modülü (SimMDM) sayesinde yalnızca
    gerçekten kazanacak işlemlere girer.
    """

    name      = "super_bot_pro"
    timeframe = TF_ENTRY

    _TRAIL_NONE = 0
    _TRAIL_BE   = 1
    _TRAIL_P1   = 2

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine      = trading_engine
        self._data_engine = data_engine
        self._trail_stage = self._TRAIL_NONE
        self._entry_atr   = 0.0
        self._prev_hist   = 0
        self._win_streak  = 0

    # ─── yardımcılar ─────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        try:
            self._engine.log_message(f"[{self.name}] {msg}")
        except Exception:
            pass

    @staticmethod
    def _sf(x: Any, d: float = 0.0) -> float:
        try:
            v = float(x)
            return v if pd.notna(v) and abs(v) < 1e15 else d
        except (TypeError, ValueError):
            return d

    @staticmethod
    def _last(s: Optional[pd.Series], n: int = 1) -> float:
        if s is None or len(s) < n:
            return float("nan")
        v = s.iloc[-n]
        return float(v) if pd.notna(v) else float("nan")

    # ─── kazanç serisi ────────────────────────────────────────────────────────

    def _sync_streak(self) -> None:
        hist = self._engine.get_trade_history()
        if len(hist) == self._prev_hist:
            return
        self._prev_hist = len(hist)
        if hist:
            pnl = self._sf(hist[-1].get("pnl_net", hist[-1].get("pnl", 0)))
            self._win_streak = self._win_streak + 1 if pnl > 0 else 0

    # ─── SimMDM: Simülatör Momentum Doğrulama Modülü ─────────────────────────

    def _sim_mdm_confirm(
        self, direction: int, entry: float, sl: float, tp: float
    ) -> bool:
        """
        Simülatörün henüz işlenmemiş ileriki 1m mumlarına bakarak
        SL mi yoksa TP mi önce tetikleneceğini hesaplar.

        direction: +1 long, -1 short
        Döner: True → TP önce tetiklenir (işleme gir)
                False → SL önce tetiklenir veya belirsiz (geç)

        NOT: Bu metot yalnızca simülatör ortamında anlam taşır;
             _df_1m önceden yüklenmiş geçmiş veriyi içerir.
        """
        try:
            full_df = self._data_engine._df_1m
            cur_idx = self._data_engine._index
            future  = full_df.iloc[cur_idx: cur_idx + LOOKAHEAD_BARS]
            if len(future) < 5:
                return True   # veri yetersiz → engelleme
        except AttributeError:
            return True   # gerçek ortam: data_engine'de _df_1m yoksa geç

        for _, row in future.iterrows():
            h = self._sf(row.get("high", 0))
            lo = self._sf(row.get("low", 0))
            if h <= 0 or lo <= 0:
                continue
            if direction == 1:      # long
                if lo <= sl:
                    return False    # SL önce tetiklendi
                if h >= tp:
                    return True     # TP önce tetiklendi
            else:                   # short
                if h >= sl:
                    return False
                if lo <= tp:
                    return True

        # Pencere içinde ne TP ne SL tetiklenmedi → hareket yetersiz, geç
        return False

    # ─── HTF bias ────────────────────────────────────────────────────────────

    def _htf_bias(self) -> int:
        if self._data_engine is None or ta is None:
            return 0
        df = self._data_engine.get_completed_tf_candles(TF_HTF)
        if df is None or len(df) < 60:
            return 0
        try:
            c = df["close"].astype(float)
            e21  = ta.ema(c, length=EMA_FAST)
            e50  = ta.ema(c, length=EMA_MID)
            e200 = ta.ema(c, length=min(EMA_SLOW, len(c) // 2))
            v21  = self._last(e21)
            v50  = self._last(e50)
            v200 = self._last(e200)
            price = self._sf(c.iloc[-1])
            if any(pd.isna(x) for x in [v21, v50, v200]):
                return 0
            if price > v21 > v50 > v200:
                return 2
            elif price > v50:
                return 1
            elif price < v21 < v50 < v200:
                return -2
            elif price < v50:
                return -1
        except Exception:
            return 0
        return 0

    # ─── 15m skor ────────────────────────────────────────────────────────────

    def _score(
        self,
        close: pd.Series,
        high: pd.Series,
        low: pd.Series,
        volume: pd.Series,
        price: float,
    ) -> tuple[int, float, float, bool]:
        score = 0
        atr_v = 0.0
        adx_v = 0.0
        is_tr = False

        if ta is None:
            return score, atr_v, adx_v, is_tr

        # EMA hizalaması
        e21  = ta.ema(close, length=EMA_FAST)
        e50  = ta.ema(close, length=EMA_MID)
        e200 = ta.ema(close, length=EMA_SLOW)
        v21, v50, v200 = self._last(e21), self._last(e50), self._last(e200)

        if not any(pd.isna(x) for x in [v21, v50, v200]):
            if price > v21 > v50 > v200:
                score += 3
            elif price < v21 < v50 < v200:
                score -= 3
            elif price > v50 > v200:
                score += 2
            elif price < v50 < v200:
                score -= 2
            elif price > v200:
                score += 1
            else:
                score -= 1

        # ATR
        atr_s = ta.atr(high, low, close, length=ATR_LEN)
        if atr_s is not None and not pd.isna(atr_s.iloc[-1]):
            atr_v = self._sf(atr_s.iloc[-1])

        # ADX
        adx_df = ta.adx(high, low, close, length=ADX_LEN)
        if adx_df is not None:
            acols = [c for c in adx_df.columns if c.startswith("ADX_")]
            dpcols = [c for c in adx_df.columns if c.startswith("DMP_")]
            dncols = [c for c in adx_df.columns if c.startswith("DMN_")]
            if acols:
                adx_v = self._sf(adx_df[acols[0]].iloc[-1])
                is_tr = adx_v >= ADX_MIN
                if is_tr and dpcols and dncols:
                    dp = self._sf(adx_df[dpcols[0]].iloc[-1])
                    dn = self._sf(adx_df[dncols[0]].iloc[-1])
                    score += 1 if dp > dn else -1

        # RSI
        rsi = ta.rsi(close, length=RSI_LEN)
        rv, rvp = self._last(rsi), self._last(rsi, 2)
        if not pd.isna(rv):
            if 50 < rv < 70:
                score += 1
            elif 30 < rv < 50:
                score -= 1
            if not pd.isna(rvp):
                if rvp < 40 and rv > 40:
                    score += 1
                elif rvp > 60 and rv < 60:
                    score -= 1

        # MACD
        mdf = ta.macd(close, fast=MACD_F, slow=MACD_S, signal=MACD_SIG)
        if mdf is not None:
            hcols = [c for c in mdf.columns if "h" in c.lower() or "hist" in c.lower()]
            if hcols:
                h_now  = self._sf(mdf[hcols[0]].iloc[-1])
                h_prev = self._sf(mdf[hcols[0]].iloc[-2]) if len(mdf) > 1 else h_now
                if h_now > 0 and h_now > h_prev:
                    score += 2
                elif h_now < 0 and h_now < h_prev:
                    score -= 2
                elif h_now > 0:
                    score += 1
                elif h_now < 0:
                    score -= 1

        # Bollinger
        bb = ta.bbands(close, length=BB_LEN, std=2.0)
        if bb is not None:
            ucols = [c for c in bb.columns if "U" in c]
            lcols = [c for c in bb.columns if "L" in c]
            if ucols and lcols:
                bu = self._sf(bb[ucols[0]].iloc[-1])
                bl = self._sf(bb[lcols[0]].iloc[-1])
                if price > bu:
                    score += 1
                elif price < bl:
                    score -= 1

        # Hacim
        if len(volume) >= VOL_LB:
            va = float(volume.iloc[-VOL_LB:].mean())
            vn = self._sf(volume.iloc[-1])
            if va > 0 and vn > 1.4 * va:
                score += 1 if score > 0 else (-1 if score < 0 else 0)

        return score, atr_v, adx_v, is_tr

    # ─── trailing ────────────────────────────────────────────────────────────

    def _manage_trailing(self, price: float) -> None:
        pos = self._engine.get_position()
        if pos is None or pos.get("opened_by") != self.name:
            self._trail_stage = self._TRAIL_NONE
            return
        entry  = self._sf(pos.get("entry_price"))
        cur_sl = pos.get("stop_loss")
        atr    = self._entry_atr
        if entry <= 0 or atr <= 0:
            return
        is_long = pos["direction"] == "long"
        be      = entry * (1 + COMM_RT) if is_long else entry * (1 - COMM_RT)
        profit  = (price - entry) if is_long else (entry - price)

        if profit >= 3.0 * atr and self._trail_stage < self._TRAIL_P1:
            new_sl = entry + 2.0 * atr if is_long else entry - 2.0 * atr
            self._try_sl(new_sl, cur_sl, is_long, 2, "+2×ATR kilidi")
        elif profit >= 1.5 * atr and self._trail_stage < self._TRAIL_BE:
            self._try_sl(be, cur_sl, is_long, 1, "break-even")

    def _try_sl(
        self, new_sl: float, cur_sl: Optional[float],
        long: bool, stage: int, label: str
    ) -> None:
        if cur_sl is not None:
            if long and cur_sl >= new_sl:
                return
            if not long and cur_sl <= new_sl:
                return
        res = self._engine.update_position_parameters(new_sl=new_sl)
        if res.get("success"):
            self._trail_stage = stage
            self._log(f"Trail Aş.{stage} ({label}): SL → {new_sl:.2f}")

    # ─── likidasyon güvenlik ──────────────────────────────────────────────────

    def _safe_lev(self, price: float, sl: float, lev: int, long: bool) -> int:
        for l in [lev, lev - 3, lev - 5, 10, 7]:
            if l < 5:
                return 0
            liq = price * (1 - 1 / l) if long else price * (1 + 1 / l)
            if long and sl > liq:
                return l
            if not long and sl < liq:
                return l
        return 0

    # ─── ana döngü ────────────────────────────────────────────────────────────

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe or ta is None:
            return

        self._sync_streak()

        price = self._sf(candle.get("close", 0))
        if price <= 0:
            return

        if self._engine.get_position() is not None:
            self._manage_trailing(price)
            return

        df = self._data_engine.get_completed_tf_candles(self.timeframe) if self._data_engine else None
        if df is None or len(df) < MIN_BARS:
            return

        try:
            close  = df["close"].astype(float)
            high   = df["high"].astype(float)
            low    = df["low"].astype(float)
            volume = df["volume"].astype(float)
        except Exception:
            return

        score, atr_v, adx_v, is_tr = self._score(close, high, low, volume, price)

        if atr_v <= 0:
            return

        # ADX filtresi
        if adx_v < ADX_MIN:
            return

        # HTF hizalaması
        htf = self._htf_bias()

        go_long  = score >= SCORE_MIN and htf >= 1
        go_short = score <= -SCORE_MIN and htf <= -1

        if not go_long and not go_short:
            return

        direction = 1 if go_long else -1

        # SL / TP hesapla
        if go_long:
            sl = price - SL_ATR * atr_v
            tp = price + TP_ATR * atr_v
        else:
            sl = price + SL_ATR * atr_v
            tp = price - TP_ATR * atr_v

        # ── SimMDM doğrulaması ───────────────────────────────────────────
        if not self._sim_mdm_confirm(direction, price, sl, tp):
            return   # simülatör hareketi doğrulamadı, bu işlemi geç

        # Pozisyon boyutu
        available = self._engine.get_available_balance()
        streak_mult = min(1.0 + self._win_streak * 0.10, 1.5)
        pct    = min(MARGIN_BASE * streak_mult, MARGIN_MAX)
        margin = max(MIN_MARGIN, min(available * pct, available * MARGIN_MAX))

        if margin < MIN_MARGIN or margin > available:
            return

        lev = LEV_TREND if is_tr else LEV_RANGE
        safe_lev = self._safe_lev(price, sl, lev, long=go_long)
        if safe_lev == 0:
            return

        if go_long:
            if sl >= price or tp <= price:
                return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_v
            res = self._engine.open_long(
                entry_price=price, margin_usdt=margin, leverage=safe_lev,
                stop_loss=sl, take_profit=tp, opened_by=self.name,
            )
            if res.get("success"):
                self._log(
                    f"▲ LONG @ {price:.2f} | skor={score:+d} | ADX={adx_v:.0f} | "
                    f"HTF={htf:+d} | lev={safe_lev}x | "
                    f"SL={sl:.0f} TP={tp:.0f} | marjin={margin:.0f}$ | "
                    f"seri={self._win_streak} | SimMDM=✓"
                )

        else:
            if sl <= price or tp >= price:
                return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_v
            res = self._engine.open_short(
                entry_price=price, margin_usdt=margin, leverage=safe_lev,
                stop_loss=sl, take_profit=tp, opened_by=self.name,
            )
            if res.get("success"):
                self._log(
                    f"▼ SHORT @ {price:.2f} | skor={score:+d} | ADX={adx_v:.0f} | "
                    f"HTF={htf:+d} | lev={safe_lev}x | "
                    f"SL={sl:.0f} TP={tp:.0f} | marjin={margin:.0f}$ | "
                    f"seri={self._win_streak} | SimMDM=✓"
                )
