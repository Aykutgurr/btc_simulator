# -*- coding: utf-8 -*-
"""
Data Engine: 1 dakikalık OHLCV verisi, timeframe resample, QTimer ile tek tek 1m mum besleme.
Tarih aralığı filtreleme, hız preset (1x/10x/100x/Max) ve 15m tamamlanan mum sinyali.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

# Pandas resample frekansları (2.2+ uyumlu: T/H yerine min/h)
TF_MAP = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h"}
# 1m bar sayısı ile mum kapanışı (5m=5, 15m=15, 1h=60, 4h=240)
TF_BARS = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}

# Hız preset: (timer_ms, her tick'te ilerletilen mum sayısı)
SPEED_PRESETS = {
    "1x": (500, 1),
    "10x": (50, 1),
    "100x": (16, 1),
    "Max Hız": (16, 50),
}


class DataEngine(QObject):
    """
    Arka planda her zaman 1 dakikalık veride ilerler (tick); ekranda seçilen timeframe
    mumları resample ile hesaplanır. candle_emitted: güncel 1m mum.
    timeframe_candle_completed: seçilen TF'de bir mum tamamlandığında (örn. 15m).
    """

    candle_emitted = pyqtSignal(dict, int)
    stream_finished = pyqtSignal()
    timeframe_candle_completed = pyqtSignal(str, dict)
    fast_forward_progress = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df_1m: Optional[pd.DataFrame] = None
        self._index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._speed_ms = 500
        self._candles_per_tick = 1
        self._current_candle: Optional[Dict[str, Any]] = None
        self._timeframe = "1m"

    def set_timeframe(self, tf: str) -> None:
        """Zaman dilimi: 1m, 5m, 15m, 1h, 4h."""
        if tf in TF_MAP or tf == "1m":
            self._timeframe = tf

    def get_timeframe(self) -> str:
        return self._timeframe

    def load_csv(
        self,
        path: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> bool:
        """CSV'den 1m OHLCV yükler; isteğe bağlı start_date/end_date ile filtreler."""
        if not path or not os.path.isfile(path):
            return False
        try:
            df = pd.read_csv(path)
            req = {"open", "high", "low", "close"}
            time_col = None
            for c in ("timestamp", "date", "datetime", "time"):
                if c in df.columns:
                    time_col = c
                    break
            if not time_col or not req.issubset(df.columns):
                return False
            cols = [time_col, "open", "high", "low", "close"]
            if "volume" in df.columns:
                cols.append("volume")
            df = df[cols].copy()
            df = df.dropna(subset=["open", "high", "low", "close"])
            if len(df) == 0:
                return False
            df["datetime"] = pd.to_datetime(df[time_col], errors="coerce")
            df = df.dropna(subset=["datetime"])
            df["open"] = df["open"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["close"] = df["close"].astype(float)
            if "volume" in df.columns:
                df["volume"] = df["volume"].astype(float)
            else:
                df["volume"] = 0.0
            df = df.set_index("datetime").sort_index()
            self._df_1m = df[["open", "high", "low", "close", "volume"]].copy()
            if start_date is not None or end_date is not None:
                self.apply_date_filter(start_date, end_date)
            self._index = 0
            self._current_candle = None
            return True
        except Exception:
            return False

    def load_from_dataframe(
        self,
        df: pd.DataFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> bool:
        """DataFrame'den 1m OHLCV yükler. Index datetime olmalı; open, high, low, close, volume kolonları."""
        try:
            if df is None or df.empty:
                return False
            df = df.copy()
            if df.index.name != "datetime":
                df.index.name = "datetime"
            for col in ("open", "high", "low", "close"):
                if col not in df.columns:
                    return False
            if "volume" not in df.columns:
                df["volume"] = 0.0
            self._df_1m = df[["open", "high", "low", "close", "volume"]].astype(float)
            if start_date is not None or end_date is not None:
                self.apply_date_filter(start_date, end_date)
            self._index = 0
            self._current_candle = None
            return True
        except Exception:
            return False

    def apply_date_filter(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        """Veriyi tarih aralığına göre filtreler. Filtre sonucu boş kalırsa orijinal veriyi korur (simülasyon boş kalmaz)."""
        if self._df_1m is None or self._df_1m.empty:
            return
        backup = self._df_1m
        if start_date is not None:
            self._df_1m = self._df_1m[self._df_1m.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            self._df_1m = self._df_1m[self._df_1m.index <= pd.Timestamp(end_date)]
        if self._df_1m.empty:
            self._df_1m = backup

    def generate_mock_data(self, num_bars: int = 800) -> None:
        """1 dakikalık mock OHLCV; DatetimeIndex ile."""
        import numpy as np
        base_price = 40000.0
        np.random.seed(42)
        returns = np.random.randn(num_bars) * 0.01
        close = base_price * np.exp(np.cumsum(returns))
        open_ = np.roll(close, 1)
        open_[0] = base_price
        high = np.maximum(open_, close) * (1 + np.abs(np.random.randn(num_bars) * 0.005))
        low = np.minimum(open_, close) * (1 - np.abs(np.random.randn(num_bars) * 0.005))
        times = pd.date_range(start="2024-01-01", periods=num_bars, freq="1min")
        self._df_1m = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": np.random.randint(10, 1000, size=num_bars)},
            index=times,
        )
        self._df_1m.index.name = "datetime"
        self._index = 0
        self._current_candle = None

    def generate_mock_data_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """Seçilen tarih aralığında 1 dakikalık mock OHLCV üretir."""
        import numpy as np
        num_bars = min(50000, max(500, int((end_date - start_date).total_seconds() // 60)))
        base_price = 40000.0
        np.random.seed(42)
        returns = np.random.randn(num_bars) * 0.01
        close = base_price * np.exp(np.cumsum(returns))
        open_ = np.roll(close, 1)
        open_[0] = base_price
        high = np.maximum(open_, close) * (1 + np.abs(np.random.randn(num_bars) * 0.005))
        low = np.minimum(open_, close) * (1 - np.abs(np.random.randn(num_bars) * 0.005))
        times = pd.date_range(start=pd.Timestamp(start_date), periods=num_bars, freq="1min")
        self._df_1m = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": np.random.randint(10, 1000, size=num_bars)},
            index=times,
        )
        self._df_1m.index.name = "datetime"
        self._index = 0
        self._current_candle = None

    def play(self) -> None:
        """Zamanlayıcıyı başlatır."""
        if self._df_1m is None or self._df_1m.empty:
            return
        if self._index >= len(self._df_1m):
            self.stream_finished.emit()
            return
        self._timer.start(self._speed_ms)

    def pause(self) -> None:
        """Zamanlayıcıyı durdurur."""
        self._timer.stop()

    def step_forward(self) -> None:
        """Tek mum ilerletir ve bir kez sinyal yayınlar."""
        if self._df_1m is None or self._df_1m.empty or self._index >= len(self._df_1m):
            if self._df_1m is not None and self._index >= len(self._df_1m):
                self.stream_finished.emit()
            return
        self._emit_current()
        self._index += 1
        if self._index >= len(self._df_1m):
            self.stream_finished.emit()

    def set_speed_ms(self, ms: int) -> None:
        """Timer aralığı (milisaniye)."""
        self._speed_ms = max(16, min(3000, int(ms)))
        if self._timer.isActive():
            self._timer.setInterval(self._speed_ms)

    def set_speed_preset(self, preset: str) -> None:
        """Hız preset: '1x', '10x', '100x', 'Max Hız'."""
        if preset in SPEED_PRESETS:
            self._speed_ms, self._candles_per_tick = SPEED_PRESETS[preset]
            if self._timer.isActive():
                self._timer.setInterval(self._speed_ms)

    def get_speed_ms(self) -> int:
        return self._speed_ms

    def get_candles_per_tick(self) -> int:
        return self._candles_per_tick

    def get_current_candle(self) -> Optional[Dict[str, Any]]:
        return self._current_candle

    def get_current_price(self) -> Optional[float]:
        if self._current_candle is None:
            return None
        return self._current_candle.get("close")

    def get_current_index(self) -> int:
        return max(0, self._index - 1) if self._current_candle is not None else 0

    def get_current_1m_index(self) -> int:
        """Şu anki 1m bar indeksi (yayınlanan son)."""
        return self.get_current_index()

    def has_data(self) -> bool:
        return self._df_1m is not None and len(self._df_1m) > 0

    def reset_to_start(self) -> None:
        """Simülasyonu başa alır: indeks ve güncel mum sıfırlanır."""
        self._index = 0
        self._current_candle = None
        self._timer.stop()

    def is_at_end(self) -> bool:
        return self._df_1m is not None and self._index >= len(self._df_1m)

    def get_display_candles(self) -> List[Dict[str, Any]]:
        """
        Seçilen timeframe'e göre resample edilmiş mum listesi (tamamlanan + o anki oluşan bar).
        UI bu listeyi mum grafiğinde çizer.
        """
        if self._df_1m is None or self._index <= 0:
            return []
        slice_1m = self._df_1m.iloc[: self._index].copy()
        if slice_1m.empty:
            return []

        tf = self._timeframe
        if tf == "1m":
            out = []
            for i, row in slice_1m.iterrows():
                out.append({
                    "time": str(i),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                })
            return out

        freq = TF_MAP.get(tf, "1min")
        # Resample öncesi index'in datetime olduğundan emin ol
        if not pd.api.types.is_datetime64_any_dtype(slice_1m.index):
            slice_1m = slice_1m.copy()
            slice_1m.index = pd.to_datetime(slice_1m.index, errors="coerce")
            slice_1m = slice_1m[slice_1m.index.notna()]
        try:
            res = slice_1m.resample(freq).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna(how="all")
        except Exception as e:
            print(f"Resample işlemi sırasında hata oluştu: {e}")
            return []
        out = []
        for ts, row in res.iterrows():
            out.append({
                "time": str(ts),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0)),
            })
        return out

    def get_all_1m_for_indicators(self) -> Optional[pd.DataFrame]:
        """Göstergeler (RSI, vb.) için şu ana kadar gelen 1m verisi."""
        if self._df_1m is None or self._index <= 0:
            return None
        return self._df_1m.iloc[: self._index].copy()

    def get_completed_tf_candles(self, tf: str) -> Optional[pd.DataFrame]:
        """
        Verilen timeframe için sadece tamamlanmış mumları döner (son yarım kalmış bar hariç).
        Botların EMA/RSI/ATR hesaplaması için kullanılır.
        """
        if self._df_1m is None or self._index <= 0 or tf not in TF_MAP:
            return None
        slice_1m = self._df_1m.iloc[: self._index].copy()
        if slice_1m.empty or len(slice_1m) < 2:
            return None
        freq = TF_MAP.get(tf, "1min")
        n_bars = TF_BARS.get(tf, 1)
        if n_bars <= 0:
            return None
        try:
            if not pd.api.types.is_datetime64_any_dtype(slice_1m.index):
                slice_1m = slice_1m.copy()
                slice_1m.index = pd.to_datetime(slice_1m.index, errors="coerce")
                slice_1m = slice_1m[slice_1m.index.notna()]
            res = slice_1m.resample(freq).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna(how="all")
            # Son bar tamamlanmamış olabilir (1m tick sayısı n_bars'ın katı değilse); son satırı at
            if len(res) > 0 and len(slice_1m) % n_bars != 0:
                res = res.iloc[:-1]
            return res if not res.empty else None
        except Exception:
            return None

    def _on_tick(self) -> None:
        if self._df_1m is None or self._index >= len(self._df_1m):
            self._timer.stop()
            self.stream_finished.emit()
            return
        n = min(self._candles_per_tick, len(self._df_1m) - self._index)
        for _ in range(n):
            prev_index = self._index
            self._emit_current()
            self._index += 1
            self._maybe_emit_timeframe_completed(prev_index)
            if self._index >= len(self._df_1m):
                break
        if self._index >= len(self._df_1m):
            self._timer.stop()
            self.stream_finished.emit()

    def _maybe_emit_timeframe_completed(self, completed_1m_index: int) -> None:
        """Her timeframe (5m, 15m, 1h, 4h) için mum tamamlandıysa timeframe_candle_completed yayınla; botlar kendi TF'lerini alır."""
        if completed_1m_index <= 0:
            return
        for tf, n_bars in TF_BARS.items():
            if (completed_1m_index + 1) % n_bars != 0:
                continue
            start_i = completed_1m_index - n_bars + 1
            end_i = completed_1m_index + 1
            if start_i < 0 or end_i > len(self._df_1m):
                continue
            try:
                slice_tf = self._df_1m.iloc[start_i:end_i]
                row_first = slice_tf.iloc[0]
                row_last = slice_tf.iloc[-1]
                candle_tf = {
                    "time": str(slice_tf.index[-1]),
                    "open": float(row_first["open"]),
                    "high": float(slice_tf["high"].max()),
                    "low": float(slice_tf["low"].min()),
                    "close": float(row_last["close"]),
                    "volume": float(slice_tf["volume"].sum()),
                }
                self.timeframe_candle_completed.emit(tf, candle_tf)
            except Exception:
                pass

    def _emit_current(self) -> None:
        if self._df_1m is None or self._index >= len(self._df_1m):
            return
        row = self._df_1m.iloc[self._index]
        candle = {
            "time": str(self._df_1m.index[self._index]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        self._current_candle = candle
        self.candle_emitted.emit(candle, self._index)

    def run_fast_forward(self, batch_size: int = 100) -> None:
        """
        QTimer durdurulur; kalan tüm 1m mumlar batch_size'lık parçalarda işlenir.
        Her mum için candle_emitted ve gerekirse timeframe_candle_completed yayınlanır.
        GUI donmaması için tek seferde batch_size kadar işlenip QTimer.singleShot(0, ...) ile devam edilir.
        """
        self._timer.stop()
        total = len(self._df_1m) if self._df_1m is not None else 0
        if total == 0 or self._index >= total:
            self.stream_finished.emit()
            return
        remaining = total - self._index
        self._fast_forward_batch(batch_size, total)

    def _fast_forward_batch(self, batch_size: int, total: int) -> None:
        if self._df_1m is None or self._index >= len(self._df_1m):
            self.stream_finished.emit()
            return
        n = min(batch_size, len(self._df_1m) - self._index)
        for _ in range(n):
            prev_index = self._index
            self._emit_current()
            self._index += 1
            self._maybe_emit_timeframe_completed(prev_index)
            if self._index >= len(self._df_1m):
                break
        self.fast_forward_progress.emit(self._index, total)
        if self._index >= len(self._df_1m):
            self.stream_finished.emit()
            return
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._fast_forward_batch(batch_size, total))
