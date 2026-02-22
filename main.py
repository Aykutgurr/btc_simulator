# -*- coding: utf-8 -*-
"""
BTC Vadeli İşlem Simülatörü — Ana giriş noktası.
Önce StartupDialog (tarih aralığı, veri çekme), sonra ana pencere.
"""

import sys
import os
from datetime import datetime

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication

from startup_dialog import StartupDialog
from data_engine import DataEngine
from trading_engine import TradingEngine
from ui_components import MainWindow
from bots import get_bots


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BTC Futures Simulator")

    dialog = StartupDialog()
    if dialog.exec_() != dialog.Accepted:
        sys.exit(0)

    start_date = dialog.get_start_date()
    end_date = dialog.get_end_date()
    csv_path = dialog.get_csv_path()
    df_fetched = dialog.get_fetched_dataframe()
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    data_engine = DataEngine()
    trading_engine = TradingEngine(initial_usdt=10_000.0)

    if df_fetched is not None and not df_fetched.empty:
        ok = data_engine.load_from_dataframe(df_fetched, start_date=start_dt, end_date=end_dt)
        if not ok:
            data_engine.load_from_dataframe(df_fetched)
    elif csv_path and os.path.isfile(csv_path):
        ok = data_engine.load_csv(csv_path, start_date=start_dt, end_date=end_dt)
        if not ok:
            data_engine.load_csv(csv_path)
    else:
        data_engine.generate_mock_data_for_range(start_dt, end_dt)

    if not data_engine.has_data():
        data_engine.generate_mock_data(800)

    bots_list = get_bots(trading_engine)
    window = MainWindow(data_engine, trading_engine, bots=bots_list)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
