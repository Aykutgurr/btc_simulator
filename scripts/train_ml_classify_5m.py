# -*- coding: utf-8 -*-
"""
5m ML sınıflandırma: hedef t+3 yüksek mi, RF/XGB.
Kullanım:
  python train_ml_classify_5m.py --csv btc_ohlcv.csv --out models/ml_classify_5m.joblib --model xgboost
  python train_ml_classify_5m.py --csv ... --rolling --train-bars 10000 --test-bars 2000 --step 2000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, log_loss

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bots.ml_classify_5m_features import (  # noqa: E402
    FEATURE_NAMES,
    LABEL_HORIZON,
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


def make_classifier(model: str, seed: int):
    if model == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=seed,
            eval_metric="logloss",
            n_jobs=-1,
        )
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=20,
        random_state=seed,
        n_jobs=-1,
        class_weight="balanced",
    )


def rolling_train(
    X: np.ndarray,
    y: np.ndarray,
    train_bars: int,
    test_bars: int,
    step: int,
    model_name: str,
    seed: int,
) -> Tuple[List[float], List[float], object]:
    """Walk-forward: her pencerede fit, sonraki blokta skor. Son fold modeli döner."""
    accs: List[float] = []
    loglosses: List[float] = []
    last_clf = None
    i = 0
    while True:
        train_end = i + train_bars
        test_end = train_end + test_bars
        if test_end > len(X):
            break
        X_train = X[i:train_end]
        y_train = y[i:train_end]
        X_test = X[train_end:test_end]
        y_test = y[train_end:test_end]
        clf = make_classifier(model_name, seed)
        clf.fit(X_train, y_train)
        proba_test = clf.predict_proba(X_test)
        pred_test = clf.predict(X_test)
        accs.append(float(accuracy_score(y_test, pred_test)))
        try:
            ll = float(log_loss(y_test, proba_test))
            if np.isfinite(ll):
                loglosses.append(ll)
        except Exception:
            pass
        last_clf = clf
        i += step
    return accs, loglosses, last_clf


def main() -> None:
    p = argparse.ArgumentParser(description="5m ML sınıflandırma (t+3 hedef) eğitimi")
    p.add_argument("--csv", type=str, default="data/btc_ohlcv.csv")
    p.add_argument("--out", type=str, default="models/ml_classify_5m.joblib")
    p.add_argument("--tf", type=str, default="5m")
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--model", type=str, choices=("xgboost", "rf"), default="xgboost")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rolling", action="store_true", help="Walk-forward pencereleri")
    p.add_argument("--train-bars", type=int, default=10_000)
    p.add_argument("--test-bars", type=int, default=2000)
    p.add_argument("--step", type=int, default=0, help="0 ise test-bars ile aynı")
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

    X, y = build_training_xy(ohlcv, horizon=LABEL_HORIZON)
    if len(X) < 100:
        print("Eğitim için yetersiz örnek.")
        sys.exit(1)

    step = args.step if args.step > 0 else args.test_bars
    import joblib

    if args.rolling:
        accs, loglosses, clf = rolling_train(
            X, y, args.train_bars, args.test_bars, step, args.model, args.seed
        )
        if clf is None:
            print(
                "Rolling: hiç fold üretilemedi (train_bars + test_bars veri uzunluğundan küçük olmalı)."
            )
            sys.exit(1)
        mean_acc = float(np.mean(accs)) if accs else 0.0
        mean_ll = float(np.mean(loglosses)) if loglosses else float("nan")
        print(f"Rolling folds={len(accs)} mean_accuracy={mean_acc:.4f} mean_log_loss={mean_ll:.4f}")
        for k, a in enumerate(accs):
            print(f"  fold {k + 1}: accuracy={a:.4f}")
        meta = {
            "feature_names": FEATURE_NAMES,
            "timeframe": args.tf,
            "label_horizon": LABEL_HORIZON,
            "model_type": args.model,
            "mode": "rolling",
            "train_bars": args.train_bars,
            "test_bars": args.test_bars,
            "step": step,
            "rolling_folds": len(accs),
            "rolling_mean_accuracy": mean_acc,
            "rolling_mean_log_loss": mean_ll if np.isfinite(mean_ll) else None,
            "csv": str(csv_path),
            "min_bars": MIN_BARS,
            "prob_threshold": 0.55,
        }
    else:
        split = max(int(len(X) * (1.0 - args.test_size)), 1)
        if split >= len(X) - 5:
            split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        clf = make_classifier(args.model, args.seed)
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

        meta = {
            "feature_names": FEATURE_NAMES,
            "timeframe": args.tf,
            "label_horizon": LABEL_HORIZON,
            "model_type": args.model,
            "mode": "chronosplit",
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
            "accuracy_test": float(acc),
            "log_loss_test": float(ll) if np.isfinite(ll) else None,
            "csv": str(csv_path),
            "min_bars": MIN_BARS,
            "prob_threshold": 0.55,
        }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "feature_names": FEATURE_NAMES, "meta": meta}, out_path)
    meta_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Kaydedildi: {out_path}")


if __name__ == "__main__":
    main()
