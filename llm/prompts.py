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
  - Called only when that timeframe candle closes.
  - You can use data_engine.get_completed_tf_candles(self.timeframe) if data_engine provided.
  - Use trading_engine methods:
    - get_position(), get_balance_usdt(), get_available_balance()
    - open_long(entry_price, margin_usdt, leverage, stop_loss, take_profit, opened_by)
    - open_short(...)
    - update_position_parameters(new_sl, new_tp)

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
- Require a warmup period for indicators.
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

Return ONLY a single Python code block with the full corrected file.
"""

