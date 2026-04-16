# -*- coding: utf-8 -*-
"""
Sandbox runner for generated bots.

Runs in a separate Python process. Imports a bot file (must define GeneratedBot),
replays candles through a minimal engine, and outputs a JSON report to stdout.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from trading_engine import TradingEngine


TF_MAP = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h"}
TF_BARS = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}


class MiniDataEngine:
    def __init__(self, df_1m: pd.DataFrame):
        self._df_1m = df_1m
        self._index = 0

    def step(self) -> Optional[Tuple[Dict[str, Any], int, List[Tuple[str, Dict[str, Any]]]]]:
        if self._index >= len(self._df_1m):
            return None
        row = self._df_1m.iloc[self._index]
        ts = self._df_1m.index[self._index]
        candle = {
            "time": str(ts),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0.0)),
        }
        tf_closes = self._maybe_tf_closes(self._index)
        idx = self._index
        self._index += 1
        return candle, idx, tf_closes

    def _maybe_tf_closes(self, completed_1m_index: int) -> List[Tuple[str, Dict[str, Any]]]:
        out: List[Tuple[str, Dict[str, Any]]] = []
        for tf, n_bars in TF_BARS.items():
            if (completed_1m_index + 1) % n_bars != 0:
                continue
            start_i = completed_1m_index - n_bars + 1
            end_i = completed_1m_index + 1
            if start_i < 0 or end_i > len(self._df_1m):
                continue
            s = self._df_1m.iloc[start_i:end_i]
            candle_tf = {
                "time": str(s.index[-1]),
                "open": float(s.iloc[0]["open"]),
                "high": float(s["high"].max()),
                "low": float(s["low"].min()),
                "close": float(s.iloc[-1]["close"]),
                "volume": float(s["volume"].sum()) if "volume" in s.columns else 0.0,
            }
            out.append((tf, candle_tf))
        return out

    def get_completed_tf_candles(self, tf: str) -> Optional[pd.DataFrame]:
        if tf not in TF_MAP or self._index <= 0:
            return None
        slice_1m = self._df_1m.iloc[: self._index].copy()
        if slice_1m.empty:
            return None
        res = (
            slice_1m.resample(TF_MAP[tf])
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna(how="all")
        )
        n_bars = TF_BARS.get(tf, 1)
        if len(res) > 0 and n_bars > 1 and (len(slice_1m) % n_bars) != 0:
            res = res.iloc[:-1]
        return res if not res.empty else None


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    time_col = None
    for c in ("timestamp", "date", "datetime", "time"):
        if c in df.columns:
            time_col = c
            break
    if not time_col:
        raise ValueError("CSV has no timestamp/date/datetime/time column")
    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            raise ValueError("CSV missing OHLC columns")
    cols = [time_col, "open", "high", "low", "close"]
    if "volume" in df.columns:
        cols.append("volume")
    df = df[cols].copy()
    df["datetime"] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=["datetime"]).set_index("datetime").sort_index()
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df["volume"] = df["volume"].astype(float)
    df.index.name = "datetime"
    return df[["open", "high", "low", "close", "volume"]]


def import_bot(bot_path: Path):
    spec = importlib.util.spec_from_file_location(f"generated_{bot_path.stem}", str(bot_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load bot module spec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    cls = getattr(mod, "GeneratedBot", None)
    if cls is None:
        raise RuntimeError("Bot file must define GeneratedBot")
    return cls


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot-path", required=True)
    ap.add_argument("--csv-path", required=True)
    ap.add_argument("--max-steps", type=int, default=5000)
    args = ap.parse_args()

    bot_path = Path(args.bot_path).resolve()
    csv_path = Path(args.csv_path).resolve()
    max_steps = max(100, min(200000, int(args.max_steps)))

    df = load_csv(csv_path)
    engine = TradingEngine(initial_usdt=10_000.0)
    data = MiniDataEngine(df)

    BotCls = import_bot(bot_path)
    bot = BotCls(engine, data)

    logs: List[str] = []
    steps = 0
    while steps < max_steps:
        s = data.step()
        if s is None:
            break
        candle, idx, tf_closes = s
        steps += 1
        # engine price check
        closed = engine.check_price(float(candle["close"]))
        if closed and closed.get("record"):
            # no-op, record already stored
            pass
        # bots on tf close (5m/15m/1h/4h)
        for tf, candle_tf in tf_closes:
            try:
                bot.on_timeframe_candle(tf, candle_tf)
            except Exception as e:
                logs.append(f"[bot_error] {e}")
        # 1m: her adımda bir 1m mum kapanır; TF_BARS'ta 1m yoktu, aksi halde 1m botlar hiç çağrılmazdı
        if getattr(bot, "timeframe", None) == "1m":
            try:
                bot.on_timeframe_candle("1m", candle)
            except Exception as e:
                logs.append(f"[bot_error] {e}")
        for m in engine.get_and_clear_log_messages():
            logs.append(m.strip())

    hist = engine.get_trade_history()
    report = {
        "ok": True,
        "steps": steps,
        "stats": engine.get_stats(),
        "tradeHistorySample": hist[-20:],
        "logsTail": logs[-200:],
    }
    sys.stdout.write(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

