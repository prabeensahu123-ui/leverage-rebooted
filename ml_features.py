"""
ml_features.py - Feature matrix for the forest.
"""

import numpy as np
from signal_engine import sma, ema, rsi, macd, bollinger_position
from features import (
    atr, volume_zscore, volatility_regime, price_volume_trend,
    adx, williams_r, classic_pivots,
)
from forecasting import ensemble_forecast

FEATURE_NAMES = [
    "price_vs_sma20",
    "price_vs_ema20",
    "price_vs_sma200",
    "price_vs_ema50",
    "rsi14",
    "macd_hist",
    "bollinger_pos",
    "forecast_gap",
    "volume_z",
    "vol_regime",
    "price_vol_trend",
    "return_1d",
    "return_3d",
    "return_7d",
    "atr_pct",
    "adx14",
    "willr14",
    "dist_pivot",
    "dist_r1",
    "dist_s1",
]

WINNING_FEATURES = [
    "atr_pct",
    "price_vol_trend",
    "return_3d",
    "price_vs_ema20",
    "price_vs_sma200",
    "price_vs_ema50",
    "macd_hist",
    "rsi14",
    "adx14",
    "willr14",
    "dist_pivot",
]


def build_features(ohlcv: dict, index: int):
    close = ohlcv["close"][: index + 1]
    high = ohlcv["high"][: index + 1]
    low = ohlcv["low"][: index + 1]
    volume = ohlcv["volume"][: index + 1]
    price = close[-1]
    atr_val = atr(high, low, close)
    atr_pct = atr_val / price if price != 0 else 0.0
    scale = atr_val if atr_val not in (0, None) else (abs(price) * 0.01 or 1.0)

    sma20 = sma(close, 20) if len(close) >= 20 else price
    ema20 = ema(close, 20) if len(close) >= 20 else price
    ema50 = ema(close, 50) if len(close) >= 50 else ema20
    sma200 = sma(close, 200) if len(close) >= 200 else sma(close, min(len(close), 100))

    rsi14 = rsi(close, 14)
    macd_line, macd_signal = macd(close)
    macd_hist = macd_line - macd_signal
    boll_pos = bollinger_position(close)
    fc = ensemble_forecast(close, steps=1)
    forecast_gap = (fc["forecast"][0] - price) / price if price != 0 else 0.0

    p, r1, s1 = classic_pivots(high, low, close)

    return [
        (price - sma20) / sma20 if sma20 != 0 else 0.0,
        (price - ema20) / ema20 if ema20 != 0 else 0.0,
        (price - sma200) / sma200 if sma200 != 0 else 0.0,
        (price - ema50) / ema50 if ema50 != 0 else 0.0,
        rsi14 / 100.0,
        macd_hist,
        boll_pos,
        forecast_gap,
        volume_zscore(volume),
        volatility_regime(close),
        price_volume_trend(close, volume),
        (close[-1] - close[-2]) / close[-2] if len(close) > 1 else 0.0,
        (close[-1] - close[-4]) / close[-4] if len(close) > 3 else 0.0,
        (close[-1] - close[-8]) / close[-8] if len(close) > 7 else 0.0,
        atr_pct,
        adx(high, low, close, 14) / 100.0,
        (williams_r(high, low, close, 14) + 100.0) / 100.0,
        (price - p) / scale,
        (price - r1) / scale,
        (price - s1) / scale,
    ]


def build_dataset(ohlcv: dict, min_history=60, label_horizon=1):
    close = ohlcv["close"]
    n = len(close)
    X, y, idxs = [], [], []
    for i in range(min_history, n - label_horizon):
        X.append(build_features(ohlcv, i))
        future_return = (close[i + label_horizon] - close[i]) / close[i]
        y.append(1 if future_return > 0 else 0)
        idxs.append(i)
    return np.array(X), np.array(y), idxs
