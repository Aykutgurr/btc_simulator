# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional


ALLOWED_IMPORTS = [
    "math",
    "statistics",
    "datetime",
    "typing",
    "pandas",
    "numpy",
    "pandas_ta",
    "bot_sdk",
]


def _developer_contract_block() -> str:
    """Technical simulator contract (not repeated in the user message)."""
    imports_line = ", ".join(ALLOWED_IMPORTS)
    return f"""
## Simulator contract (follow exactly)

### Output
- Return ONLY one markdown fenced block: ```python ... ``` containing the full file.
- Exactly one class named `GeneratedBot`.

### Class shape
- Class attributes: `name` (str), `timeframe` (str) — values are provided in the user message; embed them as string literals.
- `__init__(self, trading_engine, data_engine=None)` — store both on `self`.
- `on_timeframe_candle(self, timeframe: str, candle: dict) -> None`
  - If `self.timeframe == "1m"`: this method is invoked on every 1m step.
  - If `self.timeframe` is `5m`, `15m`, `1h`, or `4h`: invoked only when that timeframe bar **closes**.
  - `candle` keys: time, open, high, low, close, volume (float-like).
- Optional: `data_engine.get_completed_tf_candles(self.timeframe)` → pandas DataFrame of **completed** bars for that TF, or `None`. Use for indicators / history.

### TradingEngine — ONLY these methods exist
Never invent others (no `trading_engine.ema`, `close()`, etc.):
- `get_position()` → dict | None
- `get_balance_usdt()` → float
- `get_available_balance()` → float
- `open_long(entry_price, margin_usdt, leverage, stop_loss=None, take_profit=None, opened_by="...")` → dict
- `open_short(entry_price, margin_usdt, leverage, stop_loss=None, take_profit=None, opened_by="...")` → dict
- `close_position(exit_price)` → dict  **This is the ONLY way to fully close a position** (works for both long and short).
- `close_partial(exit_price, fraction=0.5)` → dict
- `update_position_parameters(new_sl=None, new_tp=None)` → dict
- `log_message(msg)` optional for debugging

**Forbidden on `self.trading_engine` (do not call — they do not exist):**  
`close_long`, `close_short`, `sell`, `buy`, `market_close`, `flatten`, `cancel_order`, `set_leverage`, `ema`, `rsi` (as methods), or any name not listed above.

### bot_sdk (only these submodules)
- `from bot_sdk.indicators import EmaState` — incremental: `state = EmaState(period=N); ema = state.update(float(close))` each bar. No `.run()`, do not pass a whole Series to `EmaState(...)`.
- `from bot_sdk.safe import get_position_fields`
- `from bot_sdk.utils import safe_get_position, safe_open_long, safe_open_short` (optional thin wrappers)
Do not `import` any other `bot_sdk.*` submodule.

### Allowed imports (stdlib / libs)
Only if needed: {imports_line}.
No network, file IO, subprocess, eval/exec, `__import__`, or `os`/`sys` usage in generated code.

### Safety
- If `get_position()` is not None, do not open a new position.
- Do not read position keys unless a position exists.
- Warm up indicators properly: update state each call; do not early-return forever before warmup can complete.
- Every `open_long` / `open_short` must include sensible `stop_loss` and `take_profit` when the strategy opens trades.
- If `pandas_ta` is used and unavailable at runtime, catch and return (no crash).

### Minimal structural example (illustrative only)
```python
class GeneratedBot:
    name = "…"
    timeframe = "15m"
    def __init__(self, trading_engine, data_engine=None):
        self.trading_engine = trading_engine
        self.data_engine = data_engine
    def on_timeframe_candle(self, timeframe: str, candle: dict) -> None:
        if timeframe != self.timeframe:
            return
        if self.trading_engine.get_position() is not None:
            return
        # df = self.data_engine.get_completed_tf_candles(self.timeframe) if self.data_engine else None
        # … implement user strategy …
```
"""


def bot_system_prompt() -> str:
    return (
        "You are a senior Python quant developer for a BTC futures **simulator**. "
        "Translate the user's **plain-language strategy** into working Python. "
        "The user is NOT a developer: they describe *what* to trade, not *how* to code APIs. "
        "You infer indicators, thresholds, and control flow from their description. "
        "Be conservative: if something is ambiguous, choose the safer interpretation (fewer trades, stricter filters).\n"
        + _developer_contract_block()
    )


def bot_user_prompt(
    *,
    bot_name: str,
    timeframe: str,
    description: str,
    constraints: Optional[Dict[str, str]] = None,
) -> str:
    c = constraints or {}
    risk = c.get("risk", "").strip()
    notes = c.get("notes", "").strip()

    extra = ""
    if risk:
        extra += f"\n### Risk / sizing hints (plain language)\n{risk}\n"
    if notes:
        extra += f"\n### Extra notes\n{notes}\n"

    return f"""
## Bot identity (use these exact literals in code)
- Class attribute `name` = "{bot_name}"
- Class attribute `timeframe` = "{timeframe}"

## User strategy (implement faithfully; user writes in everyday language — not code)
{description.strip()}
{extra}
Write the complete `GeneratedBot` file that realizes the strategy above. Do not ask clarifying questions; decide reasonable defaults yourself.
""".strip()


def bot_repair_user_prompt(*, previous_code: str, error: str) -> str:
    return f"""
The generated bot failed import, validation, or sandbox.

## Error
{error}

## Previous code
```python
{previous_code}
```

Fix the file. Keep class name `GeneratedBot`. Obey the same simulator contract:
- Only TradingEngine methods: get_position, get_balance_usdt, get_available_balance, open_long, open_short, close_position, close_partial, update_position_parameters, log_message.
- **Exit rule:** there is NO `close_long` / `close_short`. To close any side, call `close_position(exit_price)` with the current price (e.g. `float(candle["close"])`).
- `on_timeframe_candle`: skip unless `timeframe == self.timeframe`; no invented engine methods.
- `EmaState(period=N).update(price)` per bar only; bot_sdk submodules: indicators, safe, utils only.
- No os/sys/subprocess/network/file/eval/exec.

Return ONLY a single ```python ... ``` block with the full corrected file.
"""
