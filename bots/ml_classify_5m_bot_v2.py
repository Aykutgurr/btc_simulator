# -*- coding: utf-8 -*-
"""
MLClassify5m gevşek sürüm (v2): aynı özellik seti ve SL/TP/risk formülü;
girişte daha düşük olasılık eşiği ve kazanan-taraf + kenar kuralı ile daha sık sinyal.

Model sırası: ML_CLASSIFY_5MV2_MODEL_PATH → models/ml_classify_5mv2.joblib (varsa)
→ aksi halde models/ml_classify_5m.joblib (v1 ile aynı eğitim dosyası).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    import pandas_ta as ta
except ImportError:
    ta = None

from bots.ml_classify_5m_features import (
    FEATURE_NAMES,
    MIN_BARS,
    last_atr,
    last_feature_vector,
)

# Gevşetilmiş giriş: kazanan sınıf yeterince güçlü ve diğerinden anlamlı farklı
WINNER_MIN_PROBA = 0.505
EDGE_MIN = 0.008

RISK_PCT = 0.02
SL_ATR_MULT = 1.5
TP_SL_MULT = 1.5
LEVERAGE = 5.0
MIN_MARGIN_USDT = 5.0


def _resolve_model_path() -> Path:
    env = os.environ.get("ML_CLASSIFY_5MV2_MODEL_PATH")
    root = Path(__file__).resolve().parents[1]
    if env:
        return Path(env)
    dedicated = root / "models" / "ml_classify_5mv2.joblib"
    if dedicated.is_file():
        return dedicated
    return root / "models" / "ml_classify_5m.joblib"


def _desired_direction_v2(
    p0: float,
    p1: float,
    winner_min: float = WINNER_MIN_PROBA,
    edge_min: float = EDGE_MIN,
) -> Optional[str]:
    """
    Kazanan olasılık en az winner_min ve rakipten en az edge_min kadar büyükse o yönde sinyal.
    (v1'deki çift taraflı 0.55 şartından daha gevşek; ~%50.5 + %0.8 kenar yeter.)
    """
    if p1 >= winner_min and (p1 - p0) >= edge_min:
        return "long"
    if p0 >= winner_min and (p0 - p1) >= edge_min:
        return "short"
    return None


def _proba_p0_p1(model: Any, Xrow: np.ndarray) -> Optional[Tuple[float, float]]:
    if not hasattr(model, "predict_proba"):
        return None
    pr = model.predict_proba(Xrow.reshape(1, -1))[0]
    classes = getattr(model, "classes_", np.array([0, 1]))
    idx0 = int(np.where(classes == 0)[0][0]) if 0 in classes else 0
    idx1 = int(np.where(classes == 1)[0][0]) if 1 in classes else 1
    if len(pr) < 2:
        return None
    return float(pr[idx0]), float(pr[idx1])


class MLClassify5mv2Bot:
    name = "MLClassify5mv2"
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

    def _margin_for_risk(self, entry: float, sl_dist: float) -> Optional[float]:
        if sl_dist <= 0 or entry <= 0:
            return None
        balance = self._engine.get_balance_usdt()
        risk_usdt = balance * RISK_PCT
        size_btc = risk_usdt / sl_dist
        notional = size_btc * entry
        margin = notional / LEVERAGE
        available = self._engine.get_available_balance()
        if margin > available:
            margin = available
        if margin < MIN_MARGIN_USDT:
            return None
        return margin

    def _sl_tp(self, direction: str, entry: float, atr: float) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        sl_dist = SL_ATR_MULT * atr
        tp_dist = TP_SL_MULT * sl_dist
        if direction == "long":
            sl = entry - sl_dist
            tp = entry + tp_dist
        else:
            sl = entry + sl_dist
            tp = entry - tp_dist
        return sl, tp, sl_dist

    def _open_direction(self, direction: str, entry: float, sl: float, tp: float, margin: float) -> bool:
        if direction == "long":
            r = self._engine.open_long(
                entry_price=entry,
                margin_usdt=margin,
                leverage=LEVERAGE,
                stop_loss=sl,
                take_profit=tp,
                opened_by=self.name,
            )
        else:
            r = self._engine.open_short(
                entry_price=entry,
                margin_usdt=margin,
                leverage=LEVERAGE,
                stop_loss=sl,
                take_profit=tp,
                opened_by=self.name,
            )
        return bool(r.get("success"))

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe:
            return
        if self._model is None or ta is None:
            return

        df = (
            self._data_engine.get_completed_tf_candles(self.timeframe)
            if self._data_engine
            else None
        )
        if df is None or len(df) < MIN_BARS:
            return

        vec = last_feature_vector(df, min_bars=MIN_BARS)
        if vec is None:
            return

        if self._feature_names is not None:
            if list(self._feature_names) != list(FEATURE_NAMES):
                self._log("feature_names meta uyumsuz; vektör sırası FEATURE_NAMES kabul edildi.")

        pp = _proba_p0_p1(self._model, vec)
        if pp is None:
            return
        p0, p1 = pp
        desired = _desired_direction_v2(p0, p1)

        entry = self._safe_float(candle.get("close"))
        if entry <= 0:
            return

        atr = last_atr(df, min_bars=MIN_BARS)
        if atr is None or atr <= 0:
            return

        pos = self._engine.get_position()
        cur_dir: Optional[str] = None
        if pos is not None:
            cur_dir = pos.get("direction")

        if desired is None:
            return

        if cur_dir is not None:
            if cur_dir == desired:
                return
            cr = self._engine.close_position(entry)
            if not cr.get("closed"):
                self._log(f"Ters dönüş kapanamadı: {cr.get('message', cr)}")
                return

        sl, tp, sl_dist = self._sl_tp(desired, entry, atr)
        if sl is None or tp is None:
            return

        margin = self._margin_for_risk(entry, sl_dist)
        if margin is None:
            return

        ok = self._open_direction(desired, entry, sl, tp, margin)
        if ok:
            self._log(
                f"{'LONG' if desired == 'long' else 'SHORT'} p0={p0:.3f} p1={p1:.3f} "
                f"SL={sl:.2f} TP={tp:.2f} m={margin:.2f}"
            )
