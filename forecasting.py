"""
forecasting.py - Statistical forecasting for price series.
"""

import numpy as np


class DampedHoltForecaster:
    def __init__(self, alpha=0.3, beta=0.1, phi=0.90):
        self.alpha = alpha
        self.beta = beta
        self.phi = phi

    def fit(self, prices: np.ndarray):
        level, trend = prices[0], prices[1] - prices[0]
        fitted = [level]
        for price in prices[1:]:
            last_level = level
            level = self.alpha * price + (1 - self.alpha) * (level + self.phi * trend)
            trend = self.beta * (level - last_level) + (1 - self.beta) * self.phi * trend
            fitted.append(level)
        self.level, self.trend = level, trend
        self.residuals = prices - np.array(fitted)
        self.resid_std = np.std(self.residuals)
        return self

    def forecast(self, steps=1):
        points, lowers, uppers = [], [], []
        cumulative_damp = 0
        for h in range(1, steps + 1):
            cumulative_damp += self.phi ** h
            point = self.level + cumulative_damp * self.trend
            band = 1.96 * self.resid_std * np.sqrt(h)
            points.append(point)
            lowers.append(point - band)
            uppers.append(point + band)
        return np.array(points), np.array(lowers), np.array(uppers)


def log_return_trend_forecast(prices: np.ndarray, steps=1, lookback=30):
    window = prices[-lookback:]
    log_prices = np.log(window)
    x = np.arange(len(log_prices))
    slope, intercept = np.polyfit(x, log_prices, 1)
    last_x = len(log_prices) - 1
    forecasts = [np.exp(intercept + slope * (last_x + h)) for h in range(1, steps + 1)]
    return np.array(forecasts)


def ensemble_forecast(prices: np.ndarray, steps=1, holt_weight=0.65):
    holt = DampedHoltForecaster().fit(prices)
    holt_points, lower, upper = holt.forecast(steps)
    trend_points = log_return_trend_forecast(prices, steps)

    blended = holt_weight * holt_points + (1 - holt_weight) * trend_points
    disagreement = np.abs(holt_points - trend_points)
    lower = blended - (upper - holt_points) - disagreement * 0.5
    upper = blended + (upper - holt_points) + disagreement * 0.5

    return {
        "forecast": blended,
        "lower_band": lower,
        "upper_band": upper,
        "holt_only": holt_points,
        "trend_only": trend_points,
    }
