# -*- coding: utf-8 -*-
"""
5m ML sınıflandırma: RSI(14), MACD+Signal, ATR(14), (Close-EMA50)/EMA50.
Etiket: horizon mum sonra kapanış şu ankinden yüksek mi (1/0). Sızıntı yok.
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
EMA_LEN = 50
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ATR_LEN = 14
LABEL_HORIZON = 3

FEATURE_NAMES: List[str] = [
    "rsi_14",
    "macd",
    "macd_signal",
    "atr_14",
    "ema50_rel",
]

# EMA50 + MACD sinyal için güvenli alt sınır
MIN_BARS = 70


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
    """t anındaki göstergeler; yalnızca geçmiş ve güncel OHLCV."""
    if ta is None:
        raise RuntimeError("pandas_ta gerekli.")
    d = _ensure_ohlcv(df)
    close = d["close"].astype(float)
    high = d["high"].astype(float)
    low = d["low"].astype(float)

    rsi = ta.rsi(close, length=RSI_LEN)
    ema50 = ta.ema(close, length=EMA_LEN)
    ema50_safe = ema50.replace(0, np.nan)
    ema50_rel = (close - ema50) / ema50_safe

    m = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    if m is None or m.empty:
        raise RuntimeError("MACD hesaplanamadı.")
    macd_line = m["MACD_12_26_9"] if "MACD_12_26_9" in m.columns else m.iloc[:, 0]
    macd_sig = m["MACDs_12_26_9"] if "MACDs_12_26_9" in m.columns else m.iloc[:, 2]

    atr = ta.atr(high, low, close, length=ATR_LEN)

    out = pd.DataFrame(
        {
            "rsi_14": rsi,
            "macd": macd_line,
            "macd_signal": macd_sig,
            "atr_14": atr,
            "ema50_rel": ema50_rel,
        },
        index=d.index,
    )
    return out


def build_training_xy(
    df: pd.DataFrame, horizon: int = LABEL_HORIZON
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Özellikler t anında; etiket close[t+horizon] > close[t].
    Son horizon satır etiketsiz — düşer.
    """
    feat = compute_feature_frame(df)
    mat = feat[FEATURE_NAMES].copy()
    close = _ensure_ohlcv(df)["close"].astype(float)
    future = close.shift(-horizon)
    y = (future > close).astype(np.float64)
    mat = mat.assign(_y=y)
    mat = mat.dropna()
    y_clean = mat["_y"].values.astype(np.int32)
    X = mat[FEATURE_NAMES].values.astype(np.float64)
    return X, y_clean


def last_feature_vector(
    df: pd.DataFrame, min_bars: int = MIN_BARS
) -> Optional[np.ndarray]:
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


def last_atr(df: pd.DataFrame, min_bars: int = MIN_BARS) -> Optional[float]:
    """SL/TP için son ATR(14); özellik satırı ile tutarlı."""
    vec = last_feature_vector(df, min_bars=min_bars)
    if vec is None:
        return None
    try:
        atr_idx = FEATURE_NAMES.index("atr_14")
        v = float(vec[atr_idx])
        return v if np.isfinite(v) and v > 0 else None
    except (ValueError, IndexError):
        return None
