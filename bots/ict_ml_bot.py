# -*- coding: utf-8 -*-
"""
ICT özellikleri + XGBoost veya PyTorch CNN ile sinyal üreten bot.
Model: models/ict_xgb.joblib veya models/ict_cnn.pt (ICT_MODEL_PATH ile geçersiz kılınır).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None

from bots.ict_features import MIN_BARS_DEFAULT, last_feature_vector

DEFAULT_WINDOW = 64

# Executioner v2 ile uyumlu risk
ATR_LEN = 14
SL_ATR_MULT = 1.5
TP_ATR_MULT = 4.0
MARGIN_PCT_OF_BALANCE = 0.02
LEVERAGE = 5.0
MIN_MARGIN_USDT = 10.0
PROB_THRESHOLD = 0.42


def _resolve_model_path() -> Path:
    env = os.environ.get("ICT_MODEL_PATH")
    root = Path(__file__).resolve().parents[1]
    if env:
        return Path(env)
    xgb_p = root / "models" / "ict_xgb.joblib"
    pt_p = root / "models" / "ict_cnn.pt"
    if xgb_p.is_file():
        return xgb_p
    if pt_p.is_file():
        return pt_p
    return xgb_p


class ICT_ML_Bot:
    """
    ICT tabanlı özellikler + ML/DL çıkarımı.
    - .joblib: XGBoost (3 sınıf: 0 nötr, 1 long öncelik, 2 short öncelik)
    - .pt: ICTCNN aynı etiket şeması
    """

    name = "ICT_ML_Bot"
    timeframe = "15m"

    def __init__(self, trading_engine: Any, data_engine: Any):
        self._engine = trading_engine
        self._data_engine = data_engine
        self._model = None
        self._model_kind: Optional[str] = None
        self._torch_net = None
        self._build_window_tensor_from_df = None
        self._feature_names: Optional[List[str]] = None
        self._window = DEFAULT_WINDOW
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
        suf = path.suffix.lower()
        try:
            if suf == ".joblib" or path.name.endswith(".joblib"):
                import joblib

                payload = joblib.load(path)
                self._model = payload.get("model") if isinstance(payload, dict) else payload
                self._feature_names = payload.get("feature_names") if isinstance(payload, dict) else None
                self._model_kind = "xgboost"
                self._log(f"XGBoost model yüklendi: {path.name}")
            elif suf == ".pt":
                import torch
                from bots.ict_dl_model import ICTCNN, build_window_tensor_from_df

                ckpt = torch.load(path, map_location="cpu")
                w = int(ckpt.get("window", DEFAULT_WINDOW))
                self._window = w
                net = ICTCNN(window=w, channels=5, n_classes=3)
                net.load_state_dict(ckpt["state_dict"])
                net.eval()
                self._torch_net = net
                self._build_window_tensor_from_df = build_window_tensor_from_df
                self._model_kind = "torch_cnn"
                self._log(f"PyTorch CNN yüklendi: {path.name}")
            else:
                self._log(f"Desteklenmeyen model uzantısı: {path}")
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

    def _predict_probs(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        if self._model_kind == "xgboost" and self._model is not None:
            vec = last_feature_vector(df, min_bars=MIN_BARS_DEFAULT)
            if vec is None:
                return None
            X = vec.reshape(1, -1)
            if hasattr(self._model, "predict_proba"):
                return self._model.predict_proba(X)[0]
            return None
        if self._model_kind == "torch_cnn" and self._torch_net is not None:
            import torch

            if self._build_window_tensor_from_df is None:
                return None
            t = self._build_window_tensor_from_df(df, window=self._window)
            if t is None:
                return None
            with torch.no_grad():
                logits = self._torch_net(t)
                pr = torch.softmax(logits, dim=1)[0].numpy()
            return pr
        return None

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        if timeframe != self.timeframe:
            return
        if self._model_kind is None:
            return

        df = self._data_engine.get_completed_tf_candles(self.timeframe) if self._data_engine else None
        if df is None or len(df) < MIN_BARS_DEFAULT:
            return

        pos = self._engine.get_position()
        if pos is not None:
            return

        probs = self._predict_probs(df)
        if probs is None or len(probs) < 3:
            return
        pmax = float(np.max(probs))
        if pmax < PROB_THRESHOLD:
            return
        pred = int(np.argmax(probs))
        if pred == 0:
            return

        entry = self._safe_float(candle.get("close"))
        if entry <= 0:
            return

        atr = self._atr_last(df)
        if atr is None or atr <= 0:
            return

        balance = self._engine.get_balance_usdt()
        margin = balance * MARGIN_PCT_OF_BALANCE
        if margin < MIN_MARGIN_USDT:
            return

        if pred == 1:
            sl = entry - SL_ATR_MULT * atr
            tp = entry + TP_ATR_MULT * atr
            r = self._engine.open_long(
                entry_price=entry,
                margin_usdt=margin,
                leverage=LEVERAGE,
                stop_loss=sl,
                take_profit=tp,
                opened_by=self.name,
            )
            if r.get("success"):
                self._log(f"LONG p={probs.tolist()} SL={sl:.2f} TP={tp:.2f}")
        elif pred == 2:
            sl = entry + SL_ATR_MULT * atr
            tp = entry - TP_ATR_MULT * atr
            r = self._engine.open_short(
                entry_price=entry,
                margin_usdt=margin,
                leverage=LEVERAGE,
                stop_loss=sl,
                take_profit=tp,
                opened_by=self.name,
            )
            if r.get("success"):
                self._log(f"SHORT p={probs.tolist()} SL={sl:.2f} TP={tp:.2f}")
