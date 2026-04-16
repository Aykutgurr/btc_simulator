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


def bot_system_prompt() -> str:
    return (
        "You are a senior Python quant developer. "
        "You must generate a single self-contained Python file that defines exactly ONE bot class "
        "compatible with this simulator. The code must be robust and conservative. "
        "Do not use network, file IO, subprocess, eval/exec, or OS operations. "
        "Only use these imports if needed: " + ", ".join(ALLOWED_IMPORTS) + ". "
        "If pandas_ta is missing, your bot must safely do nothing (return) instead of crashing."
    )


def bot_user_prompt(
    *,
    bot_name: str,
    timeframe: str,
    description: str,
    constraints: Optional[Dict[str, str]] = None,
) -> str:
    c = constraints or {}
    risk = c.get("risk", "Low risk. Never use >10% of balance as margin. Leverage <= 10.")
    notes = c.get("notes", "")

    return f"""
Generate a Python trading bot for a BTC futures simulator.

## Required interface (MUST FOLLOW)
- Create a class named `GeneratedBot` (exact).
- Provide class attributes:
  - name = "{bot_name}"
  - timeframe = "{timeframe}"
- __init__(self, trading_engine, data_engine=None)
- on_timeframe_candle(self, timeframe: str, candle: dict) -> None
  - When `self.timeframe == "1m"`: called on EVERY 1m candle (each tick).
  - When `self.timeframe in ("5m","15m","1h","4h")`: called only on timeframe-close events.
  - `candle` dict fields: time, open, high, low, close, volume (all numbers as floats).
  - You may call: data_engine.get_completed_tf_candles(self.timeframe) to obtain a pandas DataFrame of COMPLETED candles for that timeframe (may be None).

## TradingEngine API contract (DO NOT INVENT METHODS)
You MUST ONLY call these TradingEngine methods:
- get_position() -> dict|None
- get_balance_usdt() -> float
- get_available_balance() -> float
- open_long(entry_price, margin_usdt, leverage, stop_loss=None, take_profit=None, opened_by="...") -> dict
- open_short(entry_price, margin_usdt, leverage, stop_loss=None, take_profit=None, opened_by="...") -> dict
- close_position(exit_price) -> dict
- close_partial(exit_price, fraction=0.5) -> dict
- update_position_parameters(new_sl=None, new_tp=None) -> dict

## Indicators
Prefer using the built-in helper SDK to avoid missing-method bugs:
- from bot_sdk.indicators import EmaState
Do NOT call trading_engine.ema / trading_engine.rsi etc. Those do NOT exist.

## Safety rules (MUST FOLLOW)
- If a position is already open (trading_engine.get_position() is not None), do NOT open another one.
- Do not read position fields unless a position exists.
- Never do a "warmup return" that prevents indicators from ever initializing. Initialize/update indicator state first; only then decide to trade or return.
- Always set a reasonable stop_loss and take_profit when opening a position.

## Strategy description
{description.strip()}

## Risk constraints
{risk}

## Additional notes
{notes}

## Output format
Return ONLY a single Python code block:
```python
<full file contents>
```

Implementation guidance:
- Keep it deterministic and safe (try/except around indicator calculations).
- Require a warmup period for indicators (but ensure it eventually completes).
- Do not open a new position if one is already open.
- Always set stop loss and take profit if you open a position.
"""


def bot_repair_user_prompt(*, previous_code: str, error: str) -> str:
    return f"""
The previous bot code failed validation or import.

## Error
{error}

## Previous code
```python
{previous_code}
```

Fix the code. Requirements:
- Must define class `GeneratedBot`
- Must not use network/file/subprocess/eval/exec/os
- Must be robust (catch indicator errors)
- Must follow the TradingEngine API contract:
  - get_position(), get_balance_usdt(), get_available_balance()
  - open_long/open_short(..., stop_loss=None, take_profit=None, opened_by="...")
  - close_position(exit_price), close_partial(exit_price, fraction=0.5)
  - update_position_parameters(new_sl=None, new_tp=None)
- Do NOT invent methods like trading_engine.ema / close() / etc.
- Timeframe rule: if timeframe is "1m" it will be called every tick; otherwise only on tf close.
- Prefer indicators via: from bot_sdk.indicators import EmaState

Return ONLY a single Python code block with the full corrected file.
"""

