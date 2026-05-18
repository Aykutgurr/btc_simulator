# -*- coding: utf-8 -*-
"""
OHLCV pencereleri (CNN) + triple-barrier etiketleri ile PyTorch eğitimi.
Kullanım: python train_ict_dl.py --csv btc_ohlcv.csv --tf 15m --out models/ict_cnn.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from train_ict_ml import (  # noqa: E402
    load_csv,
    resample_ohlcv,
    triple_barrier_labels,
)
from bots.ict_dl_model import ICTCNN, DEFAULT_WINDOW, normalize_window  # noqa: E402
from bots.ict_features import _atr, _ensure_ohlcv, MIN_BARS_DEFAULT  # noqa: E402


def build_windows(
    d: pd.DataFrame,
    window: int,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
    """X: (N, 5, window), y: (N,) — t anında pencere [t-window+1, t] dahil."""
    d = _ensure_ohlcv(d)
    n = len(d)
    atr_s = _atr(d["high"], d["low"], d["close"])
    atr_np = atr_s.values.astype(np.float64)
    close = d["close"].values
    high = d["high"].values
    low = d["low"].values
    o = d["open"].values
    h = d["high"].values
    l = d["low"].values
    c = d["close"].values
    v = d["volume"].values

    y_all = triple_barrier_labels(close, high, low, atr_np, horizon, 2.0)
    xs = []
    ys = []
    start = max(MIN_BARS_DEFAULT, window)
    for t in range(start, n):
        if t + horizon >= n:
            break
        w_o = o[t - window + 1 : t + 1]
        w_h = h[t - window + 1 : t + 1]
        w_l = l[t - window + 1 : t + 1]
        w_c = c[t - window + 1 : t + 1]
        w_v = v[t - window + 1 : t + 1]
        mat = np.stack([w_o, w_h, w_l, w_c, w_v], axis=0).astype(np.float32)
        xs.append(mat)
        ys.append(int(y_all[t]))
    if not xs:
        return None, None
    return np.stack(xs, axis=0), np.array(ys, dtype=np.int64)


def main() -> None:
    ap = argparse.ArgumentParser(description="ICT CNN (PyTorch) eğitimi")
    ap.add_argument("--csv", default="data/btc_ohlcv.csv")
    ap.add_argument("--tf", default="15m")
    ap.add_argument("--out", default="models/ict_cnn.pt")
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max-rows", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"CSV bulunamadı: {csv_path}")
        sys.exit(1)

    df = load_csv(str(csv_path))
    if args.max_rows and len(df) > args.max_rows:
        df = df.iloc[-args.max_rows :].copy()

    df = resample_ohlcv(df, args.tf)
    if len(df) < MIN_BARS_DEFAULT + args.window + args.horizon + 10:
        print("Yetersiz veri.")
        sys.exit(1)

    d = _ensure_ohlcv(df)
    X, y = build_windows(d, args.window, args.horizon)
    if X is None:
        print("Pencere oluşturulamadı.")
        sys.exit(1)

    # Zaman serisi: son %20 test
    n = len(y)
    split = int(n * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]

    def to_loader(Xa, ya, shuffle: bool):
        xt = torch.from_numpy(Xa)
        xt = normalize_window(xt)
        yt = torch.from_numpy(ya)
        ds = TensorDataset(xt, yt)
        return DataLoader(ds, batch_size=args.batch_size, shuffle=shuffle)

    train_loader = to_loader(X_tr, y_tr, True)
    test_loader = to_loader(X_te, y_te, False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ICTCNN(window=args.window, channels=5, n_classes=3).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    crit = nn.CrossEntropyLoss()

    for ep in range(args.epochs):
        model.train()
        total = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            logits = model(xb)
            loss = crit(logits, yb)
            loss.backward()
            opt.step()
            total += loss.item() * xb.size(0)
        print(f"epoch {ep+1}/{args.epochs} loss={total/len(X_tr):.4f}")

    model.eval()
    correct = 0
    tot = 0
    with torch.no_grad():
        for xb, yb in test_loader:
            xb, yb = xb.to(device), yb.to(device)
            pr = model(xb).argmax(dim=1)
            correct += (pr == yb).sum().item()
            tot += yb.size(0)
    print(f"Test accuracy: {correct/tot:.4f}" if tot else "no test")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state_dict": model.state_dict(),
        "window": args.window,
        "channels": 5,
        "n_classes": 3,
        "kind": "torch_cnn",
        "timeframe": args.tf,
        "horizon": args.horizon,
    }
    torch.save(payload, out_path)
    meta_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in payload.items() if k != "state_dict"}, f, indent=2)
    print(f"Kaydedildi: {out_path.resolve()}")


if __name__ == "__main__":
    main()
