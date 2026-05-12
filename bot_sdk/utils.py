# -*- coding: utf-8 -*-
"""
Thin wrappers around TradingEngine for LLM-generated bots.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def safe_get_position(engine: Any) -> Optional[Dict[str, Any]]:
    try:
        return engine.get_position()
    except Exception:
        return None


def safe_open_long(
    engine: Any,
    *,
    entry_price: float,
    margin_usdt: float,
    leverage: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    opened_by: str = "GeneratedBot",
) -> Dict[str, Any]:
    try:
        if engine.get_position() is not None:
            return {"success": False, "message": "A position is already open."}
        return engine.open_long(
            entry_price=float(entry_price),
            margin_usdt=float(margin_usdt),
            leverage=float(leverage),
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_by=opened_by or "GeneratedBot",
        )
    except Exception as e:
        return {"success": False, "message": str(e)}


def safe_open_short(
    engine: Any,
    *,
    entry_price: float,
    margin_usdt: float,
    leverage: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    opened_by: str = "GeneratedBot",
) -> Dict[str, Any]:
    try:
        if engine.get_position() is not None:
            return {"success": False, "message": "A position is already open."}
        return engine.open_short(
            entry_price=float(entry_price),
            margin_usdt=float(margin_usdt),
            leverage=float(leverage),
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_by=opened_by or "GeneratedBot",
        )
    except Exception as e:
        return {"success": False, "message": str(e)}
