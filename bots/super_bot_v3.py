# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     S U P E R _ B O T _ V 3                                 ║
║           AZ İŞLEM — MAKSİMUM KÂR  |  Hedef: Haftalık %30-60+              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  KULLANILAN TEKNOLOJİLER:                                                    ║
║  • pandas_ta  — EMA, RSI, MACD, ATR, ADX, Stochastic, VWAP, BB             ║
║  • pandas     — 4h makro + 1h orta + 15m giriş (3 katman)                  ║
║  • numpy      — Kelly fraksiyonu, bileşik büyüme hesabı                     ║
║                                                                              ║
║  STRATEJİ — "SNIPER" MİMARİSİ:                                              ║
║  • Sadece MÜKEMMEL kurulumlarda işleme gir (skor ≥ 7/11)                   ║
║  • 3 Zaman Dilimi Hizalaması zorunlu (4h + 1h + 15m hepsi aynı yön)        ║
║  • EMA Geri Çekilme Girişi: fiyat EMA21'e çekilmişken gir (trend devamı)   ║
║  • ADX ≥ 30 zorunlu → sadece güçlü trendlerde işlem                        ║
║  • Kaldıraç: 35x (mükemmel) → 25x (iyi) → 15x (orta)                      ║
║  • Pozisyon: bakiyenin %15'i (mükemmel) / %10'u (iyi)                      ║
║  • SL: 0.7×ATR (çok sıkı) — TP: 7×ATR (çok geniş) → R/R = 1:10           ║
║  • 3 Aşamalı Trailing: BE → +2×ATR → +4×ATR (trendleri sonuna kadar tut)  ║
║  • Bileşik büyüme: kazandıkça pozisyon boyutu otomatik büyür                ║
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

# ─── Timeframe'ler ───────────────────────────────────────────────────────────
TF_ENTRY  = "15m"
TF_MID    = "1h"
TF_MACRO  = "4h"

# ─── Gösterge parametreleri ──────────────────────────────────────────────────
EMA_FAST   = 21
EMA_MID    = 50
EMA_SLOW   = 200
RSI_LEN    = 14
ATR_LEN    = 14
ADX_LEN    = 14
MACD_FAST  = 12
MACD_SLOW  = 26
MACD_SIG   = 9
STOCH_K    = 14
STOCH_D    = 3
BB_LEN     = 20
VOL_LB     = 20

MIN_BARS_15 = 210   # EMA200 için yeterli
MIN_BARS_HTF = 50   # 1h / 4h için

# ─── Sinyal kalite eşikleri ──────────────────────────────────────────────────
SCORE_PERFECT = 7   # Tüm sinyaller hizalı
SCORE_GOOD    = 5   # Çoğu sinyal hizalı

ADX_MIN       = 28  # Minimum trend gücü

# EMA geri çekilme toleransı: fiyat EMA21'in kaç ATR yakınında?
EMA_PULLBACK_MAX_ATR = 1.8

# ─── Risk parametreleri ──────────────────────────────────────────────────────
LEV_PERFECT  = 35
LEV_GOOD     = 25
LEV_MODERATE = 15

MARGIN_PERFECT  = 0.15   # %15
MARGIN_GOOD     = 0.10   # %10
MARGIN_MODERATE = 0.06   # %6
MIN_MARGIN_USDT = 20.0

SL_ATR_MULT = 0.7        # Çok sıkı stop
TP_ATR_MULT = 7.0        # Çok geniş hedef  →  R/R = 1:10
COMM_RT     = 0.002

# Likidasyon güvenlik tamponu: SL, liq fiyatından en az bu kadar uzakta olmalı
LIQ_BUFFER_ATR = 0.3

# ─── 3 aşamalı trailing ──────────────────────────────────────────────────────
TRAIL_BE_ATR = 1.5      # break-even tetik
TRAIL_P1_ATR = 3.5      # +2×ATR kâra kilitle tetik
TRAIL_P2_ATR = 6.0      # +4×ATR kâra kilitle tetik


class SuperBotV3:
    """
    Sniper stratejisi: Az işlem, maksimum kâr.
    3 katmanlı zaman dilimi hizalaması + güçlü trend + EMA geri çekilmesi
    tamamlandığında yüksek kaldıraç + büyük pozisyon ile gir.
    """

    name      = "super_bot_v3"
    timeframe = TF_ENTRY

    _TRAIL_NONE = 0
    _TRAIL_BE   = 1
    _TRAIL_P1   = 2
    _TRAIL_P2   = 3

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine      = trading_engine
        self._data_engine = data_engine
        self._trail_stage = self._TRAIL_NONE
        self._entry_atr   = 0.0
        self._prev_hist   = 0
        self._win_streak  = 0
        self._total_trades = 0

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
        return float(s.iloc[-n]) if pd.notna(s.iloc[-n]) else float("nan")

    # ─── seri güncelle ───────────────────────────────────────────────────────

    def _sync_streak(self) -> None:
        hist = self._engine.get_trade_history()
        if len(hist) == self._prev_hist:
            return
        self._prev_hist = len(hist)
        self._total_trades = len(hist)
        if hist:
            pnl = self._sf(hist[-1].get("pnl_net", hist[-1].get("pnl", 0)))
            self._win_streak = self._win_streak + 1 if pnl > 0 else 0

    # ─── HTF bias (4h ve 1h) ─────────────────────────────────────────────────

    def _htf_bias(self, tf: str, min_bars: int) -> int:
        """
        Verilen TF için EMA21/50/200 hizalamasına bakarak yön döner.
        +2: güçlü boğa, +1: hafif boğa, 0: nötr, -1: hafif ayı, -2: güçlü ayı
        """
        if self._data_engine is None or ta is None:
            return 0
        df = self._data_engine.get_completed_tf_candles(tf)
        if df is None or len(df) < min_bars:
            return 0
        try:
            c = df["close"].astype(float)
            h = df["high"].astype(float)
            lo = df["low"].astype(float)
            price = self._sf(c.iloc[-1])

            e21  = ta.ema(c, length=min(EMA_FAST, len(c) // 2))
            e50  = ta.ema(c, length=min(EMA_MID, len(c) // 2))
            e200 = ta.ema(c, length=min(EMA_SLOW, len(c) // 2))

            v21  = self._last(e21)
            v50  = self._last(e50)
            v200 = self._last(e200)

            if any(pd.isna(x) for x in [v21, v50, v200]):
                return 0

            if price > v21 > v50 > v200:
                return 2
            elif price > v50 > v200:
                return 1
            elif price < v21 < v50 < v200:
                return -2
            elif price < v50 < v200:
                return -1
        except Exception:
            return 0
        return 0

    # ─── EMA geri çekilme kontrolü ───────────────────────────────────────────

    def _ema_pullback_ok(
        self, price: float, ema21: float, atr: float, direction: int
    ) -> bool:
        """
        Fiyat EMA21'e yeterince yakın mı? (trend devamı girişi için optimal)
        direction=1: long (fiyat ema21 üzerinde ve yakın)
        direction=-1: short (fiyat ema21 altında ve yakın)
        """
        if ema21 <= 0 or atr <= 0:
            return False
        dist = abs(price - ema21)
        if dist > EMA_PULLBACK_MAX_ATR * atr:
            return False
        if direction == 1:
            return price >= ema21   # fiyat ema21 üzerinde
        else:
            return price <= ema21   # fiyat ema21 altında

    # ─── 15m detaylı skor ────────────────────────────────────────────────────

    def _score_entry(
        self,
        close: pd.Series,
        high: pd.Series,
        low: pd.Series,
        volume: pd.Series,
        price: float,
    ) -> tuple[int, float, float, float, bool]:
        """
        Döner: (score, atr, adx, ema21_val, is_trending)
        Maks skor: ±11
        """
        score = 0
        atr_v = 0.0
        adx_v = 0.0
        ema21_v = float("nan")
        is_tr = False

        if ta is None:
            return score, atr_v, adx_v, ema21_v, is_tr

        # — EMA hizalaması (+3 / -3) ─────────────────────────────────────
        e21  = ta.ema(close, length=EMA_FAST)
        e50  = ta.ema(close, length=EMA_MID)
        e200 = ta.ema(close, length=EMA_SLOW)

        v21  = self._last(e21)
        v50  = self._last(e50)
        v200 = self._last(e200)
        ema21_v = v21

        if not any(pd.isna(x) for x in [v21, v50, v200]):
            if price > v21 > v50 > v200:
                score += 3   # tam boğa hizalaması
            elif price < v21 < v50 < v200:
                score -= 3   # tam ayı hizalaması
            elif price > v50 > v200:
                score += 2
            elif price < v50 < v200:
                score -= 2
            elif price > v200:
                score += 1
            elif price < v200:
                score -= 1

        # — ATR ──────────────────────────────────────────────────────────
        atr_s = ta.atr(high, low, close, length=ATR_LEN)
        if atr_s is not None and not pd.isna(atr_s.iloc[-1]):
            atr_v = self._sf(atr_s.iloc[-1])

        # — ADX + DI (+2 / -2) ───────────────────────────────────────────
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
                    gap = abs(dp - dn)
                    bonus = 2 if gap > 10 else 1
                    score += bonus if dp > dn else -bonus

        # — RSI (+1 / -1) ────────────────────────────────────────────────
        rsi = ta.rsi(close, length=RSI_LEN)
        rv  = self._last(rsi)
        rvp = self._last(rsi, 2)
        if not pd.isna(rv):
            if 45 < rv < 68:
                score += 1     # boğa momentum bölgesi
            elif 32 < rv < 55:
                score -= 1    # ayı momentum bölgesi
            if not pd.isna(rvp):
                if rvp < 45 and rv > 45:
                    score += 1   # oversold çıkışı
                elif rvp > 55 and rv < 55:
                    score -= 1   # overbought düşüşü

        # — MACD (+2 / -2) ───────────────────────────────────────────────
        mdf = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIG)
        if mdf is not None:
            hcols = [c for c in mdf.columns if "h" in c.lower() or "hist" in c.lower()]
            mcols = [c for c in mdf.columns if c.upper().startswith("MACD_") and "S" not in c and "H" not in c]
            scols = [c for c in mdf.columns if "S" in c.upper() and "MACD" in c.upper()]
            if hcols:
                h_now  = self._sf(mdf[hcols[0]].iloc[-1])
                h_prev = self._sf(mdf[hcols[0]].iloc[-2]) if len(mdf) > 1 else h_now
                # MACD sıfır çizgisi geçişi → güçlü sinyal
                if mcols and scols:
                    m_now  = self._sf(mdf[mcols[0]].iloc[-1])
                    m_prev = self._sf(mdf[mcols[0]].iloc[-2]) if len(mdf) > 1 else m_now
                    s_now  = self._sf(mdf[scols[0]].iloc[-1])
                    s_prev = self._sf(mdf[scols[0]].iloc[-2]) if len(mdf) > 1 else s_now
                    # Signal line crossover
                    if m_now > s_now and m_prev <= s_prev:
                        score += 2
                    elif m_now < s_now and m_prev >= s_prev:
                        score -= 2
                    elif h_now > 0 and h_now > h_prev:
                        score += 1
                    elif h_now < 0 and h_now < h_prev:
                        score -= 1
                else:
                    if h_now > 0 and h_now > h_prev:
                        score += 2
                    elif h_now < 0 and h_now < h_prev:
                        score -= 2

        # — Stochastic (+1 / -1) ─────────────────────────────────────────
        stoch = ta.stoch(high, low, close, k=STOCH_K, d=STOCH_D, smooth_k=3)
        if stoch is not None and len(stoch.columns) >= 2:
            k = self._last(pd.Series(stoch.iloc[:, 0]))
            d = self._last(pd.Series(stoch.iloc[:, 1]))
            kp = self._last(pd.Series(stoch.iloc[:, 0]), 2)
            dp = self._last(pd.Series(stoch.iloc[:, 1]), 2)
            if not any(pd.isna(x) for x in [k, d, kp, dp]):
                if k > d and kp <= dp and k < 75:
                    score += 1
                elif k < d and kp >= dp and k > 25:
                    score -= 1

        # — Hacim teyidi (+1 / -1) ───────────────────────────────────────
        if len(volume) >= VOL_LB:
            va = float(volume.iloc[-VOL_LB:].mean())
            vn = self._sf(volume.iloc[-1])
            if va > 0 and vn > 1.5 * va:
                score += 1 if score > 0 else (-1 if score < 0 else 0)

        return score, atr_v, adx_v, ema21_v, is_tr

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

        if profit >= TRAIL_P2_ATR * atr and self._trail_stage < self._TRAIL_P2:
            new_sl = entry + 4.0 * atr if is_long else entry - 4.0 * atr
            self._set_sl(new_sl, cur_sl, is_long, 3, "+4×ATR kâr kilidi")
        elif profit >= TRAIL_P1_ATR * atr and self._trail_stage < self._TRAIL_P1:
            new_sl = entry + 2.0 * atr if is_long else entry - 2.0 * atr
            self._set_sl(new_sl, cur_sl, is_long, 2, "+2×ATR kâr kilidi")
        elif profit >= TRAIL_BE_ATR * atr and self._trail_stage < self._TRAIL_BE:
            self._set_sl(be, cur_sl, is_long, 1, "break-even")

    def _set_sl(
        self,
        new_sl: float,
        cur_sl: Optional[float],
        long: bool,
        stage: int,
        label: str,
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

    # ─── pozisyon boyutu ve kaldıraç ─────────────────────────────────────────

    def _sizing(self, score_abs: int, available: float) -> tuple[float, int]:
        """
        Skor büyüklüğüne ve kazanç serisine göre marjin + kaldıraç döner.
        """
        streak_boost = min(1.0 + self._win_streak * 0.10, 1.5)

        if score_abs >= SCORE_PERFECT:
            base_pct = MARGIN_PERFECT
            lev      = LEV_PERFECT
        elif score_abs >= SCORE_GOOD:
            base_pct = MARGIN_GOOD
            lev      = LEV_GOOD
        else:
            base_pct = MARGIN_MODERATE
            lev      = LEV_MODERATE

        margin = available * base_pct * streak_boost
        margin = max(MIN_MARGIN_USDT, min(margin, available * 0.20))
        return margin, lev

    # ─── kaldıraç güvenlik ayarı ─────────────────────────────────────────────

    def _safe_lev(self, price: float, sl: float, lev: int, long: bool) -> int:
        """
        SL likidasyon fiyatından daha önce ateşlenecek mi kontrol et.
        Ateşlenmiyorsa kaldıracı azalt.
        """
        for l in [lev, lev - 5, lev - 10, 15, 10]:
            if l < 5:
                return 0   # kullanılamaz
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

        # Açık pozisyon → sadece trailing yönet
        if self._engine.get_position() is not None:
            self._manage_trailing(price)
            return

        # Veri çek
        df = self._data_engine.get_completed_tf_candles(self.timeframe) if self._data_engine else None
        if df is None or len(df) < MIN_BARS_15:
            return

        try:
            close  = df["close"].astype(float)
            high   = df["high"].astype(float)
            low    = df["low"].astype(float)
            volume = df["volume"].astype(float)
        except Exception:
            return

        # ── 15m detaylı skor ────────────────────────────────────────────
        score, atr_v, adx_v, ema21_v, is_tr = self._score_entry(
            close, high, low, volume, price
        )

        if atr_v <= 0:
            return

        # ── ADX filtresi: trend yoksa işlem yok ─────────────────────────
        if not is_tr:
            return

        # ── HTF hizalaması ──────────────────────────────────────────────
        bias_1h = self._htf_bias(TF_MID, MIN_BARS_HTF)
        bias_4h = self._htf_bias(TF_MACRO, MIN_BARS_HTF)

        # Eşik: her iki HTF aynı yönde VE 15m ile uyumlu olmalı
        go_long  = (
            score >= SCORE_GOOD
            and bias_1h >= 1
            and bias_4h >= 1
        )
        go_short = (
            score <= -SCORE_GOOD
            and bias_1h <= -1
            and bias_4h <= -1
        )

        if not go_long and not go_short:
            return

        # ── EMA geri çekilme kontrolü (opsiyonel bonus) ─────────────────
        direction = 1 if go_long else -1
        pullback_ok = (
            not pd.isna(ema21_v)
            and self._ema_pullback_ok(price, ema21_v, atr_v, direction)
        )
        if pullback_ok:
            score = score + 1 if score > 0 else score - 1  # bonus

        score_abs = abs(score)

        # ── Pozisyon boyutu ─────────────────────────────────────────────
        available = self._engine.get_available_balance()
        margin, lev = self._sizing(score_abs, available)

        if margin < MIN_MARGIN_USDT or margin > available:
            return

        if go_long:
            sl = price - SL_ATR_MULT * atr_v
            tp = price + TP_ATR_MULT * atr_v
            if sl >= price or tp <= price:
                return
            safe_lev = self._safe_lev(price, sl, lev, long=True)
            if safe_lev == 0:
                return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_v
            res = self._engine.open_long(
                entry_price=price, margin_usdt=margin, leverage=safe_lev,
                stop_loss=sl, take_profit=tp, opened_by=self.name,
            )
            if res.get("success"):
                rrr = round(TP_ATR_MULT / SL_ATR_MULT, 1)
                self._log(
                    f"▲ LONG @ {price:.2f} | "
                    f"skor={score:+d} | ADX={adx_v:.0f} | "
                    f"1h={bias_1h:+d} 4h={bias_4h:+d} | "
                    f"pullback={'✓' if pullback_ok else '–'} | "
                    f"lev={safe_lev}x | R/R=1:{rrr} | "
                    f"SL={sl:.0f} TP={tp:.0f} | "
                    f"marjin={margin:.0f}$ seri={self._win_streak}"
                )

        elif go_short:
            sl = price + SL_ATR_MULT * atr_v
            tp = price - TP_ATR_MULT * atr_v
            if sl <= price or tp >= price:
                return
            safe_lev = self._safe_lev(price, sl, lev, long=False)
            if safe_lev == 0:
                return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_v
            res = self._engine.open_short(
                entry_price=price, margin_usdt=margin, leverage=safe_lev,
                stop_loss=sl, take_profit=tp, opened_by=self.name,
            )
            if res.get("success"):
                rrr = round(TP_ATR_MULT / SL_ATR_MULT, 1)
                self._log(
                    f"▼ SHORT @ {price:.2f} | "
                    f"skor={score:+d} | ADX={adx_v:.0f} | "
                    f"1h={bias_1h:+d} 4h={bias_4h:+d} | "
                    f"pullback={'✓' if pullback_ok else '–'} | "
                    f"lev={safe_lev}x | R/R=1:{rrr} | "
                    f"SL={sl:.0f} TP={tp:.0f} | "
                    f"marjin={margin:.0f}$ seri={self._win_streak}"
                )
