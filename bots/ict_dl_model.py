# -*- coding: utf-8 -*-
"""ICT CNN: OHLCV penceresi üzerinden 3 sınıf (triple-barrier ile uyumlu)."""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn

DEFAULT_WINDOW = 64


class ICTCNN(nn.Module):
    def __init__(
        self,
        window: int = DEFAULT_WINDOW,
        channels: int = 5,
        n_classes: int = 3,
    ):
        super().__init__()
        self.window = window
        self.channels = channels
        self.n_classes = n_classes
        self.conv = nn.Sequential(
            nn.Conv1d(channels, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, n_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.conv(x))


def normalize_window(x: "torch.Tensor") -> torch.Tensor:
    """x: (B, C, L) — kanal bazlı z-score."""
    mean = x.mean(dim=-1, keepdim=True)
    std = x.std(dim=-1, keepdim=True).clamp(min=1e-6)
    return (x - mean) / std


def numpy_window_to_tensor(arr: "torch.Tensor") -> torch.Tensor:
    """arr: (B, C, L) float32"""
    return normalize_window(arr)


def build_window_tensor_from_df(
    df,
    window: int = DEFAULT_WINDOW,
) -> Optional[torch.Tensor]:
    """
    Son 'window' mumdan (1,5,window) tensör: open, high, low, close, volume.
    Yetersiz veri ise None.
    """
    import numpy as np

    d = df.copy()
    d.columns = [c.lower() for c in d.columns]
    if len(d) < window:
        return None
    sl = d.iloc[-window:]
    o = sl["open"].astype(float).values
    h = sl["high"].astype(float).values
    l = sl["low"].astype(float).values
    c = sl["close"].astype(float).values
    v = sl["volume"].astype(float).values if "volume" in sl.columns else np.zeros(window)
    x = np.stack([o, h, l, c, v], axis=0).astype(np.float32)
    t = torch.from_numpy(x).unsqueeze(0)
    return numpy_window_to_tensor(t)
