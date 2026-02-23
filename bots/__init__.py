# -*- coding: utf-8 -*-
"""
Bot modülleri. get_bots() ile kayıtlı bot listesi döner.
"""

from typing import List, Any

from .test_bot import TestBot15m
from .test_bot_v2 import TestBotV2
from .para_makinasi1 import ParaMakinasi1
from .aykutun_sag_tassagi import AykutunSagTassagi


def get_bots(trading_engine: Any, data_engine: Any = None) -> List[Any]:
    """Sistemde tanımlı bot örneklerini döner (trading_engine, isteğe bağlı data_engine)."""
    bots_list: List[Any] = [TestBot15m(trading_engine), TestBotV2(trading_engine)]
    if data_engine is not None:
        bots_list.append(ParaMakinasi1(trading_engine, data_engine))
        bots_list.append(AykutunSagTassagi(trading_engine, data_engine))
    return bots_list
