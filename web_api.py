# -*- coding: utf-8 -*-
"""
FastAPI backend for btc_simulator web frontend.

Implements a minimal REST + WebSocket contract that matches
`btc-simulator-web-frontend/src/api/client.ts` and `wsClient.ts`.

Run:
  python web_api.py
"""

from __future__ import annotations

import asyncio
import json
import os
import traceback
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from trading_engine import TradingEngine
from bots import get_bots
from llm.generated_bot_pipeline import (
    generate_and_register_bot,
    now_iso,
    run_sandbox_report_sync,
)

try:
    import pandas_ta as ta  # type: ignore
except Exception:
    ta = None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers / data engine (PyQt-free)
# ──────────────────────────────────────────────────────────────────────────────

TF_MAP = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h"}
TF_BARS = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}
SPEED_PRESETS: Dict[str, Tuple[int, int]] = {
    "1x": (500, 1),
    "10x": (50, 1),
    "100x": (16, 1),
    "Max Hız": (16, 50),
}


def _now_iso() -> str:
    return now_iso()


def _safe_dt_str(s: Any) -> str:
    try:
        return str(s)
    except Exception:
        return ""


class WebDataEngine:
    """Headless 1m stream with resample helpers used by bots and frontend."""

    def __init__(self):
        self._df_1m: Optional[pd.DataFrame] = None
        self._index = 0  # next row to emit
        self._current_candle: Optional[Dict[str, Any]] = None
        self._timeframe = "1m"

    # Loading
    def load_csv(self, path: str, start: Optional[datetime] = None, end: Optional[datetime] = None) -> bool:
        if not path or not os.path.isfile(path):
            return False
        try:
            df = pd.read_csv(path)
            req = {"open", "high", "low", "close"}
            time_col = None
            for c in ("timestamp", "date", "datetime", "time"):
                if c in df.columns:
                    time_col = c
                    break
            if not time_col or not req.issubset(df.columns):
                return False
            cols = [time_col, "open", "high", "low", "close"]
            if "volume" in df.columns:
                cols.append("volume")
            df = df[cols].copy()
            df = df.dropna(subset=["open", "high", "low", "close"])
            df["datetime"] = pd.to_datetime(df[time_col], errors="coerce")
            df = df.dropna(subset=["datetime"])
            df = df.set_index("datetime").sort_index()
            for col in ("open", "high", "low", "close"):
                df[col] = df[col].astype(float)
            if "volume" not in df.columns:
                df["volume"] = 0.0
            df["volume"] = df["volume"].astype(float)
            if start is not None:
                df = df[df.index >= pd.Timestamp(start)]
            if end is not None:
                df = df[df.index <= pd.Timestamp(end)]
            if df.empty:
                return False
            self._df_1m = df[["open", "high", "low", "close", "volume"]].copy()
            self._index = 0
            self._current_candle = None
            return True
        except Exception:
            return False

    def load_from_dataframe(self, df: pd.DataFrame) -> bool:
        try:
            if df is None or df.empty:
                return False
            df = df.copy()
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                df.index = pd.to_datetime(df.index, errors="coerce")
                df = df[df.index.notna()]
            for col in ("open", "high", "low", "close"):
                if col not in df.columns:
                    return False
            if "volume" not in df.columns:
                df["volume"] = 0.0
            self._df_1m = df[["open", "high", "low", "close", "volume"]].astype(float).copy()
            self._df_1m.index.name = "datetime"
            self._index = 0
            self._current_candle = None
            return True
        except Exception:
            return False

    def generate_mock_data(self, num_bars: int = 800) -> None:
        """Generate 1m mock OHLCV for demo/testing."""
        import numpy as np

        num_bars = int(max(100, min(50000, num_bars)))
        base_price = 40000.0
        np.random.seed(42)
        returns = np.random.randn(num_bars) * 0.01
        close = base_price * np.exp(np.cumsum(returns))
        open_ = np.roll(close, 1)
        open_[0] = base_price
        high = np.maximum(open_, close) * (1 + np.abs(np.random.randn(num_bars) * 0.005))
        low = np.minimum(open_, close) * (1 - np.abs(np.random.randn(num_bars) * 0.005))
        times = pd.date_range(start="2025-01-01", periods=num_bars, freq="1min")
        self._df_1m = pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(10, 1000, size=num_bars),
            },
            index=times,
        )
        self._df_1m.index.name = "datetime"
        self.reset()

    # Playback
    def has_data(self) -> bool:
        return self._df_1m is not None and len(self._df_1m) > 0

    def reset(self) -> None:
        self._index = 0
        self._current_candle = None

    def prime(self, n: int = 200) -> None:
        """Advance pointer so UI has initial candles before playback."""
        if self._df_1m is None or self._df_1m.empty:
            self.reset()
            return
        n = int(max(0, min(len(self._df_1m), n)))
        self._index = n
        if n <= 0:
            self._current_candle = None
            return
        row = self._df_1m.iloc[n - 1]
        ts = self._df_1m.index[n - 1]
        self._current_candle = {
            "time": _safe_dt_str(ts),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0.0)),
        }

    def set_timeframe(self, tf: str) -> None:
        if tf in TF_MAP or tf == "1m":
            self._timeframe = tf

    def get_timeframe(self) -> str:
        return self._timeframe

    def get_current_price(self) -> Optional[float]:
        return None if self._current_candle is None else float(self._current_candle.get("close", 0.0))

    def get_current_index(self) -> int:
        return max(0, self._index - 1) if self._current_candle is not None else 0

    def step(self) -> Optional[Tuple[Dict[str, Any], int, List[Tuple[str, Dict[str, Any]]]]]:
        """
        Emit next 1m candle. Returns (candle, index, tf_closes[]).
        tf_closes is a list of (tf, candle_tf) for completed 5m/15m/1h/4h closes.
        """
        if self._df_1m is None or self._index >= len(self._df_1m):
            return None
        candle, idx = self._emit_current()
        tf_closes: List[Tuple[str, Dict[str, Any]]] = self._maybe_timeframe_closes(idx)
        self._index += 1
        return candle, idx, tf_closes

    def _emit_current(self) -> Tuple[Dict[str, Any], int]:
        assert self._df_1m is not None
        row = self._df_1m.iloc[self._index]
        ts = self._df_1m.index[self._index]
        candle = {
            "time": _safe_dt_str(ts),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0.0)),
        }
        self._current_candle = candle
        return candle, self._index

    def _maybe_timeframe_closes(self, completed_1m_index: int) -> List[Tuple[str, Dict[str, Any]]]:
        out: List[Tuple[str, Dict[str, Any]]] = []
        if self._df_1m is None or completed_1m_index < 0:
            return out
        for tf, n_bars in TF_BARS.items():
            if (completed_1m_index + 1) % n_bars != 0:
                continue
            start_i = completed_1m_index - n_bars + 1
            end_i = completed_1m_index + 1
            if start_i < 0 or end_i > len(self._df_1m):
                continue
            s = self._df_1m.iloc[start_i:end_i]
            candle_tf = {
                "time": _safe_dt_str(s.index[-1]),
                "open": float(s.iloc[0]["open"]),
                "high": float(s["high"].max()),
                "low": float(s["low"].min()),
                "close": float(s.iloc[-1]["close"]),
                "volume": float(s["volume"].sum()) if "volume" in s.columns else 0.0,
            }
            out.append((tf, candle_tf))
        return out

    # Resample helpers (frontend + bots)
    def get_display_candles(self) -> List[Dict[str, Any]]:
        if self._df_1m is None or self._index <= 0:
            return []
        slice_1m = self._df_1m.iloc[: self._index].copy()
        if slice_1m.empty:
            return []
        tf = self._timeframe
        if tf == "1m":
            out: List[Dict[str, Any]] = []
            for ts, row in slice_1m.iterrows():
                out.append(
                    {
                        "time": _safe_dt_str(ts),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row.get("volume", 0.0)),
                    }
                )
            return out
        freq = TF_MAP.get(tf, "1min")
        res = (
            slice_1m.resample(freq)
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna(how="all")
        )
        out: List[Dict[str, Any]] = []
        for ts, row in res.iterrows():
            out.append(
                {
                    "time": _safe_dt_str(ts),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0.0)),
                }
            )
        return out

    def get_completed_tf_candles(self, tf: str) -> Optional[pd.DataFrame]:
        if self._df_1m is None or self._index <= 0 or tf not in TF_MAP:
            return None
        slice_1m = self._df_1m.iloc[: self._index].copy()
        if slice_1m.empty or len(slice_1m) < 2:
            return None
        freq = TF_MAP.get(tf, "1min")
        n_bars = TF_BARS.get(tf, 1)
        res = (
            slice_1m.resample(freq)
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna(how="all")
        )
        if len(res) > 0 and n_bars > 1 and (len(slice_1m) % n_bars) != 0:
            res = res.iloc[:-1]
        return res if not res.empty else None


# ──────────────────────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class BotState:
    name: str
    timeframe: str
    enabled: bool = False


class Session:
    def __init__(self):
        self.session_id = f"session-{_now_iso()}"
        self.data = WebDataEngine()
        self.trading = TradingEngine(initial_usdt=10_000.0)
        self.timeframe = "1m"
        self.speed_ms = 100
        self.speed_preset = "10x"
        self.is_playing = False

        self.dataset = {"source": "mock", "csvPath": None, "start": "", "end": ""}

        self._ws_clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._play_task: Optional[asyncio.Task] = None

        self._bot_logs: List[str] = []
        self._generated_registry_path = Path(__file__).resolve().parent / "generated_bots_registry.json"
        self._generated_dir = Path(__file__).resolve().parent / "bots" / "generated"
        self._generated_bots: Dict[str, Dict[str, Any]] = {}
        self._load_generated_registry()

        self._bots = get_bots(self.trading, self.data)
        self._bot_state = {}
        for b in self._bots:
            name = getattr(b, "name", str(b))
            tf = getattr(b, "timeframe", "15m")
            self._bot_state[name] = BotState(name=name, timeframe=tf, enabled=False)
        self._sync_bot_state_from_generated_registry()

    def _sync_bot_state_from_generated_registry(self) -> None:
        """Registry'deki enabled bayraklarını mevcut BotState ile hizalar."""
        for _bot_id, meta in self._generated_bots.items():
            name = meta.get("name")
            if not name or name not in self._bot_state:
                continue
            self._bot_state[name].enabled = bool(meta.get("enabled", False))

    def _load_generated_registry(self) -> None:
        try:
            if self._generated_registry_path.is_file():
                data = json.loads(self._generated_registry_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._generated_bots = data
        except Exception:
            self._generated_bots = {}

    def _save_generated_registry(self) -> None:
        try:
            self._generated_registry_path.write_text(
                json.dumps(self._generated_bots, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    async def ws_add(self, ws: WebSocket) -> None:
        async with self._lock:
            self._ws_clients.add(ws)

    async def ws_remove(self, ws: WebSocket) -> None:
        async with self._lock:
            self._ws_clients.discard(ws)

    async def ws_broadcast(self, payload: Dict[str, Any]) -> None:
        msg = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            clients = list(self._ws_clients)
        if not clients:
            return
        dead: List[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._ws_clients.discard(ws)

    def bots_response(self) -> List[Dict[str, Any]]:
        return [
            {"name": b.name, "timeframe": b.timeframe, "enabled": self._bot_state[b.name].enabled}
            for b in self._bot_state.values()
        ]

    def append_log(self, message: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        self._bot_logs.append(line)
        self._bot_logs = self._bot_logs[-200:]

    def flush_engine_logs_to_session(self) -> List[str]:
        msgs = self.trading.get_and_clear_log_messages()
        out: List[str] = []
        for m in msgs:
            s = m.strip()
            if not s:
                continue
            self.append_log(s)
            out.append(s)
        return out

    async def _handle_tick(self) -> None:
        # Advance one candle and emit WS events
        step = self.data.step()
        if step is None:
            self.is_playing = False
            return
        candle, index, tf_closes = step

        # trading engine: check SL/TP/liquidation
        closed = self.trading.check_price(float(candle["close"]))
        if closed:
            await self.ws_broadcast({"type": "tradeClosed", "record": closed["record"]})
            await self.ws_broadcast(
                {
                    "type": "stats",
                    "stats": self.trading.get_stats(),
                    "balanceUsdt": self.trading.get_balance_usdt(),
                    "position": self.trading.get_position(),
                }
            )

        # Bots on timeframe close
        for tf, candle_tf in tf_closes:
            for bot in self._bots:
                name = getattr(bot, "name", None)
                if not name:
                    continue
                st = self._bot_state.get(name)
                if not st or not st.enabled or st.timeframe != tf:
                    continue
                try:
                    bot.on_timeframe_candle(tf, candle_tf)
                except Exception:
                    pass
            await self.ws_broadcast({"type": "tfClose", "timeframe": tf, "candle": candle_tf})

        # 1m botlar: her tick bir 1m mum; yüksek TF kapanış listesinde 1m yok
        for bot in self._bots:
            name = getattr(bot, "name", None)
            if not name:
                continue
            st = self._bot_state.get(name)
            if not st or not st.enabled or st.timeframe != "1m":
                continue
            try:
                bot.on_timeframe_candle("1m", candle)
            except Exception:
                pass

        # Stream candle
        await self.ws_broadcast({"type": "candle", "candle": candle, "index": index})

        # Bot logs (from trading engine)
        new_logs = self.flush_engine_logs_to_session()
        for m in new_logs:
            await self.ws_broadcast({"type": "log", "message": m})

    async def play_loop(self) -> None:
        try:
            while self.is_playing:
                await self._handle_tick()
                await asyncio.sleep(max(0.01, self.speed_ms / 1000.0))
        finally:
            self.is_playing = False

    async def ensure_play_task(self) -> None:
        if self._play_task is None or self._play_task.done():
            self._play_task = asyncio.create_task(self.play_loop())


SESSION = Session()


# ──────────────────────────────────────────────────────────────────────────────
# External data fetchers (yfinance / ccxt) - adapted from startup_dialog.py
# ──────────────────────────────────────────────────────────────────────────────


YFINANCE_1M_MAX_DAYS_PER_REQUEST = 7


def _fetch_yfinance_1m(start: datetime, end: datetime) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        from datetime import timedelta

        ticker = yf.Ticker("BTC-USD")
        chunks = []
        current = start
        part = 0
        while current < end:
            part += 1
            chunk_end = current + timedelta(days=YFINANCE_1M_MAX_DAYS_PER_REQUEST)
            if chunk_end > end:
                chunk_end = end
            start_str = current.strftime("%Y-%m-%d")
            end_str = (chunk_end + timedelta(days=1)).strftime("%Y-%m-%d")
            df_chunk = ticker.history(start=start_str, end=end_str, interval="1m")
            if df_chunk is not None and not df_chunk.empty:
                df_chunk = df_chunk.rename(
                    columns={
                        "Open": "open",
                        "High": "high",
                        "Low": "low",
                        "Close": "close",
                        "Volume": "volume",
                    }
                )
                keep = ["open", "high", "low", "close", "volume"]
                df_chunk = df_chunk[keep].copy()
                df_chunk.index = pd.to_datetime(df_chunk.index)
                df_chunk = df_chunk[(df_chunk.index >= pd.Timestamp(start)) & (df_chunk.index <= pd.Timestamp(end))]
                if not df_chunk.empty:
                    chunks.append(df_chunk)
            current = chunk_end + timedelta(days=1)
        if not chunks:
            return None
        df = pd.concat(chunks, axis=0)
        df = df[~df.index.duplicated(keep="first")]
        df = df.sort_index()
        df.index.name = "datetime"
        if len(df) < 10:
            return None
        return df
    except Exception:
        return None


def _expand_to_1m(df: pd.DataFrame, minutes_per_bar: int) -> pd.DataFrame:
    if df is None or df.empty or minutes_per_bar < 2:
        return df
    rows: List[Dict[str, Any]] = []
    for ts, row in df.iterrows():
        t = pd.Timestamp(ts)
        vol_each = float(row.get("volume", 0.0)) / float(minutes_per_bar)
        for i in range(minutes_per_bar):
            t_i = t + pd.Timedelta(minutes=i)
            rows.append(
                {
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": vol_each,
                    "datetime": t_i,
                }
            )
    out = pd.DataFrame(rows)
    out = out.set_index("datetime").sort_index()
    out.index.name = "datetime"
    return out


def _fetch_yfinance_interval(start: datetime, end: datetime, interval: str, minutes_per_bar: int) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        from datetime import timedelta

        ticker = yf.Ticker("BTC-USD")
        start_str = start.strftime("%Y-%m-%d")
        end_str = (end.date() + timedelta(days=1)).strftime("%Y-%m-%d")
        df = ticker.history(start=start_str, end=end_str, interval=interval)
        if df is None or df.empty or len(df) < 2:
            return None
        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.to_datetime(df.index)
        df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        if df.empty or len(df) < 2:
            return None
        df_1m = _expand_to_1m(df, minutes_per_bar)
        df_1m = df_1m[(df_1m.index >= pd.Timestamp(start)) & (df_1m.index <= pd.Timestamp(end))]
        if df_1m.empty or len(df_1m) < 10:
            return None
        return df_1m
    except Exception:
        return None


def _fetch_ccxt_1m(start: datetime, end: datetime) -> Optional[pd.DataFrame]:
    try:
        import ccxt

        exchange = ccxt.binance({"enableRateLimit": True})
        since = int(pd.Timestamp(start).timestamp() * 1000)
        end_ts = int(pd.Timestamp(end).timestamp() * 1000)
        all_ohlcv: List[List[Any]] = []
        while since < end_ts:
            ohlcv = exchange.fetch_ohlcv("BTC/USDT", "1m", since=since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 60_000
            if len(ohlcv) < 1000:
                break
        if not all_ohlcv:
            return None
        df = pd.DataFrame(all_ohlcv, columns=["datetime", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
        df = df.set_index("datetime").sort_index()
        df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        if df.empty or len(df) < 10:
            return None
        df.index.name = "datetime"
        return df
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# API models
# ──────────────────────────────────────────────────────────────────────────────


class LoadSessionBody(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    source: str = Field(..., description="csv|yfinance|ccxt|mock")
    csvPath: Optional[str] = None


class SetTimeframeBody(BaseModel):
    timeframe: str


class SetSpeedBody(BaseModel):
    preset: Optional[str] = None
    speedMs: Optional[int] = None


class FastForwardBody(BaseModel):
    batchSize: Optional[int] = None


class OpenTradeBody(BaseModel):
    direction: str  # long|short
    entryPrice: float
    marginUsdt: float
    leverage: float
    stopLoss: Optional[float] = None
    takeProfit: Optional[float] = None
    openedBy: Optional[str] = "Manuel"


class CloseTradeBody(BaseModel):
    exitPrice: float


class UpdateTradeBody(BaseModel):
    stopLoss: Optional[float] = None
    takeProfit: Optional[float] = None


class ClosePartialBody(BaseModel):
    exitPrice: float
    fraction: float = Field(0.5, ge=0.01, le=0.99)


class ToggleBotBody(BaseModel):
    name: str
    enabled: bool


# ──────────────────────────────────────────────────────────────────────────────
# LLM bot generation models
# ──────────────────────────────────────────────────────────────────────────────


class LlmGenerateBotBody(BaseModel):
    name: str
    timeframe: str
    description: str
    constraints: Optional[Dict[str, str]] = None


class LlmTestBotBody(BaseModel):
    botId: str
    maxSteps: Optional[int] = 5000
    timeoutSec: Optional[int] = 20


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────────────────────────────────────


app = FastAPI(title="btc_simulator web api", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/session")
async def get_session():
    # If no data loaded yet, try default csv in repo root
    if not SESSION.data.has_data():
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "btc_ohlcv.csv")
        if os.path.isfile(csv_path):
            SESSION.data.load_csv(csv_path)
            SESSION.dataset = {"source": "csv", "csvPath": csv_path, "start": "", "end": ""}
        else:
            SESSION.data.generate_mock_data(800)
            SESSION.dataset = {"source": "mock", "csvPath": None, "start": "", "end": ""}
        SESSION.data.prime(200)
    # dataset start/end best-effort
    start = ""
    end = ""
    if SESSION.data._df_1m is not None and not SESSION.data._df_1m.empty:  # type: ignore[attr-defined]
        start = _safe_dt_str(SESSION.data._df_1m.index.min())  # type: ignore[attr-defined]
        end = _safe_dt_str(SESSION.data._df_1m.index.max())  # type: ignore[attr-defined]
    ds = dict(SESSION.dataset)
    ds["start"] = ds.get("start") or start
    ds["end"] = ds.get("end") or end
    return {
        "sessionId": SESSION.session_id,
        "dataset": ds,
        "playback": {"timeframe": SESSION.timeframe, "speedMs": SESSION.speed_ms, "preset": SESSION.speed_preset},
        "connection": {"ws": True},
    }


@app.post("/api/session/load")
async def load_session(body: LoadSessionBody):
    # Supports: mock, csv, yfinance, ccxt
    if body.source == "mock":
        # Just reset; if csv exists use it, else keep empty (frontend can still show UI)
        SESSION.data.reset()
        SESSION.trading.reset()
        SESSION.dataset = {"source": "mock", "csvPath": None, "start": body.startDate or "", "end": body.endDate or ""}
        if not SESSION.data.has_data():
            SESSION.data.generate_mock_data(800)
        SESSION.data.prime(200)
        return {"ok": True}

    if body.source == "csv":
        path = body.csvPath or os.path.join(os.path.dirname(os.path.abspath(__file__)), "btc_ohlcv.csv")
        start = datetime.fromisoformat(body.startDate) if body.startDate else None
        end = datetime.fromisoformat(body.endDate) if body.endDate else None
        ok = SESSION.data.load_csv(path, start=start, end=end)
        if not ok:
            return {"ok": False}
        SESSION.data.reset()
        SESSION.data.prime(200)
        SESSION.trading.reset()
        SESSION.dataset = {"source": "csv", "csvPath": path, "start": body.startDate or "", "end": body.endDate or ""}
        return {"ok": True}

    # Parse date range (best effort)
    start = None
    end = None
    try:
        start = datetime.fromisoformat(body.startDate) if body.startDate else None
    except Exception:
        start = None
    try:
        end = datetime.fromisoformat(body.endDate) if body.endDate else None
    except Exception:
        end = None
    if start is None:
        start = datetime(2025, 1, 1)
    if end is None:
        end = datetime.now()
    if end < start:
        start, end = end, start

    if body.source == "yfinance":
        # Try 1m first; fallback to 5m/15m/1h expanded into 1m
        df = await asyncio.to_thread(_fetch_yfinance_1m, start, end)
        if df is None or df.empty:
            for interval, minutes in [("5m", 5), ("15m", 15), ("1h", 60)]:
                df = await asyncio.to_thread(_fetch_yfinance_interval, start, end, interval, minutes)
                if df is not None and not df.empty:
                    break
        if df is None or df.empty:
            return {"ok": False}
        ok = SESSION.data.load_from_dataframe(df)
        if not ok:
            return {"ok": False}
        SESSION.data.prime(200)
        SESSION.trading.reset()
        SESSION.dataset = {"source": "yfinance", "csvPath": None, "start": start.isoformat(), "end": end.isoformat()}
        return {"ok": True}

    if body.source == "ccxt":
        df = await asyncio.to_thread(_fetch_ccxt_1m, start, end)
        if df is None or df.empty:
            return {"ok": False}
        ok = SESSION.data.load_from_dataframe(df)
        if not ok:
            return {"ok": False}
        SESSION.data.prime(200)
        SESSION.trading.reset()
        SESSION.dataset = {"source": "ccxt", "csvPath": None, "start": start.isoformat(), "end": end.isoformat()}
        return {"ok": True}

    return {"ok": False}


@app.post("/api/playback/play")
async def playback_play():
    SESSION.is_playing = True
    await SESSION.ensure_play_task()
    return {"ok": True}


@app.post("/api/playback/pause")
async def playback_pause():
    SESSION.is_playing = False
    return {"ok": True}


@app.post("/api/playback/step")
async def playback_step():
    await SESSION._handle_tick()
    return {"ok": True}


@app.post("/api/playback/fast-forward")
async def playback_fast_forward(body: FastForwardBody):
    batch = int(body.batchSize or 100)
    batch = max(1, min(10000, batch))
    for _ in range(batch):
        await SESSION._handle_tick()
        if SESSION.data._df_1m is None:  # type: ignore[attr-defined]
            break
        if SESSION.data._index >= len(SESSION.data._df_1m):  # type: ignore[attr-defined]
            break
    return {"ok": True}


@app.post("/api/playback/timeframe")
async def playback_timeframe(body: SetTimeframeBody):
    SESSION.timeframe = body.timeframe
    SESSION.data.set_timeframe(body.timeframe)
    return {"ok": True}


@app.post("/api/playback/speed")
async def playback_speed(body: SetSpeedBody):
    if body.preset and body.preset in SPEED_PRESETS:
        SESSION.speed_preset = body.preset
        ms, _ = SPEED_PRESETS[body.preset]
        SESSION.speed_ms = int(ms)
    if body.speedMs is not None:
        SESSION.speed_ms = int(max(10, min(2000, body.speedMs)))
    return {"ok": True}


@app.get("/api/market/state")
async def market_state():
    candles = SESSION.data.get_display_candles()
    current = SESSION.data._current_candle
    indicators: Dict[str, Any] = {}
    if candles:
        try:
            close = pd.Series([float(c["close"]) for c in candles])
            if ta is not None and len(close) >= 15:
                rsi = ta.rsi(close, length=14)
                if rsi is not None:
                    indicators["rsi"] = rsi.fillna(method="bfill").fillna(method="ffill").fillna(50).tolist()
            if ta is not None and len(close) >= 26 + 9:
                macd_df = ta.macd(close, fast=12, slow=26, signal=9)
                if macd_df is not None and hasattr(macd_df, "columns") and len(macd_df.columns) >= 2:
                    macd = macd_df[macd_df.columns[0]].fillna(0).tolist()
                    signal = macd_df[macd_df.columns[1]].fillna(0).tolist()
                    indicators["macd"] = {"macd": macd, "signal": signal}
            if ta is not None and len(close) >= 50:
                ema20 = ta.ema(close, length=20)
                ema50 = ta.ema(close, length=50)
                if ema20 is not None:
                    indicators["ema20"] = ema20.fillna(method="bfill").fillna(method="ffill").tolist()
                if ema50 is not None:
                    indicators["ema50"] = ema50.fillna(method="bfill").fillna(method="ffill").tolist()
            # Fallback EMA if pandas-ta missing
            if "ema20" not in indicators and len(close) >= 20:
                indicators["ema20"] = close.ewm(span=20, adjust=False).mean().tolist()
            if "ema50" not in indicators and len(close) >= 50:
                indicators["ema50"] = close.ewm(span=50, adjust=False).mean().tolist()
        except Exception:
            indicators = {}

    # Equity curve: from trade history balances + current mark-to-market as last point
    equity_x: List[float] = []
    equity_y: List[float] = []
    try:
        hist = SESSION.trading.get_trade_history()
        for i, r in enumerate(hist):
            equity_x.append(float(i))
            equity_y.append(float(r.get("bakiye", 0.0)))
        if current is not None:
            eq = float(SESSION.trading.get_equity_at_price(float(current.get("close", 0.0))))
            equity_x.append(float(len(equity_x)))
            equity_y.append(eq)
    except Exception:
        equity_x, equity_y = [], []
    return {
        "index": SESSION.data.get_current_index(),
        "currentCandle": current,
        "displayCandles": candles,
        "indicators": indicators,
        "equity": {"x": equity_x, "y": equity_y},
    }


@app.get("/api/trade/state")
async def trade_state():
    return {
        "balanceUsdt": SESSION.trading.get_balance_usdt(),
        "availableBalance": SESSION.trading.get_available_balance(),
        "position": SESSION.trading.get_position(),
        "stats": SESSION.trading.get_stats(),
        "tradeHistory": SESSION.trading.get_trade_history(),
    }


@app.post("/api/trade/open")
async def trade_open(body: OpenTradeBody):
    if body.direction not in ("long", "short"):
        return {"success": False, "message": "direction long|short olmalı"}
    if body.direction == "long":
        res = SESSION.trading.open_long(
            entry_price=body.entryPrice,
            margin_usdt=body.marginUsdt,
            leverage=body.leverage,
            stop_loss=body.stopLoss,
            take_profit=body.takeProfit,
            opened_by=body.openedBy or "Manuel",
        )
    else:
        res = SESSION.trading.open_short(
            entry_price=body.entryPrice,
            margin_usdt=body.marginUsdt,
            leverage=body.leverage,
            stop_loss=body.stopLoss,
            take_profit=body.takeProfit,
            opened_by=body.openedBy or "Manuel",
        )
    if res.get("success"):
        await SESSION.ws_broadcast(
            {
                "type": "stats",
                "stats": SESSION.trading.get_stats(),
                "balanceUsdt": SESSION.trading.get_balance_usdt(),
                "position": SESSION.trading.get_position(),
            }
        )
    return res


@app.post("/api/trade/close")
async def trade_close(body: CloseTradeBody):
    res = SESSION.trading.close_position(body.exitPrice)
    if res.get("closed"):
        await SESSION.ws_broadcast({"type": "tradeClosed", "record": res["record"]})
        await SESSION.ws_broadcast(
            {
                "type": "stats",
                "stats": SESSION.trading.get_stats(),
                "balanceUsdt": SESSION.trading.get_balance_usdt(),
                "position": SESSION.trading.get_position(),
            }
        )
        return {"closed": True, "record": res["record"]}
    return {"closed": False}


@app.post("/api/trade/update")
async def trade_update(body: UpdateTradeBody):
    res = SESSION.trading.update_position_parameters(new_sl=body.stopLoss, new_tp=body.takeProfit)
    if res.get("success"):
        await SESSION.ws_broadcast(
            {
                "type": "stats",
                "stats": SESSION.trading.get_stats(),
                "balanceUsdt": SESSION.trading.get_balance_usdt(),
                "position": SESSION.trading.get_position(),
            }
        )
    return res


@app.post("/api/trade/close-partial")
async def trade_close_partial(body: ClosePartialBody):
    res = SESSION.trading.close_partial(body.exitPrice, fraction=body.fraction)
    # close_partial returns {"partial": True, "record": ..., "position": ...}
    if res.get("partial") and res.get("record"):
        await SESSION.ws_broadcast({"type": "tradeClosed", "record": res["record"]})
        await SESSION.ws_broadcast(
            {
                "type": "stats",
                "stats": SESSION.trading.get_stats(),
                "balanceUsdt": SESSION.trading.get_balance_usdt(),
                "position": SESSION.trading.get_position(),
            }
        )
        return {"partial": True, "record": res["record"], "position": res.get("position")}
    return {"partial": False}


@app.get("/api/bots")
async def bots_list():
    return {"bots": SESSION.bots_response()}


@app.post("/api/bots/toggle")
async def bots_toggle(body: ToggleBotBody):
    st = SESSION._bot_state.get(body.name)
    if st is None:
        return {"success": False}
    st.enabled = bool(body.enabled)
    # Persist enable flag for generated bots (by name match)
    try:
        for bot_id, meta in SESSION._generated_bots.items():
            if meta.get("name") == body.name:
                meta["enabled"] = st.enabled
                SESSION._generated_bots[bot_id] = meta
        SESSION._save_generated_registry()
    except Exception:
        pass
    SESSION.append_log(f"[Bots] {body.name} => {'ON' if st.enabled else 'OFF'}")
    await SESSION.ws_broadcast({"type": "log", "message": f"[Bots] {body.name} => {'ON' if st.enabled else 'OFF'}"})
    return {"success": True}


@app.get("/api/logs")
async def logs_list():
    return {"botLogs": SESSION._bot_logs}


# ──────────────────────────────────────────────────────────────────────────────
# LLM bot generation endpoints
# ──────────────────────────────────────────────────────────────────────────────


@app.get("/api/llm/bots")
async def llm_bots_list():
    items = []
    for bot_id, meta in SESSION._generated_bots.items():
        items.append(
            {
                "id": bot_id,
                "name": meta.get("name", bot_id),
                "timeframe": meta.get("timeframe", ""),
                "path": meta.get("path", ""),
                "enabled": bool(meta.get("enabled", False)),
                "createdAt": meta.get("createdAt", ""),
                "lastTest": meta.get("lastTest"),
            }
        )
    return {"bots": items}


@app.post("/api/llm/bots/generate")
async def llm_bots_generate(body: LlmGenerateBotBody):
    bot_name = (body.name or "").strip()
    if not bot_name:
        return {"ok": False, "error": "name required"}
    tf = (body.timeframe or "").strip()
    if tf not in TF_MAP and tf != "1m":
        return {"ok": False, "error": "invalid timeframe"}

    SESSION.append_log(f"[LLM] Generating bot: {bot_name} ({tf})")
    await SESSION.ws_broadcast({"type": "log", "message": f"[LLM] Generating bot: {bot_name} ({tf})"})

    df_smoke = None
    try:
        if SESSION.data._df_1m is not None and not SESSION.data._df_1m.empty:  # type: ignore[attr-defined]
            df_smoke = SESSION.data._df_1m.copy()  # type: ignore[attr-defined]
    except Exception:
        pass

    gen = partial(
        generate_and_register_bot,
        SESSION.trading,
        SESSION.data,
        bot_name=bot_name,
        timeframe=tf,
        description=body.description,
        constraints=body.constraints,
        df_1m_for_sandbox=df_smoke,
    )
    res = await asyncio.to_thread(gen)

    if not res.get("ok"):
        err = res.get("error", "unknown")
        SESSION.append_log(f"[LLM] {err}")
        await SESSION.ws_broadcast({"type": "log", "message": f"[LLM] {err}"})
        return {
            "ok": False,
            "compileOk": bool(res.get("compileOk", False)),
            "error": err,
            "raw": (res.get("raw") or "")[:2000],
        }

    bot_obj = res["bot"]
    bot_id = res["botId"]
    name = res["name"]
    tff = res["timeframe"]
    path = res["path"]

    SESSION._bots.append(bot_obj)
    if name not in SESSION._bot_state:
        SESSION._bot_state[name] = BotState(name=name, timeframe=tff, enabled=False)
    SESSION._generated_bots[bot_id] = res["entry"]
    SESSION._save_generated_registry()

    await SESSION.ws_broadcast({"type": "botGenerated", "botId": bot_id, "name": name, "timeframe": tff})
    await SESSION.ws_broadcast({"type": "log", "message": f"[LLM] Bot generated: {name} ({tff})"})
    return {"ok": True, "botId": bot_id, "path": path, "compileOk": True}


@app.post("/api/llm/bots/test")
async def llm_bots_test(body: LlmTestBotBody):
    meta = SESSION._generated_bots.get(body.botId)
    if not meta:
        return {"ok": False, "error": "Unknown botId"}
    bot_path = Path(meta.get("path", ""))
    if not bot_path.is_absolute():
        bot_path = (Path(__file__).resolve().parent / bot_path).resolve()
    if not bot_path.is_file():
        return {"ok": False, "error": "Bot file missing"}

    if SESSION.data._df_1m is None or SESSION.data._df_1m.empty:  # type: ignore[attr-defined]
        return {"ok": False, "error": "No market data loaded"}
    df = SESSION.data._df_1m.copy()  # type: ignore[attr-defined]

    max_steps = int(body.maxSteps or 5000)
    max_steps = max(100, min(200000, max_steps))
    timeout = int(body.timeoutSec or 20)
    timeout = max(5, min(180, timeout))

    SESSION.append_log(f"[LLM] Testing bot {body.botId} (steps={max_steps})")
    await SESSION.ws_broadcast({"type": "log", "message": f"[LLM] Testing bot {body.botId} (steps={max_steps})"})

    run = partial(
        run_sandbox_report_sync,
        bot_path=bot_path,
        bot_id=body.botId,
        df_1m=df,
        max_steps=max_steps,
        timeout=timeout,
    )
    report = await asyncio.to_thread(run)

    meta["lastTest"] = report
    SESSION._generated_bots[body.botId] = meta
    SESSION._save_generated_registry()

    await SESSION.ws_broadcast({"type": "botTestReport", "botId": body.botId, "report": report})
    return {"ok": True, "report": report}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    await SESSION.ws_add(ws)
    try:
        while True:
            # frontend doesn't send messages; keep alive by receiving if any
            await ws.receive_text()
    except WebSocketDisconnect:
        await SESSION.ws_remove(ws)
    except Exception:
        await SESSION.ws_remove(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_api:app", host="0.0.0.0", port=8000, reload=False)

