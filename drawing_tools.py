# -*- coding: utf-8 -*-
"""
Çizim araçları: Trend çizgisi, Işın, Fiyat aralığı, Long/Short pozisyon ROI.
pyqtgraph ROI ve GraphicsObject kullanır.
"""

from typing import Optional, List, Tuple

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QBrush, QPen, QColor

try:
    from pyqtgraph.graphicsItems.ROI import LineSegmentROI
except ImportError:
    LineSegmentROI = None


def add_trend_line(plot: pg.PlotWidget) -> Optional[object]:
    """Trend çizgisi: iki nokta ile çizilen segment. Plot'a eklenir."""
    if LineSegmentROI is None:
        return None
    vb = plot.getViewBox()
    if vb is None:
        return None
    x0, x1 = 0, 50
    y0, y1 = 40000, 40100
    roi = LineSegmentROI(positions=[[x0, y0], [x1, y1]], pen=pg.mkPen("y", width=2))
    plot.addItem(roi)
    return roi


def add_ray(plot: pg.PlotWidget) -> Optional[object]:
    """Işın: bir başlangıç noktasından sonsuza giden çizgi (uzun segment ile)."""
    if LineSegmentROI is None:
        return None
    x0, y0 = 0, 40000
    x1, y1 = 200, 40200
    roi = LineSegmentROI(positions=[[x0, y0], [x1, y1]], pen=pg.mkPen("c", width=2))
    plot.addItem(roi)
    return roi


def add_price_range(plot: pg.PlotWidget) -> Optional[pg.LinearRegionItem]:
    """Fiyat aralığı: Y (fiyat) ekseninde bölge; iki yatay sınır sürüklenebilir."""
    try:
        region = pg.LinearRegionItem(values=[40000, 41000], orientation="horizontal")
    except Exception:
        region = pg.LinearRegionItem(values=[40000, 41000])
    region.setBrush(pg.mkBrush(100, 100, 200, 50))
    region.setPen(pg.mkPen("b", width=1))
    plot.addItem(region)
    return region


class LongShortPositionROI(pg.GraphicsObject):
    """
    Long veya Short pozisyon aracı: giriş, hedef ve stop seviyeleri.
    Long: yeşil gölge (entry-target), kırmızı (entry-stop).
    Short: kırmızı gölge (entry-stop), yeşil (entry-target).
    """

    def __init__(self, entry: float, target: float, stop: float, is_long: bool = True):
        super().__init__()
        self.entry = float(entry)
        self.target = float(target)
        self.stop = float(stop)
        self.is_long = is_long
        self.x_span = 20
        self._bounds = QRectF(0, min(entry, target, stop) - 100, self.x_span, abs(entry - stop) + abs(entry - target) + 200)

    def set_levels(self, entry: float, target: float, stop: float) -> None:
        self.entry = entry
        self.target = target
        self.stop = stop
        self._bounds = QRectF(0, min(entry, target, stop) - 100, self.x_span, abs(entry - stop) + abs(entry - target) + 200)
        self.update()

    def paint(self, p: QPainter, *args) -> None:
        p.setRenderHint(QPainter.Antialiasing)
        x0, x1 = 0, self.x_span
        entry, target, stop = self.entry, self.target, self.stop
        if self.is_long:
            # Hedef yukarıda, stop aşağıda
            p.fillRect(QRectF(x0, min(entry, target), x1 - x0, abs(entry - target)), QBrush(QColor(0, 180, 0, 60)))
            p.fillRect(QRectF(x0, min(entry, stop), x1 - x0, abs(entry - stop)), QBrush(QColor(200, 0, 0, 60)))
            p.setPen(QPen(QColor(0, 200, 0), 2))
            p.drawLine(int(x0), int(entry), int(x1), int(entry))
            p.drawLine(int(x0), int(target), int(x1), int(target))
            p.setPen(QPen(QColor(200, 0, 0), 2))
            p.drawLine(int(x0), int(stop), int(x1), int(stop))
        else:
            p.fillRect(QRectF(x0, min(entry, stop), x1 - x0, abs(entry - stop)), QBrush(QColor(200, 0, 0, 60)))
            p.fillRect(QRectF(x0, min(entry, target), x1 - x0, abs(entry - target)), QBrush(QColor(0, 180, 0, 60)))
            p.setPen(QPen(QColor(200, 0, 0), 2))
            p.drawLine(int(x0), int(entry), int(x1), int(entry))
            p.drawLine(int(x0), int(stop), int(x1), int(stop))
            p.setPen(QPen(QColor(0, 200, 0), 2))
            p.drawLine(int(x0), int(target), int(x1), int(target))

    def boundingRect(self) -> QRectF:
        return self._bounds


def add_long_position_tool(plot: pg.PlotWidget, entry: float = 40000, target: float = 41000, stop: float = 39000) -> LongShortPositionROI:
    """Long pozisyon aracı ekler (giriş, hedef, stop)."""
    item = LongShortPositionROI(entry, target, stop, is_long=True)
    plot.addItem(item)
    return item


def add_short_position_tool(plot: pg.PlotWidget, entry: float = 40000, target: float = 39000, stop: float = 41000) -> LongShortPositionROI:
    """Short pozisyon aracı ekler."""
    item = LongShortPositionROI(entry, target, stop, is_long=False)
    plot.addItem(item)
    return item
