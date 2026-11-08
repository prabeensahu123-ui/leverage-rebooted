"""
forecasting.py — Statistical price-series forecasting (spec v1.2).

Damped Holt + log-return polynomial trend + ensemble blend.
Defaults match Forecasting_Module_Specification.pdf.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np


class DampedHoltForecaster:
    def __init__(self, alpha: float = 0.30, beta: float = 0.10, phi: float = 0.90):
        self.alpha = alpha
        self.beta = beta
        self.phi = phi
        self.level = None
        self.trend = None
        self.residuals = None
        self.resid_std = None

    def fit(self, prices: np.ndarray):
        prices = np.asarray(prices, dtype=float)
        if len(prices) < 3:
            raise ValueError("Need >= 3 prices")
        level = float(prices[0])
        trend = float(prices[1] - prices[0])
        fitted = [level]
        for price in prices[1:]:
            last_level = level
            level = self.alpha * float(price) + (1 - self.alpha) * (level + self.phi * trend)
            trend = self.beta * (level - last_level) + (1 - self.beta) * self.phi * trend
            fitted.append(level)
        self.level = level
        self.trend = trend
        self.residuals = prices - np.asarray(fitted, dtype=float)
        self.resid_std = float(np.std(self.residuals)) if len(self.residuals) else 0.0
        return self

    def forecast(self, steps: int = 1):
        points, lowers, uppers = [], [], []
        cumulative_damp = 0.0
        for h in range(1, steps + 1):
            cumulative_damp += self.phi ** h
            point = self.level + cumulative_damp * self.trend
            band = 1.96 * (self.resid_std or 0.0) * np.sqrt(h)
            points.append(point)
            lowers.append(point - band)
            uppers.append(point + band)
        return np.asarray(points), np.asarray(lowers), np.asarray(uppers)


def log_return_trend_forecast(prices: np.ndarray, steps: int = 1, lookback: int = 30):
    prices = np.asarray(prices, dtype=float)
    window = prices[-lookback:] if len(prices) >= lookback else prices
    if len(window) < 5:
        last = float(prices[-1])
        return np.full(steps, last)
    log_prices = np.log(np.clip(window, 1e-12, None))
    x = np.arange(len(log_prices), dtype=float)
    slope, intercept = np.polyfit(x, log_prices, 1)
    last_x = len(log_prices) - 1
    return np.asarray(
        [np.exp(intercept + slope * (last_x + h)) for h in range(1, steps + 1)],
        dtype=float,
    )


def ensemble_forecast(
    prices: np.ndarray,
    steps: int = 1,
    holt_weight: float = 0.65,
    lookback: int = 30,
) -> Dict[str, Any]:
    prices = np.asarray(prices, dtype=float)
    holt = DampedHoltForecaster().fit(prices)
    holt_points, lower, upper = holt.forecast(steps)
    trend_points = log_return_trend_forecast(prices, steps, lookback=lookback)

    blended = holt_weight * holt_points + (1.0 - holt_weight) * trend_points
    disagreement = np.abs(holt_points - trend_points)
    lower_b = blended - (upper - holt_points) - disagreement * 0.5
    upper_b = blended + (upper - holt_points) + disagreement * 0.5

    last = float(prices[-1])
    fc0 = float(blended[0])
    chg = (fc0 / last - 1.0) * 100.0 if last else 0.0
    if chg > 0.35:
        bias = "LONG"
    elif chg < -0.35:
        bias = "SHORT"
    else:
        bias = "HOLD"

    return {
        "forecast": blended,
        "lower_band": lower_b,
        "upper_band": upper_b,
        "holt_only": holt_points,
        "trend_only": trend_points,
        "last_price": last,
        "point_forecast": fc0,
        "chg_pct": chg,
        "bias": bias,
        "resid_std": holt.resid_std,
    }


def forecast_from_ohlcv(candles: list, steps: int = 3) -> Optional[Dict[str, Any]]:
    if not candles or len(candles) < 20:
        return None
    closes = np.asarray([float(c["close"]) for c in candles], dtype=float)
    return ensemble_forecast(closes, steps=steps)
