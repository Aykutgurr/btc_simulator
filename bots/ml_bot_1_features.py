# -*- coding: utf-8 -*-
"""
ML_bot_1: eğitim ve çıkarım için ortak özellikler (5m OHLCV).
RSI, EMA9/21, MACD, hacim oranı, kısa getiriler, EMA crossover.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None

RSI_LEN = 14
EMA_FAST = 9
EMA_SLOW = 21
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
VOL_MA = 20

# Sabit sıra — model ve bot aynı vektörü kullanmalı
FEATURE_NAMES: List[str] = [
    "rsi_14",
    "ema9_rel",
    "ema21_rel",
    "macd",
    "macd_signal",
    "macd_hist",
    "volume_ratio",
    "ret_1",
    "ret_2",
    "ret_3",
    "ret_4",
    "ret_5",
    "ema_cross",
]

MIN_BARS = 64


def _ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    need = {"open", "high", "low", "close"}
    lower = {c.lower() for c in df.columns}
    if not need.issubset(lower):
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


def compute_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tüm satırlar için gösterge kolonlarını üretir (ta ile).
    """
    if ta is None:
        raise RuntimeError("pandas_ta gerekli.")
    d = _ensure_ohlcv(df)
    close = d["close"].astype(float)
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    vol = d["volume"].astype(float)

    rsi = ta.rsi(close, length=RSI_LEN)
    ema9 = ta.ema(close, length=EMA_FAST)
    ema21 = ta.ema(close, length=EMA_SLOW)
    m = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    if m is None or m.empty:
        raise RuntimeError("MACD hesaplanamadı.")
    # pandas_ta: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
    macd_line = m["MACD_12_26_9"] if "MACD_12_26_9" in m.columns else m.iloc[:, 0]
    macd_hist = m["MACDh_12_26_9"] if "MACDh_12_26_9" in m.columns else m.iloc[:, 1]
    macd_sig = m["MACDs_12_26_9"] if "MACDs_12_26_9" in m.columns else m.iloc[:, 2]

    vol_ma = vol.rolling(VOL_MA, min_periods=VOL_MA).mean()
    vol_ratio = vol / vol_ma.replace(0, np.nan)

    ret1 = close.pct_change(1)
    ret2 = close.pct_change(2)
    ret3 = close.pct_change(3)
    ret4 = close.pct_change(4)
    ret5 = close.pct_change(5)

    ema_cross = (ema9 > ema21).astype(float)

    out = pd.DataFrame(
        {
            "rsi_14": rsi,
            "ema9_rel": ema9 / close.replace(0, np.nan),
            "ema21_rel": ema21 / close.replace(0, np.nan),
            "macd": macd_line,
            "macd_signal": macd_sig,
            "macd_hist": macd_hist,
            "volume_ratio": vol_ratio,
            "ret_1": ret1,
            "ret_2": ret2,
            "ret_3": ret3,
            "ret_4": ret4,
            "ret_5": ret5,
            "ema_cross": ema_cross,
        },
        index=d.index,
    )
    return out


def build_training_xy(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """
    Özellikler t anında; etiket bir sonraki mum yönü. Son satır (gelecek yok) düşer.
    Sızıntı yok: göstergeler sadece geçmiş veriye dayanır.
    """
    feat = compute_feature_frame(df)
    mat = feat[FEATURE_NAMES].copy()
    close = _ensure_ohlcv(df)["close"].astype(float)
    y = (close.shift(-1) > close).astype(np.float64)
    mat = mat.assign(_y=y)
    mat = mat.dropna()
    y_clean = mat["_y"].values.astype(np.int32)
    X = mat[FEATURE_NAMES].values.astype(np.float64)
    return X, y_clean


def last_feature_vector(df: pd.DataFrame, min_bars: int = MIN_BARS) -> Optional[np.ndarray]:
    """Son tamamlanmış mum için 1xF vektör (çıkarım)."""
    if df is None or len(df) < min_bars or ta is None:
        return None
    feat = compute_feature_frame(df)
    if feat is None or len(feat) < 1:
        return None
    row = feat[FEATURE_NAMES].iloc[-1]
    if row.isna().any():
        return None
    return row.values.astype(np.float64)


def build_labels_next_direction(close: pd.Series) -> pd.Series:
    """y[t] = 1 if close[t+1] > close[t] else 0. Son satır NaN."""
    nxt = close.shift(-1)
    y = (nxt > close).astype(float)
    y.loc[nxt.isna()] = np.nan
    return y
