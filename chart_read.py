"""
chart_read.py
BTC / multi-asset 1h chart snapshot for context and caution filters.
Computes multi-lookback range position, SMAs, RSI, ATR, volume ratio/trend,
trend bias, and symmetric chase-risk caution flags.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:]) or 1e-9
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < 2:
        return 0.0
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - prev), np.abs(lows - prev)))
    return float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr))


def _range_pos(price: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 50.0
    return float((price - lo) / (hi - lo) * 100.0)


def snapshot(candles: List[dict]) -> Optional[Dict[str, Any]]:
    """Build chart snapshot from 1h (or similar) candle list, oldest-first or newest-first.

    Expects list of dicts with 'close', 'high', 'low', 'volume' (and optionally 'open', 'time').
    """
    if not candles or len(candles) < 20:
        return None

    # Normalize order: oldest first
    try:
        t0 = float(candles[0].get("time") or candles[0].get("timestamp") or 0)
        t1 = float(candles[-1].get("time") or candles[-1].get("timestamp") or 0)
        if t0 > t1:
            candles = list(reversed(candles))
    except Exception:
        pass

    closes = np.array([float(c.get("close", 0) or 0) for c in candles], dtype=float)
    highs = np.array([float(c.get("high", c.get("close", 0)) or 0) for c in candles], dtype=float)
    lows = np.array([float(c.get("low", c.get("close", 0)) or 0) for c in candles], dtype=float)
    vols = np.array([float(c.get("volume", 0) or 0) for c in candles], dtype=float)

    if closes[-1] <= 0:
        return None

    px = float(closes[-1])
    n = len(closes)

    # Multi-lookback ranges (1h bars)
    def _rng(bars: int):
        b = min(bars, n)
        return float(lows[-b:].min()), float(highs[-b:].max())

    lo48, hi48 = _rng(48)
    lo24, hi24 = _rng(24)
    lo7d, hi7d = _rng(168)

    pos48 = _range_pos(px, lo48, hi48)
    pos24 = _range_pos(px, lo24, hi24)
    pos7d = _range_pos(px, lo7d, hi7d)

    sma20 = float(np.mean(closes[-20:])) if n >= 20 else px
    sma50 = float(np.mean(closes[-50:])) if n >= 50 else float(np.mean(closes))

    rsi14 = _rsi(closes)
    atr14 = _atr(highs, lows, closes)

    # Volume: median last 5 vs prior 15 (or available)
    recent_n = min(5, n)
    prior_start = max(0, n - 20)
    prior_end = max(0, n - 5)
    vol_recent = float(np.median(vols[-recent_n:])) if recent_n else 0.0
    vol_prior = float(np.median(vols[prior_start:prior_end])) if prior_end > prior_start else vol_recent
    vol_ratio = vol_recent / vol_prior if vol_prior > 0 else 1.0
    vol_trend = "falling" if vols[-1] < vol_prior else ("rising" if vols[-1] > vol_prior * 1.1 else "flat")

    if px > sma20 > sma50:
        trend = "bullish"
    elif px < sma20 < sma50:
        trend = "bearish"
    else:
        trend = "mixed"

    # Caution flags — upper/lower range + low volume chase risk
    long_caution = ""
    short_caution = ""
    if pos48 > 72 and vol_ratio < 0.55:
        long_caution = "upper-range low-vol (avoid chase)"
    elif pos48 > 78 and rsi14 > 65:
        long_caution = "high range_pos + elevated RSI"
    if pos48 < 28 and vol_ratio < 0.55:
        short_caution = "lower-range low-vol (avoid chase)"
    elif pos48 < 22 and rsi14 < 35:
        short_caution = "low range_pos + depressed RSI"

    vol_weak = vol_ratio < 0.4

    return {
        "price": round(px, 1),
        "range_48h": (round(lo48, 1), round(hi48, 1)),
        "range_pos_48h": round(pos48, 1),
        "range_pos_24h": round(pos24, 1),
        "range_pos_7d": round(pos7d, 1),
        "range_pos_pct": round(pos48, 1),  # alias used by model_engine
        "sma20": round(sma20, 1),
        "sma50": round(sma50, 1),
        "rsi14": round(rsi14, 1),
        "atr14": round(atr14, 1),
        "trend": trend,
        "vol_ratio": round(vol_ratio, 2),
        "vol_trend": vol_trend,
        "vol_weak": vol_weak,
        "long_caution": long_caution,
        "short_caution": short_caution,
        "caution": bool(long_caution or short_caution or vol_weak),
    }


def caption(snap: Dict[str, Any]) -> str:
    """Human-readable multi-line caption matching README style."""
    if not snap:
        return "No chart snapshot"
    lo, hi = snap.get("range_48h", (0, 0))
    lines = [
        f"Last ~${snap['price']:,.1f}",
        f"48h range: ${lo:,.1f} – ${hi:,.1f} (pos {snap['range_pos_48h']:.1f}% — "
        f"{'upper' if snap['range_pos_48h']>65 else 'lower' if snap['range_pos_48h']<35 else 'mid'} range)",
        f"24h pos ~{snap['range_pos_24h']:.1f}% / 7d pos ~{snap['range_pos_7d']:.1f}%",
        f"Trend: **{snap['trend']}** (px {'>' if snap['price']>snap['sma20'] else '<'} SMA20 {'>' if snap['sma20']>snap['sma50'] else '<'} SMA50)",
        f"RSI(14): **{snap['rsi14']:.1f}**",
        f"ATR(14): ~{snap['atr14']:.0f}",
        f"Vol ratio: **{snap['vol_ratio']:.2f}** ({snap['vol_trend']})"
        + (" → VOL WEAK" if snap.get("vol_weak") else ""),
    ]
    if snap.get("long_caution"):
        lines.append(f"LONG caution: {snap['long_caution']}")
    if snap.get("short_caution"):
        lines.append(f"SHORT caution: {snap['short_caution']}")
    return "\n".join(lines)
