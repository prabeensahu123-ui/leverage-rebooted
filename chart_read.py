"""
chart_read.py — richer chart snapshot helpers for the paper bot.
Provides last price, prior range, position, simple trend, momentum, ATR and volume context.
Enhanced with symmetric caution flags for high/low range position + low volume (chasing risk on both sides).
"""

import numpy as np


def _sma(arr, n):
    if len(arr) < n:
        return float(arr[-1]) if arr else 0.0
    return float(np.mean(arr[-n:]))


def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.clip(deltas, 0, None)
    losses = np.clip(-deltas, 0, None)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr(highs, lows, closes, period=14):
    if len(closes) < 2:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        trs.append(tr)
    if not trs:
        return 0.0
    return float(np.mean(trs[-period:])) if len(trs) >= period else float(np.mean(trs))


def snapshot(candles):
    if not candles:
        return {}
    closes = np.array([float(c.get("close", 0) or 0) for c in candles], dtype=float)
    highs = np.array([float(c.get("high", c.get("close", 0)) or 0) for c in candles], dtype=float)
    lows = np.array([float(c.get("low", c.get("close", 0)) or 0) for c in candles], dtype=float)
    vols = np.array([float(c.get("volume", 0) or 0) for c in candles], dtype=float)

    px = float(closes[-1]) if len(closes) else 0.0
    look = min(48, len(highs))
    prior_range_high = float(np.max(highs[-look:])) if look else px
    prior_range_low = float(np.min(lows[-look:])) if look else px
    range_width = prior_range_high - prior_range_low
    range_pos = (px - prior_range_low) / range_width if range_width > 0 else 0.5

    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50) if len(closes) >= 50 else sma20
    rsi14 = _rsi(closes, 14)
    atr14 = _atr(highs, lows, closes, 14)

    # simple trend bias
    trend = "neutral"
    if px > sma20 and sma20 > sma50:
        trend = "bullish"
    elif px < sma20 and sma20 < sma50:
        trend = "bearish"

    vol_avg = float(np.mean(vols[-20:])) if len(vols) >= 20 else float(np.mean(vols)) if len(vols) else 0.0
    vol_last = float(vols[-1]) if len(vols) else 0.0
    vol_ratio = vol_last / vol_avg if vol_avg > 0 else 1.0

    # Caution flags — avoid chasing extremes on low volume
    caution = ""
    long_caution = ""
    short_caution = ""
    if range_pos > 0.70 and vol_ratio < 0.5:
        caution = "upper-range low-vol (avoid chase)"
        long_caution = caution
    elif range_pos < 0.30 and vol_ratio < 0.5:
        caution = "lower-range low-vol (wait for volume)"
        short_caution = caution
    elif vol_ratio < 0.3:
        caution = "very low volume"

    # Extra RSI extremes
    if range_pos > 0.72 and rsi14 > 68:
        long_caution = long_caution or "high range + elevated RSI (chase risk)"
    if range_pos < 0.28 and rsi14 < 32:
        short_caution = short_caution or "low range + depressed RSI (chase risk)"

    return {
        "last": round(px, 2),
        "prior_range_high": round(prior_range_high, 2),
        "prior_range_low": round(prior_range_low, 2),
        "range_width": round(range_width, 2),
        "range_pos_pct": round(range_pos * 100, 1),
        "sma20": round(sma20, 2),
        "sma50": round(sma50, 2),
        "rsi14": round(rsi14, 1),
        "atr14": round(atr14, 2),
        "trend": trend,
        "vol_ratio": round(vol_ratio, 2),
        "caution": caution,
        "long_caution": long_caution,
        "short_caution": short_caution,
        "n": len(candles),
    }


def caption(snap):
    if not snap:
        return "no chart"
    base = (
        f"last={snap.get('last')} "
        f"range={snap.get('prior_range_low')}-{snap.get('prior_range_high')} "
        f"pos={snap.get('range_pos_pct')}% "
        f"trend={snap.get('trend')} "
        f"rsi={snap.get('rsi14')} "
        f"atr={snap.get('atr14')} "
        f"sma20={snap.get('sma20')} "
        f"volx={snap.get('vol_ratio')} "
        f"n={snap.get('n')}"
    )
    if snap.get("caution"):
        base += f" | CAUTION: {snap['caution']}"
    if snap.get("long_caution"):
        base += f" | LONG: {snap['long_caution']}"
    if snap.get("short_caution"):
        base += f" | SHORT: {snap['short_caution']}"
    return base
