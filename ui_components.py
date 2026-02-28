# -*- coding: utf-8 -*-
"""
UI: Timeframe selector, sol çizim araç çubuğu, mum/hacim/RSI grafikleri, futures paneli, log.
"""

from datetime import datetime as dt, date
from typing import Optional, List, Dict, Any, Callable

import pyqtgraph as pg
import pandas as pd
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QFileDialog,
    QDoubleSpinBox,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QFrame,
    QScrollArea,
    QComboBox,
    QTabWidget,
    QGridLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
)
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPainter, QPicture

from data_engine import DataEngine
from trading_engine import TradingEngine
from drawing_tools import (
    add_trend_line,
    add_ray,
    add_price_range,
    add_long_position_tool,
    add_short_position_tool,
)

try:
    import pandas_ta as ta
except ImportError:
    ta = None


class DateAxisItem(pg.AxisItem):
    """X ekseninde index yerine get_display_candles() 'time' değerlerini gösterir."""
    def __init__(self, orientation="bottom", time_labels=None, *args, **kwargs):
        super().__init__(orientation, *args, **kwargs)
        self._time_labels = time_labels or []

    def set_time_labels(self, labels: List[str]) -> None:
        self._time_labels = labels

    def tickStrings(self, values, scale, spacing):
        if not self._time_labels:
            return super().tickStrings(values, scale, spacing)
        result = []
        for v in values:
            i = int(round(v))
            if 0 <= i < len(self._time_labels):
                s = str(self._time_labels[i])
                if len(s) > 12:
                    s = s[:10] + ".."
                result.append(s)
            else:
                result.append(str(i))
        return result


class CandlestickItem(pg.GraphicsObject):
    """OHLC mum çizimi."""

    def __init__(self, data: List[Dict[str, Any]]):
        super().__init__()
        self.data = data or []
        self.generate_picture()

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        self.data = data or []
        self.generate_picture()
        self.update()

    def generate_picture(self) -> None:
        self.picture = QPicture()
        n = len(self.data)
        if not self.data:
            return
        p = QPainter(self.picture)
        w = 0.4
        for i, bar in enumerate(self.data):
            o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
            x = i
            p.setPen(pg.mkPen("w", width=1))
            p.drawLine(QPointF(x, l), QPointF(x, h))
            p.setBrush(pg.mkBrush("g") if c >= o else pg.mkBrush("r"))
            p.setPen(pg.mkPen("g") if c >= o else pg.mkPen("r"))
            p.drawRect(QRectF(x - w, min(o, c), w * 2, abs(c - o) or 0.001))
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QRectF(self.picture.boundingRect())


class MainWindow(QMainWindow):
    def __init__(
        self,
        data_engine: DataEngine,
        trading_engine: TradingEngine,
        bots: Optional[List[Any]] = None,
        get_bots: Optional[Callable[..., List[Any]]] = None,
    ):
        super().__init__()
        self.data_engine = data_engine
        self.trading_engine = trading_engine
        self._bots = bots or []
        self._get_bots = get_bots
        self._bot_checkboxes: Dict[str, QCheckBox] = {}
        self.setWindowTitle("BTC Futures Simülatörü")
        self.setMinimumSize(1100, 750)
        self._candles: List[Dict[str, Any]] = []
        self._buy_marker_x: List[float] = []
        self._buy_marker_y: List[float] = []
        self._sell_marker_x: List[float] = []
        self._sell_marker_y: List[float] = []
        self.resize(1300, 850)

        self._equity_x: List[float] = []
        self._equity_y: List[float] = []
        self._fast_forward_active = False

        # Sol toolbar
        left_toolbar = QFrame()
        left_toolbar.setFrameStyle(QFrame.StyledPanel)
        left_layout = QVBoxLayout(left_toolbar)
        left_layout.addWidget(QLabel("Çizim Araçları"))
        btn_trend = QPushButton("Trend Çizgisi")
        btn_ray = QPushButton("Işın")
        btn_range = QPushButton("Fiyat Aralığı")
        btn_long = QPushButton("Long Pozisyon")
        btn_short = QPushButton("Short Pozisyon")
        for b in (btn_trend, btn_ray, btn_range, btn_long, btn_short):
            left_layout.addWidget(b)
        left_layout.addStretch()

        # Sağ: sekmeli ana içerik
        right = QWidget()
        right_main = QVBoxLayout(right)
        self.tabs = QTabWidget()

        # ========== SEKME 1: Grafik & İşlem ==========
        tab1 = QWidget()
        main_layout = QVBoxLayout(tab1)

        # ----- Üst: Timeframe + Kontroller + İndikatörler + Bakiye -----
        top = QHBoxLayout()
        top.addWidget(QLabel("Zaman:"))
        self._tf_buttons = {}
        for tf in ("1m", "5m", "15m", "1h", "4h"):
            btn = QPushButton(tf)
            btn.setCheckable(True)
            if tf == "1m":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, t=tf: self._set_timeframe(t))
            top.addWidget(btn)
            self._tf_buttons[tf] = btn
        top.addWidget(QLabel("Hız:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["1x", "10x", "100x", "Max Hız"])
        self.combo_speed.setCurrentText("1x")
        self.combo_speed.currentTextChanged.connect(self._on_speed_preset_changed)
        top.addWidget(self.combo_speed)
        top.addWidget(QLabel("(ms):"))
        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setMinimum(16)
        self.slider_speed.setMaximum(2000)
        self.slider_speed.setValue(500)
        self.slider_speed.valueChanged.connect(self._on_speed_changed)
        top.addWidget(self.slider_speed)
        self.label_speed = QLabel("500")
        top.addWidget(self.label_speed)

        self.cb_volume = QCheckBox("Hacim Göster")
        self.cb_rsi = QCheckBox("RSI")
        self.cb_macd = QCheckBox("MACD")
        self.cb_ema = QCheckBox("EMA (20, 50)")
        self.cb_volume.toggled.connect(self._toggle_volume)
        self.cb_rsi.toggled.connect(self._toggle_rsi)
        self.cb_macd.toggled.connect(self._toggle_macd)
        self.cb_ema.toggled.connect(self._toggle_ema)
        top.addWidget(self.cb_volume)
        top.addWidget(self.cb_rsi)
        top.addWidget(self.cb_macd)
        top.addWidget(self.cb_ema)

        top.addStretch()
        self.label_balance = QLabel("USDT: 0.00")
        top.addWidget(self.label_balance)

        main_layout.addLayout(top)

        # ----- Grafikler -----
        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        self._axis_dates = DateAxisItem(orientation="bottom")
        self.plot_candles = pg.PlotWidget(title="BTC OHLC", axisItems={"bottom": self._axis_dates})

        self.buy_markers = pg.ScatterPlotItem(
            size=12,

            symbol="t",
            brush=pg.mkBrush("g"),
            pen=pg.mkPen("g"),
        )
        self.plot_candles.addItem(self.buy_markers)
        self.sell_markers = pg.ScatterPlotItem(
            size=12,
            symbol="t",
            brush=pg.mkBrush("r"),
            pen=pg.mkPen("r"),
        )
        self.sell_markers.setRotation(180)
        self.plot_candles.addItem(self.sell_markers)

        self.plot_candles.setBackground("k")
        self.plot_candles.showGrid(x=True, y=True, alpha=0.3)
        self.candlestick_item = CandlestickItem([])
        self.plot_candles.addItem(self.candlestick_item)
        self.ema20_curve = self.plot_candles.plot(pen=pg.mkPen("y", width=1))
        self.ema50_curve = self.plot_candles.plot(pen=pg.mkPen("w", width=1))
        self.ema20_curve.setVisible(False)
        self.ema50_curve.setVisible(False)
        self.price_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("y", width=1))
        self.plot_candles.addItem(self.price_line)
        chart_layout.addWidget(self.plot_candles, stretch=3)

        self._axis_dates_volume = DateAxisItem(orientation="bottom")
        self.plot_volume = pg.PlotWidget(title="Hacim", axisItems={"bottom": self._axis_dates_volume})
        self.plot_volume.setBackground("k")
        self.plot_volume.showGrid(x=True, y=True, alpha=0.3)
        self.volume_bars = pg.BarGraphItem(x=[], height=[], width=0.8, brush=pg.mkBrush(100, 100, 200, 150))
        self.plot_volume.addItem(self.volume_bars)
        chart_layout.addWidget(self.plot_volume, stretch=1)
        self.plot_volume.hide()

        self._axis_dates_rsi = DateAxisItem(orientation="bottom")
        self.plot_rsi = pg.PlotWidget(title="RSI", axisItems={"bottom": self._axis_dates_rsi})
        self.plot_rsi.setBackground("k")
        self.plot_rsi.showGrid(x=True, y=True, alpha=0.3)
        self.plot_rsi.setYRange(0, 100)
        self.rsi_curve = self.plot_rsi.plot(pen=pg.mkPen("m", width=2))
        chart_layout.addWidget(self.plot_rsi, stretch=1)
        self.plot_rsi.hide()

        self._axis_dates_macd = DateAxisItem(orientation="bottom")
        self.plot_macd = pg.PlotWidget(title="MACD", axisItems={"bottom": self._axis_dates_macd})
        self.plot_macd.setBackground("k")
        self.plot_macd.showGrid(x=True, y=True, alpha=0.3)
        self.macd_curve = self.plot_macd.plot(pen=pg.mkPen("c", width=2))
        self.macd_signal_curve = self.plot_macd.plot(pen=pg.mkPen("y", width=1))
        chart_layout.addWidget(self.plot_macd, stretch=1)
        self.plot_macd.hide()

        self.plot_equity = pg.PlotWidget(title="Portföy (USDT)")
        self.plot_equity.setBackground("k")
        self.plot_equity.showGrid(x=True, y=True, alpha=0.3)
        self.equity_curve = self.plot_equity.plot(pen=pg.mkPen("c", width=2))
        chart_layout.addWidget(self.plot_equity, stretch=1)

        main_layout.addWidget(chart_container)

        # ----- Futures panel -----
        futures_group = QGroupBox("Futures (İzole Marjin)")
        flay = QHBoxLayout(futures_group)
        flay.addWidget(QLabel("Kaldıraç (1-100):"))
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setMinimum(1)
        self.leverage_spin.setMaximum(100)
        self.leverage_spin.setValue(10)
        flay.addWidget(self.leverage_spin)
        flay.addWidget(QLabel("Marjin (USDT):"))
        self.margin_spin = QDoubleSpinBox()
        self.margin_spin.setDecimals(2)
        self.margin_spin.setMinimum(10)
        self.margin_spin.setMaximum(1000000)
        self.margin_spin.setValue(500)
        flay.addWidget(self.margin_spin)
        flay.addWidget(QLabel("Stop Loss (Fiyat):"))
        self.sl_spin = QDoubleSpinBox()
        self.sl_spin.setDecimals(2)
        self.sl_spin.setMinimum(0)
        self.sl_spin.setMaximum(1000000)
        self.sl_spin.setValue(0)
        self.sl_spin.setSpecialValueText("Yok")
        flay.addWidget(self.sl_spin)
        self.btn_long = QPushButton("Long Aç")
        self.btn_short = QPushButton("Short Aç")
        self.btn_close = QPushButton("Pozisyonu Kapat (Market)")
        self.btn_long.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_short.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;")
        self.btn_long.clicked.connect(self._on_long)
        self.btn_short.clicked.connect(self._on_short)
        self.btn_close.clicked.connect(self._on_close_position)
        flay.addWidget(self.btn_long)
        flay.addWidget(self.btn_short)
        flay.addWidget(self.btn_close)
        flay.addStretch()
        self.label_position = QLabel("Açık pozisyon yok")
        flay.addWidget(self.label_position)
        main_layout.addWidget(futures_group)

        # ----- Oynat / Duraklat / İleri Sar / Hızlı Test -----
        ctrl_row = QHBoxLayout()
        self.btn_play = QPushButton("Oynat")
        self.btn_pause = QPushButton("Duraklat")
        self.btn_step = QPushButton("İleri Sar (Tek Mum)")
        self.btn_fast_forward = QPushButton("Hızlı Test (Backtest)")
        self.btn_play.clicked.connect(self._on_play)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_step.clicked.connect(self._on_step)
        self.btn_fast_forward.clicked.connect(self._on_fast_forward)
        self.btn_restart = QPushButton("Baştan Simüle Et")
        self.btn_restart.clicked.connect(self._on_restart_simulation)
        self.btn_new_dates = QPushButton("Farklı Tarihlerle Simüle Et")
        self.btn_new_dates.clicked.connect(self._on_simulate_different_dates)
        ctrl_row.addWidget(self.btn_play)
        ctrl_row.addWidget(self.btn_pause)
        ctrl_row.addWidget(self.btn_step)
        ctrl_row.addWidget(self.btn_fast_forward)
        ctrl_row.addWidget(self.btn_restart)
        ctrl_row.addWidget(self.btn_new_dates)
        main_layout.addLayout(ctrl_row)

        # ----- Canlı İşlem Paneli (Sekme 1 altı) -----
        live_group = QGroupBox("Canlı İşlem")
        live_layout = QVBoxLayout(live_group)
        self.table_live = QTableWidget()
        self.table_live.setColumnCount(6)
        self.table_live.setHorizontalHeaderLabels([
            "Bot İsmi", "Yön", "Giriş", "Güncel SL", "Güncel TP", "Canlı PnL (%)"
        ])
        self.table_live.horizontalHeader().setStretchLastSection(True)
        live_layout.addWidget(self.table_live)
        main_layout.addWidget(live_group)

        self.tabs.addTab(tab1, "Grafik & İşlem")

        # ========== SEKME 2: Botlar & İstatistikler ==========
        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)
        bot_group = QGroupBox("Bot Yöneticisi")
        self._bot_layout = QVBoxLayout(bot_group)
        for bot in self._bots:
            cb = QCheckBox(getattr(bot, "name", str(bot)))
            cb.setChecked(False)
            self._bot_checkboxes[getattr(bot, "name", str(bot))] = cb
            self._bot_layout.addWidget(cb)
        if not self._bots:
            self._bot_layout.addWidget(QLabel("Tanımlı bot yok."))
        self._bot_layout.addStretch()
        tab2_layout.addWidget(bot_group)
        stats_group = QGroupBox("Gelişmiş İstatistikler (Tüm Zamanlar / Anlık Test)")
        stats_grid = QGridLayout(stats_group)
        self.label_win_rate = QLabel("Win Rate: -")
        self.label_total_pnl = QLabel("Toplam PnL: -")
        self.label_max_dd = QLabel("Max Drawdown: -")
        self.label_total_trades = QLabel("Toplam İşlem: -")
        self.label_commission = QLabel("Toplam Komisyon: -")
        stats_grid.addWidget(self.label_win_rate, 0, 0)
        stats_grid.addWidget(self.label_total_pnl, 0, 1)
        stats_grid.addWidget(self.label_max_dd, 1, 0)
        stats_grid.addWidget(self.label_total_trades, 1, 1)
        stats_grid.addWidget(self.label_commission, 2, 0)
        tab2_layout.addWidget(stats_group)
        bot_stats_group = QGroupBox("Bot Bazlı İstatistikler")
        bot_stats_layout = QVBoxLayout(bot_stats_group)
        self.tree_bot_stats = QTreeWidget()
        self.tree_bot_stats.setHeaderLabels(["Metrik", "Değer"])
        self.tree_bot_stats.setColumnCount(2)
        bot_stats_layout.addWidget(self.tree_bot_stats)
        tab2_layout.addWidget(bot_stats_group)
        tab2_layout.addWidget(QLabel("Bot Logları (hata / bilgi):"))
        self.text_bot_log = QTextEdit()
        self.text_bot_log.setReadOnly(True)
        self.text_bot_log.setMaximumHeight(120)
        tab2_layout.addWidget(self.text_bot_log)
        tab2_layout.addStretch()
        self.tabs.addTab(tab2, "Botlar & İstatistikler")

        # ========== SEKME 3: İşlem Logu ==========
        tab3 = QWidget()
        log_layout = QVBoxLayout(tab3)
        export_row = QHBoxLayout()
        self.btn_export = QPushButton("Logları CSV'ye Aktar")
        self.btn_export.clicked.connect(self._on_export_csv)
        export_row.addWidget(self.btn_export)
        export_row.addStretch()
        log_layout.addLayout(export_row)
        self.table_log = QTableWidget()
        self.table_log.setColumnCount(11)
        self.table_log.setHorizontalHeaderLabels([
            "Tarih", "Yön", "Giriş Fiyat", "Çıkış Fiyat", "Marjin", "PnL", "ROE %", "Kapanış Sebebi", "Tetikleyici", "Komisyon", "Bakiye"
        ])
        self.table_log.horizontalHeader().setStretchLastSection(True)
        log_layout.addWidget(self.table_log)
        self.tabs.addTab(tab3, "İşlem Logu")

        right_main.addWidget(self.tabs)

        # Ana yerleşim: sol toolbar + sağ içerik
        central = QWidget()
        h = QHBoxLayout(central)
        h.addWidget(left_toolbar)
        h.addWidget(right, stretch=1)
        self.setCentralWidget(central)

        # Çizim araçları bağlantıları
        btn_trend.clicked.connect(lambda: add_trend_line(self.plot_candles))
        btn_ray.clicked.connect(lambda: add_ray(self.plot_candles))
        btn_range.clicked.connect(lambda: add_price_range(self.plot_candles))
        btn_long.clicked.connect(lambda: add_long_position_tool(self.plot_candles))
        btn_short.clicked.connect(lambda: add_short_position_tool(self.plot_candles))

        data_engine.candle_emitted.connect(self._on_candle)
        data_engine.stream_finished.connect(self._on_stream_finished)
        data_engine.timeframe_candle_completed.connect(self._on_timeframe_candle_completed)
        data_engine.fast_forward_progress.connect(self._on_fast_forward_progress)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._update_balance_label()
        self._update_position_label()
        self._update_stats()
        self._on_speed_preset_changed(self.combo_speed.currentText())

    def _set_timeframe(self, tf: str) -> None:
        self.data_engine.set_timeframe(tf)
        for t, btn in self._tf_buttons.items():
            if isinstance(btn, QPushButton):
                btn.setChecked(btn.text() == tf)
        self._refresh_display_candles()

    def _refresh_display_candles(self) -> None:
        candles = self.data_engine.get_display_candles()
        times = [c.get("time", "") for c in candles]
        self._axis_dates.set_time_labels(times)
        self._axis_dates_volume.set_time_labels(times)
        self._axis_dates_rsi.set_time_labels(times)
        self._axis_dates_macd.set_time_labels(times)
        self.candlestick_item.set_data(candles)
        if candles:
            close = candles[-1]["close"]
            self.price_line.setPos(close)
            x_range = max(1, len(candles) * 1.1)
            self.plot_candles.setXRange(0, x_range)
            y_min = min(c["low"] for c in candles)
            y_max = max(c["high"] for c in candles)
            margin = (y_max - y_min) * 0.05 or 1
            self.plot_candles.setYRange(y_min - margin, y_max + margin)
        if self.cb_volume.isChecked():
            self._update_volume(candles)
        if self.cb_rsi.isChecked():
            self._update_rsi_from_candles(candles)
        if self.cb_macd.isChecked():
            self._update_macd_from_candles(candles)
        if self.cb_ema.isChecked():
            self._update_ema_from_candles(candles)

    def _toggle_rsi(self, checked: bool) -> None:
        self.plot_rsi.setVisible(checked)
        if checked:
            self._update_rsi_from_candles(self.data_engine.get_display_candles())

    def _toggle_volume(self, checked: bool) -> None:
        self.plot_volume.setVisible(checked)
        if checked:
            self._update_volume(self.data_engine.get_display_candles())

    def _toggle_macd(self, checked: bool) -> None:
        self.plot_macd.setVisible(checked)
        if checked:
            self._update_macd_from_candles(self.data_engine.get_display_candles())

    def _toggle_ema(self, checked: bool) -> None:
        self.ema20_curve.setVisible(checked)
        self.ema50_curve.setVisible(checked)
        if checked:
            self._update_ema_from_candles(self.data_engine.get_display_candles())

    def _update_volume(self, candles: List[Dict[str, Any]]) -> None:
        if not candles:
            self.volume_bars.setOpts(x=[], height=[])
            return
        x = list(range(len(candles)))
        heights = [c.get("volume", 0) for c in candles]
        self.volume_bars.setOpts(x=x, height=heights, width=0.8)
        self.plot_volume.setXRange(0, max(1, len(candles) * 1.1))

    def _update_rsi_from_candles(self, candles: List[Dict[str, Any]]) -> None:
        if not candles or len(candles) < 15 or ta is None:
            return
        try:
            close = pd.Series([c["close"] for c in candles])
            rsi = ta.rsi(close, length=14)
            if rsi is None or rsi.dropna().empty:
                return
            rsi = rsi.fillna(50)
            self.rsi_curve.setData(rsi.tolist())
            self.plot_rsi.setXRange(0, max(1, len(rsi) * 1.05))
        except Exception:
            pass

    def _update_macd_from_candles(self, candles: List[Dict[str, Any]]) -> None:
        if not candles or len(candles) < 30 or ta is None:
            return
        try:
            close = pd.Series([c["close"] for c in candles])
            macd = ta.macd(close, fast=12, slow=26, signal=9)
            if macd is None or not isinstance(macd, pd.DataFrame):
                return
            if len(macd.columns) >= 1:
                self.macd_curve.setData(macd[macd.columns[0]].fillna(0).tolist())
            if len(macd.columns) >= 2:
                self.macd_signal_curve.setData(macd[macd.columns[1]].fillna(0).tolist())
            self.plot_macd.setXRange(0, max(1, len(candles) * 1.05))
        except Exception:
            pass

    def _update_ema_from_candles(self, candles: List[Dict[str, Any]]) -> None:
        if not candles or ta is None:
            return
        try:
            close = pd.Series([c["close"] for c in candles])
            ema20 = ta.ema(close, length=20)
            ema50 = ta.ema(close, length=50)
            if ema20 is not None and not ema20.dropna().empty:
                self.ema20_curve.setData(ema20.bfill().ffill().tolist())
            if ema50 is not None and not ema50.dropna().empty:
                self.ema50_curve.setData(ema50.bfill().ffill().tolist())
        except Exception:
            try:
                if len(candles) >= 20:
                    close = pd.Series([c["close"] for c in candles])
                    self.ema20_curve.setData(close.ewm(span=20, adjust=False).mean().tolist())
                if len(candles) >= 50:
                    self.ema50_curve.setData(close.ewm(span=50, adjust=False).mean().tolist())
            except Exception:
                pass

    def _on_play(self) -> None:
        self.data_engine.play()

    def _on_pause(self) -> None:
        self.data_engine.pause()

    def _on_step(self) -> None:
        self.data_engine.step_forward()

    def _on_speed_preset_changed(self, preset: str) -> None:
        from data_engine import SPEED_PRESETS
        if preset in SPEED_PRESETS:
            self.data_engine.set_speed_preset(preset)
            ms, _ = SPEED_PRESETS[preset]
            self.slider_speed.setValue(ms)
            self.label_speed.setText(str(ms))

    def _on_speed_changed(self, value: int) -> None:
        self.data_engine.set_speed_ms(value)
        self.label_speed.setText(str(value))

    def _on_timeframe_candle_completed(self, timeframe: str, candle: Dict[str, Any]) -> None:
        for bot in self._bots:
            if getattr(bot, "timeframe", None) != timeframe:
                continue
            name = getattr(bot, "name", None)
            if name and self._bot_checkboxes.get(name) and self._bot_checkboxes[name].isChecked():
                try:
                    bot.on_timeframe_candle(timeframe, candle)
                except Exception:
                    pass

    def _on_candle(self, candle: Dict[str, Any], index: int) -> None:
        close = candle["close"]

        closed = self.trading_engine.check_price(close)

        if self._fast_forward_active:
            # Hızlı simülasyon: sadece motor çalışır; grafik/UI atlanır, sonunda tek seferde güncellenir
            equity = self.trading_engine.get_equity_at_price(close)
            self._equity_x.append(float(index))
            self._equity_y.append(equity)
            return

        self._refresh_display_candles()
        if closed:
            self._update_balance_label()
            self._update_position_label()
            self._add_log_row(closed["record"])
            self._update_stats()

        self._update_live_trades_table(close)
        self._sync_log_table_from_history()
        for msg in self.trading_engine.get_and_clear_log_messages():
            self.text_bot_log.append(msg.strip())

        equity = self.trading_engine.get_equity_at_price(close)
        self._equity_x.append(float(index))
        self._equity_y.append(equity)
        self.equity_curve.setData(self._equity_x, self._equity_y)
        if self._equity_x:
            self.plot_equity.setXRange(0, max(self._equity_x) * 1.05)
            if self._equity_y:
                self.plot_equity.setYRange(min(self._equity_y) * 0.99, max(self._equity_y) * 1.01)

    def _on_stream_finished(self) -> None:
        self.btn_play.setEnabled(False)
        self.btn_fast_forward.setEnabled(False)
        self.data_engine.pause()
        self.setWindowTitle("BTC Futures Simülatörü")

        if self._fast_forward_active:
            # Hızlı simülasyon bitti: grafik ve tüm UI tek seferde güncellenir
            self._refresh_display_candles()
            self._update_balance_label()
            self._update_position_label()
            self._update_stats()
            price = self.data_engine.get_current_price()
            if price is not None:
                self._update_live_trades_table(price)
            self._sync_log_table_from_history()
            if self._equity_x and self._equity_y:
                self.equity_curve.setData(self._equity_x, self._equity_y)
                self.plot_equity.setXRange(0, max(self._equity_x) * 1.05)
                self.plot_equity.setYRange(min(self._equity_y) * 0.99, max(self._equity_y) * 1.01)
            for msg in self.trading_engine.get_and_clear_log_messages():
                self.text_bot_log.append(msg.strip())
            self._fast_forward_active = False

        QMessageBox.information(self, "Bilgi", "Veri sonuna ulaşıldı.")

    def _on_fast_forward(self) -> None:
        self.btn_play.setEnabled(False)
        self.btn_fast_forward.setEnabled(False)
        self._fast_forward_active = True
        self.data_engine.run_fast_forward(batch_size=100)

    def _rebuild_bot_checkboxes(self) -> None:
        """Bot listesine göre checkbox'ları yeniden oluşturur."""
        while self._bot_layout.count():
            item = self._bot_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._bot_checkboxes.clear()
        for bot in self._bots:
            cb = QCheckBox(getattr(bot, "name", str(bot)))
            cb.setChecked(False)
            self._bot_checkboxes[getattr(bot, "name", str(bot))] = cb
            self._bot_layout.insertWidget(self._bot_layout.count(), cb)
        if not self._bots:
            self._bot_layout.insertWidget(0, QLabel("Tanımlı bot yok."))
        self._bot_layout.addStretch()

    def _on_restart_simulation(self) -> None:
        """Simülasyonu başa alır; motor ve botlar sıfırlanır."""
        self.data_engine.reset_to_start()
        self.trading_engine.reset()
        if self._get_bots:
            self._bots = self._get_bots(self.trading_engine, self.data_engine)
            self._rebuild_bot_checkboxes()
        self._equity_x.clear()
        self._equity_y.clear()
        self.equity_curve.setData([], [])
        self.table_log.setRowCount(0)
        self.text_bot_log.clear()
        self._refresh_display_candles()
        self._update_balance_label()
        self._update_position_label()
        self._update_stats()
        self._update_live_trades_table(
            self.data_engine.get_current_price() or 0.0
        )
        if self.data_engine.has_data():
            self.btn_play.setEnabled(True)
            self.btn_fast_forward.setEnabled(True)
        self.setWindowTitle("BTC Futures Simülatörü")

    def _on_simulate_different_dates(self) -> None:
        """Tarih aralığı seçerek yeni veri yükler ve simülasyonu sıfırlar."""
        from startup_dialog import StartupDialog
        dialog = StartupDialog(self)
        if dialog.exec_() != dialog.Accepted:
            return
        start_date = dialog.get_start_date()
        end_date = dialog.get_end_date()
        csv_path = dialog.get_csv_path()
        df_fetched = dialog.get_fetched_dataframe()
        start_dt = dt.combine(start_date, dt.min.time())
        end_dt = dt.now() if end_date == date.today() else dt.combine(end_date, dt.max.time())
        if df_fetched is not None and not df_fetched.empty:
            ok = self.data_engine.load_from_dataframe(
                df_fetched, start_date=start_dt, end_date=end_dt
            )
            if not ok:
                self.data_engine.load_from_dataframe(df_fetched)
        elif csv_path and csv_path.strip():
            import os
            if os.path.isfile(csv_path):
                ok = self.data_engine.load_csv(
                    csv_path, start_date=start_dt, end_date=end_dt
                )
                if not ok:
                    self.data_engine.load_csv(csv_path)
        if not self.data_engine.has_data():
            self.data_engine.generate_mock_data_for_range(start_dt, end_dt)
        if not self.data_engine.has_data():
            self.data_engine.generate_mock_data(800)
        self.data_engine.reset_to_start()
        self.trading_engine.reset()
        if self._get_bots:
            self._bots = self._get_bots(self.trading_engine, self.data_engine)
            self._rebuild_bot_checkboxes()
        self._equity_x.clear()
        self._equity_y.clear()
        self.equity_curve.setData([], [])
        self.table_log.setRowCount(0)
        self.text_bot_log.clear()
        self._refresh_display_candles()
        self._update_balance_label()
        self._update_position_label()
        self._update_stats()
        if self.data_engine.has_data():
            self.btn_play.setEnabled(True)
            self.btn_fast_forward.setEnabled(True)
        self.setWindowTitle("BTC Futures Simülatörü")
        QMessageBox.information(
            self,
            "Bilgi",
            f"Veri yüklendi: {start_date} - {end_date}. Simülasyonu Oynat veya Hızlı Test ile başlatın.",
        )

    def _update_stats(self) -> None:
        s = self.trading_engine.get_stats()
        self.label_win_rate.setText(f"Win Rate: {s['win_rate_pct']:.1f}%")
        self.label_total_pnl.setText(f"Toplam PnL: {s['total_pnl']:.2f} USDT")
        self.label_max_dd.setText(f"Max Drawdown: {s['max_drawdown']:.2f} USDT")
        self.label_total_trades.setText(f"Toplam İşlem: {s['total_trades']}")
        self.label_commission.setText(f"Toplam Komisyon: {s['total_commission']:.2f} USDT")
        self._update_bot_stats_tree()

    def _update_live_trades_table(self, current_price: float) -> None:
        """Canlı işlem tablosunu günceller (her 1m mumda)."""
        pos = self.trading_engine.get_position()
        self.table_live.setRowCount(0)
        if pos is None:
            return
        row = self.table_live.rowCount()
        self.table_live.insertRow(row)
        entry = pos["entry_price"]
        if pos["direction"] == "long":
            pnl_pct = (current_price - entry) / entry * 100.0
        else:
            pnl_pct = (entry - current_price) / entry * 100.0
        self.table_live.setItem(row, 0, QTableWidgetItem(pos.get("opened_by", "Manuel")))
        self.table_live.setItem(row, 1, QTableWidgetItem(pos["direction"].upper()))
        self.table_live.setItem(row, 2, QTableWidgetItem(f"{entry:.2f}"))
        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")
        self.table_live.setItem(row, 3, QTableWidgetItem(f"{sl:.2f}" if sl is not None else "-"))
        self.table_live.setItem(row, 4, QTableWidgetItem(f"{tp:.2f}" if tp is not None else "-"))
        self.table_live.setItem(row, 5, QTableWidgetItem(f"{pnl_pct:.2f}%"))

    def _sync_log_table_from_history(self) -> None:
        """İşlem geçmişindeki yeni kayıtları tabloya ekler (kısmi kapanış vb.)."""
        history = self.trading_engine.get_trade_history()
        current_rows = self.table_log.rowCount()
        if len(history) <= current_rows:
            return
        for r in history[current_rows:]:
            self._add_log_row(r)

    def _update_bot_stats_tree(self) -> None:
        """Bot bazlı istatistikleri QTreeWidget'ta gösterir."""
        self.tree_bot_stats.clear()
        history = self.trading_engine.get_trade_history()
        if not history:
            return
        by_bot: Dict[str, List[Dict]] = {}
        for r in history:
            bot_name = r.get("tetikleyici") or "Manuel"
            by_bot.setdefault(bot_name, []).append(r)
        for bot_name, recs in by_bot.items():
            parent = QTreeWidgetItem(self.tree_bot_stats, [bot_name, ""])
            wins = sum(1 for r in recs if r.get("pnl", 0) > 0)
            total = len(recs)
            win_rate = (wins / total * 100.0) if total else 0.0
            parent.addChild(QTreeWidgetItem(["Win Rate (%)", f"{win_rate:.1f}"]))
            durations_min = []
            for r in recs:
                et = r.get("entry_time") or ""
                xt = r.get("exit_time") or r.get("tarih") or ""
                if et and xt:
                    try:
                        t0 = dt.strptime(et, "%Y-%m-%d %H:%M:%S")
                        t1 = dt.strptime(xt, "%Y-%m-%d %H:%M:%S")
                        durations_min.append((t1 - t0).total_seconds() / 60.0)
                    except Exception:
                        pass
            avg_min = sum(durations_min) / len(durations_min) if durations_min else 0.0
            parent.addChild(QTreeWidgetItem(["Ortalama İşlem Süresi (Dakika)", f"{avg_min:.1f}"]))
            parent.addChild(QTreeWidgetItem(["Toplam İşlem", str(total)]))
        self.tree_bot_stats.expandAll()

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self._update_stats()

    def _on_fast_forward_progress(self, current: int, total: int) -> None:
        self.setWindowTitle(f"BTC Futures Simülatörü — Hızlı Test {current}/{total}")

    def _update_balance_label(self) -> None:
        u = self.trading_engine.get_balance_usdt()
        pos = self.trading_engine.get_position()
        if pos:
            self.label_balance.setText(f"USDT: {u:,.2f} (Marjin bloke: {pos['margin_usdt']:.2f})")
        else:
            self.label_balance.setText(f"USDT: {u:,.2f}")

    def _update_position_label(self) -> None:
        pos = self.trading_engine.get_position()
        if pos is None:
            self.label_position.setText("Açık pozisyon yok")
            return
        self.label_position.setText(
            f"{pos['direction'].upper()} | Giriş: {pos['entry_price']:.2f} | "
            f"Liq: {pos['liquidation_price']:.2f} | SL: {pos['stop_loss'] or '-'}"
        )

    def _on_long(self) -> None:
        price = self.data_engine.get_current_price()
        if price is None:
            QMessageBox.warning(self, "Uyarı", "Fiyat yok. Veriyi oynatın veya ileri sarın.")
            return
        margin = self.margin_spin.value()
        lev = self.leverage_spin.value()
        sl = self.sl_spin.value() if self.sl_spin.value() > 0 else None
        r = self.trading_engine.open_long(price, margin, lev, sl)
        if r.get("success"):
            self._update_balance_label()
            self._update_position_label()
        else:
            QMessageBox.warning(self, "Hata", r.get("message", "Bilinmeyen hata"))

    def _on_short(self) -> None:
        price = self.data_engine.get_current_price()
        if price is None:
            QMessageBox.warning(self, "Uyarı", "Fiyat yok. Veriyi oynatın veya ileri sarın.")
            return
        margin = self.margin_spin.value()
        lev = self.leverage_spin.value()
        sl = self.sl_spin.value() if self.sl_spin.value() > 0 else None
        r = self.trading_engine.open_short(price, margin, lev, sl)
        if r.get("success"):
            self._update_balance_label()
            self._update_position_label()
        else:
            QMessageBox.warning(self, "Hata", r.get("message", "Bilinmeyen hata"))

    def _on_close_position(self) -> None:
        price = self.data_engine.get_current_price()
        if price is None:
            QMessageBox.warning(self, "Uyarı", "Fiyat yok.")
            return
        r = self.trading_engine.close_position(price)
        if "closed" in r and r["closed"]:
            self._update_balance_label()
            self._update_position_label()
            self._add_log_row(r["record"])
            self._update_stats()
        else:
            QMessageBox.information(self, "Bilgi", r.get("message", "Açık pozisyon yok."))

    def _add_log_row(self, record: Dict[str, Any]) -> None:
        row = self.table_log.rowCount()
        self.table_log.insertRow(row)
        self.table_log.setItem(row, 0, QTableWidgetItem(record.get("tarih", "")))
        self.table_log.setItem(row, 1, QTableWidgetItem(record.get("yon", "")))
        self.table_log.setItem(row, 2, QTableWidgetItem(f"{record.get('giris_fiyat', 0):.2f}"))
        self.table_log.setItem(row, 3, QTableWidgetItem(f"{record.get('cikis_fiyat', 0):.2f}"))
        self.table_log.setItem(row, 4, QTableWidgetItem(f"{record.get('marjin', 0):.2f}"))
        self.table_log.setItem(row, 5, QTableWidgetItem(f"{record.get('pnl', 0):.2f}"))
        self.table_log.setItem(row, 6, QTableWidgetItem(f"{record.get('roe_pct', 0):.2f}"))
        self.table_log.setItem(row, 7, QTableWidgetItem(record.get("kapanis_sebebi", "")))
        self.table_log.setItem(row, 8, QTableWidgetItem(record.get("tetikleyici", "Manuel")))
        self.table_log.setItem(row, 9, QTableWidgetItem(f"{record.get('komisyon', 0):.2f}"))
        self.table_log.setItem(row, 10, QTableWidgetItem(f"{record.get('bakiye', 0):.2f}"))

    def _on_export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Logları CSV'ye Aktar", "", "CSV (*.csv);;Tüm Dosyalar (*)")
        if not path:
            return
        history = self.trading_engine.get_trade_history()
        if not history:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak işlem yok.")
            return
        df = pd.DataFrame(history)
        try:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            QMessageBox.information(self, "Başarılı", f"Kaydedildi: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kayıt hatası: {e}")
