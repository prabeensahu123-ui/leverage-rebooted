"""
chart_read.py
BTC / multi-asset 1h chart snapshot for context and caution filters.
Computes multi-lookback range position, SMAs/EMAs, RSI, ATR, volume ratio/trend,
trend bias, volume confirmation, ADX/regime context, and improved symmetric chase-risk caution flags.
Adds low-ATR compression awareness, range-bound detection, and low-RSI bounce awareness for better filtering in quiet/consolidating markets.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional

try:
    from regime import classify_regime
    HAS_REGIME = True
except Exception:
    HAS_REGIME = False
    classify_regime = None


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


def _ema(prices: np.ndarray, period: int) -> float:
    if len(prices) == 0:
        return 0.0
    if len(prices) < period:
        return float(np.mean(prices))
    k = 2.0 / (period + 1.0)
    ema = float(np.mean(prices[:period]))
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return float(ema)


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
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50) if n >= 50 else sma50
    dist_sma20_pct = ((px - sma20) / sma20 * 100.0) if sma20 > 0 else 0.0

    rsi14 = _rsi(closes)
    atr14 = _atr(highs, lows, closes)
    atr_pct = (atr14 / px * 100.0) if px > 0 else 0.0

    # Volume: median last 5 vs prior 15 (or available) + relative strength
    recent_n = min(5, n)
    prior_start = max(0, n - 20)
    prior_end = max(0, n - 5)
    vol_recent = float(np.median(vols[-recent_n:])) if recent_n else 0.0
    vol_prior = float(np.median(vols[prior_start:prior_end])) if prior_end > prior_start else vol_recent
    vol_ratio = vol_recent / vol_prior if vol_prior > 0 else 1.0
    vol_trend = "falling" if vols[-1] < vol_prior else ("rising" if vols[-1] > vol_prior * 1.1 else "flat")
    vol_confirm = vols[-1] > vol_prior * 1.25  # last bar volume expansion
    vol_strength = "strong" if vol_ratio >= 1.2 else ("weak" if vol_ratio < 0.5 else "normal")

    if px > sma20 > sma50 and px > ema20 > ema50:
        trend = "bullish"
    elif px < sma20 < sma50 and px < ema20 < ema50:
        trend = "bearish"
    else:
        trend = "mixed"

    # Regime / ADX context (optional)
    regime_info = {}
    adx_val = 0.0
    regime_name = "UNKNOWN"
    if HAS_REGIME and n >= 30:
        try:
            regime_info = classify_regime(highs, lows, closes) or {}
            adx_val = float(regime_info.get("adx") or 0.0)
            regime_name = str(regime_info.get("vol_state") or "UNKNOWN")
        except Exception:
            pass
    weak_trend = adx_val < 20.0 if adx_val else False
    low_atr = atr_pct < 0.40  # quiet market threshold

    # Range-bound detection for tight consolidations (common in current BTC environment)
    range_width_pct = ((hi48 - lo48) / px * 100.0) if px > 0 else 0.0
    range_bound = range_width_pct < 2.5 and (adx_val < 25.0 if adx_val else True)

    # Improved caution flags - location + weak participation or weak trend; stronger in compression / range-bound
    long_caution = ""
    short_caution = ""
    near_24h_high = pos24 > 85
    near_24h_low = pos24 < 15

    upper_extreme = pos48 > 70 or near_24h_high
    lower_extreme = pos48 < 30 or near_24h_low

    if upper_extreme and (vol_ratio < 0.55 or weak_trend or low_atr or range_bound):
        long_caution = "upper/near-high range + low-vol/weak ADX/low-ATR or range-bound (avoid chase)"
    elif pos48 > 75 and rsi14 > 62 and not vol_confirm:
        long_caution = "elevated range_pos + RSI without volume confirm"
    if lower_extreme and (vol_ratio < 0.55 or weak_trend or low_atr or range_bound):
        short_caution = "lower/near-low range + low-vol/weak ADX/low-ATR or range-bound (avoid chase)"
    elif pos48 < 25 and rsi14 < 38 and not vol_confirm:
        short_caution = "depressed range_pos + RSI without volume confirm"

    # Extra mid-range caution in tight consolidations: prefer waiting for break or extreme + volume
    if range_bound and 35 < pos48 < 65 and not vol_confirm:
        if not long_caution:
            long_caution = "tight range-bound mid-position — wait for break or volume expansion"
        if not short_caution:
            short_caution = "tight range-bound mid-position — wait for break or volume expansion"

    # Low RSI + weak vol bounce awareness (avoid aggressive shorts in oversold quiet conditions)
    bounce_potential = rsi14 < 35 and vol_ratio < 0.6 and pos48 < 60
    if bounce_potential and not short_caution:
        short_caution = "low RSI + weak vol near lower-mid range — bounce risk, avoid chase shorts"

    vol_weak = vol_ratio < 0.45
    compression_flag = regime_name == "COMPRESSION" or low_atr or range_bound

    return {
        "price": round(px, 1),
        "range_48h": (round(lo48, 1), round(hi48, 1)),
        "range_pos_48h": round(pos48, 1),
        "range_pos_24h": round(pos24, 1),
        "range_pos_7d": round(pos7d, 1),
        "range_pos_pct": round(pos48, 1),
        "range_width_pct": round(range_width_pct, 2),
        "sma20": round(sma20, 1),
        "sma50": round(sma50, 1),
        "ema20": round(ema20, 1),
        "ema50": round(ema50, 1),
        "dist_sma20_pct": round(dist_sma20_pct, 2),
        "rsi14": round(rsi14, 1),
        "atr14": round(atr14, 1),
        "atr_pct": round(atr_pct, 2),
        "trend": trend,
        "vol_ratio": round(vol_ratio, 2),
        "vol_trend": vol_trend,
        "vol_confirm": vol_confirm,
        "vol_weak": vol_weak,
        "vol_strength": vol_strength,
        "near_24h_high": near_24h_high,
        "near_24h_low": near_24h_low,
        "long_caution": long_caution,
        "short_caution": short_caution,
        "caution": bool(long_caution or short_caution or vol_weak or compression_flag),
        "adx": round(adx_val, 1),
        "regime": regime_name,
        "regime_info": regime_info,
        "low_atr": low_atr,
        "compression_flag": compression_flag,
        "range_bound": range_bound,
        "bounce_potential": bounce_potential,
    }


def caption(snap: Dict[str, Any]) -> str:
    """Human-readable multi-line caption matching README style."""
    if not snap:
        return "No chart snapshot"
    lo, hi = snap.get("range_48h", (0, 0))
    lines = [
        f"Last ~${snap['price']:,.1f}",
        f"48h range: ${lo:,.1f} - ${hi:,.1f} (pos {snap['range_pos_48h']:.1f}% - "
        f"{'upper' if snap['range_pos_48h']>65 else 'lower' if snap['range_pos_48h']<35 else 'mid'} range, width {snap.get('range_width_pct',0):.1f}%)"
        + (" [RANGE-BOUND]" if snap.get("range_bound") else ""),
        f"24h pos ~{snap['range_pos_24h']:.1f}% / 7d pos ~{snap['range_pos_7d']:.1f}%",
        f"Trend: **{snap['trend']}** (SMA20={snap['sma20']:.0f} SMA50={snap['sma50']:.0f} | EMA20={snap.get('ema20',0):.0f} | dist SMA20 {snap.get('dist_sma20_pct',0):+.1f}%)",
        f"RSI(14): **{snap['rsi14']:.1f}**  ATR(14): ~{snap['atr14']:.0f} ({snap.get('atr_pct',0):.2f}%)"
        + (" [LOW ATR]" if snap.get("low_atr") else "")
        + (" [BOUNCE POTENTIAL]" if snap.get("bounce_potential") else ""),
        f"Vol ratio: **{snap['vol_ratio']:.2f}** ({snap['vol_trend']}, {snap.get('vol_strength','')})"
        + (" -> VOL WEAK" if snap.get("vol_weak") else "")
        + (" + CONFIRM" if snap.get("vol_confirm") else ""),
    ]
    if snap.get("adx") or snap.get("regime"):
        lines.append(f"Regime: **{snap.get('regime','?')}**  ADX: {snap.get('adx',0):.1f}"
                     + (" [COMPRESSION/RANGE]" if snap.get("compression_flag") else ""))
    if snap.get("long_caution"):
        lines.append(f"LONG caution: {snap['long_caution']}")
    if snap.get("short_caution"):
        lines.append(f"SHORT caution: {snap['short_caution']}")
    if snap.get("near_24h_high"):
        lines.append("Near 24h high")
    if snap.get("near_24h_low"):
        lines.append("Near 24h low")
    return "\n".join(lines)
