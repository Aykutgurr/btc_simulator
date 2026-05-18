# -*- coding: utf-8 -*-
"""
ICT özellikleri + triple-barrier etiketleri ile XGBoost eğitimi.
Kullanım: python train_ict_ml.py --csv btc_ohlcv.csv --tf 15m --out models/ict_xgb.joblib
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

# Proje kökü
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bots.ict_features import (  # noqa: E402
    MIN_BARS_DEFAULT,
    FEATURE_NAMES,
    build_feature_matrix,
    _atr,
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
        df.index = pd.RangeIndex(len(df))
    else:
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


def triple_barrier_labels(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    atr: np.ndarray,
    horizon: int,
    k_atr: float,
) -> np.ndarray:
    """0 = zaman/önce dokunulmadı, 1 = üst bariyer önce, 2 = alt bariyer önce."""
    n = len(close)
    y = np.zeros(n, dtype=np.int32)
    for t in range(n):
        if t + horizon >= n:
            y[t] = 0
            continue
        a = atr[t]
        if not np.isfinite(a) or a <= 0:
            y[t] = 0
            continue
        entry = close[t]
        upper = entry + k_atr * a
        lower = entry - k_atr * a
        lbl = 0
        for k in range(1, horizon + 1):
            hi = high[t + k]
            lo = low[t + k]
            if hi >= upper:
                lbl = 1
                break
            if lo <= lower:
                lbl = 2
                break
        y[t] = lbl
    return y


def main() -> None:
    ap = argparse.ArgumentParser(description="ICT + XGBoost eğitimi")
    ap.add_argument("--csv", default="data/btc_ohlcv.csv", help="1m veya OHLCV CSV")
    ap.add_argument("--tf", default="15m", help="5m, 15m, 1h, 4h veya 1m")
    ap.add_argument("--out", default="models/ict_xgb.joblib", help="Çıktı model dosyası")
    ap.add_argument("--horizon", type=int, default=20, help="Triple-barrier ufuk (bar)")
    ap.add_argument("--k-atr", type=float, default=2.0, help="Bariyer çarpanı (ATR)")
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--max-rows", type=int, default=0, help="0 = tümü")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    try:
        import joblib
        from xgboost import XGBClassifier
    except ImportError as e:
        print("xgboost ve joblib gerekli:", e)
        sys.exit(1)

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"CSV bulunamadı: {csv_path}")
        sys.exit(1)

    df = load_csv(str(csv_path))
    if args.max_rows and len(df) > args.max_rows:
        df = df.iloc[-args.max_rows :].copy()

    df = resample_ohlcv(df, args.tf)
    if len(df) < MIN_BARS_DEFAULT + args.horizon + 10:
        print("Yetersiz veri.")
        sys.exit(1)

    d = _ensure_ohlcv(df)
    atr_series = _atr(d["high"], d["low"], d["close"])
    atr_np = atr_series.values.astype(np.float64)
    close = d["close"].values
    high = d["high"].values
    low = d["low"].values

    y_all = triple_barrier_labels(close, high, low, atr_np, args.horizon, args.k_atr)
    X, row_ix = build_feature_matrix(d, min_bars=MIN_BARS_DEFAULT)
    # Satır indeksleri ile etiketleri hizala; horizon sonrası geçersiz etiketleri at
    keep = []
    y_list = []
    for j, t in enumerate(row_ix):
        if t + args.horizon >= len(d):
            continue
        yt = int(y_all[t])
        keep.append(j)
        y_list.append(yt)
    if not keep:
        print("Etiket üretilemedi.")
        sys.exit(1)
    X = X[keep]
    y = np.array(y_list, dtype=np.int32)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=args.test_size, shuffle=False, random_state=None
    )

    clf = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        objective="multi:softprob",
        num_class=3,
        random_state=args.seed,
        n_jobs=-1,
        eval_metric="mlogloss",
    )
    clf.fit(X_tr, y_tr)
    pred = clf.predict(X_te)
    print(classification_report(y_te, pred, digits=4))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"model": clf, "feature_names": FEATURE_NAMES, "kind": "xgboost"}
    joblib.dump(payload, out_path)

    meta = {
        "feature_names": FEATURE_NAMES,
        "timeframe": args.tf,
        "horizon": args.horizon,
        "k_atr": args.k_atr,
        "csv": str(csv_path.resolve()),
        "n_samples": int(len(y)),
        "kind": "xgboost",
    }
    meta_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Model kaydedildi: {out_path.resolve()}")
    print(f"Meta: {meta_path.resolve()}")


if __name__ == "__main__":
    main()
