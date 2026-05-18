# -*- coding: utf-8 -*-
"""
ML_bot_1: 5m mum, ikili sınıf (sonraki mum yukarı), RF veya XGBoost.
Kullanım: python train_ml_bot_1.py --csv btc_ohlcv.csv --out models/ml_bot_1.joblib --model xgboost
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, log_loss
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bots.ml_bot_1_features import (  # noqa: E402
    FEATURE_NAMES,
    MIN_BARS,
    build_training_xy,
    _ensure_ohlcv,
)

TF_MAP = {"5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h"}


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    time_col = None
    for c in df.columns:
        if c.lower() in ("datetime", "date", "time", "timestamp"):
            time_col = c
            break
    if time_col is None:
        raise ValueError("CSV'de datetime/timestamp kolonu gerekli.")
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col])
    df = df.set_index(time_col)
    return _ensure_ohlcv(df)


def resample_ohlcv(df: pd.DataFrame, tf_key: str) -> pd.DataFrame:
    if tf_key == "1m":
        return df
    freq = TF_MAP.get(tf_key)
    if not freq:
        raise ValueError(f"Bilinmeyen TF: {tf_key}")
    o = df.resample(freq).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return o.dropna(how="any")


def main() -> None:
    p = argparse.ArgumentParser(description="ML_bot_1 model eğitimi")
    p.add_argument("--csv", type=str, default="data/btc_ohlcv.csv")
    p.add_argument("--out", type=str, default="models/ml_bot_1.joblib")
    p.add_argument("--tf", type=str, default="5m")
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--model", type=str, choices=("xgboost", "rf"), default="xgboost")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"Dosya yok: {csv_path}")
        sys.exit(1)

    raw = load_csv(str(csv_path))
    ohlcv = resample_ohlcv(raw, args.tf)
    if len(ohlcv) < MIN_BARS + 50:
        print(f"Yetersiz veri: {len(ohlcv)} satır (min ~{MIN_BARS + 50})")
        sys.exit(1)

    X, y = build_training_xy(ohlcv)
    if len(X) < 100:
        print("Eğitim için yetersiz örnek.")
        sys.exit(1)

    split = max(int(len(X) * (1.0 - args.test_size)), 1)
    if split >= len(X) - 5:
        split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    if args.model == "xgboost":
        from xgboost import XGBClassifier

        clf = XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=args.seed,
            eval_metric="logloss",
            n_jobs=-1,
        )
    else:
        from sklearn.ensemble import RandomForestClassifier

        clf = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=20,
            random_state=args.seed,
            n_jobs=-1,
            class_weight="balanced",
        )

    clf.fit(X_train, y_train)
    proba_test = clf.predict_proba(X_test)
    pred_test = clf.predict(X_test)
    acc = accuracy_score(y_test, pred_test)
    try:
        ll = log_loss(y_test, proba_test)
    except Exception:
        ll = float("nan")

    print(classification_report(y_test, pred_test, digits=4))
    print(f"accuracy={acc:.4f} log_loss={ll:.4f}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    import joblib

    meta = {
        "feature_names": FEATURE_NAMES,
        "timeframe": args.tf,
        "model_type": args.model,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "accuracy_test": float(acc),
        "log_loss_test": float(ll) if np.isfinite(ll) else None,
        "csv": str(csv_path),
        "min_bars": MIN_BARS,
    }
    joblib.dump({"model": clf, "feature_names": FEATURE_NAMES, "meta": meta}, out_path)
    meta_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Kaydedildi: {out_path}")


if __name__ == "__main__":
    main()
