"""
triple_barrier.py - Lopez de Prado triple-barrier labels + cost filter.
Hits are checked on candle high/low so a wick can tag TP or SL.
If both print on the same bar, stop wins (conservative).
"""

import numpy as np


def compute_local_volatility(close, period=20):
    n = len(close)
    vol = np.zeros(n)
    if n < 3:
        return vol
    log_returns = np.diff(np.log(np.clip(close, 1e-12, None)))
    period = min(period, len(log_returns))
    for i in range(period, n):
        vol[i] = np.std(log_returns[i - period:i])
    fill = vol[period] if period < n else 0.0
    vol[:period] = fill
    return vol


def triple_barrier_labels(
    close,
    k_profit=2.0,
    k_stop=2.0,
    max_holding_bars=24,
    vol_period=20,
    high=None,
    low=None,
):
    close = np.asarray(close, dtype=float)
    n = len(close)
    high = np.asarray(close if high is None else high, dtype=float)
    low = np.asarray(close if low is None else low, dtype=float)
    if len(high) != n:
        high = close
    if len(low) != n:
        low = close

    vol = compute_local_volatility(close, vol_period)
    labels = np.zeros(n, dtype=int)
    valid = np.zeros(n, dtype=bool)
    exit_prices = np.zeros(n)
    exit_indices = np.zeros(n, dtype=int)

    last_trainable = n - max_holding_bars
    for i in range(vol_period, last_trainable):
        entry_price = close[i]
        if entry_price <= 0 or vol[i] <= 0:
            continue
        upper_barrier = entry_price * (1 + k_profit * vol[i])
        lower_barrier = entry_price * (1 - k_stop * vol[i])
        end_idx = i + max_holding_bars
        wh = high[i + 1: end_idx + 1]
        wl = low[i + 1: end_idx + 1]
        wc = close[i + 1: end_idx + 1]
        if len(wh) < max_holding_bars:
            continue

        hit_upper = np.where(wh >= upper_barrier)[0]
        hit_lower = np.where(wl <= lower_barrier)[0]
        first_upper = int(hit_upper[0]) if len(hit_upper) else None
        first_lower = int(hit_lower[0]) if len(hit_lower) else None

        if first_upper is None and first_lower is None:
            labels[i] = 0
            exit_prices[i] = wc[-1]
            exit_indices[i] = i + len(wc)
        elif first_lower is not None and (first_upper is None or first_lower <= first_upper):
            labels[i] = -1
            exit_prices[i] = lower_barrier
            exit_indices[i] = i + 1 + first_lower
        else:
            labels[i] = 1
            exit_prices[i] = upper_barrier
            exit_indices[i] = i + 1 + first_upper
        valid[i] = True

    return labels, valid, vol, exit_prices, exit_indices


def apply_cost_filter(labels, close, exit_prices, valid, min_move_pct=0.0015):
    out = labels.copy()
    for i in range(len(close)):
        if not valid[i] or close[i] == 0:
            continue
        move = abs(exit_prices[i] - close[i]) / close[i]
        if move < min_move_pct:
            out[i] = 0
    return out
