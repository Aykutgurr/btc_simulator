# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       S U P E R _ B O T _ V 2                               ║
║              Agresif Bileşik Büyüme — Hedef: Aylık %60+                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  KULLANILAN TEKNOLOJİLER:                                                    ║
║  • pandas_ta  — EMA, RSI, MACD, ATR, ADX, Stochastic, Bollinger Bands       ║
║  • pandas     — Zaman serisi, 5m & 15m çift zaman dilimi                    ║
║  • numpy      — Anti-martingale bileşik büyüme hesabı                       ║
║                                                                              ║
║  STRATEJİ:                                                                   ║
║  1. Çift Zaman Dilimi (5m hızlı sinyal + 15m trend teyidi)                  ║
║  2. Momentum Patlaması Dedektörü (son 3 mumda 2×ATR'den fazla hareket)       ║
║  3. Agresif Pozisyon Boyutu — bakiyenin %8-12'si                            ║
║  4. Anti-Martingale: Kazanan seriye göre pozisyon büyütme                   ║
║     3 ardışık kazanç → ×1.5 büyütme (max ×2.5)                              ║
║  5. Çok Düşük Giriş Eşiği (skor ≥ 3) → günde çok işlem                     ║
║  6. Sıkı SL (0.8×ATR) + Geniş TP (5×ATR) → R/R = 1:6.25                   ║
║  7. Kaldıraç: Trend=25x, Yatay=15x (engine max 100x)                        ║
║  8. 2 Aşamalı Trailing: BE + kâr kilidi                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None

# ─── Zaman dilimleri ────────────────────────────────────────────────────────
TIMEFRAME_FAST  = "5m"      # Hızlı sinyal
TIMEFRAME_SLOW  = "15m"     # Trend teyidi (ana timeframe)

# ─── Göstergeler ─────────────────────────────────────────────────────────────
EMA_FAST    = 8
EMA_MID     = 21
EMA_SLOW    = 55
RSI_LEN     = 9        # Daha hassas RSI
ATR_LEN     = 10
ADX_LEN     = 10
MACD_FAST   = 8
MACD_SLOW   = 17
MACD_SIG    = 9
BB_LEN      = 14
BB_STD      = 1.8
VOL_LB      = 10

MIN_BARS_FAST = 80     # 5m için minimum mum
MIN_BARS_SLOW = 80     # 15m için minimum mum

# ─── Sinyal eşiği ────────────────────────────────────────────────────────────
SCORE_MIN = 3          # Çok düşük eşik = çok daha fazla işlem

# ─── Risk & Kaldıraç ─────────────────────────────────────────────────────────
LEVERAGE_TREND   = 25
LEVERAGE_RANGE   = 15
ADX_TREND_THRESH = 20   # Daha düşük eşik → trend daha sık algılanır

# Temel pozisyon boyutu
MARGIN_BASE  = 0.08     # Bakiyenin %8'i
MARGIN_BOOST = 0.12     # Anti-martingale ile %12'ye çıkabilir
MIN_MARGIN   = 20.0

# SL / TP
SL_ATR = 0.8            # Sıkı stop (kısa sürede max zarar minimize)
TP_ATR = 5.0            # Geniş take-profit
COMM_RT = 0.002

# ─── Anti-martingale ─────────────────────────────────────────────────────────
STREAK_BOOST_AT  = 3    # Kaç ardışık kazançtan sonra büyüt
STREAK_MAX_MULT  = 2.5  # Maksimum çarpan

# ─── Trailing ────────────────────────────────────────────────────────────────
TRAIL_BE_ATR  = 1.2     # Break-even tetik
TRAIL_P1_ATR  = 2.5     # +1.5×ATR kâr kilidi tetik


class SuperBotV2:
    """
    Super Bot V2 — Agresif kaldıraç, anti-martingale bileşik büyüme,
    çift zaman dilimi momentum stratejisi. Hedef aylık ≥%60.
    """

    name      = "super_bot_v2"
    timeframe = TIMEFRAME_SLOW   # Ana tetikleyici 15m (5m teyid için)

    _TRAIL_NONE = 0
    _TRAIL_BE   = 1
    _TRAIL_P1   = 2

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine      = trading_engine
        self._data_engine = data_engine

        # Seri takip
        self._win_streak   = 0
        self._last_pnl     = 0.0
        self._trade_count  = 0

        # Trailing
        self._trail_stage  = self._TRAIL_NONE
        self._entry_atr    = 0.0

        # Önceki işlem sayısı (güncelleme takibi)
        self._prev_hist_len = 0

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

    # ─── anti-martingale pozisyon boyutu ─────────────────────────────────────

    def _margin(self, available: float) -> float:
        mult = min(1.0 + (self._win_streak // STREAK_BOOST_AT) * 0.5, STREAK_MAX_MULT)
        pct  = min(MARGIN_BASE * mult, MARGIN_BOOST)
        return max(MIN_MARGIN, min(available * pct, available * 0.20))

    # ─── kazanç serisi güncelle ───────────────────────────────────────────────

    def _update_streak(self) -> None:
        hist = self._engine.get_trade_history()
        if len(hist) == self._prev_hist_len:
            return
        self._prev_hist_len = len(hist)
        if not hist:
            return
        last = hist[-1]
        pnl  = self._sf(last.get("pnl_net", last.get("pnl", 0)))
        if pnl > 0:
            self._win_streak  += 1
        else:
            self._win_streak   = 0
        self._trade_count = len(hist)

    # ─── 5m sinyal hesapla ───────────────────────────────────────────────────

    def _fast_signal(self) -> int:
        """
        5m verisinden hızlı momentum skoru döner.
        +1 yukarı baskı, -1 aşağı baskı, 0 belirsiz.
        """
        if self._data_engine is None or ta is None:
            return 0
        df5 = self._data_engine.get_completed_tf_candles(TIMEFRAME_FAST)
        if df5 is None or len(df5) < MIN_BARS_FAST:
            return 0
        try:
            c = df5["close"].astype(float)
            h = df5["high"].astype(float)
            lo = df5["low"].astype(float)

            # Momentum patlaması: son 3 mumda toplam hareket > 1.5×ATR
            atr_s = ta.atr(h, lo, c, length=ATR_LEN)
            if atr_s is None or pd.isna(atr_s.iloc[-1]):
                return 0
            atr_v = self._sf(atr_s.iloc[-1])
            move3 = abs(float(c.iloc[-1]) - float(c.iloc[-4])) if len(c) > 4 else 0.0
            direction = 1 if float(c.iloc[-1]) > float(c.iloc[-4]) else -1
            if atr_v > 0 and move3 > 1.5 * atr_v:
                return direction   # momentum patlaması

            # EMA 8 vs 21
            e8  = ta.ema(c, length=EMA_FAST)
            e21 = ta.ema(c, length=EMA_MID)
            if e8 is not None and e21 is not None:
                if not pd.isna(e8.iloc[-1]) and not pd.isna(e21.iloc[-1]):
                    if self._sf(e8.iloc[-1]) > self._sf(e21.iloc[-1]):
                        return 1
                    elif self._sf(e8.iloc[-1]) < self._sf(e21.iloc[-1]):
                        return -1
        except Exception:
            pass
        return 0

    # ─── 15m ana skor ────────────────────────────────────────────────────────

    def _score_15m(
        self,
        close: pd.Series,
        high: pd.Series,
        low: pd.Series,
        volume: pd.Series,
        price: float,
    ) -> tuple[int, float, bool]:
        """
        Döner: (score, atr, is_trending)
        """
        score = 0
        atr_v = 0.0
        is_tr = False

        if ta is None:
            return score, atr_v, is_tr

        def _l(s: Optional[pd.Series], n: int = 1) -> float:
            if s is None or len(s) < n:
                return float("nan")
            return self._sf(s.iloc[-n])

        # — EMA hizalaması ————————————————————————————————————————————
        e8  = ta.ema(close, length=EMA_FAST)
        e21 = ta.ema(close, length=EMA_MID)
        e55 = ta.ema(close, length=EMA_SLOW)

        v8, v21, v55 = _l(e8), _l(e21), _l(e55)
        if not any(pd.isna(x) for x in [v8, v21, v55]):
            if price > v8 > v21 > v55:
                score += 2
            elif price < v8 < v21 < v55:
                score -= 2
            elif price > v55:
                score += 1
            elif price < v55:
                score -= 1

        # — RSI ─────────────────────────────────────────────────────────
        rsi = ta.rsi(close, length=RSI_LEN)
        rv, rvp = _l(rsi), _l(rsi, 2)
        if not pd.isna(rv):
            if 50 < rv < 75:
                score += 1
            elif 25 < rv < 50:
                score -= 1
            if not pd.isna(rvp):
                if rvp < 40 and rv > rvp:
                    score += 1     # oversold dönüşü
                elif rvp > 60 and rv < rvp:
                    score -= 1    # overbought dönüşü

        # — MACD ────────────────────────────────────────────────────────
        mdf = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIG)
        if mdf is not None:
            hcols = [c for c in mdf.columns if "h" in c.lower() or "hist" in c.lower()]
            if hcols:
                h_now  = self._sf(mdf[hcols[0]].iloc[-1])
                h_prev = self._sf(mdf[hcols[0]].iloc[-2]) if len(mdf) > 1 else h_now
                if h_now > 0:
                    score += 2 if h_now > h_prev else 1
                elif h_now < 0:
                    score -= 2 if h_now < h_prev else 1

        # — ATR & ADX ───────────────────────────────────────────────────
        atr_s = ta.atr(high, low, close, length=ATR_LEN)
        if atr_s is not None and not pd.isna(atr_s.iloc[-1]):
            atr_v = self._sf(atr_s.iloc[-1])

        adx_df = ta.adx(high, low, close, length=ADX_LEN)
        if adx_df is not None:
            acols  = [c for c in adx_df.columns if c.startswith("ADX_")]
            dpcols = [c for c in adx_df.columns if c.startswith("DMP_")]
            dncols = [c for c in adx_df.columns if c.startswith("DMN_")]
            if acols:
                adx_v = self._sf(adx_df[acols[0]].iloc[-1])
                is_tr = adx_v >= ADX_TREND_THRESH
                if is_tr and dpcols and dncols:
                    dp = self._sf(adx_df[dpcols[0]].iloc[-1])
                    dn = self._sf(adx_df[dncols[0]].iloc[-1])
                    score += 1 if dp > dn else -1

        # — Bollinger ───────────────────────────────────────────────────
        bb = ta.bbands(close, length=BB_LEN, std=BB_STD)
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

        # — Hacim ───────────────────────────────────────────────────────
        if len(volume) >= VOL_LB:
            va = float(volume.iloc[-VOL_LB:].mean())
            vn = self._sf(volume.iloc[-1])
            if va > 0 and vn > 1.3 * va:
                score += 1 if score >= 0 else -1

        return score, atr_v, is_tr

    # ─── trailing yönetimi ────────────────────────────────────────────────────

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
        be = entry * (1 + COMM_RT) if is_long else entry * (1 - COMM_RT)

        profit = (price - entry) if is_long else (entry - price)

        # Aşama 2: +1.5×ATR kâra kilitle
        if profit >= TRAIL_P1_ATR * atr and self._trail_stage < self._TRAIL_P1:
            new_sl = entry + 1.5 * atr if is_long else entry - 1.5 * atr
            self._try_sl(new_sl, cur_sl, is_long, stage=2)
            return

        # Aşama 1: break-even
        if profit >= TRAIL_BE_ATR * atr and self._trail_stage < self._TRAIL_BE:
            self._try_sl(be, cur_sl, is_long, stage=1)

    def _try_sl(self, new_sl: float, cur_sl: Optional[float], long: bool, stage: int) -> None:
        if cur_sl is not None:
            if long and cur_sl >= new_sl:
                return
            if not long and cur_sl <= new_sl:
                return
        res = self._engine.update_position_parameters(new_sl=new_sl)
        if res.get("success"):
            self._trail_stage = stage
            lbl = {1: "break-even", 2: "+1.5×ATR kâr"}[stage]
            self._log(f"Trail Aşama {stage} ({lbl}): SL → {new_sl:.2f}")

    # ─── ana döngü ────────────────────────────────────────────────────────────

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe or ta is None:
            return

        self._update_streak()

        price = self._sf(candle.get("close", 0))
        if price <= 0:
            return

        # Açık pozisyon → trailing yönet
        if self._engine.get_position() is not None:
            self._manage_trailing(price)
            return

        # Veri çek
        df = self._data_engine.get_completed_tf_candles(self.timeframe) if self._data_engine else None
        if df is None or len(df) < MIN_BARS_SLOW:
            return

        try:
            close  = df["close"].astype(float)
            high   = df["high"].astype(float)
            low    = df["low"].astype(float)
            volume = df["volume"].astype(float)
        except Exception:
            return

        # 15m skor
        score, atr_v, is_tr = self._score_15m(close, high, low, volume, price)
        if atr_v <= 0:
            return

        # 5m hızlı teyid
        fast_sig = self._fast_signal()

        # Eşik kontrolü — 5m teyidi yoksa 1 puan daha gerekli
        required = SCORE_MIN if fast_sig != 0 else SCORE_MIN + 1

        go_long  = score >= required and (fast_sig >= 0)
        go_short = score <= -required and (fast_sig <= 0)

        if not go_long and not go_short:
            return

        # Pozisyon boyutu
        avail  = self._engine.get_available_balance()
        margin = self._margin(avail)
        if margin < MIN_MARGIN or margin > avail:
            return

        lev = LEVERAGE_TREND if is_tr else LEVERAGE_RANGE

        # Likidasyon güvenlik kontrolü: SL likidasyon fiyatından daha önce olmalı
        # Long liq = entry * (1 - 1/lev), SL = entry - 0.8*atr
        # Emin olmak için: SL > liq_price + 0.1*atr
        liq_long  = price * (1.0 - 1.0 / lev)
        liq_short = price * (1.0 + 1.0 / lev)

        if go_long:
            sl = price - SL_ATR * atr_v
            tp = price + TP_ATR * atr_v
            if sl <= liq_long or sl >= price or tp <= price:
                # SL likidasyon seviyesine çok yakın → kaldıracı azalt
                lev = 10
                liq_long = price * (1.0 - 1.0 / lev)
                sl = price - SL_ATR * atr_v
                if sl <= liq_long:
                    return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_v
            res = self._engine.open_long(
                entry_price=price, margin_usdt=margin, leverage=lev,
                stop_loss=sl, take_profit=tp, opened_by=self.name,
            )
            if res.get("success"):
                self._log(
                    f"LONG @ {price:.2f} | skor={score:+d} | 5m={fast_sig:+d} | "
                    f"lev={lev}x | SL={sl:.2f} TP={tp:.2f} | "
                    f"marjin={margin:.1f}$ | seri={self._win_streak}"
                )

        elif go_short:
            sl = price + SL_ATR * atr_v
            tp = price - TP_ATR * atr_v
            if sl >= liq_short or sl <= price or tp >= price:
                lev = 10
                liq_short = price * (1.0 + 1.0 / lev)
                sl = price + SL_ATR * atr_v
                if sl >= liq_short:
                    return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_v
            res = self._engine.open_short(
                entry_price=price, margin_usdt=margin, leverage=lev,
                stop_loss=sl, take_profit=tp, opened_by=self.name,
            )
            if res.get("success"):
                self._log(
                    f"SHORT @ {price:.2f} | skor={score:+d} | 5m={fast_sig:+d} | "
                    f"lev={lev}x | SL={sl:.2f} TP={tp:.2f} | "
                    f"marjin={margin:.1f}$ | seri={self._win_streak}"
                )
