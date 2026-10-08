"""
features.py - Feature engineering using full OHLCV data.
"""

import numpy as np


def atr(high, low, close, period=14):
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    return np.mean(tr[-period:])


def volume_zscore(volume, period=20):
    window = volume[-period:]
    mean, std = np.mean(window), np.std(window)
    if std == 0:
        return 0.0
    return (volume[-1] - mean) / std


def volatility_regime(close, period=20, lookback=100):
    returns = np.diff(np.log(close))
    current_vol = np.std(returns[-period:])
    historical_vol = np.std(returns[-lookback:])
    if historical_vol == 0:
        return 1.0
    return current_vol / historical_vol


def price_volume_trend(close, volume, period=14):
    returns = np.diff(close[-period - 1:]) / close[-period - 1:-1]
    vol_changes = np.diff(volume[-period - 1:])
    if np.std(vol_changes) == 0 or np.std(returns) == 0:
        return 0.0
    correlation = np.corrcoef(returns, vol_changes)[0, 1]
    return correlation if not np.isnan(correlation) else 0.0


def adx(high, low, close, period=14):
    n = len(close)
    if n < period + 2:
        return 20.0
    up = high[1:] - high[:-1]
    down = low[:-1] - low[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    prev = close[:-1]
    tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - prev), np.abs(low[1:] - prev)))
    tr_s = np.mean(tr[-period:])
    if tr_s == 0:
        return 20.0
    plus_di = 100.0 * np.mean(plus_dm[-period:]) / tr_s
    minus_di = 100.0 * np.mean(minus_dm[-period:]) / tr_s
    denom = plus_di + minus_di
    if denom == 0:
        return 20.0
    dx = 100.0 * abs(plus_di - minus_di) / denom
    return float(dx)


def williams_r(high, low, close, period=14):
    if len(close) < period:
        return -50.0
    hh = np.max(high[-period:])
    ll = np.min(low[-period:])
    if hh == ll:
        return -50.0
    return float(-100.0 * (hh - close[-1]) / (hh - ll))


def classic_pivots(high, low, close):
    if len(close) < 2:
        p = float(close[-1])
        return p, p, p
    h, l, c = float(high[-2]), float(low[-2]), float(close[-2])
    p = (h + l + c) / 3.0
    r1 = 2.0 * p - l
    s1 = 2.0 * p - h
    return p, r1, s1
