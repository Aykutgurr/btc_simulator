# -*- coding: utf-8 -*-
"""
Bot modülleri. get_bots() ile kayıtlı bot listesi döner.
"""

from typing import List, Any

from .test_bot import TestBot15m


def get_bots(trading_engine: Any) -> List[Any]:
    """Sistemde tanımlı bot örneklerini döner (trading_engine referansı ile)."""
    return [TestBot15m(trading_engine)]
