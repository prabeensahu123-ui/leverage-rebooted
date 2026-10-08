"""
squeeze_scanner.py
Phase 3: COMPRESSION -> EXPANSION handoff.
"""

import numpy as np

from regime import atr, adx, ATR_COMPRESS, ATR_EXPAND, ADX_TREND


def squeeze_handoff(high, low, close, lookback=24):
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    n = len(close)
    if n < lookback + 5:
        return {
            "squeeze": False,
            "handoff": False,
            "direction": None,
            "atr_ratio": None,
            "reason": "not enough bars",
        }

    atr_s = atr(high, low, close, 14)
    last_atr = float(atr_s[-1])
    base = float(np.mean(atr_s[-max(42, lookback):]))
    atr_ratio = last_atr / base if base > 0 else 1.0
    prior_ratio = float(atr_s[-3]) / base if base > 0 else 1.0

    squeeze_window = atr_s[-(lookback + 1):-1]
    compressed = float(np.median(squeeze_window) / base) <= ATR_COMPRESS if base else False

    prior_hi = float(np.max(high[-(lookback + 1):-1]))
    prior_lo = float(np.min(low[-(lookback + 1):-1]))
    px = float(close[-1])
    broke_up = px > prior_hi
    broke_dn = px < prior_lo
    expanding = atr_ratio >= min(ATR_EXPAND, 1.20) and atr_ratio > prior_ratio
    a, pdi, mdi = adx(high, low, close, 14)
    adx_ok = a >= (ADX_TREND - 4)

    direction = None
    if broke_up and (pdi >= mdi):
        direction = "LONG"
    elif broke_dn and (mdi >= pdi):
        direction = "SHORT"

    handoff = bool(compressed and expanding and direction and adx_ok)
    if not compressed:
        reason = "no prior squeeze"
    elif not expanding:
        reason = "ATR not expanding yet"
    elif direction is None:
        reason = "no range break"
    elif not adx_ok:
        reason = "ADX still asleep"
    else:
        reason = f"squeeze->{direction.lower()} break"

    return {
        "squeeze": bool(compressed),
        "handoff": handoff,
        "direction": direction if handoff else None,
        "atr_ratio": round(atr_ratio, 3),
        "adx": round(a, 2),
        "prior_high": round(prior_hi, 2),
        "prior_low": round(prior_lo, 2),
        "reason": reason,
    }
