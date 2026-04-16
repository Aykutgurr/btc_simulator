import pandas as pd
import numpy as np

class GeneratedBot:
    def __init__(self, trading_engine, data_engine=None):
        self.name = "ema bot_1m"
        self.timeframe = "1m"
        self.trading_engine = trading_engine
        self.data_engine = data_engine
        self.ema20 = None
        self.ema50 = None

    def on_timeframe_candle(self, timeframe: str, candle: dict) -> None:
        if self.ema20 is None or self.ema50 is None:
            # Warm up period for indicators
            return
        
        # Get completed TF candles from data engine (if provided)
        completed_candles = self.data_engine.get_completed_tf_candles(self.timeframe) if self.data_engine else []
        
        # Update EMA values
        self.ema20 = self.trading_engine.ema(candle['high'], candle['low'], 20, completed_candles)
        self.ema50 = self.trading_engine.ema(candle['high'], candle['low'], 50, completed_candles)

        # Check for crossover signals
        if self.ema20 > self.ema50:
            # Open BUY trade
            entry_price = candle['close']
            margin_usdt = self.trading_engine.get_balance_usdt() * 0.01  # 1% of balance as margin
            leverage = 10
            stop_loss = self.trading_engine.get_position()['stop_loss'] + (entry_price - self.ema20) * 0.02  # 2% of entry price as stop loss
            take_profit = self.trading_engine.get_position()['take_profit'] + (self.ema50 - entry_price) * 0.02  # 2% of entry price as take profit
            opened_by = 'bot'
            self.trading_engine.open_long(entry_price, margin_usdt, leverage, stop_loss, take_profit, opened_by)
        elif self.ema20 < self.ema50:
            # Open SELL trade
            entry_price = candle['close']
            margin_usdt = self.trading_engine.get_balance_usdt() * 0.01  # 1% of balance as margin
            leverage = 10
            stop_loss = self.trading_engine.get_position()['stop_loss'] + (entry_price - self.ema50) * 0.02  # 2% of entry price as stop loss
            take_profit = self.trading_engine.get_position()['take_profit'] + (self.ema20 - entry_price) * 0.02  # 2% of entry price as take profit
            opened_by = 'bot'
            self.trading_engine.open_short(entry_price, margin_usdt, leverage, stop_loss, take_profit, opened_by)

        # Update position parameters
        if self.trading_engine.get_position():
            new_sl = self.trading_engine.get_position()['stop_loss']
            new_tp = self.trading_engine.get_position()['take_profit']
            self.trading_engine.update_position_parameters(new_sl, new_tp)
        
        # Close trade when EMA 20 crosses below EMA 50
        if self.ema20 < self.ema50:
            entry_price = self.trading_engine.get_position()['entry_price']
            exit_price = candle['close']
            profit_loss = (exit_price - entry_price) * 0.02  # 2% of entry price as profit/loss
            self.trading_engine.close(self.trading_engine.get_position(), profit_loss)
        
        # Close trade when EMA 20 crosses above EMA 50
        if self.ema20 > self.ema50:
            entry_price = self.trading_engine.get_position()['entry_price']
            exit_price = candle['close']
            loss_profit = (exit_price - entry_price) * 0.02  # 2% of entry price as profit/loss
            self.trading_engine.close(self.trading_engine.get_position(), loss_profit)
