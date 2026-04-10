# -*- coding: utf-8 -*-
"""
Bot modülleri. get_bots() ile kayıtlı bot listesi döner.
"""

from typing import List, Any

from .test_bot import TestBot15m
from .test_bot_v2 import TestBotV2
from .ai_bot_mean_reversion import AIBot_MeanReversion
from .gemini_testbot import Gemini_TestBot
from .para_makinasi1 import ParaMakinasi1
from .deneme import AykutunSagTassagi
from .executioner_bot import ExecutionerBot
from .executioner_bot_v2 import ExecutionerBotV2
from .ict_ml_bot import ICT_ML_Bot
from .ml_bot_1 import ML_bot_1
from .msb_mtf_bot import MSB_MTF_Bot


def get_bots(trading_engine: Any, data_engine: Any = None) -> List[Any]:
    """Sistemde tanımlı bot örneklerini döner (trading_engine, isteğe bağlı data_engine)."""
    bots_list: List[Any] = [
        TestBot15m(trading_engine),
        TestBotV2(trading_engine),
        AIBot_MeanReversion(trading_engine),
        Gemini_TestBot(trading_engine),
    ]
    if data_engine is not None:
        bots_list.append(ParaMakinasi1(trading_engine, data_engine))
        bots_list.append(AykutunSagTassagi(trading_engine, data_engine))
        bots_list.append(ExecutionerBot(trading_engine, data_engine))
        bots_list.append(ExecutionerBotV2(trading_engine, data_engine))
        bots_list.append(ICT_ML_Bot(trading_engine, data_engine))
        bots_list.append(ML_bot_1(trading_engine, data_engine))
        bots_list.append(MSB_MTF_Bot(trading_engine, data_engine))
    return bots_list
