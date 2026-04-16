import math
from typing import Dict, Optional
import pandas as pd
import numpy as np

class GeneratedBot:
    def __init__(self, trading_engine, data_engine=None):
        self.name = "ema bot"
        self.timeframe = "15m"
        self.data_engine = data_engine
        self.ema20 = None
        self.ema50 = None
        self.position_opened = False

    def on_timeframe_candle(self, timeframe: str, candle: Dict) -> None:
        if not isinstance(candle, dict):
            return
        
        # Check if we have the required data for EMA calculation
        if self.ema20 is None or self.ema50 is None:
            return

        # Calculate new EMA values
        new_ema20 = self.calculate_ema(self.ema20, candle['close'], 20)
        new_ema50 = self.calculate_ema(self.ema50, candle['close'], 50)

        # Update EMA values
        self.ema20 = new_ema20
        self.ema50 = new_ema50

        # Check for crossover signals
        if not self.position_opened:
            if new_ema20 > new_ema50 and candle['close'] < self.get_balance_usdt() * 0.01:
                self.open_long(candle['time'], candle['close'], 10, 0.001, 0.02, 'open_by_me')
            elif new_ema20 < new_ema50 and candle['close'] > self.get_balance_usdt() * 0.99:
                self.open_short(candle['time'], candle['close'], 10, 0.001, 0.02, 'open_by_me')

        # Update position parameters
        if self.position_opened:
            if new_ema20 < new_ema50 and candle['close'] > self.get_position()[2]:
                self.update_position_parameters(0.001, 0.02)
            elif new_ema20 > new_ema50 and candle['close'] < self.get_position()[3]:
                self.update_position_parameters(0.01, 0.03)

    def calculate_ema(self, previous_ema: float, current_price: float, period: int) -> float:
        try:
            return (previous_ema * (period - 1) + current_price) / period
        except ZeroDivisionError:
            return current_price

    def open_long(self, entry_time: str, entry_price: float, margin_usdt: float, leverage: int, stop_loss: float, take_profit: float, opened_by: str):
        self.trading_engine.open_long(entry_time, entry_price, margin_usdt, leverage, stop_loss, take_profit, opened_by)

    def open_short(self, entry_time: str, entry_price: float, margin_usdt: float, leverage: int, stop_loss: float, take_profit: float, opened_by: str):
        self.trading_engine.open_short(entry_time, entry_price, margin_usdt, leverage, stop_loss, take_profit, opened_by)

    def update_position_parameters(self, new_sl: float, new_tp: float):
        self.trading_engine.update_position_parameters(new_sl, new_tp)

    def get_balance_usdt(self) -> float:
        return self.trading_engine.get_balance_usdt()

    def get_position(self) -> tuple:
        return self.trading_engine.get_position()
