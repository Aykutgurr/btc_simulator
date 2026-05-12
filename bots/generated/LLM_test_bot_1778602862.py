class GeneratedBot:
    name = "LLM test bot"
    timeframe = "15m"

    def __init__(self, trading_engine, data_engine=None):
        self.trading_engine = trading_engine
        self.data_engine = data_engine
        self.rsi_state = None
        self.position_opened = False

    def on_timeframe_candle(self, timeframe: str, candle: dict) -> None:
        if timeframe != self.timeframe:
            return
        
        # Wait until there are at least 30 completed 15m bars before taking the first signal
        df = self.data_engine.get_completed_tf_candles(self.timeframe) if self.data_engine else None
        if df is not None and len(df) < 30:
            return

        close_price = float(candle['close'])
        
        # Initialize RSI state if it hasn't been initialized yet
        if self.rsi_state is None:
            self.rsi_state = EmaState(period=14)
        
        # Update RSI state
        rsi_value = self.rsi_state.update(close_price)
        
        current_rsi = rsi_value
        
        # Check for long entry condition
        if not self.position_opened and current_rsi < 30:
            previous_candle = df.iloc[-2]
            previous_rsi = self.rsi_state.update(float(previous_candle['close']))
            
            if previous_rsi >= 30 and current_rsi < 30:
                available_balance = self.trading_engine.get_available_balance()
                margin_usdt = max(10, available_balance * 0.05)
                
                entry_price = close_price
                stop_loss = entry_price * (1 - 0.015)
                take_profit = entry_price * (1 + 0.025)
                
                safe_open_long(
                    self.trading_engine,
                    entry_price=entry_price,
                    margin_usdt=margin_usdt,
                    leverage=5,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    opened_by=self.name
                )
                self.position_opened = True

        # Check for short entry condition
        if not self.position_opened and current_rsi > 70:
            previous_candle = df.iloc[-2]
            previous_rsi = self.rsi_state.update(float(previous_candle['close']))
            
            if previous_rsi <= 70 and current_rsi > 70:
                available_balance = self.trading_engine.get_available_balance()
                margin_usdt = max(10, available_balance * 0.05)
                
                entry_price = close_price
                stop_loss = entry_price * (1 + 0.015)
                take_profit = entry_price * (1 - 0.025)
                
                safe_open_short(
                    self.trading_engine,
                    entry_price=entry_price,
                    margin_usdt=margin_usdt,
                    leverage=5,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    opened_by=self.name
                )
                self.position_opened = True

        # If a position is open, do nothing until it is closed by stop or take profit
        if self.position_opened and get_position_fields(self.trading_engine.get_position()):
            return

        # Update the RSI state with the current close price for the next iteration
        self.rsi_state.update(close_price)
