# -*- coding: utf-8 -*-
"""
Başlangıç penceresi: Tarih aralığı seçimi, CSV yoksa yfinance/ccxt ile 1m veri çekme.
"""

import os
from datetime import datetime, date, timedelta

import pandas as pd

# yfinance 1m veri için istek başına en fazla 8 gün
YFINANCE_1M_MAX_DAYS_PER_REQUEST = 8
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

    def run(self):
        try:
            self.progress.emit("Veri kaynağı deneniyor (yfinance)...")
            df = self._fetch_yfinance()
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
        """1m veriyi 8 günlük parçalarda çeker (yfinance limiti); parçaları birleştirir."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("BTC-USD")
            chunks = []
            current = datetime.combine(self.start_date, datetime.min.time())
            end_dt = datetime.combine(self.end_date, datetime.max.time())
            chunk_days = YFINANCE_1M_MAX_DAYS_PER_REQUEST
            total_days = (end_dt - current).days + 1
            part = 0
            while current < end_dt:
                part += 1
                chunk_end = min(current + timedelta(days=chunk_days), end_dt)
                self.progress.emit(f"yfinance: parça {part} çekiliyor ({current.date()} - {chunk_end.date()})...")
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

    def _fetch_ccxt(self):
        try:
            import ccxt
            exchange = ccxt.binance({"enableRateLimit": True})
            since = int(datetime.combine(self.start_date, datetime.min.time()).timestamp() * 1000)
            end_ts = int(datetime.combine(self.end_date, datetime.max.time()).timestamp() * 1000)
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
            df = df[(df.index >= pd.Timestamp(self.start_date)) & (df.index <= pd.Timestamp(self.end_date))]
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
        self.date_start.setMaximumDate(QDate(2026, 2, 20))
        gl.addWidget(self.date_start)
        gl.addWidget(QLabel("Bitiş Tarihi (en geç 20 Şubat 2026):"))
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate(2025, 2, 20))
        self.date_end.setMinimumDate(QDate(2025, 1, 1))
        self.date_end.setMaximumDate(QDate(2026, 2, 20))
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
        csv_path = os.path.join(base_dir, "btc_ohlcv.csv")
        if os.path.isfile(csv_path):
            try:
                df = pd.read_csv(csv_path, nrows=5)
                for c in ("timestamp", "date", "datetime", "time"):
                    if c in df.columns:
                        break
                else:
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
            out_path = os.path.join(base_dir, "btc_ohlcv.csv")
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
