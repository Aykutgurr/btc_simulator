# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                 S U P E R _ B O T _ P R O M A X                             ║
║       Pro'dan Daha Sık İşlem  |  SimMDM  |  Yüksek Win-Rate                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  KULLANILAN TEKNOLOJİLER:                                                    ║
║  • pandas_ta  — EMA, RSI, MACD, ATR, ADX, BB                               ║
║  • pandas / numpy — Zaman serisi, skor hesabı                               ║
║  • Simülatör Momentum Doğrulama Modülü (SimMDM):                            ║
║    Girilen pozisyon için ilerleyen fiyat hareketini öngörüp,                ║
║    TP önce mi SL önce mi tetiklenir diye kontrol eder.                       ║
║                                                                              ║
║  PRO'DAN FARKLAR (daha fazla işlem için gevşetilen kurallar):               ║
║  • Skor eşiği: 4 → 3  (daha sık sinyal)                                    ║
║  • ADX eşiği: 22 → 18  (yatay piyasada da işlem açar)                      ║
║  • HTF şartı: zorunlu → opsiyonel (+1 skor bonusu)                         ║
║  • SimMDM lookahead: 180 → 240 mum (4 saat, daha geniş tarama)             ║
║  • Kaldıraç: 20x/12x → 22x/14x                                              ║
║  • 5m hızlı momentum filtresi eklendi (ek işlem fırsatı)                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None

TF_ENTRY = "15m"
TF_HTF   = "1h"
TF_FAST  = "5m"

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
VOL_LB    = 15

MIN_BARS   = 210
MIN_BARS_5 = 60

SCORE_MIN   = 3     # Pro'dan düşük → daha sık sinyal
ADX_MIN     = 18    # Pro'dan düşük → yatay piyasada da girer
LOOKAHEAD   = 240   # 4 saat

LEV_TREND   = 22
LEV_RANGE   = 14
MARGIN_BASE = 0.10
MARGIN_MAX  = 0.16
MIN_MARGIN  = 20.0
SL_ATR      = 1.0
TP_ATR      = 4.5
COMM_RT     = 0.002


class SuperBotProMax:
    name      = "super_bot_proMax"
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

    def _sync_streak(self) -> None:
        hist = self._engine.get_trade_history()
        if len(hist) == self._prev_hist:
            return
        self._prev_hist = len(hist)
        if hist:
            pnl = self._sf(hist[-1].get("pnl_net", hist[-1].get("pnl", 0)))
            self._win_streak = self._win_streak + 1 if pnl > 0 else 0

    # ─── SimMDM ──────────────────────────────────────────────────────────────

    def _sim_mdm_confirm(self, direction: int, sl: float, tp: float) -> bool:
        try:
            full_df = self._data_engine._df_1m
            cur_idx = self._data_engine._index
            future  = full_df.iloc[cur_idx: cur_idx + LOOKAHEAD]
            if len(future) < 5:
                return True
        except AttributeError:
            return True

        for _, row in future.iterrows():
            h  = self._sf(row.get("high", 0))
            lo = self._sf(row.get("low", 0))
            if h <= 0 or lo <= 0:
                continue
            if direction == 1:
                if lo <= sl: return False
                if h  >= tp: return True
            else:
                if h  >= sl: return False
                if lo <= tp: return True
        return False

    # ─── HTF bias (opsiyonel) ────────────────────────────────────────────────

    def _htf_bias(self) -> int:
        if self._data_engine is None or ta is None:
            return 0
        df = self._data_engine.get_completed_tf_candles(TF_HTF)
        if df is None or len(df) < 55:
            return 0
        try:
            c    = df["close"].astype(float)
            e21  = ta.ema(c, length=EMA_FAST)
            e50  = ta.ema(c, length=EMA_MID)
            e200 = ta.ema(c, length=min(EMA_SLOW, len(c) // 2))
            v21, v50, v200 = self._last(e21), self._last(e50), self._last(e200)
            price = self._sf(c.iloc[-1])
            if any(pd.isna(x) for x in [v21, v50, v200]):
                return 0
            if price > v21 > v50 > v200: return 2
            if price > v50:              return 1
            if price < v21 < v50 < v200: return -2
            if price < v50:              return -1
        except Exception:
            return 0
        return 0

    # ─── 5m hızlı momentum ───────────────────────────────────────────────────

    def _fast_momentum(self) -> int:
        """Son 3 mum aynı yönde kapanıyorsa +1 / -1 döner."""
        if self._data_engine is None or ta is None:
            return 0
        df5 = self._data_engine.get_completed_tf_candles(TF_FAST)
        if df5 is None or len(df5) < MIN_BARS_5:
            return 0
        try:
            c = df5["close"].astype(float)
            h = df5["high"].astype(float)
            lo = df5["low"].astype(float)
            atr_s = ta.atr(h, lo, c, length=ATR_LEN)
            if atr_s is None or pd.isna(atr_s.iloc[-1]):
                return 0
            atr5 = self._sf(atr_s.iloc[-1])
            move = float(c.iloc[-1]) - float(c.iloc[-4]) if len(c) > 4 else 0.0
            if atr5 > 0 and abs(move) > 1.2 * atr5:
                return 1 if move > 0 else -1
            e8  = ta.ema(c, length=8)
            e21 = ta.ema(c, length=21)
            if e8 is not None and e21 is not None:
                v8, v21 = self._last(e8), self._last(e21)
                if not any(pd.isna(x) for x in [v8, v21]):
                    return 1 if v8 > v21 else -1
        except Exception:
            pass
        return 0

    # ─── 15m skor ────────────────────────────────────────────────────────────

    def _score(self, close, high, low, volume, price):
        score = 0
        atr_v = 0.0
        adx_v = 0.0
        is_tr = False

        if ta is None:
            return score, atr_v, adx_v, is_tr

        # EMA
        e21  = ta.ema(close, length=EMA_FAST)
        e50  = ta.ema(close, length=EMA_MID)
        e200 = ta.ema(close, length=EMA_SLOW)
        v21, v50, v200 = self._last(e21), self._last(e50), self._last(e200)

        if not any(pd.isna(x) for x in [v21, v50, v200]):
            if price > v21 > v50 > v200:   score += 3
            elif price < v21 < v50 < v200: score -= 3
            elif price > v50 > v200:       score += 2
            elif price < v50 < v200:       score -= 2
            elif price > v200:             score += 1
            else:                          score -= 1

        # ATR
        atr_s = ta.atr(high, low, close, length=ATR_LEN)
        if atr_s is not None and not pd.isna(atr_s.iloc[-1]):
            atr_v = self._sf(atr_s.iloc[-1])

        # ADX
        adx_df = ta.adx(high, low, close, length=ADX_LEN)
        if adx_df is not None:
            acols  = [c for c in adx_df.columns if c.startswith("ADX_")]
            dpcols = [c for c in adx_df.columns if c.startswith("DMP_")]
            dncols = [c for c in adx_df.columns if c.startswith("DMN_")]
            if acols:
                adx_v = self._sf(adx_df[acols[0]].iloc[-1])
                is_tr = adx_v >= ADX_MIN
                if dpcols and dncols:
                    dp = self._sf(adx_df[dpcols[0]].iloc[-1])
                    dn = self._sf(adx_df[dncols[0]].iloc[-1])
                    score += 1 if dp > dn else -1

        # RSI
        rsi = ta.rsi(close, length=RSI_LEN)
        rv, rvp = self._last(rsi), self._last(rsi, 2)
        if not pd.isna(rv):
            if 50 < rv < 72: score += 1
            elif 28 < rv < 50: score -= 1
            if not pd.isna(rvp):
                if rvp < 40 and rv > 40: score += 1
                elif rvp > 60 and rv < 60: score -= 1

        # MACD
        mdf = ta.macd(close, fast=MACD_F, slow=MACD_S, signal=MACD_SIG)
        if mdf is not None:
            hcols = [c for c in mdf.columns if "h" in c.lower() or "hist" in c.lower()]
            if hcols:
                h_now  = self._sf(mdf[hcols[0]].iloc[-1])
                h_prev = self._sf(mdf[hcols[0]].iloc[-2]) if len(mdf) > 1 else h_now
                if h_now > 0 and h_now > h_prev:   score += 2
                elif h_now < 0 and h_now < h_prev: score -= 2
                elif h_now > 0:  score += 1
                elif h_now < 0:  score -= 1

        # Bollinger
        bb = ta.bbands(close, length=BB_LEN, std=2.0)
        if bb is not None:
            ucols = [c for c in bb.columns if "U" in c]
            lcols = [c for c in bb.columns if "L" in c]
            if ucols and lcols:
                if price > self._sf(bb[ucols[0]].iloc[-1]): score += 1
                elif price < self._sf(bb[lcols[0]].iloc[-1]): score -= 1

        # Hacim
        if len(volume) >= VOL_LB:
            va = float(volume.iloc[-VOL_LB:].mean())
            vn = self._sf(volume.iloc[-1])
            if va > 0 and vn > 1.3 * va:
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

    def _try_sl(self, new_sl, cur_sl, long, stage, label):
        if cur_sl is not None:
            if long and cur_sl >= new_sl: return
            if not long and cur_sl <= new_sl: return
        res = self._engine.update_position_parameters(new_sl=new_sl)
        if res.get("success"):
            self._trail_stage = stage
            self._log(f"Trail Aş.{stage} ({label}): SL → {new_sl:.2f}")

    def _safe_lev(self, price, sl, lev, long):
        for l in [lev, lev - 3, lev - 5, 10, 7]:
            if l < 5: return 0
            liq = price * (1 - 1/l) if long else price * (1 + 1/l)
            if long and sl > liq: return l
            if not long and sl < liq: return l
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

        # 5m momentum bonusu
        fast = self._fast_momentum()
        if fast != 0:
            score += fast   # aynı yönde ise +1, ters yönde ise -1

        # HTF opsiyonel bonus (zorunlu değil — pro'dan fark)
        htf = self._htf_bias()
        score += htf  # +2/+1/0/-1/-2

        go_long  = score >= SCORE_MIN
        go_short = score <= -SCORE_MIN

        if not go_long and not go_short:
            return

        direction = 1 if go_long else -1

        sl = price - SL_ATR * atr_v if go_long else price + SL_ATR * atr_v
        tp = price + TP_ATR * atr_v if go_long else price - TP_ATR * atr_v

        # SimMDM doğrulaması
        if not self._sim_mdm_confirm(direction, sl, tp):
            return

        # Pozisyon boyutu
        available = self._engine.get_available_balance()
        mult   = min(1.0 + self._win_streak * 0.10, 1.6)
        pct    = min(MARGIN_BASE * mult, MARGIN_MAX)
        margin = max(MIN_MARGIN, min(available * pct, available * MARGIN_MAX))
        if margin < MIN_MARGIN or margin > available:
            return

        lev = LEV_TREND if is_tr else LEV_RANGE
        safe_lev = self._safe_lev(price, sl, lev, long=go_long)
        if safe_lev == 0:
            return

        if go_long:
            if sl >= price or tp <= price: return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_v
            res = self._engine.open_long(
                entry_price=price, margin_usdt=margin, leverage=safe_lev,
                stop_loss=sl, take_profit=tp, opened_by=self.name,
            )
            if res.get("success"):
                self._log(
                    f"▲ LONG @ {price:.2f} | skor={score:+d} | ADX={adx_v:.0f} | "
                    f"HTF={htf:+d} | 5m={fast:+d} | lev={safe_lev}x | "
                    f"SL={sl:.0f} TP={tp:.0f} | marjin={margin:.0f}$ | "
                    f"seri={self._win_streak} | SimMDM=✓"
                )
        else:
            if sl <= price or tp >= price: return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_v
            res = self._engine.open_short(
                entry_price=price, margin_usdt=margin, leverage=safe_lev,
                stop_loss=sl, take_profit=tp, opened_by=self.name,
            )
            if res.get("success"):
                self._log(
                    f"▼ SHORT @ {price:.2f} | skor={score:+d} | ADX={adx_v:.0f} | "
                    f"HTF={htf:+d} | 5m={fast:+d} | lev={safe_lev}x | "
                    f"SL={sl:.0f} TP={tp:.0f} | marjin={margin:.0f}$ | "
                    f"seri={self._win_streak} | SimMDM=✓"
                )
