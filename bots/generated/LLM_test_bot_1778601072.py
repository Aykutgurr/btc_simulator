import pandas as pd
from bot_sdk.indicators import EmaState
from bot_sdk.trading_engine import TradingEngine

class GeneratedBot:
    name = "LLM test bot"
    timeframe = "15m"

    def __init__(self, trading_engine: TradingEngine, data_engine=None):
        self.engine = trading_engine
        self.data_engine = data_engine
        self.position = None
        self.prev_candle = None
        self.prev_ema12 = None
        self.prev_ema26 = None

    def on_timeframe_candle(self, timeframe: str, candle: dict) -> None:
        if timeframe != self.timeframe:
            return
        
        try:
            # Get completed 15m candles
            df = self.data_engine.get_completed_tf_candles("15m")
            
            if df is None or len(df) < 50:
                return
            
            # Calculate EMA12 and EMA26 if pandas_ta is available
            try:
                ema12, ema26 = df.ta.ema(length=12), df.ta.ema(length=26)
                self.prev_ema12, self.prev_ema26 = ema12.iloc[-2], ema26.iloc[-2]
            except AttributeError:
                pass

            # Check if position is open
            if self.position is not None:
                return
            
            # Get current candle's EMA values
            try:
                current_ema12, current_ema26 = df.ta.ema(length=12).iloc[-1], df.ta.ema(length=26).iloc[-1]
            except (AttributeError, IndexError):
                return

            # Check for crossover conditions
            if self.prev_ema12 is not None and self.prev_ema26 is not None:
                if current_ema12 > current_ema26 and self.prev_ema12 <= self.prev_ema26:
                    self.open_position("long")
                elif current_ema12 < current_ema26 and self.prev_ema12 >= self.prev_ema26:
                    self.open_position("short")

        except Exception as e:
            print(f"Error in on_timeframe_candle: {e}")

    def open_position(self, direction):
        balance = self.engine.get_balance_usdt()
        margin = min(balance * 0.05, 10)
        leverage = 10
        stop_loss = None
        take_profit = None

        if direction == "long":
            entry_price = candle["close"]
            stop_loss = entry_price - 0.015 * entry_price
            take_profit = entry_price + 0.025 * entry_price
        elif direction == "short":
            entry_price = candle["close"]
            stop_loss = entry_price + 0.015 * entry_price
            take_profit = entry_price - 0.025 * entry_price

        if self.engine.get_position() is None:
            position_info = self.engine.open_long(entry_price, margin, leverage, stop_loss, take_profit, opened_by="GeneratedBot")
            print(f"Opened {direction} position at {entry_price}")
        else:
            print("Position already open, not opening another one.")

    def on_tick(self, candle: dict) -> None:
        if self.timeframe != "1m":
            return
        # This method is a placeholder for the tick-based logic.
        # In this case, we do nothing as it's not required by the bot.
        pass

# Example usage (not part of the class):
# generated_bot = GeneratedBot(trading_engine)
# generated_bot.on_timeframe_candle("15m", candle_data)
