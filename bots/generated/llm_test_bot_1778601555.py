import pandas as pd
from bot_sdk.indicators import EmaState
from bot_sdk.utils import safe_get_position, safe_open_long, safe_open_short

class GeneratedBot:
    name = "llm test bot"
    timeframe = "15m"

    def __init__(self, trading_engine, data_engine=None):
        self.trading_engine = trading_engine
        self.data_engine = data_engine
        self.position = None
        self.prev_ema12 = None
        self.prev_ema26 = None

    def on_timeframe_candle(self, timeframe: str, candle: dict) -> None:
        if timeframe != "15m":
            return

        completed_candles = self.data_engine.get_completed_tf_candles("15m")
        if completed_candles is None or len(completed_candles) < 50:
            return

        try:
            ema12, ema26 = EmaState(close=completed_candles.close).run()
        except Exception as e:
            print(f"Error calculating EMAs: {e}")
            return

        if self.position is not None:
            return

        last_close = candle["close"]
        if self.prev_ema12 is not None and self.prev_ema26 is not None:
            if (self.prev_ema12 <= self.prev_ema26) and ema12 > ema26:
                entry_price = last_close
                margin_usdt = max(self.trading_engine.get_available_balance() * 0.05, 10)
                stop_loss = entry_price - 0.015 * entry_price
                take_profit = entry_price + 0.025 * entry_price
                self.position = safe_open_long(
                    self.trading_engine,
                    entry_price=entry_price,
                    margin_usdt=margin_usdt,
                    leverage=min(10, int(margin_usdt / stop_loss)),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    opened_by="GeneratedBot"
                )
            elif (self.prev_ema12 >= self.prev_ema26) and ema12 < ema26:
                entry_price = last_close
                margin_usdt = max(self.trading_engine.get_available_balance() * 0.05, 10)
                stop_loss = entry_price + 0.015 * entry_price
                take_profit = entry_price - 0.025 * entry_price
                self.position = safe_open_short(
                    self.trading_engine,
                    entry_price=entry_price,
                    margin_usdt=margin_usdt,
                    leverage=min(10, int(margin_usdt / stop_loss)),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    opened_by="GeneratedBot"
                )

        self.prev_ema12 = ema12
        self.prev_ema26 = ema26

    def on_tick(self, tick: dict) -> None:
        if self.timeframe != "1m":
            return

        # No action needed for 1m timeframe as it's only called on candle close
        pass

# Example usage (not part of the bot class)
if __name__ == "__main__":
    # Mock TradingEngine and DataEngine
    class MockTradingEngine:
        def get_position(self):
            return None

        def get_balance_usdt(self):
            return 10000.0

        def get_available_balance(self):
            return 5000.0

        def open_long(self, entry_price, margin_usdt, leverage, stop_loss, take_profit, opened_by):
            print(f"Opening long position at {entry_price} with stop loss: {stop_loss}, take profit: {take_profit}")

        def open_short(self, entry_price, margin_usdt, leverage, stop_loss, take_profit, opened_by):
            print(f"Opening short position at {entry_price} with stop loss: {stop_loss}, take profit: {take_profit}")

    class MockDataEngine:
        def get_completed_tf_candles(self, timeframe):
            return pd.DataFrame({
                "close": [10.0] * 50
            })

    # Create and run the bot
    bot = GeneratedBot(MockTradingEngine(), MockDataEngine())
    for _ in range(10):  # Simulate multiple ticks/candles
        bot.on_timeframe_candle("15m", {"close": 10.0})
