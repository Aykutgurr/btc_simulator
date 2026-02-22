# -*- coding: utf-8 -*-
"""
UI: Timeframe selector, sol çizim araç çubuğu, mum/hacim/RSI grafikleri, futures paneli, log.
"""

from typing import Optional, List, Dict, Any

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
    ):
        super().__init__()
        self.data_engine = data_engine
        self.trading_engine = trading_engine
        self._bots = bots or []
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

        # Sağ: ana içerik
        right = QWidget()
        main_layout = QVBoxLayout(right)

        # ----- Üst: Timeframe + Kontroller + RSI/Hacim + Bakiye -----
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

        self.cb_rsi = QCheckBox("RSI Göster")
        self.cb_volume = QCheckBox("Hacim Göster")
        self.cb_rsi.toggled.connect(self._toggle_rsi)
        self.cb_volume.toggled.connect(self._toggle_volume)
        top.addWidget(self.cb_rsi)
        top.addWidget(self.cb_volume)

        top.addStretch()
        self.label_balance = QLabel("USDT: 0.00")
        top.addWidget(self.label_balance)

        main_layout.addLayout(top)

        # ----- Grafikler -----
        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_candles = pg.PlotWidget(title="BTC OHLC")

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
        self.price_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("y", width=1))
        self.plot_candles.addItem(self.price_line)
        chart_layout.addWidget(self.plot_candles, stretch=3)

        self.plot_volume = pg.PlotWidget(title="Hacim")
        self.plot_volume.setBackground("k")
        self.plot_volume.showGrid(x=True, y=True, alpha=0.3)
        self.volume_bars = pg.BarGraphItem(x=[], height=[], width=0.8, brush=pg.mkBrush(100, 100, 200, 150))
        self.plot_volume.addItem(self.volume_bars)
        self.volume_container = chart_layout.addWidget(self.plot_volume, stretch=1)
        self.plot_volume.hide()

        self.plot_rsi = pg.PlotWidget(title="RSI")
        self.plot_rsi.setBackground("k")
        self.plot_rsi.showGrid(x=True, y=True, alpha=0.3)
        self.plot_rsi.setYRange(0, 100)
        self.rsi_curve = self.plot_rsi.plot(pen=pg.mkPen("m", width=2))
        self.rsi_container = chart_layout.addWidget(self.plot_rsi, stretch=1)
        self.plot_rsi.hide()

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

        # ----- Bot Yöneticisi -----
        bot_group = QGroupBox("Bot Yöneticisi")
        bot_layout = QVBoxLayout(bot_group)
        for bot in self._bots:
            cb = QCheckBox(getattr(bot, "name", str(bot)))
            cb.setChecked(False)
            self._bot_checkboxes[getattr(bot, "name", str(bot))] = cb
            bot_layout.addWidget(cb)
        if not self._bots:
            bot_layout.addWidget(QLabel("Tanımlı bot yok."))
        bot_layout.addStretch()
        main_layout.addWidget(bot_group)

        # ----- Oynat / Duraklat / İleri Sar -----
        ctrl_row = QHBoxLayout()
        self.btn_play = QPushButton("Oynat")
        self.btn_pause = QPushButton("Duraklat")
        self.btn_step = QPushButton("İleri Sar (Tek Mum)")
        self.btn_play.clicked.connect(self._on_play)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_step.clicked.connect(self._on_step)
        ctrl_row.addWidget(self.btn_play)
        ctrl_row.addWidget(self.btn_pause)
        ctrl_row.addWidget(self.btn_step)
        main_layout.addLayout(ctrl_row)

        # ----- Log + Export -----
        log_group = QGroupBox("İşlem Logu")
        log_layout = QVBoxLayout(log_group)
        export_row = QHBoxLayout()
        self.btn_export = QPushButton("Logları CSV'ye Aktar")
        self.btn_export.clicked.connect(self._on_export_csv)
        export_row.addWidget(self.btn_export)
        export_row.addStretch()
        log_layout.addLayout(export_row)
        self.table_log = QTableWidget()
        self.table_log.setColumnCount(10)
        self.table_log.setHorizontalHeaderLabels([
            "Tarih", "Yön", "Giriş Fiyat", "Çıkış Fiyat", "Marjin", "PnL", "ROE %", "Kapanış Sebebi", "Tetikleyici", "Bakiye"
        ])
        self.table_log.horizontalHeader().setStretchLastSection(True)
        log_layout.addWidget(self.table_log)
        main_layout.addWidget(log_group)

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
        self._update_balance_label()
        self._update_position_label()
        self._on_speed_preset_changed(self.combo_speed.currentText())

    def _set_timeframe(self, tf: str) -> None:
        self.data_engine.set_timeframe(tf)
        for t, btn in self._tf_buttons.items():
            if isinstance(btn, QPushButton):
                btn.setChecked(btn.text() == tf)
        self._refresh_display_candles()

    def _refresh_display_candles(self) -> None:
        candles = self.data_engine.get_display_candles()
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
            self._update_rsi()

    def _toggle_rsi(self, checked: bool) -> None:
        self.plot_rsi.setVisible(checked)
        if checked:
            self._update_rsi()

    def _toggle_volume(self, checked: bool) -> None:
        self.plot_volume.setVisible(checked)
        if checked:
            self._update_volume(self.data_engine.get_display_candles())

    def _update_volume(self, candles: List[Dict[str, Any]]) -> None:
        if not candles:
            self.volume_bars.setOpts(x=[], height=[])
            return
        x = list(range(len(candles)))
        heights = [c.get("volume", 0) for c in candles]
        self.volume_bars.setOpts(x=x, height=heights, width=0.8)
        self.plot_volume.setXRange(0, max(1, len(candles) * 1.1))

    def _update_rsi(self) -> None:
        df = self.data_engine.get_all_1m_for_indicators()
        if df is None or len(df) < 15 or ta is None:
            return
        try:
            rsi = ta.rsi(df["close"], length=14)
            if rsi is None or rsi.dropna().empty:
                return
            rsi = rsi.fillna(50)
            self.rsi_curve.setData(rsi.tolist())
            self.plot_rsi.setXRange(0, max(1, len(rsi) * 1.05))
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
        self._refresh_display_candles()

        closed = self.trading_engine.check_price(close)
        if closed:
            self._update_balance_label()
            self._update_position_label()
            self._add_log_row(closed["record"])

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
        self.data_engine.pause()
        QMessageBox.information(self, "Bilgi", "Veri sonuna ulaşıldı.")

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
        self.table_log.setItem(row, 9, QTableWidgetItem(f"{record.get('bakiye', 0):.2f}"))

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
