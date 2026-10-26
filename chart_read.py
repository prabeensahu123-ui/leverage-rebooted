"""
chart_read.py
BTC / multi-asset 1h chart snapshot for context and caution filters.
Computes multi-lookback range position, SMAs/EMAs, RSI, ATR, volume ratio/trend,
trend bias, volume confirmation, ADX/regime context, and improved symmetric chase-risk caution flags.
Adds low-ATR compression awareness, range-bound detection, low-RSI / weak-vol bounce awareness,
near-support proximity, and breakout-watch for better filtering in quiet or post-dump markets.

Updates (Oct 2026):
- Dual volume measure (median + mean) for robustness
- Lightweight ADX fallback so regime is never blank when enough bars exist
- Bollinger position + short-term momentum added
- Refined caution / bias thresholds while keeping conservative philosophy
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


def _simple_adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Lightweight ADX fallback when regime import fails."""
    n = len(closes)
    if n < period + 2:
        return 0.0
    up = highs[1:] - highs[:-1]
    dn = lows[:-1] - lows[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - prev), np.abs(lows - prev)))[1:]
    def wilder(arr):
        s = np.zeros(len(arr))
        if len(arr) < period:
            return s
        s[period - 1] = np.sum(arr[:period])
        for i in range(period, len(arr)):
            s[i] = s[i - 1] - (s[i - 1] / period) + arr[i]
        return s
    atr_w = wilder(tr)
    plus_s = wilder(plus_dm)
    minus_s = wilder(minus_dm)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * plus_s / np.where(atr_w == 0, np.nan, atr_w)
        minus_di = 100.0 * minus_s / np.where(atr_w == 0, np.nan, atr_w)
        dx = 100.0 * np.abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, np.nan, (plus_di + minus_di))
    dx = np.nan_to_num(dx, nan=0.0)
    if len(dx) < period * 2:
        return float(np.mean(dx)) if len(dx) else 0.0
    adx_val = float(np.mean(dx[-period:]))
    return adx_val


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

    # Bollinger position (20, 2)
    bb_window = closes[-20:] if n >= 20 else closes
    bb_mid = float(np.mean(bb_window))
    bb_std = float(np.std(bb_window)) or 1e-9
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_pos = (px - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5

    # Short-term momentum (last 4 bars % change)
    mom4 = ((closes[-1] - closes[-5]) / closes[-5] * 100.0) if n >= 5 and closes[-5] > 0 else 0.0

    # Volume: dual measure for robustness (median preferred, mean fallback)
    recent_n = min(3, n)
    prior_start = max(0, n - 15)
    prior_end = max(0, n - 3)
    vol_recent_med = float(np.median(vols[-recent_n:])) if recent_n else 0.0
    vol_prior_med = float(np.median(vols[prior_start:prior_end])) if prior_end > prior_start else vol_recent_med
    vol_recent_mean = float(np.mean(vols[-recent_n:])) if recent_n else 0.0
    vol_prior_mean = float(np.mean(vols[prior_start:prior_end])) if prior_end > prior_start else vol_recent_mean
    vol_ratio = (vol_recent_med / vol_prior_med if vol_prior_med > 0 else
                 vol_recent_mean / vol_prior_mean if vol_prior_mean > 0 else 1.0)
    vol_trend = "falling" if vols[-1] < vol_prior_med else ("rising" if vols[-1] > vol_prior_med * 1.1 else "flat")
    vol_confirm = vols[-1] > max(vol_prior_med, vol_prior_mean) * 1.25
    vol_strength = "strong" if vol_ratio >= 1.15 else ("weak" if vol_ratio < 0.55 else "normal")

    if px > sma20 > sma50 and px > ema20 > ema50:
        trend = "bullish"
    elif px < sma20 < sma50 and px < ema20 < ema50:
        trend = "bearish"
    else:
        trend = "mixed"

    # Regime / ADX context
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
    if adx_val <= 0 and n >= 30:
        adx_val = _simple_adx(highs, lows, closes)
        if adx_val > 0 and regime_name == "UNKNOWN":
            if adx_val < 18:
                regime_name = "RANGE"
            elif adx_val >= 25:
                regime_name = "TREND"
            else:
                regime_name = "MIXED"
    weak_trend = adx_val < 20.0 if adx_val else True
    low_atr = atr_pct < 0.45

    # Range-bound detection
    range_width_pct = ((hi48 - lo48) / px * 100.0) if px > 0 else 0.0
    range_bound = range_width_pct <= 2.6 and (adx_val < 26.0 if adx_val else True)

    # Near support / resistance
    near_support = (px - lo48) / px * 100.0 < 0.6 if px > 0 else False
    near_resistance = (hi48 - px) / px * 100.0 < 0.6 if px > 0 else False

    # Caution flags
    long_caution = ""
    short_caution = ""
    near_24h_high = pos24 > 85
    near_24h_low = pos24 < 15

    upper_extreme = pos48 > 68 or near_24h_high or near_resistance
    lower_extreme = pos48 < 32 or near_24h_low or near_support

    if upper_extreme and (vol_ratio < 0.60 or weak_trend or low_atr or range_bound):
        long_caution = "upper/near-high range + low-vol/weak ADX/low-ATR or range-bound (avoid chase)"
    elif pos48 > 72 and rsi14 > 60 and not vol_confirm:
        long_caution = "elevated range_pos + RSI without volume confirm"

    if lower_extreme and (vol_ratio < 0.60 or weak_trend or low_atr or range_bound):
        short_caution = "lower/near-low range + low-vol/weak ADX/low-ATR or range-bound (avoid chase)"
    elif pos48 < 28 and rsi14 < 42 and not vol_confirm:
        short_caution = "depressed range_pos + RSI without volume confirm"

    if range_bound and 32 < pos48 < 68 and not vol_confirm:
        if not long_caution:
            long_caution = "tight range-bound mid-position — wait for break or volume expansion"
        if not short_caution:
            short_caution = "tight range-bound mid-position — wait for break or volume expansion"

    bounce_potential = (rsi14 < 44 and vol_ratio < 0.65 and (pos48 < 38 or near_support))
    if bounce_potential and not short_caution:
        short_caution = "weak-vol lower range / near support — bounce risk, avoid chase shorts"

    breakout_watch = False
    if (near_resistance or pos48 > 75) and (vol_ratio > 0.9 or (adx_val > 22 and not weak_trend)):
        breakout_watch = True
    if (near_support or pos48 < 25) and (vol_ratio > 0.9 or (adx_val > 22 and not weak_trend)):
        breakout_watch = True

    vol_weak = vol_ratio < 0.50
    compression_flag = regime_name in ("COMPRESSION", "RANGE") or low_atr or range_bound

    # Actionable bias
    if range_bound and not breakout_watch and not vol_confirm:
        bias = "WAIT — range-bound / compression, prefer break or volume confirm"
    elif long_caution and not short_caution:
        bias = "CAUTION LONGS — avoid chase"
    elif short_caution and not long_caution:
        bias = "CAUTION SHORTS — avoid chase"
    elif bounce_potential:
        bias = "BOUNCE WATCH — mean-reversion risk on shorts"
    elif abs(mom4) > 1.2 and vol_confirm:
        bias = "MOMENTUM BUILDING — monitor for follow-through"
    else:
        bias = "NEUTRAL — monitor for expansion"

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
        "bb_pos": round(bb_pos, 3),
        "mom4_pct": round(mom4, 2),
        "trend": trend,
        "vol_ratio": round(vol_ratio, 2),
        "vol_trend": vol_trend,
        "vol_confirm": bool(vol_confirm),
        "vol_weak": vol_weak,
        "vol_strength": vol_strength,
        "near_24h_high": near_24h_high,
        "near_24h_low": near_24h_low,
        "near_support": near_support,
        "near_resistance": near_resistance,
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
        "breakout_watch": breakout_watch,
        "bias": bias,
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
        + (" [RANGE-BOUND]" if snap.get("range_bound") else "")
        + (" [NEAR SUPPORT]" if snap.get("near_support") else "")
        + (" [NEAR RESIST]" if snap.get("near_resistance") else ""),
        f"24h pos ~{snap['range_pos_24h']:.1f}% / 7d pos ~{snap['range_pos_7d']:.1f}%",
        f"Trend: **{snap['trend']}** (SMA20={snap['sma20']:.0f} SMA50={snap['sma50']:.0f} | EMA20={snap.get('ema20',0):.0f} | dist SMA20 {snap.get('dist_sma20_pct',0):+.1f}%)",
        f"RSI(14): **{snap['rsi14']:.1f}**  ATR(14): ~{snap['atr14']:.0f} ({snap.get('atr_pct',0):.2f}%)"
        + (" [LOW ATR]" if snap.get("low_atr") else "")
        + (" [BOUNCE POTENTIAL]" if snap.get("bounce_potential") else ""),
        f"BB pos: {snap.get('bb_pos', 0.5):.2f}  Mom4: {snap.get('mom4_pct', 0):+.2f}%",
        f"Vol ratio: **{snap['vol_ratio']:.2f}** ({snap['vol_trend']}, {snap.get('vol_strength','')})"
        + (" -> VOL WEAK" if snap.get("vol_weak") else "")
        + (" + CONFIRM" if snap.get("vol_confirm") else ""),
    ]
    if snap.get("adx") or snap.get("regime"):
        lines.append(f"Regime: **{snap.get('regime','?')}**  ADX: {snap.get('adx',0):.1f}"
                     + (" [COMPRESSION/RANGE]" if snap.get("compression_flag") else ""))
    if snap.get("breakout_watch"):
        lines.append("BREAKOUT WATCH: near range edge + volume/ADX building")
    if snap.get("long_caution"):
        lines.append(f"LONG caution: {snap['long_caution']}")
    if snap.get("short_caution"):
        lines.append(f"SHORT caution: {snap['short_caution']}")
    if snap.get("near_24h_high"):
        lines.append("Near 24h high")
    if snap.get("near_24h_low"):
        lines.append("Near 24h low")
    if snap.get("near_support"):
        lines.append("Near 48h support / possible liq magnet")
    if snap.get("bias"):
        lines.append(f"Bias: {snap['bias']}")
    return "\n".join(lines)
