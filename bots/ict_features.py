# -*- coding: utf-8 -*-
"""
ICT-türevli operasyonel özellikler (OHLCV): swing, FVG, order block proxy, likidite sweep, BOS/CHoCH proxy.
Eğitim ve ICT_ML_Bot aynı vektörü kullanır.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

# Sabit özellik sırası — model eğitimi ve çıkarımda aynı olmalı
FEATURE_NAMES: List[str] = [
    "atr_rel",
    "dist_swing_high_atr",
    "dist_swing_low_atr",
    "bos_up",
    "bos_down",
    "structure_bias",  # -1 bearish, 0 neutral, 1 bullish (HH/HL vs LH/LL proxy)
    "fvg_bull_gap_open",
    "fvg_bear_gap_open",
    "fvg_dist_below_atr",
    "fvg_dist_above_atr",
    "ob_dist_atr",
    "sweep_high_recent",
    "sweep_low_recent",
    "mom_5_atr",
    "vol_rel",
    "ret_1",
    "hl_range_atr",
]

MIN_BARS_DEFAULT = 120
SWING_LOOKBACK = 2
ATR_LEN = 14
VOL_MA = 20


def _ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    need = {"open", "high", "low", "close"}
    if not need.issubset(set(c.lower() for c in df.columns)):
        raise ValueError("DataFrame open, high, low, close içermeli.")
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    for c in ("open", "high", "low", "close"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    if "volume" not in out.columns:
        out["volume"] = 0.0
    else:
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0.0)
    return out.dropna(subset=["open", "high", "low", "close"])


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = ATR_LEN) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(length, min_periods=length).mean()


def _swing_high_low(
    high: np.ndarray, low: np.ndarray, lookback: int = SWING_LOOKBACK
) -> Tuple[np.ndarray, np.ndarray]:
    """Fraktal swing: i'de swing high ise high[i] strictly max in window."""
    n = len(high)
    is_sh = np.zeros(n, dtype=np.float64)
    is_sl = np.zeros(n, dtype=np.float64)
    for i in range(lookback, n - lookback):
        w_h = high[i - lookback : i + lookback + 1]
        w_l = low[i - lookback : i + lookback + 1]
        if high[i] >= np.max(w_h):
            is_sh[i] = 1.0
        if low[i] <= np.min(w_l):
            is_sl[i] = 1.0
    return is_sh, is_sl


def _last_swing_levels(
    high: np.ndarray, low: np.ndarray, is_sh: np.ndarray, is_sl: np.ndarray, upto: int
) -> Tuple[float, float]:
    """upto dahil son swing high fiyatı ve son swing low fiyatı."""
    sh = 0.0
    sl = 0.0
    for i in range(upto, -1, -1):
        if is_sh[i] and sh == 0.0:
            sh = float(high[i])
        if is_sl[i] and sl == 0.0:
            sl = float(low[i])
        if sh > 0 and sl > 0:
            break
    if sh == 0.0:
        sh = float(np.max(high[: upto + 1]))
    if sl == 0.0:
        sl = float(np.min(low[: upto + 1]))
    return sh, sl


def _fvg_states(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, upto: int
) -> Tuple[float, float, float, float]:
    """
    Son barda açık bull/bear FVG var mı (3 mum kuralı); alt/üst taraftaki en yakın açık gap mesafesi (ATR ile normalize edilecek).
    Bull FVG: low[i] > high[i-2]. Bear FVG: high[i] < low[i-2].
    Gap'in doldurulmuş sayılması: son kapanış gap içine geri döndü mü.
    """
    if upto < 2:
        return 0.0, 0.0, np.nan, np.nan
    i = upto
    bull_open = 0.0
    bear_open = 0.0
    # i anında oluşan FVG
    lo_i, hi_i2 = low[i], high[i - 2]
    hi_i, lo_i2 = high[i], low[i - 2]
    if lo_i > hi_i2:
        gap_low, gap_high = hi_i2, lo_i
        filled = close[upto] <= gap_high and close[upto] >= gap_low
        if not filled:
            bull_open = 1.0
    if hi_i < lo_i2:
        gap_low, gap_high = hi_i, lo_i2
        filled = close[upto] <= gap_high and close[upto] >= gap_low
        if not filled:
            bear_open = 1.0

    # Yakın FVG mesafeleri (son 30 bar tarama)
    dist_below = np.nan
    dist_above = np.nan
    c = close[upto]
    start = max(2, upto - 30)
    for j in range(upto, start - 1, -1):
        if j < 2:
            continue
        if low[j] > high[j - 2]:
            mid = (low[j] + high[j - 2]) / 2.0
            if mid < c and (np.isnan(dist_below) or (c - mid) < dist_below):
                dist_below = c - mid
        if high[j] < low[j - 2]:
            mid = (high[j] + low[j - 2]) / 2.0
            if mid > c and (np.isnan(dist_above) or (mid - c) < dist_above):
                dist_above = mid - c
    return bull_open, bear_open, dist_below, dist_above


def _ob_proxy_dist(high: np.ndarray, low: np.ndarray, open_: np.ndarray, close: np.ndarray, upto: int) -> float:
    """
    Son 'güçlü' mumdan önceki karşıt mumun gövde bölgesine mesafe (fiyat biriminde).
    Güçlü mum: |close-open| > median body * 1.2 ve range yüksek.
    """
    if upto < 5:
        return np.nan
    bodies = np.abs(close - open_)
    med_body = np.median(bodies[max(0, upto - 50) : upto + 1])
    if med_body <= 0:
        med_body = 1e-9
    dist = np.nan
    for j in range(upto, max(4, upto - 40), -1):
        rng = high[j] - low[j]
        body = abs(close[j] - open_[j])
        if body < 1.2 * med_body or rng <= 0:
            continue
        bull = close[j] > open_[j]
        # önceki karşıt mum
        for k in range(j - 1, max(0, j - 6), -1):
            prev_bull = close[k] > open_[k]
            if prev_bull == bull:
                continue
            ob_low = min(open_[k], close[k])
            ob_high = max(open_[k], close[k])
            mid = (ob_low + ob_high) / 2.0
            dist = close[upto] - mid
            break
        if not np.isnan(dist):
            break
    return dist


def _liquidity_sweep(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, is_sh: np.ndarray, is_sl: np.ndarray, upto: int, look: int = 6
) -> Tuple[float, float]:
    """Son 'look' barda swing üstü/altı ihlal + kapanış geri içeride mi."""
    if upto < 5:
        return 0.0, 0.0
    sh = 0.0
    sl = 0.0
    for j in range(upto - 1, max(0, upto - 30), -1):
        if is_sh[j]:
            sh = high[j]
            break
    for j in range(upto - 1, max(0, upto - 30), -1):
        if is_sl[j]:
            sl = low[j]
            break
    sweep_h = 0.0
    sweep_l = 0.0
    for j in range(max(0, upto - look), upto + 1):
        if sh > 0 and high[j] > sh and close[j] < sh:
            sweep_h = 1.0
        if sl > 0 and low[j] < sl and close[j] > sl:
            sweep_l = 1.0
    return sweep_h, sweep_l


def _structure_bias(close: np.ndarray, upto: int, seg: int = 20) -> float:
    """Basit: son seg kapanış ortalaması vs önceki seg — eğim işareti."""
    if upto < seg * 2:
        return 0.0
    m1 = float(np.mean(close[upto - seg : upto]))
    m0 = float(np.mean(close[upto - 2 * seg : upto - seg]))
    diff = m1 - m0
    atr_est = float(np.std(close[upto - seg : upto]) + 1e-9)
    x = diff / atr_est
    if x > 0.5:
        return 1.0
    if x < -0.5:
        return -1.0
    return 0.0


def feature_row_at_index(
    df: pd.DataFrame, idx: int, atr_series: pd.Series, min_bars: int = MIN_BARS_DEFAULT
) -> Optional[np.ndarray]:
    """Tek bir t anı için özellik vektörü (numpy 1d)."""
    d = _ensure_ohlcv(df)
    if idx < min_bars or idx >= len(d):
        return None
    high = d["high"].values
    low = d["low"].values
    close = d["close"].values
    open_ = d["open"].values
    vol = d["volume"].values

    is_sh, is_sl = _swing_high_low(high, low, SWING_LOOKBACK)
    atr = float(atr_series.iloc[idx]) if idx < len(atr_series) and pd.notna(atr_series.iloc[idx]) else np.nan
    if atr is None or not np.isfinite(atr) or atr <= 0:
        atr = float(np.mean(high[max(0, idx - ATR_LEN) : idx + 1] - low[max(0, idx - ATR_LEN) : idx + 1]) + 1e-9)

    c = close[idx]
    sh, sl = _last_swing_levels(high, low, is_sh, is_sl, idx)
    dist_sh = (sh - c) / atr
    dist_sl = (c - sl) / atr
    bos_up = 1.0 if c > sh else 0.0
    bos_down = 1.0 if c < sl else 0.0
    bias = _structure_bias(close, idx)

    b_open, s_open, d_below, d_above = _fvg_states(high, low, close, idx)
    d_below_n = (d_below / atr) if d_below is not None and np.isfinite(d_below) else 0.0
    d_above_n = (d_above / atr) if d_above is not None and np.isfinite(d_above) else 0.0

    ob_d = _ob_proxy_dist(high, low, open_, close, idx)
    ob_n = (ob_d / atr) if ob_d is not None and np.isfinite(ob_d) else 0.0

    sw_h, sw_l = _liquidity_sweep(high, low, close, is_sh, is_sl, idx)
    mom_5 = (c - close[idx - 5]) / atr if idx >= 5 else 0.0
    vma = np.mean(vol[max(0, idx - VOL_MA) : idx + 1])
    vol_rel = (vol[idx] / vma) if vma and vma > 0 else 1.0
    ret_1 = (c / close[idx - 1] - 1.0) if idx >= 1 else 0.0
    hl_rng = (high[idx] - low[idx]) / atr

    vec = np.array(
        [
            atr / c,
            float(dist_sh),
            float(dist_sl),
            bos_up,
            bos_down,
            bias,
            b_open,
            s_open,
            float(d_below_n),
            float(d_above_n),
            float(ob_n),
            sw_h,
            sw_l,
            float(mom_5),
            float(vol_rel),
            float(ret_1),
            float(hl_rng),
        ],
        dtype=np.float64,
    )
    vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
    return vec


def compute_features_dataframe(df: pd.DataFrame, min_bars: int = MIN_BARS_DEFAULT) -> pd.DataFrame:
    """Her satır için özellikler (ilk min_bars satır NaN)."""
    d = _ensure_ohlcv(df)
    atr_s = _atr(d["high"], d["low"], d["close"], ATR_LEN)
    rows = []
    n = len(d)
    for i in range(n):
        if i < min_bars:
            rows.append([np.nan] * len(FEATURE_NAMES))
            continue
        v = feature_row_at_index(d, i, atr_s, min_bars=min_bars)
        rows.append(v.tolist() if v is not None else [np.nan] * len(FEATURE_NAMES))
    out = pd.DataFrame(rows, index=d.index, columns=FEATURE_NAMES)
    return out


def last_feature_vector(df: pd.DataFrame, min_bars: int = MIN_BARS_DEFAULT) -> Optional[np.ndarray]:
    """Bot: tamamlanmış TF DataFrame'inin son barı için vektör."""
    d = _ensure_ohlcv(df)
    if len(d) < min_bars:
        return None
    atr_s = _atr(d["high"], d["low"], d["close"], ATR_LEN)
    idx = len(d) - 1
    return feature_row_at_index(d, idx, atr_s, min_bars=min_bars)


def build_feature_matrix(
    df: pd.DataFrame, min_bars: int = MIN_BARS_DEFAULT
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Eğitim: (X, index_positions) — sadece geçerli satırlar.
    X shape (n_samples, n_features).
    """
    feat_df = compute_features_dataframe(df, min_bars=min_bars)
    valid = feat_df.notna().all(axis=1)
    ix = np.where(valid.values)[0]
    X = feat_df.loc[feat_df.index[valid]].values.astype(np.float64)
    return X, ix
