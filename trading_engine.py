# -*- coding: utf-8 -*-
"""
Trading Engine: İzole marjinli vadeli işlem (Futures) motoru.
Tek açık pozisyon; likidasyon ve stop-loss kontrolü her fiyat güncellemesinde.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

# Position: giriş fiyatı, yön, kaldıraç, marjin, likidasyon fiyatı, stop loss
_POSITION_FIELDS = (
    "entry_price", "direction", "leverage", "margin_usdt",
    "liquidation_price", "stop_loss", "position_size_btc"
)


def _liquidation_long(entry: float, leverage: float) -> float:
    """Long için likidasyon fiyatı: entry * (1 - 1/leverage)."""
    return entry * (1.0 - 1.0 / leverage)


def _liquidation_short(entry: float, leverage: float) -> float:
    """Short için likidasyon fiyatı: entry * (1 + 1/leverage)."""
    return entry * (1.0 + 1.0 / leverage)


class TradingEngine:
    """
    İzole marjinli futures simülasyonu.
    - Tek açık pozisyon (Long veya Short).
    - Marjin USDT cinsinden bloke edilir.
    - check_price(current_price) her fiyat güncellemesinde çağrılmalı; stop/likidasyon tetiklenirse otomatik kapatır.
    - open_long / open_short: marjin ve kaldıraç ile pozisyon açar.
    - close_position: piyasa fiyatı ile manuel kapatma.
    """

    def __init__(self, initial_usdt: float = 10_000.0):
        self._balance_usdt = float(initial_usdt)
        self._initial_usdt = float(initial_usdt)
        self._position: Optional[Dict[str, Any]] = None  # tek pozisyon
        self._trade_history: List[Dict[str, Any]] = []

    def get_balance_usdt(self) -> float:
        """Toplam USDT (serbest + bloke marjin)."""
        return self._balance_usdt

    def get_available_balance(self) -> float:
        """İşleme açık bakiye (bloke marjin düşülmüş)."""
        if self._position is None:
            return self._balance_usdt
        return self._balance_usdt - self._position["margin_usdt"]

    def get_position(self) -> Optional[Dict[str, Any]]:
        """Açık pozisyon veya None."""
        return self._position.copy() if self._position else None

    def get_trade_history(self) -> List[Dict[str, Any]]:
        return self._trade_history.copy()

    def get_equity_at_price(self, mark_price: float) -> float:
        """Verilen fiyata göre toplam equity (USDT). Serbest bakiye + pozisyonun anlık değeri."""
        eq = self._balance_usdt
        if self._position:
            pos = self._position
            entry = pos["entry_price"]
            size_btc = pos["position_size_btc"]
            if pos["direction"] == "long":
                eq += size_btc * (mark_price - entry)
            else:
                eq += size_btc * (entry - mark_price)
        return eq

    def open_long(
        self,
        entry_price: float,
        margin_usdt: float,
        leverage: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        opened_by: str = "Manuel",
    ) -> Dict[str, Any]:
        """
        Long pozisyon açar. Marjin kadar USDT bloke edilir.
        position_size_btc = (margin_usdt * leverage) / entry_price
        opened_by: "Manuel" veya bot adı (örn. "TestBot_15m").
        """
        if self._position is not None:
            return self._fail("Zaten açık pozisyon var. Önce kapatın.")
        try:
            margin = float(margin_usdt)
            lev = float(leverage)
            price = float(entry_price)
        except (TypeError, ValueError):
            return self._fail("Geçersiz sayı.")

        if margin <= 0 or lev < 1 or price <= 0:
            return self._fail("Marjin, kaldıraç ve fiyat pozitif olmalı.")
        if lev > 100:
            return self._fail("Kaldıraç en fazla 100x olabilir.")

        available = self._balance_usdt
        if margin > available:
            return self._fail(f"Yetersiz bakiye. Gerekli marjin: {margin:.2f}, Mevcut: {available:.2f}")

        notional = margin * lev
        size_btc = notional / price
        liq = _liquidation_long(price, lev)
        self._position = {
            "entry_price": price,
            "direction": "long",
            "leverage": lev,
            "margin_usdt": margin,
            "liquidation_price": liq,
            "stop_loss": float(stop_loss) if stop_loss is not None else None,
            "take_profit": float(take_profit) if take_profit is not None else None,
            "position_size_btc": size_btc,
            "opened_by": opened_by or "Manuel",
        }
        return {"success": True, "message": "Long açıldı.", "position": self._position.copy()}

    def open_short(
        self,
        entry_price: float,
        margin_usdt: float,
        leverage: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        opened_by: str = "Manuel",
    ) -> Dict[str, Any]:
        """Short pozisyon açar. opened_by: 'Manuel' veya bot adı."""
        if self._position is not None:
            return self._fail("Zaten açık pozisyon var. Önce kapatın.")
        try:
            margin = float(margin_usdt)
            lev = float(leverage)
            price = float(entry_price)
        except (TypeError, ValueError):
            return self._fail("Geçersiz sayı.")

        if margin <= 0 or lev < 1 or price <= 0:
            return self._fail("Marjin, kaldıraç ve fiyat pozitif olmalı.")
        if lev > 100:
            return self._fail("Kaldıraç en fazla 100x olabilir.")

        available = self._balance_usdt
        if margin > available:
            return self._fail(f"Yetersiz bakiye. Gerekli marjin: {margin:.2f}, Mevcut: {available:.2f}")

        notional = margin * lev
        size_btc = notional / price
        liq = _liquidation_short(price, lev)
        self._position = {
            "entry_price": price,
            "direction": "short",
            "leverage": lev,
            "margin_usdt": margin,
            "liquidation_price": liq,
            "stop_loss": float(stop_loss) if stop_loss is not None else None,
            "take_profit": float(take_profit) if take_profit is not None else None,
            "position_size_btc": size_btc,
            "opened_by": opened_by or "Manuel",
        }
        return {"success": True, "message": "Short açıldı.", "position": self._position.copy()}

    def close_position(self, exit_price: float) -> Dict[str, Any]:
        """Pozisyonu piyasa fiyatı ile kapatır. PnL bakiye ile birleştirilir."""
        if self._position is None:
            return self._fail("Açık pozisyon yok.")
        return self._do_close(exit_price, "Manuel (Market)", None)

    def check_price(self, current_price: float) -> Optional[Dict[str, Any]]:
        """
        Her fiyat güncellemesinde çağrılmalı. Take Profit, Stop Loss veya likidasyon
        tetiklenirse pozisyonu otomatik kapatır ve kapanış kaydı döner; yoksa None.
        """
        if self._position is None:
            return None
        pos = self._position
        entry = pos["entry_price"]
        liq = pos["liquidation_price"]
        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")

        if pos["direction"] == "long":
            if current_price <= liq:
                return self._do_close(liq, "Likidasyon", pos.get("opened_by"))
            if tp is not None and current_price >= tp:
                return self._do_close(current_price, "Take Profit", pos.get("opened_by"))
            if sl is not None and current_price <= sl:
                return self._do_close(sl, "Stop Loss", pos.get("opened_by"))
        else:
            if current_price >= liq:
                return self._do_close(liq, "Likidasyon", pos.get("opened_by"))
            if tp is not None and current_price <= tp:
                return self._do_close(current_price, "Take Profit", pos.get("opened_by"))
            if sl is not None and current_price >= sl:
                return self._do_close(sl, "Stop Loss", pos.get("opened_by"))
        return None

    def _do_close(self, exit_price: float, close_reason: str, tetikleyici: Optional[str] = None) -> Dict[str, Any]:
        pos = self._position
        entry = pos["entry_price"]
        margin = pos["margin_usdt"]
        size_btc = pos["position_size_btc"]
        direction = pos["direction"]
        trigger = tetikleyici if tetikleyici is not None else pos.get("opened_by", "Manuel")

        if direction == "long":
            pnl = size_btc * (exit_price - entry)
        else:
            pnl = size_btc * (entry - exit_price)

        roe_pct = (pnl / margin) * 100.0 if margin else 0.0
        self._balance_usdt += margin + pnl
        self._position = None

        record = {
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "yon": "Long" if direction == "long" else "Short",
            "giris_fiyat": entry,
            "cikis_fiyat": exit_price,
            "marjin": margin,
            "pnl": pnl,
            "roe_pct": roe_pct,
            "kapanis_sebebi": close_reason,
            "tetikleyici": trigger,
            "bakiye": self._balance_usdt,
        }
        self._trade_history.append(record)
        return {"closed": True, "record": record, "balance_usdt": self._balance_usdt}

    def _fail(self, message: str) -> Dict[str, Any]:
        return {"success": False, "message": message}
