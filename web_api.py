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
import re
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Set, Tuple
import subprocess
import tempfile

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from trading_engine import TradingEngine
from bots import get_bots
from llm.client_ollama import OllamaClient
from llm.prompts import bot_system_prompt, bot_user_prompt, bot_repair_user_prompt

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
    return datetime.now().isoformat(timespec="seconds")


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

        self._bots = get_bots(self.trading, self.data)
        self._bot_state: Dict[str, BotState] = {}
        for b in self._bots:
            name = getattr(b, "name", str(b))
            tf = getattr(b, "timeframe", "15m")
            self._bot_state[name] = BotState(name=name, timeframe=tf, enabled=False)

        self._bot_logs: List[str] = []
        self._generated_registry_path = Path(__file__).resolve().parent / "generated_bots_registry.json"
        self._generated_dir = Path(__file__).resolve().parent / "bots" / "generated"
        self._generated_bots: Dict[str, Dict[str, Any]] = {}
        self._load_generated_registry()
        self._load_generated_bots_into_session()

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

    def _load_generated_bots_into_session(self) -> None:
        # Best-effort import + instantiate any previously generated bots.
        for bot_id, meta in list(self._generated_bots.items()):
            try:
                path = Path(meta.get("path", ""))
                if not path.is_absolute():
                    path = (Path(__file__).resolve().parent / path).resolve()
                bot = _import_generated_bot(path)
                if bot is None:
                    continue
                self._bots.append(bot)
                name = getattr(bot, "name", meta.get("name", bot_id))
                tf = getattr(bot, "timeframe", meta.get("timeframe", "15m"))
                if name not in self._bot_state:
                    self._bot_state[name] = BotState(name=name, timeframe=tf, enabled=bool(meta.get("enabled", False)))
            except Exception:
                continue

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


def _slugify(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^\w\- ]+", "", s, flags=re.UNICODE)
    s = s.replace(" ", "_")
    s = re.sub(r"_+", "_", s)
    return s[:60] or "bot"


def _extract_python_codeblock(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"```python\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if not m:
        return None
    code = m.group(1).strip()
    return code if code else None


def _syntax_check(code: str) -> Optional[str]:
    try:
        compile(code, "<generated_bot>", "exec")
        return None
    except Exception as e:
        return str(e)


def _validate_generated_bot_code(code: str) -> Optional[str]:
    """
    Best-effort static validation to prevent common LLM failures:
    - invented TradingEngine methods (e.g., trading_engine.ema, close(), etc.)
    - forbidden imports / unsafe modules
    """
    try:
        import ast
    except Exception:
        return None

    # Keep in sync with trading_engine.TradingEngine public API used by bots.
    allowed_engine_methods = {
        "get_position",
        "get_balance_usdt",
        "get_available_balance",
        "open_long",
        "open_short",
        "close_position",
        "close_partial",
        "update_position_parameters",
        "log_message",
    }

    forbidden_import_roots = {
        "os",
        "sys",
        "subprocess",
        "socket",
        "requests",
        "http",
        "urllib",
        "pathlib",
        "shutil",
        "importlib",
    }

    try:
        tree = ast.parse(code)
    except Exception as e:
        return f"AST parse failed: {e}"

    bad_engine_calls = set()
    bad_imports = set()
    uses_eval_exec = False

    for node in ast.walk(tree):
        # imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = (alias.name or "").split(".")[0]
                if root in forbidden_import_roots:
                    bad_imports.add(root)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0] if node.module else ""
            if root in forbidden_import_roots:
                bad_imports.add(root)

        # eval/exec
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "__import__"}:
                uses_eval_exec = True

        # trading_engine.<method>(...)
        if isinstance(node, ast.Attribute):
            # match self.trading_engine.<attr>
            v = node.value
            if (
                isinstance(v, ast.Attribute)
                and isinstance(v.value, ast.Name)
                and v.value.id == "self"
                and v.attr == "trading_engine"
            ):
                attr = node.attr
                if attr not in allowed_engine_methods:
                    bad_engine_calls.add(attr)

    problems = []
    if bad_imports:
        problems.append("Forbidden imports used: " + ", ".join(sorted(bad_imports)))
    if uses_eval_exec:
        problems.append("Forbidden builtins used: eval/exec/__import__")
    if bad_engine_calls:
        problems.append(
            "Invented TradingEngine methods: "
            + ", ".join(sorted(bad_engine_calls))
            + f". Allowed: {', '.join(sorted(allowed_engine_methods))}"
        )
    return "; ".join(problems) if problems else None


def _import_generated_bot(path: Path) -> Optional[Any]:
    try:
        import importlib.util

        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location(f"generated_{path.stem}", str(path))
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        cls = getattr(mod, "GeneratedBot", None)
        if cls is None:
            return None
        # Instantiate with (trading_engine, data_engine)
        return cls(SESSION.trading, SESSION.data)
    except Exception:
        return None


async def _run_sandbox_report_for_path(
    *,
    bot_path: Path,
    bot_id: str,
    df_1m: "pd.DataFrame",
    max_steps: int = 800,
    timeout: int = 20,
) -> Dict[str, Any]:
    """
    Run sandbox_runner.py and return its JSON report (or an error dict).
    Intended as a quick smoke test during generation/repair.
    """
    tmpdir = Path(tempfile.gettempdir())
    csv_path = tmpdir / f"btc_sim_sandbox_{bot_id}.csv"
    try:
        df_out = df_1m.reset_index().rename(columns={"datetime": "datetime"})
        df_out.to_csv(csv_path, index=False, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Failed to write sandbox csv: {e}"}

    max_steps = max(100, min(5000, int(max_steps)))
    timeout = max(5, min(180, int(timeout)))

    runner_path = (Path(__file__).resolve().parent / "sandbox_runner.py").resolve()
    cmd = [
        "python",
        str(runner_path),
        "--bot-path",
        str(bot_path),
        "--csv-path",
        str(csv_path),
        "--max-steps",
        str(max_steps),
    ]
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).resolve().parent),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Sandbox timeout"}
    except Exception as e:
        return {"ok": False, "error": f"Sandbox failed: {e}"}

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:4000]
        return {"ok": False, "error": f"Sandbox error: {err}"}

    try:
        report = json.loads(proc.stdout)
    except Exception:
        report = {"ok": False, "error": "Invalid sandbox JSON output", "raw": (proc.stdout or "")[:2000]}
    return report


def _sandbox_has_bot_errors(report: Dict[str, Any]) -> Optional[str]:
    try:
        tail = report.get("logsTail") or []
        for line in tail:
            if isinstance(line, str) and "[bot_error]" in line:
                return line
    except Exception:
        return None
    return None


def _relpath_to_repo(p: Path) -> str:
    try:
        root = Path(__file__).resolve().parent
        return str(p.resolve().relative_to(root))
    except Exception:
        return str(p)


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

    # Call Ollama (with auto-repair on common failures)
    client = OllamaClient()
    prompt = bot_user_prompt(
        bot_name=bot_name,
        timeframe=tf,
        description=body.description,
        constraints=body.constraints,
    )

    content = ""
    code = None
    last_error = None
    for attempt in range(1, 3):  # 1 initial + 1 repair
        try:
            content, _raw = await asyncio.to_thread(
                client.chat,
                [{"role": "user", "content": prompt}],
                system=bot_system_prompt(),
            )
        except Exception as e:
            last_error = f"LLM call failed: {e}"
            break

        code = _extract_python_codeblock(content)
        if not code:
            last_error = "No python code block returned by model."
            prompt = bot_repair_user_prompt(previous_code=content[:4000], error=last_error)
            await SESSION.ws_broadcast(
                {"type": "log", "message": f"[LLM] Repair attempt {attempt}: {last_error}"}
            )
            continue

        syn = _syntax_check(code)
        if syn:
            last_error = f"Syntax error: {syn}"
            prompt = bot_repair_user_prompt(previous_code=code, error=last_error)
            await SESSION.ws_broadcast(
                {"type": "log", "message": f"[LLM] Repair attempt {attempt}: {last_error}"}
            )
            code = None
            continue

        val = _validate_generated_bot_code(code)
        if val:
            last_error = f"Validation error: {val}"
            prompt = bot_repair_user_prompt(previous_code=code, error=last_error)
            await SESSION.ws_broadcast(
                {"type": "log", "message": f"[LLM] Repair attempt {attempt}: {last_error}"}
            )
            code = None
            continue

        # ok
        last_error = None
        break

    if last_error:
        SESSION.append_log(f"[LLM] {last_error}")
        await SESSION.ws_broadcast({"type": "log", "message": f"[LLM] {last_error}"})
        return {"ok": False, "compileOk": False, "error": last_error, "raw": content[:2000]}

    assert code is not None

    # Persist file
    SESSION._generated_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(bot_name)
    bot_id = f"{slug}_{int(datetime.now().timestamp())}"
    path = SESSION._generated_dir / f"{bot_id}.py"
    try:
        path.write_text(code + "\n", encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Failed to write file: {e}"}

    # Import and attach (with runtime smoke-test repair if market data is loaded)
    bot_obj = _import_generated_bot(path)
    for _attempt in range(2):  # initial + 1 repair (import/runtime)
        if bot_obj is None:
            err = "Import failed (GeneratedBot missing or runtime error)."
        else:
            err = None
            try:
                # Optional smoke test: if we have 1m data, run sandbox and repair on bot_error.
                df_ok = SESSION.data._df_1m is not None and not SESSION.data._df_1m.empty  # type: ignore[attr-defined]
                if df_ok:
                    df_smoke = SESSION.data._df_1m.copy()  # type: ignore[attr-defined]
                    report = await _run_sandbox_report_for_path(
                        bot_path=path, bot_id=bot_id, df_1m=df_smoke, max_steps=800, timeout=20
                    )
                    bot_err = _sandbox_has_bot_errors(report) if isinstance(report, dict) else None
                    if not report.get("ok", False) or bot_err:
                        err = f"Sandbox runtime error: {bot_err or report.get('error', 'unknown')}"
            except Exception as e:
                err = f"Sandbox smoke test failed: {e}"

        if not err:
            break

        await SESSION.ws_broadcast({"type": "log", "message": f"[LLM] Repair: {err}"})
        try:
            repair_prompt = bot_repair_user_prompt(previous_code=path.read_text(encoding='utf-8')[:6000], error=err)
            content2, _ = await asyncio.to_thread(
                client.chat,
                [{"role": "user", "content": repair_prompt}],
                system=bot_system_prompt(),
            )
            code2 = _extract_python_codeblock(content2) or ""
            syn2 = _syntax_check(code2) if code2 else "No code block"
            val2 = _validate_generated_bot_code(code2) if (not syn2 and code2) else None
            if syn2 or val2 or not code2:
                # keep prior error message; fall through
                bot_obj = None
            else:
                path.write_text(code2 + "\n", encoding="utf-8")
                bot_obj = _import_generated_bot(path)
        except Exception:
            bot_obj = None

    if bot_obj is None:
        return {"ok": False, "error": "Generated code failed to import/run after repair.", "path": str(path)}

    SESSION._bots.append(bot_obj)
    name = getattr(bot_obj, "name", bot_name)
    tff = getattr(bot_obj, "timeframe", tf)
    if name not in SESSION._bot_state:
        SESSION._bot_state[name] = BotState(name=name, timeframe=tff, enabled=False)

    SESSION._generated_bots[bot_id] = {
        "id": bot_id,
        "name": name,
        "timeframe": tff,
        "path": _relpath_to_repo(path),
        "enabled": False,
        "createdAt": _now_iso(),
        "lastTest": None,
    }
    SESSION._save_generated_registry()

    await SESSION.ws_broadcast({"type": "botGenerated", "botId": bot_id, "name": name, "timeframe": tff})
    await SESSION.ws_broadcast({"type": "log", "message": f"[LLM] Bot generated: {name} ({tff})"})
    return {"ok": True, "botId": bot_id, "path": str(path), "compileOk": True}


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

    tmpdir = Path(tempfile.gettempdir())
    csv_path = tmpdir / f"btc_sim_sandbox_{body.botId}.csv"
    try:
        df_out = df.reset_index().rename(columns={"datetime": "datetime"})
        df_out.to_csv(csv_path, index=False, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Failed to write sandbox csv: {e}"}

    max_steps = int(body.maxSteps or 5000)
    max_steps = max(100, min(200000, max_steps))
    timeout = int(body.timeoutSec or 20)
    timeout = max(5, min(180, timeout))

    SESSION.append_log(f"[LLM] Testing bot {body.botId} (steps={max_steps})")
    await SESSION.ws_broadcast({"type": "log", "message": f"[LLM] Testing bot {body.botId} (steps={max_steps})"})

    runner_path = (Path(__file__).resolve().parent / "sandbox_runner.py").resolve()
    cmd = [
        "python",
        str(runner_path),
        "--bot-path",
        str(bot_path),
        "--csv-path",
        str(csv_path),
        "--max-steps",
        str(max_steps),
    ]
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).resolve().parent),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Sandbox timeout"}
    except Exception as e:
        return {"ok": False, "error": f"Sandbox failed: {e}"}

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:4000]
        return {"ok": False, "error": f"Sandbox error: {err}"}

    try:
        report = json.loads(proc.stdout)
    except Exception:
        report = {"ok": False, "error": "Invalid sandbox JSON output", "raw": (proc.stdout or "")[:2000]}

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

