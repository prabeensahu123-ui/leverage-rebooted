"""
chart_read.py
Technical snapshot of recent candles for caution flags and structure notes.
Used by Streamlit chart section and model signal filters.
Enhanced with extreme RSI bounce detection, bounce_score, and structure details.
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


def _bounce_score(rsi: float, dist_sma20_pct: float, vol_z: float, atr_ratio: float) -> int:
    """0-100 score for mean-reversion bounce likelihood. Higher = stronger bounce setup."""
    score = 0
    # RSI extremity (primary)
    if rsi < 15:
        score += 45
    elif rsi < 20:
        score += 40
    elif rsi < 25:
        score += 35
    elif rsi < 30:
        score += 25
    elif rsi < 35:
        score += 15
    # Distance below SMA20
    if dist_sma20_pct < -3.0:
        score += 25
    elif dist_sma20_pct < -1.5:
        score += 18
    elif dist_sma20_pct < -0.5:
        score += 10
    # Low volume supports exhaustion
    if vol_z < -0.5:
        score += 15
    elif vol_z < 0.5:
        score += 8
    # Not too compressed (some volatility for move)
    if atr_ratio > 0.004:
        score += 10
    return min(100, score)


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

    recent_range = float(np.max(h[-10:]) - np.min(l[-10:]))
    vol_z = 0.0
    if len(v) >= 20 and np.std(v[-20:]) > 0:
        vol_z = float((v[-1] - np.mean(v[-20:])) / np.std(v[-20:]))

    long_caution = False
    short_caution = False
    bounce_potential = False
    extreme_oversold = False
    notes = []

    if price > sma20 * 1.03 and rsi > 70:
        long_caution = True
        notes.append("Overextended above SMA20 + high RSI → long caution")
    if price < sma20 * 0.97 and rsi < 30:
        short_caution = True
        notes.append("Oversold below SMA20 + low RSI → short caution")

    if price > sma20 > sma50 and rsi > 65:
        notes.append("Strong uptrend but extended")
        long_caution = True
    if price < sma20 < sma50 and rsi < 35:
        notes.append("Strong downtrend but stretched")
        short_caution = True

    if rsi < 25:
        extreme_oversold = True
        bounce_potential = True
        notes.append("EXTREME oversold RSI <25 → high bounce potential (mean reversion)")
    elif rsi < 32 and vol_z < 0.5:
        bounce_potential = True
        notes.append("Low RSI + weak volume → bounce potential")

    if vol_z > 2.5:
        notes.append("Volume climax — possible exhaustion")
        if price > sma20:
            long_caution = True
        else:
            short_caution = True

    avg_atr_ratio = atr_val / price if price else 0
    if avg_atr_ratio < 0.005 and recent_range / price < 0.015:
        notes.append("Low volatility range — breakout pending")

    dist_sma20_pct = (price - sma20) / sma20 * 100 if sma20 else 0
    dist_sma50_pct = (price - sma50) / sma50 * 100 if sma50 else 0

    bounce_score = _bounce_score(rsi, dist_sma20_pct, vol_z, avg_atr_ratio)
    if bounce_score >= 70:
        notes.append(f"High bounce_score {bounce_score}/100 — consider mean-reversion bias")
    elif bounce_score >= 50:
        notes.append(f"Moderate bounce_score {bounce_score}/100")

    caution = long_caution or short_caution

    return {
        "ok": True,
        "price": round(price, 2),
        "rsi": round(rsi, 1),
        "atr": round(atr_val, 2),
        "sma20": round(sma20, 2),
        "sma50": round(sma50, 2),
        "dist_sma20_pct": round(dist_sma20_pct, 2),
        "dist_sma50_pct": round(dist_sma50_pct, 2),
        "vol_zscore": round(vol_z, 2),
        "long_caution": long_caution,
        "short_caution": short_caution,
        "caution": caution,
        "bounce_potential": bounce_potential,
        "extreme_oversold": extreme_oversold,
        "bounce_score": bounce_score,
        "notes": notes,
        "structure": "above_sma20" if price > sma20 else "below_sma20",
    }


def caption(snap: Dict[str, Any]) -> str:
    if not snap or not snap.get("ok"):
        return "Chart snapshot unavailable"
    lines = [
        f"Price ${snap['price']:,.2f} | RSI {snap['rsi']} | ATR {snap['atr']}",
        f"SMA20 ${snap['sma20']:,.2f} ({snap.get('dist_sma20_pct', 0):+.1f}%) | SMA50 ${snap['sma50']:,.2f} ({snap.get('dist_sma50_pct', 0):+.1f}%) | {snap['structure']}",
        f"Vol z {snap['vol_zscore']} | Long caution: {snap['long_caution']} | Short caution: {snap['short_caution']}",
        f"Bounce score: {snap.get('bounce_score', 0)}/100",
    ]
    if snap.get("extreme_oversold"):
        lines.append("⚠️ EXTREME OVERSOLD — bounce potential high")
    elif snap.get("bounce_potential"):
        lines.append("Bounce potential flagged")
    if snap.get("notes"):
        lines.append("Notes: " + " | ".join(snap["notes"]))
    return "\n".join(lines)
