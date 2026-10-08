"""
regime.py
Range vs trend vs expansion from ADX + ATR.
"""

import numpy as np

ADX_RANGE = 18.0
ADX_TREND = 25.0
ATR_EXPAND = 1.35
ATR_COMPRESS = 0.75


def _true_range(high, low, close):
    prev = np.roll(close, 1)
    prev[0] = close[0]
    return np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))


def atr(high, low, close, period=14):
    tr = _true_range(high, low, close)
    out = np.zeros(len(tr))
    if len(tr) < period:
        out[:] = np.mean(tr) if len(tr) else 0.0
        return out
    out[:period] = np.mean(tr[:period])
    k = 1.0 / period
    for i in range(period, len(tr)):
        out[i] = out[i - 1] * (1 - k) + tr[i] * k
    return out


def adx(high, low, close, period=14):
    n = len(close)
    if n < period + 2:
        return 0.0, 0.0, 0.0

    up = high[1:] - high[:-1]
    dn = low[:-1] - low[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = _true_range(high, low, close)[1:]

    def _wilder(arr):
        s = np.zeros(len(arr))
        s[period - 1] = np.sum(arr[:period])
        for i in range(period, len(arr)):
            s[i] = s[i - 1] - (s[i - 1] / period) + arr[i]
        return s

    atr_w = _wilder(tr)
    plus_s = _wilder(plus_dm)
    minus_s = _wilder(minus_dm)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * plus_s / np.where(atr_w == 0, np.nan, atr_w)
        minus_di = 100.0 * minus_s / np.where(atr_w == 0, np.nan, atr_w)
        dx = 100.0 * np.abs(plus_di - minus_di) / np.where(
            (plus_di + minus_di) == 0, np.nan, (plus_di + minus_di)
        )
    dx = np.nan_to_num(dx, nan=0.0)
    adx_s = np.zeros(len(dx))
    start = 2 * period - 1
    if start < len(dx):
        adx_s[start] = np.mean(dx[period - 1:start + 1])
        for i in range(start + 1, len(dx)):
            adx_s[i] = (adx_s[i - 1] * (period - 1) + dx[i]) / period
    return float(adx_s[-1]), float(np.nan_to_num(plus_di[-1])), float(np.nan_to_num(minus_di[-1]))


def classify_regime(high, low, close, period=14):
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    a, pdi, mdi = adx(high, low, close, period)
    atr_s = atr(high, low, close, period)
    last_atr = float(atr_s[-1]) if len(atr_s) else 0.0
    base = float(np.mean(atr_s[-max(period * 3, 20):])) if len(atr_s) else last_atr
    atr_ratio = (last_atr / base) if base > 0 else 1.0
    px = float(close[-1]) if len(close) else 0.0
    atr_pct = (last_atr / px) if px else 0.0

    if atr_ratio >= ATR_EXPAND and a >= ADX_TREND:
        name = "EXPANSION"
    elif atr_ratio <= ATR_COMPRESS:
        name = "COMPRESSION"
    elif a < ADX_RANGE:
        name = "RANGE"
    else:
        name = "TREND"

    return {
        "vol_state": name,
        "adx": round(a, 2),
        "plus_di": round(pdi, 2),
        "minus_di": round(mdi, 2),
        "atr": round(last_atr, 4),
        "atr_pct": round(atr_pct, 5),
        "atr_ratio": round(atr_ratio, 3),
    }


def apply_regime_filter(side, vol_state, entry_style=None):
    if side is None:
        return None, ""
    if vol_state == "RANGE":
        return None, "ADX range — skip trend-follow"
    if vol_state == "COMPRESSION":
        return None, "ATR compressed — squeeze risk"
    if vol_state == "EXPANSION":
        style = (entry_style or "").lower()
        if "break" not in style:
            return None, "expansion — wait for break, not fade"
    return side, ""
