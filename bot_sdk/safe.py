from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def get_position_fields(position: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[float]]:
    """
    Convenience unpack for common position fields.
    Returns: (direction, entry_price, stop_loss, take_profit)
    """
    if not position:
        return None, None, None, None
    direction = position.get("direction")
    entry = position.get("entry_price")
    sl = position.get("stop_loss")
    tp = position.get("take_profit")
    try:
        entry_f = float(entry) if entry is not None else None
    except Exception:
        entry_f = None
    try:
        sl_f = float(sl) if sl is not None else None
    except Exception:
        sl_f = None
    try:
        tp_f = float(tp) if tp is not None else None
    except Exception:
        tp_f = None
    return direction, entry_f, sl_f, tp_f

