# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          S U P E R _ B O T                                  ║
║                   Yüksek Getiri Odaklı Çok-Katmanlı Bot                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  KULLANILAN TEKNOLOJİLER:                                                    ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  • pandas_ta  — 10+ teknik gösterge (EMA, RSI, MACD, BB, ATR, ADX,          ║
║                 Stochastic, VWAP proxy)                                      ║
║  • pandas     — Zaman serisi veri işleme                                     ║
║  • numpy      — Vektörel hesaplamalar, Kelly formülü                         ║
║                                                                              ║
║  STRATEJI MİMARİSİ:                                                          ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  1. Piyasa Rejimi Tespiti  — ADX ile trend / yatay ayrımı                   ║
║  2. Çok Zaman Dilimi Analiz — 1s makro trend (EMA200) + 15d giriş           ║
║  3. Ağırlıklı Skor Sistemi  — 10 sinyal, eşik ≥ +5 long / ≤ −5 short       ║
║     Sinyaller:                                                                ║
║       • EMA 21/50/200 hizalaması ve crossover (+2/−2)                        ║
║       • RSI(14) momentum + aşırı bölge filtresi (+1/−1)                     ║
║       • MACD histogram yönü + sıfır çizgisi geçişi (+2/−2)                  ║
║       • Bollinger Band kırılımı (+1/−1)                                      ║
║       • ADX trend gücü filtresi (≥25 bonus: +1/−1)                           ║
║       • Stochastic %K/%D çaprazlaması (+1/−1)                               ║
║       • Hacim oranı konfirmasyonu (+1/−1)                                    ║
║       • HTF (1s) EMA200 üzeri/altı (+1/−1)                                  ║
║       • Fair Value Gap (dengesizlik) tespiti (+1/−1)                         ║
║  4. Dinamik Pozisyon Boyutu — Kelly Kriteri ilhamı + balance guard           ║
║  5. 3 Aşamalı Trailing Stop — kademeli kâr kilitleme                        ║
║     Aşama 1 (1.5×ATR): SL → break-even                                      ║
║     Aşama 2 (3.0×ATR): SL → +1.5×ATR (kâr kilidi)                          ║
║     Aşama 3 (5.0×ATR): SL → +3.0×ATR (büyük trend kilidi)                  ║
║  6. Devre Kesici — bakiye %15 düşerse bot duraklar                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from trading_engine import TradingEngine
    from data_engine import DataEngine

try:
    import pandas_ta as ta
except ImportError:
    ta = None

# ─── Zaman dilimleri ────────────────────────────────────────────────────────
TIMEFRAME = "15m"          # Giriş zaman dilimi
HTF = "1h"                 # Makro trend zaman dilimi

# ─── Gösterge parametreleri ─────────────────────────────────────────────────
EMA_FAST   = 21
EMA_MID    = 50
EMA_SLOW   = 200
RSI_LEN    = 14
MACD_FAST  = 12
MACD_SLOW  = 26
MACD_SIG   = 9
BB_LEN     = 20
BB_STD     = 2.0
ATR_LEN    = 14
ADX_LEN    = 14
STOCH_K    = 14
STOCH_D    = 3
STOCH_SMO  = 3
VOL_LB     = 20            # Hacim karşılaştırma penceresi
FVG_LB     = 3             # FVG tespiti için geri bakış mumu sayısı

MIN_BARS   = 250           # Göstergeler için minimum mum sayısı (EMA200 + tampon)
HTF_MIN    = 60            # HTF analiz için minimum 1s mum sayısı

# ─── Risk parametreleri ──────────────────────────────────────────────────────
LEVERAGE_TREND   = 10      # Trend rejiminde kaldıraç
LEVERAGE_RANGE   = 7       # Yatay piyasada kaldıraç
MARGIN_BASE      = 0.03    # Bakiyenin %3'ü baz marjin
MARGIN_MAX       = 0.06    # Kelly skor ile maks %6'ya çıkabilir
MIN_MARGIN_USDT  = 15.0

SL_ATR_MULT      = 1.2     # Stop-loss mesafesi (ATR katı) — sıkı
TP_ATR_MULT      = 5.0     # Take-profit mesafesi (ATR katı) — geniş

# 3 aşamalı trailing tetik noktaları
TRAIL1_ATR = 1.5           # Aşama 1: break-even'a çek
TRAIL2_ATR = 3.0           # Aşama 2: +1.5×ATR kâra çek
TRAIL3_ATR = 5.0           # Aşama 3: +3.0×ATR kâra kilitle

# Sinyal eşiği
LONG_SCORE_MIN  = 5        # Toplam ≥ +5 → long gir
SHORT_SCORE_MIN = 5        # Toplam ≤ −5 → short gir

# ADX trend eşiği
ADX_TREND_THRESH = 25.0

# Hacim oranı eşiği
VOL_RATIO_MIN = 1.20       # Mevcut mum hacmi, ortalamadan %20 fazla olmalı

# RSI filtreleri (giriş yönünde aşırı bölgeye girilmemesi)
RSI_LONG_MAX  = 72         # Long için RSI bu değerin altında olmalı
RSI_SHORT_MIN = 28         # Short için RSI bu değerin üstünde olmalı

# Komisyon
COMM_RATE_RT = 0.002       # round-trip %0.2

# Devre kesici
CIRCUIT_BREAKER_DROP = 0.15   # Başlangıç bakiyesinden %15 düşüşte dur


class SuperBot:
    """
    Super Bot — Puan tabanlı çok-faktörlü, 3 aşamalı trailing-stop,
    dinamik pozisyon boyutu ve devre-kesici özellikli yüksek-getiri botu.
    """

    name  = "super_bot"
    timeframe = TIMEFRAME

    # Trailing aşama takibi
    _TRAIL_NONE  = 0
    _TRAIL_BE    = 1   # break-even'a çekildi
    _TRAIL_P1    = 2   # +1.5×ATR'ye çekildi
    _TRAIL_P2    = 3   # +3.0×ATR'ye çekildi

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine      = trading_engine
        self._data_engine = data_engine
        self._trail_stage = self._TRAIL_NONE
        self._entry_atr   = 0.0
        self._initial_bal = None   # İlk çalışmada set edilir
        self._paused      = False
        self._trade_count = 0
        self._wins        = 0

    # ──────────────────────────── helpers ────────────────────────────────────

    def _log(self, msg: str) -> None:
        try:
            self._engine.log_message(f"[{self.name}] {msg}")
        except Exception:
            pass

    @staticmethod
    def _sf(x: Any, default: float = 0.0) -> float:
        try:
            v = float(x)
            return v if pd.notna(v) and abs(v) < 1e15 else default
        except (TypeError, ValueError):
            return default

    def _kelly_margin(self, base: float, available: float) -> float:
        """
        Win-rate geçmişine göre Kelly fraksiyonu ile marjini büyüt.
        Yeterli işlem yoksa base ile devam et.
        """
        if self._trade_count < 10:
            pct = MARGIN_BASE
        else:
            wr = self._wins / max(self._trade_count, 1)
            rr = TP_ATR_MULT / SL_ATR_MULT  # ödül/risk oranı
            kelly = wr - (1 - wr) / rr
            kelly = max(MARGIN_BASE, min(kelly, MARGIN_MAX))
            pct = kelly
        margin = available * pct
        return max(MIN_MARGIN_USDT, min(margin, available * MARGIN_MAX))

    # ──────────────────────────── devre kesici ───────────────────────────────

    def _check_circuit_breaker(self) -> bool:
        """
        Bakiye başlangıçtan %15 düştüyse True döner (işlem yapmayı durdur).
        """
        if self._initial_bal is None:
            return False
        current = self._engine.get_balance_usdt()
        if current < self._initial_bal * (1 - CIRCUIT_BREAKER_DROP):
            if not self._paused:
                self._paused = True
                self._log(
                    f"DEVRE KESİCİ: Bakiye {current:.2f} USDT — "
                    f"başlangıcın %{(1-current/self._initial_bal)*100:.1f} altında. "
                    "Bot duraklatıldı."
                )
            return True
        if self._paused:
            # Toparlandıysa devam et
            if current >= self._initial_bal * (1 - CIRCUIT_BREAKER_DROP * 0.5):
                self._paused = False
                self._log("Devre kesici sıfırlandı, bot yeniden aktif.")
        return self._paused

    # ──────────────────────── HTF trend analizi ───────────────────────────────

    def _htf_bias(self) -> int:
        """
        1s verisine bakarak makro trendi döner:  +1 boğa, −1 ayı, 0 nötr.
        """
        if self._data_engine is None or ta is None:
            return 0
        df_1m = self._data_engine.get_all_1m_for_indicators()
        if df_1m is None or len(df_1m) < HTF_MIN * 60:
            return 0
        try:
            # 1m verisini 1s'ye resample et
            df = df_1m[["open", "high", "low", "close", "volume"]].copy()
            df.index = pd.to_datetime(df.index)
            df_h = df.resample("1h").agg(
                {"open": "first", "high": "max", "low": "min",
                 "close": "last", "volume": "sum"}
            ).dropna()
            if len(df_h) < HTF_MIN:
                return 0
            close_h = df_h["close"].astype(float)
            ema200h = ta.ema(close_h, length=min(200, len(close_h) // 2))
            if ema200h is None or pd.isna(ema200h.iloc[-1]):
                return 0
            price_h = self._sf(close_h.iloc[-1])
            ema200_val = self._sf(ema200h.iloc[-1])
            if price_h > ema200_val * 1.002:
                return 1
            if price_h < ema200_val * 0.998:
                return -1
        except Exception:
            return 0
        return 0

    # ─────────────────────── Fair Value Gap tespiti ──────────────────────────

    @staticmethod
    def _detect_fvg(high: pd.Series, low: pd.Series, direction: int) -> bool:
        """
        Son FVG_LB mumda belirli yönde dengesizlik (FVG) var mı?
        Boğa FVG: mum[i-2].high < mum[i].low  (iki mum arası boşluk)
        Ayı FVG:  mum[i-2].low  > mum[i].high
        """
        if len(high) < FVG_LB + 1:
            return False
        for i in range(len(high) - FVG_LB, len(high)):
            if direction == 1 and high.iloc[i - 2] < low.iloc[i]:
                return True
            if direction == -1 and low.iloc[i - 2] > high.iloc[i]:
                return True
        return False

    # ────────────────────────── sinyal motoru ────────────────────────────────

    def _compute_score(
        self,
        close: pd.Series,
        high: pd.Series,
        low: pd.Series,
        volume: pd.Series,
        price: float,
    ) -> tuple[int, float, float, bool]:
        """
        Ağırlıklı sinyal skoru hesaplar.
        Döner: (score, atr, adx, is_trending)
        """
        score = 0
        atr_val = 0.0
        adx_val = 0.0
        is_trending = False

        if ta is None:
            return score, atr_val, adx_val, is_trending

        # — EMA hesapla ——————————————————————————————————————————————————
        ema21  = ta.ema(close, length=EMA_FAST)
        ema50  = ta.ema(close, length=EMA_MID)
        ema200 = ta.ema(close, length=EMA_SLOW)

        def last(s: Optional[pd.Series], n: int = 1) -> float:
            if s is None or len(s) < n:
                return float("nan")
            return self._sf(s.iloc[-n])

        e21  = last(ema21)
        e50  = last(ema50)
        e200 = last(ema200)
        e21p = last(ema21, 2)
        e50p = last(ema50, 2)

        if not (pd.isna(e21) or pd.isna(e50) or pd.isna(e200)):
            # Tam hizalama: fiyat > EMA21 > EMA50 > EMA200 → +2
            if price > e21 > e50 > e200:
                score += 2
            elif price < e21 < e50 < e200:
                score -= 2
            elif price > e200:
                score += 1
            elif price < e200:
                score -= 1

            # EMA21/50 crossover
            if e21 > e50 and e21p <= e50p:
                score += 1
            elif e21 < e50 and e21p >= e50p:
                score -= 1

        # — RSI ──────────────────────────────────────────────────────────
        rsi = ta.rsi(close, length=RSI_LEN)
        rsi_val  = last(rsi)
        rsi_prev = last(rsi, 2)
        if not pd.isna(rsi_val):
            if rsi_val > 50 and rsi_val < RSI_LONG_MAX:
                score += 1
            elif rsi_val < 50 and rsi_val > RSI_SHORT_MIN:
                score -= 1
            # Aşırı bölgeden dönüş (oversold→up / overbought→down)
            if not pd.isna(rsi_prev):
                if rsi_prev < 35 and rsi_val > rsi_prev:
                    score += 1
                elif rsi_prev > 65 and rsi_val < rsi_prev:
                    score -= 1

        # — MACD ─────────────────────────────────────────────────────────
        macd_df = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIG)
        if macd_df is not None and len(macd_df.columns) >= 3:
            hist_col = [c for c in macd_df.columns if "h" in c.lower() or "hist" in c.lower()]
            macd_col = [c for c in macd_df.columns if c.upper().startswith("MACD_")]
            if hist_col:
                hist     = self._sf(macd_df[hist_col[0]].iloc[-1])
                hist_p   = self._sf(macd_df[hist_col[0]].iloc[-2]) if len(macd_df) > 1 else hist
                if hist > 0 and hist > hist_p:
                    score += 2    # yükselen pozitif histogram
                elif hist < 0 and hist < hist_p:
                    score -= 2    # düşen negatif histogram
                elif hist > 0:
                    score += 1
                elif hist < 0:
                    score -= 1

        # — Bollinger Bands ───────────────────────────────────────────────
        bb = ta.bbands(close, length=BB_LEN, std=BB_STD)
        if bb is not None:
            bb_cols = list(bb.columns)
            upper_cols = [c for c in bb_cols if "U" in c]
            lower_cols = [c for c in bb_cols if "L" in c]
            mid_cols   = [c for c in bb_cols if "M" in c]
            if upper_cols and lower_cols and mid_cols:
                bb_upper = self._sf(bb[upper_cols[0]].iloc[-1])
                bb_lower = self._sf(bb[lower_cols[0]].iloc[-1])
                bb_mid   = self._sf(bb[mid_cols[0]].iloc[-1])
                if bb_upper > bb_lower and bb_mid > 0:
                    if price > bb_upper:
                        score += 1   # üst bant kırılımı → momentum
                    elif price < bb_lower:
                        score -= 1   # alt bant kırılımı

        # — ATR ──────────────────────────────────────────────────────────
        atr_s = ta.atr(high, low, close, length=ATR_LEN)
        if atr_s is not None and not pd.isna(atr_s.iloc[-1]):
            atr_val = self._sf(atr_s.iloc[-1])

        # — ADX (trend gücü) ──────────────────────────────────────────────
        adx_df = ta.adx(high, low, close, length=ADX_LEN)
        if adx_df is not None:
            adx_cols = [c for c in adx_df.columns if c.startswith("ADX_")]
            dmp_cols = [c for c in adx_df.columns if c.startswith("DMP_")]
            dmn_cols = [c for c in adx_df.columns if c.startswith("DMN_")]
            if adx_cols:
                adx_val = self._sf(adx_df[adx_cols[0]].iloc[-1])
                is_trending = adx_val >= ADX_TREND_THRESH
                if is_trending:
                    # ADX trend bonus: yönü DI+ / DI− ile belirle
                    if dmp_cols and dmn_cols:
                        dmp = self._sf(adx_df[dmp_cols[0]].iloc[-1])
                        dmn = self._sf(adx_df[dmn_cols[0]].iloc[-1])
                        if dmp > dmn:
                            score += 1
                        elif dmn > dmp:
                            score -= 1

        # — Stochastic ────────────────────────────────────────────────────
        stoch = ta.stoch(high, low, close, k=STOCH_K, d=STOCH_D, smooth_k=STOCH_SMO)
        if stoch is not None and len(stoch.columns) >= 2:
            k_col = stoch.columns[0]
            d_col = stoch.columns[1]
            k_now  = self._sf(stoch[k_col].iloc[-1])
            d_now  = self._sf(stoch[d_col].iloc[-1])
            k_prev = self._sf(stoch[k_col].iloc[-2]) if len(stoch) > 1 else k_now
            d_prev = self._sf(stoch[d_col].iloc[-2]) if len(stoch) > 1 else d_now
            if k_now > d_now and k_prev <= d_prev and k_now < 80:
                score += 1
            elif k_now < d_now and k_prev >= d_prev and k_now > 20:
                score -= 1

        # — Hacim onayı ────────────────────────────────────────────────────
        if len(volume) >= VOL_LB:
            vol_avg = float(volume.iloc[-VOL_LB:].mean())
            vol_now = self._sf(volume.iloc[-1])
            if vol_avg > 0:
                ratio = vol_now / vol_avg
                if ratio >= VOL_RATIO_MIN:
                    score += 1 if score > 0 else -1  # yön mevcut skora uyar

        # — HTF bias ──────────────────────────────────────────────────────
        htf = self._htf_bias()
        score += htf  # +1 / 0 / −1

        # — Fair Value Gap ─────────────────────────────────────────────────
        direction_hint = 1 if score > 0 else -1
        if self._detect_fvg(high, low, direction_hint):
            score += direction_hint  # +1 or −1

        return score, atr_val, adx_val, is_trending

    # ─────────────────────── trailing stop yönetimi ──────────────────────────

    def _manage_trailing(self, price: float) -> None:
        pos = self._engine.get_position()
        if pos is None or pos.get("opened_by") != self.name:
            self._trail_stage = self._TRAIL_NONE
            return

        entry   = self._sf(pos.get("entry_price"))
        cur_sl  = pos.get("stop_loss")
        atr     = self._entry_atr
        if entry <= 0 or atr <= 0:
            return

        is_long = pos["direction"] == "long"
        be_long  = entry * (1 + COMM_RATE_RT)
        be_short = entry * (1 - COMM_RATE_RT)

        def dist(mult: float) -> float:
            return mult * atr

        stage = self._trail_stage

        if is_long:
            profit_dist = price - entry
            if profit_dist >= dist(TRAIL3_ATR) and stage < self._TRAIL_P2:
                new_sl = entry + dist(3.0)
                self._update_sl(new_sl, cur_sl, long=True, stage=3)
                return
            if profit_dist >= dist(TRAIL2_ATR) and stage < self._TRAIL_P1:
                new_sl = entry + dist(1.5)
                self._update_sl(new_sl, cur_sl, long=True, stage=2)
                return
            if profit_dist >= dist(TRAIL1_ATR) and stage < self._TRAIL_BE:
                self._update_sl(be_long, cur_sl, long=True, stage=1)
        else:
            profit_dist = entry - price
            if profit_dist >= dist(TRAIL3_ATR) and stage < self._TRAIL_P2:
                new_sl = entry - dist(3.0)
                self._update_sl(new_sl, cur_sl, long=False, stage=3)
                return
            if profit_dist >= dist(TRAIL2_ATR) and stage < self._TRAIL_P1:
                new_sl = entry - dist(1.5)
                self._update_sl(new_sl, cur_sl, long=False, stage=2)
                return
            if profit_dist >= dist(TRAIL1_ATR) and stage < self._TRAIL_BE:
                self._update_sl(be_short, cur_sl, long=False, stage=1)

    def _update_sl(
        self, new_sl: float, cur_sl: Optional[float], long: bool, stage: int
    ) -> None:
        # Daha iyi bir stop zaten varsa dokunma
        if cur_sl is not None:
            if long and cur_sl >= new_sl:
                return
            if not long and cur_sl <= new_sl:
                return
        res = self._engine.update_position_parameters(new_sl=new_sl)
        if res.get("success"):
            labels = {1: "break-even", 2: "+1.5×ATR kâr", 3: "+3.0×ATR kâr"}
            self._trail_stage = stage
            self._log(
                f"Trailing Aşama {stage} ({labels[stage]}): SL → {new_sl:.2f}"
            )

    # ──────────────────────── istatistik güncelle ────────────────────────────

    def _update_stats_from_history(self) -> None:
        history = self._engine.get_trade_history()
        self._trade_count = len(history)
        self._wins = sum(
            1 for t in history if self._sf(t.get("pnl_net", t.get("pnl", 0))) > 0
        )

    # ─────────────────────────── ana döngü ───────────────────────────────────

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe or ta is None:
            return

        # Başlangıç bakiyesini kaydet
        if self._initial_bal is None:
            self._initial_bal = self._engine.get_balance_usdt()

        # Devre kesici kontrolü
        if self._check_circuit_breaker():
            return

        price = self._sf(candle.get("close", 0))
        if price <= 0:
            return

        # Trailing stop yönetimi (pozisyon varsa)
        if self._engine.get_position() is not None:
            self._manage_trailing(price)
            return

        # Yeni giriş araması
        df = self._data_engine.get_completed_tf_candles(self.timeframe) if self._data_engine else None
        if df is None or len(df) < MIN_BARS:
            return

        try:
            close  = df["close"].astype(float)
            high   = df["high"].astype(float)
            low    = df["low"].astype(float)
            volume = df["volume"].astype(float)
        except Exception as e:
            self._log(f"Veri hatası: {e}")
            return

        score, atr_val, adx_val, is_trending = self._compute_score(
            close, high, low, volume, price
        )

        if atr_val <= 0:
            return

        # Yön kararı
        go_long  = score >= LONG_SCORE_MIN
        go_short = score <= -SHORT_SCORE_MIN

        if not go_long and not go_short:
            return

        # İstatistikleri güncelle (Kelly için)
        self._update_stats_from_history()

        # Pozisyon boyutu
        available = self._engine.get_available_balance()
        margin = self._kelly_margin(MARGIN_BASE * available, available)
        if margin < MIN_MARGIN_USDT or margin > available:
            self._log("Yetersiz bakiye veya marjin limiti aşıldı.")
            return

        leverage = LEVERAGE_TREND if is_trending else LEVERAGE_RANGE

        if go_long:
            sl_price = price - SL_ATR_MULT * atr_val
            tp_price = price + TP_ATR_MULT * atr_val
            if sl_price >= price or tp_price <= price:
                return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_val
            res = self._engine.open_long(
                entry_price=price,
                margin_usdt=margin,
                leverage=leverage,
                stop_loss=sl_price,
                take_profit=tp_price,
                opened_by=self.name,
            )
            if res.get("success"):
                self._log(
                    f"LONG açıldı @ {price:.2f} | Skor={score:+d} | "
                    f"ADX={adx_val:.1f}({'trend' if is_trending else 'range'}) | "
                    f"Lev={leverage}x | SL={sl_price:.2f} TP={tp_price:.2f} | "
                    f"ATR={atr_val:.2f} | Marjin={margin:.2f} USDT"
                )
            else:
                self._log(f"LONG açılamadı: {res.get('message', '')}")

        elif go_short:
            sl_price = price + SL_ATR_MULT * atr_val
            tp_price = price - TP_ATR_MULT * atr_val
            if sl_price <= price or tp_price >= price:
                return
            self._trail_stage = self._TRAIL_NONE
            self._entry_atr   = atr_val
            res = self._engine.open_short(
                entry_price=price,
                margin_usdt=margin,
                leverage=leverage,
                stop_loss=sl_price,
                take_profit=tp_price,
                opened_by=self.name,
            )
            if res.get("success"):
                self._log(
                    f"SHORT açıldı @ {price:.2f} | Skor={score:+d} | "
                    f"ADX={adx_val:.1f}({'trend' if is_trending else 'range'}) | "
                    f"Lev={leverage}x | SL={sl_price:.2f} TP={tp_price:.2f} | "
                    f"ATR={atr_val:.2f} | Marjin={margin:.2f} USDT"
                )
            else:
                self._log(f"SHORT açılamadı: {res.get('message', '')}")
