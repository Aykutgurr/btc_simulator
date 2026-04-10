# -*- coding: utf-8 -*-
"""
MTF AOI + MSB saf mantık: 1m OHLCV üzerinden HTF oylaması, günlük AOI, 15m MSB (gövde kapanışı), SL/TP.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# —— Parametreler (bot ile uyumlu sabitler) ——
LOOKBACK_DAYS_MAX = 1095
LOOKBACK_DAYS_DEFAULT = 500
AOI_MIN_TOUCHES = 3
AOI_BAND_PCT = 0.0035
RETRACE_BARS_15M = 56
PIVOT_LEFT = 2
PIVOT_RIGHT = 2
MIN_BARS_15M = 80
MIN_BARS_HTF = 24
SL_BUFFER_PCT = 0.0012
TP_BUFFER_PCT = 0.0015
HTF_MAJORITY = 2  # 3 HTF'den en az 2 aynı yönde


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    slice_df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(slice_df.index):
        slice_df.index = pd.to_datetime(slice_df.index, errors="coerce")
        slice_df = slice_df[slice_df.index.notna()]
    if slice_df.empty:
        return pd.DataFrame()
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    cols = [c for c in agg if c in slice_df.columns]
    if "volume" not in cols:
        slice_df = slice_df.copy()
        slice_df["volume"] = 0.0
        cols = list(agg.keys())
    out = slice_df[cols].resample(rule).agg({k: agg[k] for k in cols}).dropna(how="all")
    return out


def _pivot_highs(df: pd.DataFrame, left: int = PIVOT_LEFT, right: int = PIVOT_RIGHT) -> List[Tuple[int, float]]:
    if df is None or len(df) < left + right + 1:
        return []
    highs: List[Tuple[int, float]] = []
    highs_s = df["high"].values
    n = len(df)
    for i in range(left, n - right):
        v = highs_s[i]
        if v == max(highs_s[i - left : i + right + 1]):
            highs.append((i, float(v)))
    return highs


def _pivot_lows(df: pd.DataFrame, left: int = PIVOT_LEFT, right: int = PIVOT_RIGHT) -> List[Tuple[int, float]]:
    if df is None or len(df) < left + right + 1:
        return []
    lows: List[Tuple[int, float]] = []
    lows_s = df["low"].values
    n = len(df)
    for i in range(left, n - right):
        v = lows_s[i]
        if v == min(lows_s[i - left : i + right + 1]):
            lows.append((i, float(v)))
    return lows


def htf_trend_vote(df: pd.DataFrame) -> int:
    """
    Son iki pivot high / iki pivot low ile yapı: HH+HL -> +1, LH+LL -> -1, aksi 0.
    """
    if df is None or len(df) < MIN_BARS_HTF:
        return 0
    ph = _pivot_highs(df)
    pl = _pivot_lows(df)
    if len(ph) < 2 or len(pl) < 2:
        return 0
    _, h_prev = ph[-2]
    _, h_last = ph[-1]
    _, l_prev = pl[-2]
    _, l_last = pl[-1]
    if h_last > h_prev and l_last > l_prev:
        return 1
    if h_last < h_prev and l_last < l_prev:
        return -1
    return 0


def htf_bias_sum(df_4h: pd.DataFrame, df_1d: pd.DataFrame, df_1w: pd.DataFrame) -> int:
    return htf_trend_vote(df_4h) + htf_trend_vote(df_1d) + htf_trend_vote(df_1w)


def _daily_atr(daily: pd.DataFrame, length: int = 14) -> float:
    if daily is None or len(daily) < length + 1:
        return 0.0
    h, l, c = daily["high"], daily["low"], daily["close"]
    prev_c = c.shift(1)
    tr = pd.concat(
        [(h - l).abs(), (h - prev_c).abs(), (l - prev_c).abs()],
        axis=1,
    ).max(axis=1)
    atr = float(tr.rolling(length).mean().iloc[-1])
    return atr if pd.notna(atr) else 0.0


def find_aoi_zones(
    daily: pd.DataFrame,
    lookback_days: int,
    min_touches: int = AOI_MIN_TOUCHES,
    band_pct: float = AOI_BAND_PCT,
) -> List[Tuple[float, float, int]]:
    """
    Günlük veride pivot merkezleri; band içi dokunuş sayısı >= min_touches olan bölgeler.
    Dönüş: [(low, high, touches), ...]
    """
    if daily is None or daily.empty:
        return []
    lb_eff = int(max(30, min(lookback_days, LOOKBACK_DAYS_MAX)))
    cut = daily.index[-1] - pd.Timedelta(days=lb_eff)
    d = daily[daily.index >= cut]
    if len(d) < 30:
        return []

    centers: List[float] = []
    for _, p in _pivot_highs(d):
        centers.append(p)
    for _, p in _pivot_lows(d):
        centers.append(p)
    if not centers:
        return []

    last_close = float(d["close"].iloc[-1])
    atr = _daily_atr(d)
    half_w = max(last_close * band_pct * 0.5, atr * 0.35 if atr > 0 else last_close * band_pct * 0.5)

    raw: List[Tuple[float, float, int]] = []
    for c in centers:
        lo, hi = c - half_w, c + half_w
        touches = 0
        for _, row in d.iterrows():
            if float(row["high"]) >= lo and float(row["low"]) <= hi:
                touches += 1
        if touches >= min_touches:
            raw.append((lo, hi, touches))

    if not raw:
        return []
    raw.sort(key=lambda z: z[0])
    merged: List[Tuple[float, float, int]] = []
    cur_lo, cur_hi, cur_t = raw[0]
    for lo, hi, t in raw[1:]:
        if lo <= cur_hi + half_w:
            cur_hi = max(cur_hi, hi)
            cur_t = max(cur_t, t)
        else:
            merged.append((cur_lo, cur_hi, cur_t))
            cur_lo, cur_hi, cur_t = lo, hi, t
    merged.append((cur_lo, cur_hi, cur_t))
    merged.sort(key=lambda z: z[2], reverse=True)
    return merged


def _bar_touches_zone(low: float, high: float, z_lo: float, z_hi: float) -> bool:
    return high >= z_lo and low <= z_hi


def _recent_retrace_into_aoi_short(
    df15: pd.DataFrame,
    zones: List[Tuple[float, float, int]],
    retrace_bars: int = RETRACE_BARS_15M,
) -> Optional[Tuple[float, float]]:
    """Bearish: önce bölgenin altından, sonra AOI'ye yukarı temas."""
    if df15 is None or len(df15) < retrace_bars + 2 or not zones:
        return None
    tail = df15.iloc[-retrace_bars:]
    for z_lo, z_hi, _ in zones:
        touched = False
        was_below = False
        for _, row in tail.iterrows():
            lo, hi = float(row["low"]), float(row["high"])
            if hi < z_lo:
                was_below = True
            if was_below and _bar_touches_zone(lo, hi, z_lo, z_hi):
                touched = True
            if touched:
                return (z_lo, z_hi)
    return None


def _recent_retrace_into_aoi_long(
    df15: pd.DataFrame,
    zones: List[Tuple[float, float, int]],
    retrace_bars: int = RETRACE_BARS_15M,
) -> Optional[Tuple[float, float]]:
    """Bullish: önce bölgenin üstünden, sonra AOI'ye aşağı temas."""
    if df15 is None or len(df15) < retrace_bars + 2 or not zones:
        return None
    tail = df15.iloc[-retrace_bars:]
    for z_lo, z_hi, _ in zones:
        touched = False
        was_above = False
        for _, row in tail.iterrows():
            lo, hi = float(row["low"]), float(row["high"])
            if lo > z_hi:
                was_above = True
            if was_above and _bar_touches_zone(lo, hi, z_lo, z_hi):
                touched = True
            if touched:
                return (z_lo, z_hi)
    return None


def _last_hl_level(df15: pd.DataFrame, lookback: int = 96) -> Optional[float]:
    """Son iki pivot low yükselen ise son low seviyesi = HL."""
    if df15 is None or len(df15) < lookback:
        return None
    seg = df15.iloc[-lookback:]
    pl = _pivot_lows(seg)
    if len(pl) < 2:
        return None
    _, p0 = pl[-1]
    _, p1 = pl[-2]
    if p0 > p1:
        return float(p0)
    return None


def _last_lh_level(df15: pd.DataFrame, lookback: int = 96) -> Optional[float]:
    """Son iki pivot high alçalan ise son high = LH (long kırılımı için)."""
    if df15 is None or len(df15) < lookback:
        return None
    seg = df15.iloc[-lookback:]
    ph = _pivot_highs(seg)
    if len(ph) < 2:
        return None
    _, p0 = ph[-1]
    _, p1 = ph[-2]
    if p0 < p1:
        return float(p0)
    return None


def _swing_high_before_msb(df15: pd.DataFrame, end_idx: int, lookback: int = 96) -> Optional[float]:
    if end_idx < 1:
        return None
    seg = df15.iloc[max(0, end_idx - lookback) : end_idx]
    ph = _pivot_highs(seg)
    if not ph:
        return float(seg["high"].max())
    return float(ph[-1][1])


def _swing_low_before_msb(df15: pd.DataFrame, end_idx: int, lookback: int = 96) -> Optional[float]:
    if end_idx < 1:
        return None
    seg = df15.iloc[max(0, end_idx - lookback) : end_idx]
    pl = _pivot_lows(seg)
    if not pl:
        return float(seg["low"].min())
    return float(pl[-1][1])


def _nearest_support_below(entry: float, levels: List[float]) -> Optional[float]:
    below = [x for x in levels if x < entry]
    if not below:
        return None
    return max(below)


def _nearest_resistance_above(entry: float, levels: List[float]) -> Optional[float]:
    above = [x for x in levels if x > entry]
    if not above:
        return None
    return min(above)


def _collect_htf_swings(df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> Tuple[List[float], List[float]]:
    """Tüm pivot high / low fiyatları (TP/SL yardımcı)."""
    highs: List[float] = []
    lows: List[float] = []
    for d in (df_4h, df_1d):
        if d is None or d.empty:
            continue
        for _, p in _pivot_highs(d):
            highs.append(p)
        for _, p in _pivot_lows(d):
            lows.append(p)
    return highs, lows


def sl_tp_short(
    entry: float,
    swing_high_sl: float,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
) -> Tuple[float, float]:
    sl = swing_high_sl * (1.0 + SL_BUFFER_PCT)
    h_levels, l_levels = _collect_htf_swings(df_4h, df_1d)
    sup = _nearest_support_below(entry, l_levels)
    if sup is None:
        tp = entry * (1.0 - 0.02)
    else:
        tp = sup + abs(entry * TP_BUFFER_PCT)
    if tp >= entry:
        tp = entry * (1.0 - 0.015)
    return sl, tp


def sl_tp_long(
    entry: float,
    swing_low_sl: float,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
) -> Tuple[float, float]:
    sl = swing_low_sl * (1.0 - SL_BUFFER_PCT)
    h_levels, l_levels = _collect_htf_swings(df_4h, df_1d)
    res = _nearest_resistance_above(entry, h_levels)
    if res is None:
        tp = entry * (1.0 + 0.02)
    else:
        tp = res - abs(entry * TP_BUFFER_PCT)
    if tp <= entry:
        tp = entry * (1.0 + 0.015)
    return sl, tp


def evaluate_msb_mtf(df_1m: pd.DataFrame, lookback_days: int = LOOKBACK_DAYS_DEFAULT) -> Optional[Dict[str, Any]]:
    """
    Tamamlanmış 1m serisi (simülasyon anına kadar) ile sinyal üretir.
    Dönüş: direction, entry, stop_loss, take_profit veya None.
    """
    if df_1m is None or len(df_1m) < 500:
        return None

    df_1m = df_1m.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_1m.index):
        df_1m.index = pd.to_datetime(df_1m.index, errors="coerce")
        df_1m = df_1m[df_1m.index.notna()]
    if df_1m.empty:
        return None

    available_days = max(1, (df_1m.index[-1] - df_1m.index[0]).days)
    lb = int(min(max(30, available_days), min(lookback_days, LOOKBACK_DAYS_MAX)))

    df_4h = resample_ohlcv(df_1m, "4h")
    df_1d = resample_ohlcv(df_1m, "1D")
    df_1w = resample_ohlcv(df_1m, "1W")
    df_15m = resample_ohlcv(df_1m, "15min")

    if len(df_15m) < MIN_BARS_15M:
        return None

    bias = htf_bias_sum(df_4h, df_1d, df_1w)
    if abs(bias) < HTF_MAJORITY:
        return None

    zones = find_aoi_zones(df_1d, lb)
    if not zones:
        return None

    last = df_15m.iloc[-1]
    o = float(last["open"])
    c = float(last["close"])
    entry = c

    if bias <= -HTF_MAJORITY:
        active = _recent_retrace_into_aoi_short(df_15m, zones)
        if active is None:
            return None
        hl = _last_hl_level(df_15m)
        if hl is None:
            return None
        if c >= hl:
            return None
        if o < hl and c < hl:
            pass
        end_idx = len(df_15m) - 1
        swing_hi = _swing_high_before_msb(df_15m, end_idx)
        if swing_hi is None or swing_hi <= entry:
            swing_hi = float(df_15m.iloc[-RETRACE_BARS_15M : end_idx]["high"].max()) if end_idx > 0 else entry * 1.01
        sl, tp = sl_tp_short(entry, swing_hi, df_4h, df_1d)
        if sl <= entry or tp >= entry:
            return None
        risk = sl - entry
        reward = entry - tp
        if risk <= 0 or reward <= 0 or reward < risk * 0.5:
            return None
        return {
            "direction": "short",
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
        }

    if bias >= HTF_MAJORITY:
        active = _recent_retrace_into_aoi_long(df_15m, zones)
        if active is None:
            return None
        lh = _last_lh_level(df_15m)
        if lh is None:
            return None
        if c <= lh:
            return None
        end_idx = len(df_15m) - 1
        swing_lo = _swing_low_before_msb(df_15m, end_idx)
        if swing_lo is None or swing_lo >= entry:
            swing_lo = float(df_15m.iloc[-RETRACE_BARS_15M : end_idx]["low"].min()) if end_idx > 0 else entry * 0.99
        sl, tp = sl_tp_long(entry, swing_lo, df_4h, df_1d)
        if sl >= entry or tp <= entry:
            return None
        risk = entry - sl
        reward = tp - entry
        if risk <= 0 or reward <= 0 or reward < risk * 0.5:
            return None
        return {
            "direction": "long",
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
        }

    return None
