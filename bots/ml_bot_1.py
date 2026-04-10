# -*- coding: utf-8 -*-
"""
ML_bot_1: 5m XGBoost/RF — kısa vadeli yön olasılığı + yapı/ATR SL-TP, RR filtresi, %0.5 risk.
Model: models/ml_bot_1.joblib veya ML_BOT_1_MODEL_PATH.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None

from bots.ml_bot_1_features import MIN_BARS, last_feature_vector

LONG_THRESHOLD = 0.6
SHORT_THRESHOLD = 0.4

ATR_LEN = 14
SWING_LOOKBACK = 15
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.5
RR_TARGET = 1.2
RR_MIN = 1.0

VOL_LOOKBACK = 20
VOL_MIN_RATIO = 1.05

ATR_PCT_FILTER_LOOKBACK = 50
ATR_PCT_MIN_VS_MEDIAN = 0.75

RISK_PCT = 0.005
LEVERAGE = 5.0
MIN_MARGIN_USDT = 10.0
STOP_DIST_MIN_ATR_FRAC = 0.5
STOP_DIST_MIN_PRICE_FRAC = 0.0005


def _resolve_model_path() -> Path:
    env = os.environ.get("ML_BOT_1_MODEL_PATH")
    root = Path(__file__).resolve().parents[1]
    if env:
        return Path(env)
    return root / "models" / "ml_bot_1.joblib"


class ML_bot_1:
    name = "ML_bot_1"
    timeframe = "5m"

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine = trading_engine
        self._data_engine = data_engine
        self._model = None
        self._feature_names: Optional[list] = None
        self._load_model()

    def _log(self, msg: str) -> None:
        try:
            self._engine.log_message(f"[{self.name}] {msg}")
        except Exception:
            pass

    def _load_model(self) -> None:
        path = _resolve_model_path()
        if not path.is_file():
            self._log(f"Model yok: {path} — bot pasif.")
            return
        try:
            import joblib

            payload = joblib.load(path)
            self._model = payload.get("model") if isinstance(payload, dict) else payload
            self._feature_names = payload.get("feature_names") if isinstance(payload, dict) else None
            self._log(f"Model yüklendi: {path.name}")
        except Exception as e:
            self._log(f"Model yüklenemedi: {e}")

    def _safe_float(self, x: Any, default: float = 0.0) -> float:
        try:
            v = float(x)
            return v if np.isfinite(v) and abs(v) < 1e15 else default
        except (TypeError, ValueError):
            return default

    def _atr_last(self, df: pd.DataFrame) -> Optional[float]:
        if ta is None or df is None or len(df) < ATR_LEN + 1:
            return None
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        atr_series = ta.atr(high, low, close, length=ATR_LEN)
        if atr_series is None or pd.isna(atr_series.iloc[-1]):
            return None
        return self._safe_float(atr_series.iloc[-1])

    def _volume_filter_ok(self, df: pd.DataFrame) -> bool:
        if len(df) < VOL_LOOKBACK + 1:
            return False
        vol = df["volume"].astype(float)
        last_v = self._safe_float(vol.iloc[-1])
        prev = vol.iloc[-VOL_LOOKBACK:-1]
        mean_prev = float(prev.mean())
        if mean_prev <= 0:
            return False
        return last_v >= VOL_MIN_RATIO * mean_prev

    def _volatility_filter_ok(self, df: pd.DataFrame) -> bool:
        if ta is None or len(df) < ATR_PCT_FILTER_LOOKBACK + ATR_LEN:
            return False
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        atr_series = ta.atr(high, low, close, length=ATR_LEN)
        if atr_series is None:
            return False
        atr_pct = atr_series / close.replace(0, np.nan)
        tail = atr_pct.iloc[-ATR_PCT_FILTER_LOOKBACK :].dropna()
        if len(tail) < 10:
            return False
        med = float(tail.median())
        last = self._safe_float(atr_pct.iloc[-1])
        if med <= 0:
            return last > 0
        return last >= med * ATR_PCT_MIN_VS_MEDIAN

    def _predict_p_up(self, df: pd.DataFrame) -> Optional[float]:
        if self._model is None:
            return None
        vec = last_feature_vector(df, min_bars=MIN_BARS)
        if vec is None:
            return None
        X = vec.reshape(1, -1)
        if hasattr(self._model, "predict_proba"):
            pr = self._model.predict_proba(X)[0]
            if len(pr) >= 2:
                return float(pr[1])
        return None

    def _sl_tp_long(
        self, df: pd.DataFrame, entry: float, atr: float
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        low = df["low"].astype(float)
        high = df["high"].astype(float)
        swing_low = float(low.iloc[-SWING_LOOKBACK:].min())
        swing_high = float(high.iloc[-SWING_LOOKBACK:].max())

        if swing_low < entry:
            sl = swing_low
        else:
            sl = entry - SL_ATR_MULT * atr
        if sl >= entry:
            sl = entry - SL_ATR_MULT * atr

        risk = entry - sl
        min_risk = max(STOP_DIST_MIN_ATR_FRAC * atr, STOP_DIST_MIN_PRICE_FRAC * entry)
        if risk < min_risk:
            sl = entry - min_risk
            risk = min_risk

        if swing_high > entry:
            tp = swing_high
        else:
            tp = entry + TP_ATR_MULT * atr

        reward = tp - entry
        rr = reward / risk if risk > 0 else 0.0
        if rr < RR_MIN:
            tp = entry + RR_TARGET * risk
            reward = tp - entry
            rr = reward / risk if risk > 0 else 0.0
        if rr < RR_MIN:
            return None, None, None
        if rr < RR_TARGET:
            tp = entry + RR_TARGET * risk
        return sl, tp, risk

    def _sl_tp_short(
        self, df: pd.DataFrame, entry: float, atr: float
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        low = df["low"].astype(float)
        high = df["high"].astype(float)
        swing_high = float(high.iloc[-SWING_LOOKBACK:].max())
        swing_low = float(low.iloc[-SWING_LOOKBACK:].min())

        if swing_high > entry:
            sl = swing_high
        else:
            sl = entry + SL_ATR_MULT * atr
        if sl <= entry:
            sl = entry + SL_ATR_MULT * atr

        risk = sl - entry
        min_risk = max(STOP_DIST_MIN_ATR_FRAC * atr, STOP_DIST_MIN_PRICE_FRAC * entry)
        if risk < min_risk:
            sl = entry + min_risk
            risk = min_risk

        if swing_low < entry:
            tp = swing_low
        else:
            tp = entry - TP_ATR_MULT * atr

        reward = entry - tp
        rr = reward / risk if risk > 0 else 0.0
        if rr < RR_MIN:
            tp = entry - RR_TARGET * risk
            reward = entry - tp
            rr = reward / risk if risk > 0 else 0.0
        if rr < RR_MIN:
            return None, None, None
        if rr < RR_TARGET:
            tp = entry - RR_TARGET * risk
        return sl, tp, risk

    def _size_margin(self, entry: float, stop_distance: float) -> Optional[float]:
        balance = self._engine.get_balance_usdt()
        risk_usdt = balance * RISK_PCT
        if stop_distance <= 0 or entry <= 0:
            return None
        size_btc = risk_usdt / stop_distance
        notional = size_btc * entry
        margin = notional / LEVERAGE
        available = self._engine.get_available_balance()
        if margin > available:
            margin = available
        if margin < MIN_MARGIN_USDT:
            return None
        return margin

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe:
            return
        if self._model is None:
            return

        df = self._data_engine.get_completed_tf_candles(self.timeframe) if self._data_engine else None
        if df is None or len(df) < MIN_BARS:
            return

        if self._engine.get_position() is not None:
            return

        if not self._volume_filter_ok(df):
            return
        if not self._volatility_filter_ok(df):
            return

        p_up = self._predict_p_up(df)
        if p_up is None:
            return

        entry = self._safe_float(candle.get("close"))
        if entry <= 0:
            return

        atr = self._atr_last(df)
        if atr is None or atr <= 0:
            return

        direction: Optional[str] = None
        if p_up > LONG_THRESHOLD:
            direction = "long"
        elif p_up < SHORT_THRESHOLD:
            direction = "short"
        else:
            return

        if direction == "long":
            sl, tp, risk_dist = self._sl_tp_long(df, entry, atr)
        else:
            sl, tp, risk_dist = self._sl_tp_short(df, entry, atr)

        if sl is None or tp is None or risk_dist is None or risk_dist <= 0:
            return

        margin = self._size_margin(entry, risk_dist)
        if margin is None:
            return

        if direction == "long":
            r = self._engine.open_long(
                entry_price=entry,
                margin_usdt=margin,
                leverage=LEVERAGE,
                stop_loss=sl,
                take_profit=tp,
                opened_by=self.name,
            )
            if r.get("success"):
                rr_show = (tp - entry) / risk_dist
                self._log(f"LONG p_up={p_up:.3f} RR~{rr_show:.2f} SL={sl:.2f} TP={tp:.2f} m={margin:.2f}")
        else:
            r = self._engine.open_short(
                entry_price=entry,
                margin_usdt=margin,
                leverage=LEVERAGE,
                stop_loss=sl,
                take_profit=tp,
                opened_by=self.name,
            )
            if r.get("success"):
                rr_show = (entry - tp) / risk_dist
                self._log(f"SHORT p_up={p_up:.3f} RR~{rr_show:.2f} SL={sl:.2f} TP={tp:.2f} m={margin:.2f}")
