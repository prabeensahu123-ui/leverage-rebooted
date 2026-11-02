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
- Stricter breakout_watch: requires volume participation (ratio >=0.65 or confirm) even with ADX
- ATR-adaptive range-bound threshold (width relative to recent ATR) for tighter compression detection
- Stronger upper-range caution when RSI elevated + weak vol even if not extreme pos (crowded long risk)
- Oct 30: Strong volume (ratio>=1.15 or confirm) softens pure range-bound caution on extremes so high-participation moves aren't auto-vetoed solely for range-bound.

Nov 2026 R&D:
- Explicit DI bias (+DI/-DI) integrated into caution and caption.
- Symmetric rejection_potential for upper-range elevated RSI + weak volume.
- Long caution strengthened by bearish DI at extremes.
- Nov 02: Candle pattern detection + Supertrend (10x3) as directional filter.
- Nov 03: Full integration of patterns/ST into snapshot return + caution influence; relative volume expanded.
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

try:
    from candle_patterns import detect_candle_pattern
    HAS_PATTERNS = True
except Exception:
    HAS_PATTERNS = False
    detect_candle_pattern = None


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(np.mean(gains[-period:]))
    avg_loss = float(np.mean(losses[-period:]))
    if avg_loss <= 1e-12:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return float(np.mean(highs[-period:] - lows[-period:])) if len(highs) else 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return float(np.mean(trs[-period:])) if trs else 0.0


def _ema(prices: np.ndarray, period: int) -> float:
    if len(prices) == 0:
        return 0.0
    if len(prices) < period:
        return float(np.mean(prices))
    k = 2.0 / (period + 1)
    ema = float(np.mean(prices[:period]))
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema


def _range_pos(price: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return float(max(0.0, min(1.0, (price - lo) / (hi - lo))))


def _simple_adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    n = len(closes)
    if n < period + 2:
        return 0.0
    plus_dm = []
    minus_dm = []
    trs = []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))

    def wilder(arr):
        if len(arr) < period:
            return float(np.mean(arr)) if arr else 0.0
        s = float(sum(arr[:period]))
        for v in arr[period:]:
            s = s - s / period + v
        return s / period

    atr = wilder(trs)
    if atr <= 1e-12:
        return 0.0
    pdi = 100.0 * wilder(plus_dm) / atr
    mdi = 100.0 * wilder(minus_dm) / atr
    dx = abs(pdi - mdi) / max(pdi + mdi, 1e-12) * 100.0
    return float(dx)


def _supertrend(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 10, mult: float = 3.0):
    if len(closes) < period + 1:
        return "neutral", closes[-1]
    atr = _atr(highs, lows, closes, period)
    hl2 = (highs + lows) / 2.0
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    # Simple final value approx (full Supertrend would track previous)
    st_dir = "bullish" if closes[-1] > lower[-1] else "bearish"
    st_val = float(lower[-1] if st_dir == "bullish" else upper[-1])
    return st_dir, st_val


def snapshot(candles: List[dict]) -> Optional[Dict[str, Any]]:
    if not candles or len(candles) < 30:
        return None
    closes = np.array([float(c.get("close") or 0) for c in candles], dtype=float)
    highs = np.array([float(c.get("high") or 0) for c in candles], dtype=float)
    lows = np.array([float(c.get("low") or 0) for c in candles], dtype=float)
    vols = np.array([float(c.get("volume") or 0) for c in candles], dtype=float)
    opens = np.array([float(c.get("open") or c.get("close") or 0) for c in candles], dtype=float)
    price = float(closes[-1])
    if price <= 0:
        return None

    def _rng(bars: int):
        lo = float(np.min(lows[-bars:])) if len(lows) >= bars else float(np.min(lows))
        hi = float(np.max(highs[-bars:])) if len(highs) >= bars else float(np.max(highs))
        return lo, hi, _range_pos(price, lo, hi)

    lo48, hi48, pos48 = _rng(min(48, len(candles)))
    lo24, hi24, pos24 = _rng(min(24, len(candles)))
    lo7d, hi7d, pos7d = _rng(min(168, len(candles)))

    sma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else float(np.mean(closes))
    sma50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else sma20
    ema20 = _ema(closes, 20)
    rsi = _rsi(closes, 14)
    atr = _atr(highs, lows, closes, 14)
    atr_pct = atr / price * 100.0 if price else 0.0

    # volume (expanded relative)
    recent = vols[-15:] if len(vols) >= 15 else vols
    last3 = vols[-3:] if len(vols) >= 3 else vols
    prior = vols[-18:-3] if len(vols) >= 18 else vols[:-3] if len(vols) > 3 else vols
    med_recent = float(np.median(recent)) if len(recent) else 0.0
    med_prior = float(np.median(prior)) if len(prior) else med_recent
    vol_ratio = (med_recent / med_prior) if med_prior > 1e-12 else 1.0
    rel_vol = float(np.median(vols[-20:]) / np.median(vols[-40:-20])) if len(vols) >= 40 else vol_ratio
    vol_confirm = bool(len(vols) >= 2 and vols[-1] > vols[-2] * 1.1)
    vol_strength = "strong" if vol_ratio >= 1.15 or vol_confirm else ("weak" if vol_ratio < 0.45 or rel_vol < 0.6 else "normal")
    vol_trend = "rising" if vol_ratio >= 1.05 else ("falling" if vol_ratio < 0.9 else "flat")

    # BB pos + mom
    if len(closes) >= 20:
        mid = float(np.mean(closes[-20:]))
        std = float(np.std(closes[-20:]))
        bb_pos = (price - (mid - 2 * std)) / max(4 * std, 1e-12)
        bb_pos = float(max(0.0, min(1.0, bb_pos)))
    else:
        bb_pos = 0.5
    mom4 = float((closes[-1] - closes[-5]) / closes[-5] * 100.0) if len(closes) >= 5 and closes[-5] else 0.0

    dist_sma20 = (price - sma20) / sma20 * 100.0 if sma20 else 0.0
    range_width = (hi48 - lo48) / price * 100.0 if price else 0.0
    range_bound = range_width < max(1.5, 6.0 * atr_pct) and atr_pct < 0.5

    near_24h_high = pos24 >= 0.9
    near_24h_low = pos24 <= 0.1
    near_support = abs(price - lo48) / price * 100.0 < max(0.4, atr_pct)
    near_resistance = abs(hi48 - price) / price * 100.0 < max(0.4, atr_pct)

    adx = _simple_adx(highs, lows, closes, 14)
    # DI rough
    pdi = mdi = 20.0
    if len(closes) >= 16:
        up_moves = np.maximum(np.diff(highs[-15:]), 0)
        down_moves = np.maximum(-np.diff(lows[-15:]), 0)
        pdi = float(np.mean(up_moves))
        mdi = float(np.mean(down_moves))
    di_bias = "bullish" if pdi > mdi * 1.1 else ("bearish" if mdi > pdi * 1.1 else "neutral")

    st_dir, st_val = _supertrend(highs, lows, closes)

    pattern_name, pattern_bias = ("No clear pattern", "HOLD")
    if HAS_PATTERNS and detect_candle_pattern:
        try:
            pattern_name, pattern_bias = detect_candle_pattern(opens, highs, lows, closes)
        except Exception:
            pass

    regime = "UNKNOWN"
    if HAS_REGIME and classify_regime:
        try:
            r = classify_regime(candles)
            if isinstance(r, dict):
                regime = r.get("regime") or r.get("label") or regime
            elif isinstance(r, str):
                regime = r
        except Exception:
            pass
    if regime == "UNKNOWN":
        if atr_pct < 0.3 and adx < 18:
            regime = "COMPRESSION"
        elif adx >= 25:
            regime = "TREND"
        else:
            regime = "RANGE"

    upper_extreme = pos48 >= 0.85 or near_24h_high
    lower_extreme = pos48 <= 0.15 or near_24h_low
    weak_part = vol_ratio < 0.85 or vol_strength == "weak"
    strong_part = vol_ratio >= 1.15 or vol_confirm

    long_caution = False
    short_caution = False
    if upper_extreme and (weak_part or adx < 18 or (range_bound and not strong_part) or di_bias == "bearish" or st_dir == "bearish"):
        long_caution = True
    if upper_extreme and rsi >= 60 and weak_part:
        long_caution = True
    if lower_extreme and (weak_part or adx < 18 or (range_bound and not strong_part) or st_dir == "bullish"):
        short_caution = True

    bounce_potential = lower_extreme and rsi <= 40 and weak_part
    rejection_potential = upper_extreme and rsi >= 60 and weak_part

    breakout_watch = (upper_extreme or lower_extreme) and (vol_ratio >= 0.65 or vol_confirm) and adx >= 18

    if long_caution and not short_caution:
        bias = "CAUTION LONGS — avoid chase"
    elif short_caution and not long_caution:
        bias = "CAUTION SHORTS — avoid chase"
    elif rejection_potential:
        bias = "REJECTION WATCH"
    elif bounce_potential:
        bias = "BOUNCE WATCH"
    elif breakout_watch:
        bias = "BREAKOUT WATCH"
    elif pattern_bias != "HOLD" and (strong_part or st_dir != "neutral"):
        bias = f"PATTERN {pattern_bias}"
    else:
        bias = "NEUTRAL"

    trend = "bullish" if sma20 > sma50 and price > sma20 else ("bearish" if sma20 < sma50 and price < sma20 else "mixed")

    return {
        "price": price,
        "pos_48h": pos48,
        "pos_24h": pos24,
        "pos_7d": pos7d,
        "lo_48h": lo48,
        "hi_48h": hi48,
        "sma20": sma20,
        "sma50": sma50,
        "ema20": ema20,
        "dist_sma20_pct": dist_sma20,
        "rsi": rsi,
        "atr": atr,
        "atr_pct": atr_pct,
        "vol_ratio": vol_ratio,
        "rel_vol": rel_vol,
        "vol_trend": vol_trend,
        "vol_confirm": vol_confirm,
        "vol_strength": vol_strength,
        "bb_pos": bb_pos,
        "mom4": mom4,
        "adx": adx,
        "di_bias": di_bias,
        "regime": regime,
        "range_width_pct": range_width,
        "range_bound": range_bound,
        "near_24h_high": near_24h_high,
        "near_24h_low": near_24h_low,
        "near_support": near_support,
        "near_resistance": near_resistance,
        "long_caution": long_caution,
        "short_caution": short_caution,
        "bounce_potential": bounce_potential,
        "rejection_potential": rejection_potential,
        "breakout_watch": breakout_watch,
        "bias": bias,
        "trend": trend,
        "supertrend": st_dir,
        "supertrend_val": st_val,
        "pattern": pattern_name,
        "pattern_bias": pattern_bias,
    }


def caption(snap: Dict[str, Any]) -> str:
    if not snap:
        return "No chart snapshot"
    parts = [
        f"Last ~${snap['price']:,.1f}",
        f"48h pos {snap['pos_48h']*100:.1f}%",
        f"RSI {snap['rsi']:.1f}",
        f"ATR% {snap['atr_pct']:.2f}",
        f"vol {snap['vol_ratio']:.2f} ({snap['vol_trend']})",
        f"ADX {snap['adx']:.1f} DI {snap.get('di_bias','?')}",
        f"ST {snap.get('supertrend','?')}",
        f"pattern {snap.get('pattern','?')}",
        f"regime {snap.get('regime')}",
        f"bias {snap.get('bias')}",
    ]
    if snap.get("long_caution"):
        parts.append("LONG caution")
    if snap.get("short_caution"):
        parts.append("SHORT caution")
    if snap.get("rejection_potential"):
        parts.append("rejection risk")
    if snap.get("bounce_potential"):
        parts.append("bounce risk")
    return " · ".join(parts)
