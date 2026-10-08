"""
signal_engine.py - Weighted technical signal scoring.
"""

import numpy as np
from forecasting import ensemble_forecast

WEIGHTS = {
    "trend_sma": 1.0,
    "trend_ema": 1.0,
    "rsi": 2.0,
    "macd": 1.5,
    "bollinger": 1.5,
    "forecast": 1.5,
}

BUY_THRESHOLD = 3.0
SELL_THRESHOLD = -3.0


def sma(prices, period):
    if len(prices) == 0:
        return 0.0
    return float(np.mean(prices[-period:]))


def ema_series(prices, period):
    prices = np.asarray(prices, dtype=float)
    if len(prices) == 0:
        return np.array([])
    if len(prices) < period:
        out = np.empty(len(prices))
        out[:] = prices[0]
        k = 2.0 / (period + 1.0)
        for i in range(1, len(prices)):
            out[i] = prices[i] * k + out[i - 1] * (1 - k)
        return out
    out = np.empty(len(prices))
    out[:period] = np.mean(prices[:period])
    k = 2.0 / (period + 1.0)
    for i in range(period, len(prices)):
        out[i] = prices[i] * k + out[i - 1] * (1 - k)
    return out


def ema(prices, period):
    series = ema_series(prices, period)
    return float(series[-1]) if len(series) else 0.0


def rsi(prices, period=14):
    prices = np.asarray(prices, dtype=float)
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.clip(deltas, 0, None)
    losses = np.clip(-deltas, 0, None)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow + signal:
        return 0.0, 0.0
    ema_fast = ema_series(prices, fast)
    ema_slow = ema_series(prices, slow)
    macd_line_series = ema_fast - ema_slow
    signal_line = float(np.mean(macd_line_series[-signal:]))
    return float(macd_line_series[-1]), signal_line


def bollinger_position(prices, period=20, num_std=2):
    window = prices[-period:]
    mid = np.mean(window)
    std = np.std(window)
    upper, lower = mid + num_std * std, mid - num_std * std
    price = prices[-1]
    if price <= lower:
        return -1.0
    if price >= upper:
        return 1.0
    return (price - mid) / (upper - mid) if upper != mid else 0.0


def generate_signal(prices: np.ndarray, weights: dict = None):
    w = weights or WEIGHTS
    price = prices[-1]

    sma20, ema20 = sma(prices, 20), ema(prices, 20)
    rsi14 = rsi(prices, 14)
    macd_line, macd_signal = macd(prices)
    boll_pos = bollinger_position(prices)
    fc = ensemble_forecast(prices, steps=1)
    forecast_price = fc["forecast"][0]

    components = {}
    components["trend_sma"] = w["trend_sma"] * (1 if price > sma20 else -1)
    components["trend_ema"] = w["trend_ema"] * (1 if price > ema20 else -1)

    if rsi14 < 30:
        components["rsi"] = w["rsi"] * 1
    elif rsi14 > 70:
        components["rsi"] = w["rsi"] * -1
    else:
        components["rsi"] = 0.0

    components["macd"] = w["macd"] * (1 if macd_line > macd_signal else -1)
    components["bollinger"] = w["bollinger"] * (-boll_pos)
    components["forecast"] = w["forecast"] * (1 if forecast_price > price else -1)

    score = sum(components.values())

    if score >= BUY_THRESHOLD:
        decision = "LONG"
    elif score <= SELL_THRESHOLD:
        decision = "SHORT"
    else:
        decision = "HOLD"

    return {
        "price": price, "score": round(score, 2), "decision": decision,
        "components": {k: round(v, 2) for k, v in components.items()},
        "rsi": round(rsi14, 1), "macd": round(macd_line, 2),
        "forecast": round(forecast_price, 2),
        "forecast_band": (round(fc["lower_band"][0], 2), round(fc["upper_band"][0], 2)),
    }
