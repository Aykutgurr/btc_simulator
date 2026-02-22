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

    COMMISSION_RATE = 0.001  # %0.1 pozisyon büyüklüğü (margin * leverage) üzerinden

    def __init__(self, initial_usdt: float = 10_000.0):
        self._balance_usdt = float(initial_usdt)
        self._initial_usdt = float(initial_usdt)
        self._position: Optional[Dict[str, Any]] = None
        self._trade_history: List[Dict[str, Any]] = []
        self._log_messages: List[str] = []

    def log_message(self, msg: str) -> None:
        """UI'da gösterilmek üzere log mesajı ekler."""
        self._log_messages.append(msg)

    def get_and_clear_log_messages(self) -> List[str]:
        """Biriktirilmiş log mesajlarını döndürür ve listeyi temizler."""
        out = self._log_messages.copy()
        self._log_messages.clear()
        return out

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
        """Verilen fiyata göre toplam equity (USDT). Bakiye (marjin bloke) + pozisyonun anlık değeri."""
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

    def get_stats(self) -> Dict[str, Any]:
        """Win rate %, toplam PnL, max drawdown, toplam işlem sayısı (tüm zamanlar)."""
        total = len(self._trade_history)
        if total == 0:
            return {
                "win_rate_pct": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "total_trades": 0,
                "total_commission": 0.0,
            }
        wins = sum(1 for r in self._trade_history if r.get("pnl_net", r.get("pnl", 0)) > 0)
        total_pnl = sum(r.get("pnl_net", r.get("pnl", 0)) for r in self._trade_history)
        total_commission = sum(r.get("komisyon", 0) for r in self._trade_history)
        peak = self._initial_usdt
        max_dd = 0.0
        running = self._initial_usdt
        for r in self._trade_history:
            running = r.get("bakiye", running)
            if running > peak:
                peak = running
            dd = peak - running
            if dd > max_dd:
                max_dd = dd
        return {
            "win_rate_pct": (wins / total * 100.0) if total else 0.0,
            "total_pnl": total_pnl,
            "max_drawdown": max_dd,
            "total_trades": total,
            "total_commission": total_commission,
        }

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

        self._balance_usdt -= margin
        notional = margin * lev
        size_btc = notional / price
        liq = _liquidation_long(price, lev)
        entry_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            "entry_time": entry_time_str,
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

        self._balance_usdt -= margin
        notional = margin * lev
        size_btc = notional / price
        liq = _liquidation_short(price, lev)
        entry_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            "entry_time": entry_time_str,
        }
        return {"success": True, "message": "Short açıldı.", "position": self._position.copy()}

    def close_position(self, exit_price: float) -> Dict[str, Any]:
        """Pozisyonu piyasa fiyatı ile kapatır. PnL bakiye ile birleştirilir."""
        if self._position is None:
            return self._fail("Açık pozisyon yok.")
        return self._do_close(exit_price, "Manuel (Market)", None)

    def close_partial(self, exit_price: float, fraction: float = 0.5) -> Dict[str, Any]:
        """
        Açık pozisyonun belirtilen oranını piyasa fiyatından kapatır.
        fraction: 0-1 arası (örn. 0.5 = %50). Realize edilen kâr bakiyeye eklenir,
        kalan miktar opened_by korunarak güncellenir.
        """
        if self._position is None:
            return self._fail("Açık pozisyon yok.")
        try:
            frac = float(fraction)
        except (TypeError, ValueError):
            return self._fail("Geçersiz oran.")
        if frac <= 0 or frac >= 1:
            return self._fail("Oran 0 ile 1 arasında olmalı (örn. 0.5).")
        pos = self._position
        entry = pos["entry_price"]
        margin = pos["margin_usdt"]
        lev = pos["leverage"]
        size_btc = pos["position_size_btc"]
        direction = pos["direction"]
        notional = margin * lev
        commission_partial = (frac * notional) * self.COMMISSION_RATE
        if direction == "long":
            pnl_gross = frac * size_btc * (exit_price - entry)
        else:
            pnl_gross = frac * size_btc * (entry - exit_price)
        pnl_net = pnl_gross - commission_partial
        self._balance_usdt += frac * margin + pnl_net
        # Kalan pozisyonu güncelle
        pos["margin_usdt"] = (1 - frac) * margin
        pos["position_size_btc"] = (1 - frac) * size_btc
        entry_time = pos.get("entry_time", "")
        exit_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "tarih": exit_time_str,
            "yon": "Long" if direction == "long" else "Short",
            "giris_fiyat": entry,
            "cikis_fiyat": exit_price,
            "marjin": frac * margin,
            "pnl": pnl_net,
            "pnl_gross": pnl_gross,
            "roe_pct": (pnl_gross / (frac * margin) * 100.0) if margin else 0.0,
            "kapanis_sebebi": "Kısmi Kapanış",
            "tetikleyici": pos.get("opened_by", "Manuel"),
            "komisyon": commission_partial,
            "bakiye": self._balance_usdt,
            "entry_time": entry_time,
            "exit_time": exit_time_str,
        }
        self._trade_history.append(record)
        return {
            "partial": True,
            "record": record,
            "balance_usdt": self._balance_usdt,
            "position": self._position.copy(),
        }

    def update_position_parameters(
        self,
        new_sl: Optional[float] = None,
        new_tp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Aktif pozisyonun SL ve TP değerlerini günceller."""
        if self._position is None:
            return self._fail("Açık pozisyon yok.")
        if new_sl is not None:
            self._position["stop_loss"] = float(new_sl)
        if new_tp is not None:
            self._position["take_profit"] = float(new_tp)
        return {"success": True, "position": self._position.copy()}

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
        lev = pos["leverage"]
        size_btc = pos["position_size_btc"]
        direction = pos["direction"]
        trigger = tetikleyici if tetikleyici is not None else pos.get("opened_by", "Manuel")

        notional = margin * lev
        commission = notional * self.COMMISSION_RATE
        if direction == "long":
            pnl_gross = size_btc * (exit_price - entry)
        else:
            pnl_gross = size_btc * (entry - exit_price)
        pnl_net = pnl_gross - commission

        roe_pct = (pnl_gross / margin) * 100.0 if margin else 0.0
        self._balance_usdt += margin + pnl_net
        self._position = None

        exit_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_time = pos.get("entry_time", "")
        record = {
            "tarih": exit_time_str,
            "yon": "Long" if direction == "long" else "Short",
            "giris_fiyat": entry,
            "cikis_fiyat": exit_price,
            "marjin": margin,
            "pnl": pnl_net,
            "pnl_gross": pnl_gross,
            "roe_pct": roe_pct,
            "kapanis_sebebi": close_reason,
            "tetikleyici": trigger,
            "komisyon": commission,
            "bakiye": self._balance_usdt,
            "entry_time": entry_time,
            "exit_time": exit_time_str,
        }
        self._trade_history.append(record)
        return {"closed": True, "record": record, "balance_usdt": self._balance_usdt}

    def _fail(self, message: str) -> Dict[str, Any]:
        return {"success": False, "message": message}
