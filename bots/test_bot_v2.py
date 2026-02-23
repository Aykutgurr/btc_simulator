# -*- coding: utf-8 -*-
"""
TestBotV2: 15m timeframe, XGBoost Classifier ile yatay piyasalarda gün içi sekme noktaları.
Özellikler: RSI, Stoch RSI, BB %B, ATR, Volume Ratio, ADX. Hedef: sonraki 5 mumda +/- %0.5.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import pandas_ta as ta
except ImportError:
    ta = None

try:
    import xgboost as xgb
except ImportError:
    xgb = None


# Feature column names used in training and inference
FEATURE_COLS = [
    "rsi",
    "stochrsi_k",
    "bbp",
    "atr",
    "volume_ratio",
    "adx",
]


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV DataFrame üzerinde pandas_ta ile özellikleri hesaplar.
    Veri sızıntısı yok: göstergeler sadece o satıra kadar olan veriyle hesaplanır.
    """
    if ta is None or df.empty or len(df) < 21:
        return pd.DataFrame()

    high = df["high"]
    low = df["low"]
    close = df["close"]
    volume = df["volume"]

    out = pd.DataFrame(index=df.index)

    rsi = ta.rsi(close, length=14)
    if rsi is not None:
        out["rsi"] = rsi

    stoch = ta.stochrsi(close, length=14, rsi_length=14, k=3, d=3)
    if stoch is not None:
        if isinstance(stoch, pd.DataFrame):
            # STOCHRSIk_14_14_3_3, STOCHRSId_14_14_3_3 veya benzeri
            k_col = [c for c in stoch.columns if "k" in c.lower() or c.endswith("_k")]
            d_col = [c for c in stoch.columns if "d" in c.lower() and "k" not in c.lower()]
            out["stochrsi_k"] = stoch.iloc[:, 0] if not k_col else stoch[k_col[0]]
        else:
            out["stochrsi_k"] = stoch

    bbands = ta.bbands(close, length=20, std=2)
    if bbands is not None and isinstance(bbands, pd.DataFrame):
        bbp_col = [c for c in bbands.columns if "BBP" in c.upper() or "P" == c[-1]]
        if bbp_col:
            out["bbp"] = bbands[bbp_col[0]]
        else:
            out["bbp"] = bbands.iloc[:, -1]

    atr = ta.atr(high, low, close, length=14)
    if atr is not None:
        out["atr"] = atr

    vol_sma = ta.sma(volume, length=20)
    if vol_sma is not None and (vol_sma > 0).any():
        out["volume_ratio"] = volume / vol_sma.replace(0, pd.NA)
    else:
        out["volume_ratio"] = 1.0

    adx_df = ta.adx(high, low, close, length=14)
    if adx_df is not None:
        if isinstance(adx_df, pd.DataFrame):
            adx_col = [c for c in adx_df.columns if "ADX" in c.upper()]
            out["adx"] = adx_df[adx_col[0]] if adx_col else adx_df.iloc[:, 0]
        else:
            out["adx"] = adx_df

    return out


def _build_target(df: pd.DataFrame, close_col: str = "close") -> pd.Series:
    """
    Her satır için sonraki 5 mumun close'una göre hedef: 1=Long, 2=Short, 0=Nötr.
    Veri sızıntısı: sadece gelecek veri kullanılır, feature'larda kullanılmaz.
    """
    close = df[close_col]
    target = pd.Series(0, index=df.index, dtype=int)

    for i in range(len(df) - 5):
        c = close.iloc[i]
        next_closes = close.iloc[i + 1 : i + 6]
        max_fwd = next_closes.max()
        min_fwd = next_closes.min()
        up_hit = max_fwd >= c * 1.005
        down_hit = min_fwd <= c * 0.995
        if up_hit and not down_hit:
            target.iloc[i] = 1
        elif down_hit and not up_hit:
            target.iloc[i] = 2
        elif up_hit and down_hit:
            target.iloc[i] = 1  # öncelik Long

    return target


class TestBotV2:
    """
    15m mumlarda XGBoost Classifier kullanarak yatay (sideways/chop) piyasalarda
    gün içi sekme noktalarını hedefleyen ticaret botu.
    """

    name = "TestBot_V2"
    timeframe = "15m"

    def __init__(self, trading_engine: Any) -> None:
        self._engine = trading_engine
        self._history_15m: List[Dict[str, Any]] = []
        self.model = None

    def _train_model(self) -> None:
        """
        _history_15m'i DataFrame'e çevirir, özellik/hedef üretir ve XGBoost
        sınıflandırıcıyı eğitir. Veri sızıntısı yok: X geçmiş, y gelecek bilgisi.
        """
        if xgb is None or ta is None or len(self._history_15m) < 500:
            return
        try:
            df = pd.DataFrame(self._history_15m)
            df = df[["open", "high", "low", "close", "volume"]].astype(float)

            X_df = _build_features(df)
            y_series = _build_target(df)

            for col in FEATURE_COLS:
                if col not in X_df.columns:
                    return
            X_df = X_df[FEATURE_COLS].copy()
            X_df["target"] = y_series

            # NaN (gösterge warmup veya hedef yok) satırları at
            clean = X_df.dropna()
            if len(clean) < 100:
                return

            y_clean = clean["target"].astype(int)
            X_clean = clean.drop(columns=["target"])

            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric="logloss",
            )
            self.model.fit(X_clean, y_clean)
        except Exception:
            self.model = None

    def _get_last_features(self) -> Optional[pd.Series]:
        """Son mum için feature vektörünü döndürür. Eksik/NaN varsa None."""
        if len(self._history_15m) < 21 or ta is None:
            return None
        try:
            df = pd.DataFrame(self._history_15m)
            df = df[["open", "high", "low", "close", "volume"]].astype(float)
            X_df = _build_features(df)
            for col in FEATURE_COLS:
                if col not in X_df.columns:
                    return None
            last = X_df[FEATURE_COLS].iloc[-1]
            if last.isna().any():
                return None
            return last
        except Exception:
            return None

    def on_timeframe_candle(self, timeframe: str, candle: Dict[str, Any]) -> None:
        """
        15m mum tamamlandığında çağrılır. Mumları biriktirir; 500'e ulaşınca model
        eğitilir. Eğitim sonrası, yatay piyasa filtresi geçilirse XGBoost ile
        sinyal üretip long/short açar.
        """
        if timeframe != self.timeframe:
            return

        self._history_15m.append(candle.copy())

        if len(self._history_15m) >= 500:
            try:
                self._train_model()
            except Exception:
                pass

        if self.model is None:
            return
        pos = self._engine.get_position()
        if pos is not None:
            return

        try:
            df = pd.DataFrame(self._history_15m)
            if len(df) < 21:
                return
            df = df[["open", "high", "low", "close", "volume"]].astype(float)
            X_df = _build_features(df)
            if "adx" not in X_df.columns or "volume_ratio" not in X_df.columns:
                return

            last_row = X_df.iloc[-1]
            adx = last_row.get("adx", 0)
            vol_ratio = last_row.get("volume_ratio", 1.0)
            volume = float(candle.get("volume", 0))
            vol_sma = ta.sma(df["volume"], length=20)
            vol_sma_last = float(vol_sma.iloc[-1]) if vol_sma is not None and len(vol_sma) else volume

            # Piyasa filtresi: sadece yatay ve düşük hacimde işlem
            if adx >= 25 or (vol_sma_last > 0 and volume >= vol_sma_last):
                return

            features = self._get_last_features()
            if features is None:
                return

            pred = self.model.predict(features.to_frame().T)[0]
            balance = self._engine.get_balance_usdt()
            margin = balance * 0.05
            if margin < 10:
                return

            price = float(candle["close"])
            leverage = 5.0

            if pred == 1:
                tp = price * 1.005
                sl = price * 0.997
                self._engine.open_long(
                    entry_price=price,
                    margin_usdt=margin,
                    leverage=leverage,
                    stop_loss=sl,
                    take_profit=tp,
                    opened_by=self.name,
                )
            elif pred == 2:
                tp = price * 0.995
                sl = price * 1.003
                self._engine.open_short(
                    entry_price=price,
                    margin_usdt=margin,
                    leverage=leverage,
                    stop_loss=sl,
                    take_profit=tp,
                    opened_by=self.name,
                )
        except Exception:
            pass
