from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import math


def ema_from_prices(prices: Iterable[float], period: int) -> Optional[float]:
    """
    Calculate EMA from a finite list/iterable of prices.
    Returns None if there isn't enough data or period invalid.
    """
    try:
        p = int(period)
    except Exception:
        return None
    if p <= 1:
        return None
    prices_list = [float(x) for x in prices if x is not None]
    if len(prices_list) < p:
        return None
    k = 2.0 / (p + 1.0)
    ema = sum(prices_list[:p]) / float(p)
    for v in prices_list[p:]:
        ema = (v * k) + (ema * (1.0 - k))
    return float(ema)


def ema_update(prev_ema: Optional[float], price: float, period: int) -> Optional[float]:
    """
    Incremental EMA update. If prev_ema is None, returns None (caller should warm up).
    """
    try:
        p = int(period)
        x = float(price)
    except Exception:
        return None
    if p <= 1 or not math.isfinite(x):
        return None
    if prev_ema is None:
        return None
    k = 2.0 / (p + 1.0)
    return float((x * k) + (prev_ema * (1.0 - k)))


@dataclass
class EmaState:
    """
    Helper state for incremental EMA with warmup via SMA.
    """

    period: int
    value: Optional[float] = None
    _count: int = 0
    _sum: float = 0.0

    def update(self, price: float) -> Optional[float]:
        try:
            x = float(price)
        except Exception:
            return self.value
        if not math.isfinite(x):
            return self.value

        p = int(self.period)
        if p <= 1:
            return self.value

        if self.value is None:
            self._count += 1
            self._sum += x
            if self._count < p:
                return None
            self.value = self._sum / float(p)
            return float(self.value)

        self.value = ema_update(self.value, x, p)
        return float(self.value) if self.value is not None else None

