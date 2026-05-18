# -*- coding: utf-8 -*-
"""
Başlangıç penceresi: Tarih aralığı seçimi, CSV yoksa yfinance/ccxt ile 1m veri çekme.
"""

import os
from datetime import datetime, date, timedelta

import pandas as pd

# yfinance 1m: istek başına en fazla 7 gün (Yahoo 8 gün sınırı; 7 ile güvende kal)
YFINANCE_1M_MAX_DAYS_PER_REQUEST = 7
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDateEdit,
    QProgressBar,
    QMessageBox,
    QGroupBox,
)
from PyQt5.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont


class FetchWorker(QThread):
    """Arka planda 1m BTC verisi çeker; GUI donmaz."""
    finished = pyqtSignal(bool, object)
    progress = pyqtSignal(str)

    def __init__(self, start_date: date, end_date: date):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date

    def _end_dt(self):
        """Bitiş anı: bugün seçiliyse şu an, değilse seçilen günün sonu."""
        if self.end_date == date.today():
            return datetime.now()
        return datetime.combine(self.end_date, datetime.max.time())

    def run(self):
        try:
            self.progress.emit("Veri kaynağı deneniyor (yfinance 1m)...")
            df = self._fetch_yfinance()
            if df is not None and not df.empty:
                self.progress.emit("Veri alındı, kaydediliyor...")
                self.finished.emit(True, df)
                return
            for interval, minutes in [("5m", 5), ("15m", 15), ("1h", 60)]:
                self.progress.emit(f"yfinance 1m yok, {interval} deneniyor...")
                df = self._fetch_yfinance_interval(interval, minutes)
                if df is not None and not df.empty:
                    self.progress.emit("Veri alındı, kaydediliyor...")
                    self.finished.emit(True, df)
                    return
            self.progress.emit("yfinance uygun değil, ccxt deneniyor...")
            df = self._fetch_ccxt()
            if df is not None and not df.empty:
                self.progress.emit("Veri alındı, kaydediliyor...")
                self.finished.emit(True, df)
                return
            self.finished.emit(False, None)
        except Exception as e:
            self.progress.emit(f"Hata: {e}")
            self.finished.emit(False, None)

    def _fetch_yfinance(self):
        """1m veriyi 7 günlük parçalarda çeker (Yahoo ~8 gün limiti); parçaları birleştirir."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("BTC-USD")
            chunks = []
            current = datetime.combine(self.start_date, datetime.min.time())
            end_dt = self._end_dt()
            chunk_days = YFINANCE_1M_MAX_DAYS_PER_REQUEST
            part = 0
            while current < end_dt:
                part += 1
                chunk_end = current + timedelta(days=chunk_days)
                if chunk_end > end_dt:
                    chunk_end = end_dt
                self.progress.emit(f"yfinance 1m: parça {part} ({current.date()} - {chunk_end.date()})...")
                start_str = current.strftime("%Y-%m-%d")
                end_str = (chunk_end + timedelta(days=1)).strftime("%Y-%m-%d")
                df_chunk = ticker.history(start=start_str, end=end_str, interval="1m")
                if df_chunk is not None and not df_chunk.empty:
                    df_chunk = df_chunk.rename(columns={
                        "Open": "open", "High": "high", "Low": "low",
                        "Close": "close", "Volume": "volume"
                    })
                    df_chunk = df_chunk[["open", "high", "low", "close", "volume"]].copy()
                    df_chunk.index = pd.to_datetime(df_chunk.index)
                    df_chunk = df_chunk[(df_chunk.index >= pd.Timestamp(current)) & (df_chunk.index <= pd.Timestamp(end_dt))]
                    if not df_chunk.empty:
                        chunks.append(df_chunk)
                current = chunk_end + timedelta(days=1)
            if not chunks:
                return None
            df = pd.concat(chunks, axis=0)
            df = df[~df.index.duplicated(keep="first")]
            df = df.sort_index()
            df.index.name = "datetime"
            if len(df) < 10:
                return None
            return df
        except Exception:
            return None

    def _expand_to_1m(self, df: pd.DataFrame, minutes_per_bar: int) -> pd.DataFrame:
        """5m/15m/1h OHLCV'yi sentetik 1m çubuklara genişletir (her bar N adet 1m bar)."""
        if df is None or df.empty or minutes_per_bar < 2:
            return df
        rows = []
        for ts, row in df.iterrows():
            t = pd.Timestamp(ts)
            vol_each = float(row["volume"]) / minutes_per_bar
            for i in range(minutes_per_bar):
                t_i = t + pd.Timedelta(minutes=i)
                rows.append({
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": vol_each,
                    "datetime": t_i,
                })
        out = pd.DataFrame(rows)
        out = out.set_index("datetime").sort_index()
        out.index.name = "datetime"
        return out

    def _fetch_yfinance_interval(self, interval: str, minutes_per_bar: int):
        """Belirtilen aralıkta (5m, 15m, 1h) veri çeker ve sentetik 1m'ye genişletir."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("BTC-USD")
            start_str = self.start_date.strftime("%Y-%m-%d")
            end_dt = self._end_dt()
            end_str = (end_dt.date() + timedelta(days=1)).strftime("%Y-%m-%d")
            self.progress.emit(f"yfinance {interval} çekiliyor, 1m'ye dönüştürülüyor...")
            df = ticker.history(start=start_str, end=end_str, interval=interval)
            if df is None or df.empty or len(df) < 2:
                return None
            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Volume": "volume"
            })
            df = df[["open", "high", "low", "close", "volume"]].copy()
            df.index = pd.to_datetime(df.index)
            df = df[(df.index >= pd.Timestamp(self.start_date)) & (df.index <= pd.Timestamp(end_dt))]
            if df.empty or len(df) < 2:
                return None
            df = self._expand_to_1m(df, minutes_per_bar)
            df = df[(df.index >= pd.Timestamp(datetime.combine(self.start_date, datetime.min.time()))) & (df.index <= pd.Timestamp(end_dt))]
            if df.empty or len(df) < 10:
                return None
            return df
        except Exception:
            return None

    def _fetch_ccxt(self):
        try:
            import ccxt
            exchange = ccxt.binance({"enableRateLimit": True})
            since = int(datetime.combine(self.start_date, datetime.min.time()).timestamp() * 1000)
            end_ts = int(self._end_dt().timestamp() * 1000)
            all_ohlcv = []
            while since < end_ts:
                ohlcv = exchange.fetch_ohlcv("BTC/USDT", "1m", since=since, limit=1000)
                if not ohlcv:
                    break
                all_ohlcv.extend(ohlcv)
                since = ohlcv[-1][0] + 60000
                if len(ohlcv) < 1000:
                    break
            if not all_ohlcv:
                return None
            df = pd.DataFrame(all_ohlcv, columns=["datetime", "open", "high", "low", "close", "volume"])
            df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
            df = df.set_index("datetime")
            df = df[(df.index >= pd.Timestamp(self.start_date)) & (df.index <= pd.Timestamp(self._end_dt()))]
            if df.empty or len(df) < 10:
                return None
            return df
        except Exception:
            return None


class StartupDialog(QDialog):
    """Başlangıç ve bitiş tarihi seçimi; CSV yoksa veri çekme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simülasyon Başlangıç Ayarları")
        self.setMinimumWidth(420)
        self._csv_path: str = ""
        self._df_fetched = None
        self._start_date: date = date(2025, 1, 15)
        self._end_date: date = date(2025, 2, 20)
        self._worker = None

        layout = QVBoxLayout(self)
        grp = QGroupBox("Tarih Aralığı")
        gl = QVBoxLayout(grp)
        gl.addWidget(QLabel("Başlangıç Tarihi (en erken 1 Ocak 2025):"))
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate(2025, 1, 15))
        self.date_start.setMinimumDate(QDate(2025, 1, 1))
        self.date_start.setMaximumDate(QDate.currentDate())
        gl.addWidget(self.date_start)
        gl.addWidget(QLabel("Bitiş Tarihi (bugüne kadar; bugün seçilirse güncel veri çekilir):"))
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setMinimumDate(QDate(2025, 1, 1))
        self.date_end.setMaximumDate(QDate.currentDate())
        gl.addWidget(self.date_end)
        layout.addWidget(grp)

        self.label_status = QLabel("Başlat'a tıklayın. CSV yoksa veri indirilecektir.")
        self.label_status.setWordWrap(True)
        layout.addWidget(self.label_status)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_start = QPushButton("Başlat")
        self.btn_start.setDefault(True)
        self.btn_start.clicked.connect(self._on_start)
        btn_row.addWidget(self.btn_start)
        self.btn_mock = QPushButton("Mock veri ile başlat")
        self.btn_mock.clicked.connect(self._start_with_mock)
        self.btn_mock.setVisible(False)
        btn_row.addWidget(self.btn_mock)
        layout.addLayout(btn_row)

    def _on_start(self):
        self._start_date = self.date_start.date().toPyDate()
        self._end_date = self.date_end.date().toPyDate()
        if self._start_date > self._end_date:
            QMessageBox.warning(self, "Uyarı", "Başlangıç tarihi bitişten sonra olamaz.")
            return
        base_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(base_dir, "data", "btc_ohlcv.csv")
        if os.path.isfile(csv_path):
            try:
                df = pd.read_csv(csv_path, nrows=5)
                has_time = any(c in df.columns for c in ("timestamp", "date", "datetime", "time"))
                has_ohlc = {"open", "high", "low", "close"}.issubset(df.columns)
                if not (has_time and has_ohlc):
                    csv_path = ""
            except Exception:
                csv_path = ""
        if csv_path and os.path.isfile(csv_path):
            self._csv_path = csv_path
            self._df_fetched = None
            self.accept()
            return
        self.label_status.setText("Veri bulunamadı. İnternetten çekiliyor...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.btn_start.setEnabled(False)
        self._worker = FetchWorker(self._start_date, self._end_date)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_fetch_finished)
        self._worker.start()

    def _on_progress(self, msg: str):
        self.label_status.setText(msg)

    def _on_fetch_finished(self, success: bool, df):
        self.progress.setVisible(False)
        self.btn_start.setEnabled(True)
        if success and df is not None and not df.empty:
            self._df_fetched = df
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            out_path = os.path.join(data_dir, "btc_ohlcv.csv")
            try:
                df.to_csv(out_path, index=True, encoding="utf-8-sig")
                self._csv_path = out_path
            except Exception:
                self._csv_path = ""
            self.label_status.setText("Veri kaydedildi. Simülasyon başlatılıyor.")
            self.accept()
        else:
            self.label_status.setText("Veri çekilemedi. 'Mock veri ile başlat' ile devam edebilirsiniz.")
            self._csv_path = ""
            self._df_fetched = None
            self.btn_mock.setVisible(True)

    def get_start_date(self) -> date:
        return self._start_date

    def get_end_date(self) -> date:
        return self._end_date

    def get_csv_path(self) -> str:
        return self._csv_path or ""

    def get_fetched_dataframe(self):
        """İndirilen veri (varsa); yoksa None."""
        return self._df_fetched

    def _start_with_mock(self):
        self._csv_path = ""
        self._df_fetched = None
        self.accept()
