"""
chart_read.py
Technical snapshot of recent candles for caution flags and structure notes.
Used by Streamlit chart section and model signal filters.
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Any, List


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(high, low, close, period: int = 14) -> float:
    if len(close) < 2:
        return 0.0
    prev = np.roll(close, 1)
    prev[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    return float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr))


def snapshot(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return structure / caution snapshot from OHLCV list (dicts with open/high/low/close/volume)."""
    if not candles or len(candles) < 20:
        return {"ok": False, "reason": "insufficient candles"}

    o = np.array([float(c.get("open", c["close"])) for c in candles])
    h = np.array([float(c["high"]) for c in candles])
    l = np.array([float(c["low"]) for c in candles])
    c = np.array([float(c["close"]) for c in candles])
    v = np.array([float(c.get("volume", 0)) for c in candles])

    price = float(c[-1])
    rsi = _rsi(c)
    atr_val = _atr(h, l, c)
    sma20 = float(np.mean(c[-20:]))
    sma50 = float(np.mean(c[-50:])) if len(c) >= 50 else sma20

    # Recent range / volatility
    recent_range = float(np.max(h[-10:]) - np.min(l[-10:]))
    vol_z = 0.0
    if len(v) >= 20 and np.std(v[-20:]) > 0:
        vol_z = float((v[-1] - np.mean(v[-20:])) / np.std(v[-20:]))

    # Caution flags
    long_caution = False
    short_caution = False
    bounce_potential = False
    notes = []

    # Overextended
    if price > sma20 * 1.03 and rsi > 70:
        long_caution = True
        notes.append("Overextended above SMA20 + high RSI → long caution")
    if price < sma20 * 0.97 and rsi < 30:
        short_caution = True
        notes.append("Oversold below SMA20 + low RSI → short caution")

    # Trend vs price
    if price > sma20 > sma50 and rsi > 65:
        notes.append("Strong uptrend but extended")
        long_caution = True
    if price < sma20 < sma50 and rsi < 35:
        notes.append("Strong downtrend but stretched")
        short_caution = True

    # Low RSI bounce
    if rsi < 32 and vol_z < 0.5:
        bounce_potential = True
        notes.append("Low RSI + weak volume → bounce potential")

    # Volume climax
    if vol_z > 2.5:
        notes.append("Volume climax — possible exhaustion")
        if price > sma20:
            long_caution = True
        else:
            short_caution = True

    # Tight range / low ATR relative
    avg_atr_ratio = atr_val / price if price else 0
    if avg_atr_ratio < 0.005 and recent_range / price < 0.015:
        notes.append("Low volatility range — breakout pending")

    caution = long_caution or short_caution

    return {
        "ok": True,
        "price": round(price, 2),
        "rsi": round(rsi, 1),
        "atr": round(atr_val, 2),
        "sma20": round(sma20, 2),
        "sma50": round(sma50, 2),
        "vol_zscore": round(vol_z, 2),
        "long_caution": long_caution,
        "short_caution": short_caution,
        "caution": caution,
        "bounce_potential": bounce_potential,
        "notes": notes,
        "structure": "above_sma20" if price > sma20 else "below_sma20",
    }


def caption(snap: Dict[str, Any]) -> str:
    if not snap or not snap.get("ok"):
        return "Chart snapshot unavailable"
    lines = [
        f"Price ${snap['price']:,.2f} | RSI {snap['rsi']} | ATR {snap['atr']}",
        f"SMA20 ${snap['sma20']:,.2f} | SMA50 ${snap['sma50']:,.2f} | {snap['structure']}",
        f"Vol z {snap['vol_zscore']} | Long caution: {snap['long_caution']} | Short caution: {snap['short_caution']}",
    ]
    if snap.get("bounce_potential"):
        lines.append("Bounce potential flagged")
    if snap.get("notes"):
        lines.append("Notes: " + " | ".join(snap["notes"]))
    return "\n".join(lines)
