"""
funding_confluence.py
BTC Funding Rate & Trade Confirmation Matrix (v2) — confluence scorer.

Educational framework for BTCUSDT perps. Not financial advice.
Source: BTC Funding Confluence Matrix (6-point score).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# --- Funding regime bands (Binance BTCUSDT 8h, rules of thumb) ---
def funding_regime(funding_pct: float) -> str:
    """Classify 8h funding print into a regime label."""
    if funding_pct is None:
        return "UNKNOWN"
    f = float(funding_pct)
    if f > 0.05:
        return "EXTREME_POSITIVE"
    if f >= 0.01:
        return "MILD_POSITIVE"
    if f > -0.01:
        return "NEUTRAL"
    if f >= -0.04:
        return "MILD_NEGATIVE"
    return "EXTREME_NEGATIVE"


REGIME_BIAS = {
    "EXTREME_POSITIVE": "Crowded longs — elevated long-squeeze / pullback risk",
    "MILD_POSITIVE": "Healthy bullish continuation (normal bull baseline)",
    "NEUTRAL": "Range / chop — no positioning edge",
    "MILD_NEGATIVE": "Bearish pressure or choppy decline",
    "EXTREME_NEGATIVE": "Crowded shorts — elevated short-squeeze / bounce risk",
    "UNKNOWN": "Funding unknown",
}


def score_long(
    funding_pct: Optional[float],
    rsi: Optional[float],
    long_share_pct: Optional[float],
    oi_chg_pct: Optional[float],
    price_chg_pct: Optional[float],
    cluster_above: Optional[float],
    cluster_below: Optional[float],
    pa_confirm: bool,
) -> Tuple[int, List[str]]:
    """
    Long setup criteria (6 points):
    1. Funding <= +0.03% (longs not crowded)
    2. RSI <= 65 (not overbought)
    3. Long share <= 55%
    4. OI up AND price up
    5. Cluster above price > cluster below
    6. Support held / reclaim candle (user Yes)
    """
    hits: List[str] = []
    n = 0

    if funding_pct is not None and funding_pct <= 0.03:
        n += 1
        hits.append("Funding <= +0.03% (not crowded long)")
    elif funding_pct is not None:
        hits.append("FAIL funding: %.4f%% > +0.03%%" % funding_pct)

    if rsi is not None and rsi <= 65:
        n += 1
        hits.append("RSI <= 65 (not overbought)")
    elif rsi is not None:
        hits.append("FAIL RSI: %.1f > 65" % rsi)

    if long_share_pct is not None and long_share_pct <= 55:
        n += 1
        hits.append("Long share <= 55%%")
    elif long_share_pct is not None:
        hits.append("FAIL long share: %.1f%% > 55%%" % long_share_pct)

    if oi_chg_pct is not None and price_chg_pct is not None:
        if oi_chg_pct > 0 and price_chg_pct > 0:
            n += 1
            hits.append("OI up + price up (healthy accumulation)")
        else:
            hits.append("FAIL OI/price: need both up")
    else:
        hits.append("SKIP OI/price (missing data)")

    if cluster_above is not None and cluster_below is not None:
        if cluster_above > cluster_below:
            n += 1
            hits.append("Cluster above > cluster below (short-liq fuel up)")
        else:
            hits.append("FAIL clusters: above not larger than below")
    else:
        hits.append("SKIP clusters (missing data)")

    if pa_confirm:
        n += 1
        hits.append("PA confirm: support held / reclaim")
    else:
        hits.append("FAIL PA: no support/reclaim confirm")

    return n, hits


def score_short(
    funding_pct: Optional[float],
    rsi: Optional[float],
    long_share_pct: Optional[float],
    oi_chg_pct: Optional[float],
    price_chg_pct: Optional[float],
    cluster_above: Optional[float],
    cluster_below: Optional[float],
    pa_confirm: bool,
) -> Tuple[int, List[str]]:
    """
    Short setup criteria (6 points):
    1. Funding >= +0.05% (longs crowded)
    2. RSI >= 70 (overbought)
    3. Long share >= 60%
    4. OI up AND price flat or down
    5. Cluster below price > cluster above
    6. Resistance rejection candle (user Yes)
    """
    hits: List[str] = []
    n = 0

    if funding_pct is not None and funding_pct >= 0.05:
        n += 1
        hits.append("Funding >= +0.05% (longs crowded)")
    elif funding_pct is not None:
        hits.append("FAIL funding: %.4f%% < +0.05%%" % funding_pct)

    if rsi is not None and rsi >= 70:
        n += 1
        hits.append("RSI >= 70 (overbought)")
    elif rsi is not None:
        hits.append("FAIL RSI: %.1f < 70" % rsi)

    if long_share_pct is not None and long_share_pct >= 60:
        n += 1
        hits.append("Long share >= 60%%")
    elif long_share_pct is not None:
        hits.append("FAIL long share: %.1f%% < 60%%" % long_share_pct)

    if oi_chg_pct is not None and price_chg_pct is not None:
        if oi_chg_pct > 0 and price_chg_pct <= 0:
            n += 1
            hits.append("OI up + price flat/down (late longs trapped)")
        else:
            hits.append("FAIL OI/price: need OI up and price flat/down")
    else:
        hits.append("SKIP OI/price (missing data)")

    if cluster_above is not None and cluster_below is not None:
        if cluster_below > cluster_above:
            n += 1
            hits.append("Cluster below > cluster above (long-liq fuel down)")
        else:
            hits.append("FAIL clusters: below not larger than above")
    else:
        hits.append("SKIP clusters (missing data)")

    if pa_confirm:
        n += 1
        hits.append("PA confirm: resistance rejection")
    else:
        hits.append("FAIL PA: no rejection confirm")

    return n, hits


def verdict(long_score: int, short_score: int) -> Dict[str, Any]:
    """
    Score reading:
    5-6 STRONG | 4 MODERATE | <=3 NO TRADE | both >=4 CONFLICT
    """
    if long_score >= 4 and short_score >= 4:
        return {
            "side": "HOLD",
            "label": "CONFLICT",
            "action": "Signals contradict. Stand aside.",
            "size_mult": 0.0,
        }
    if long_score >= 5 and long_score > short_score:
        return {
            "side": "LONG",
            "label": "STRONG LONG",
            "action": "Valid long. Normal planned risk (≤1% account).",
            "size_mult": 1.0,
        }
    if short_score >= 5 and short_score > long_score:
        return {
            "side": "SHORT",
            "label": "STRONG SHORT",
            "action": "Valid short. Normal planned risk (≤1% account).",
            "size_mult": 1.0,
        }
    if long_score == 4 and long_score > short_score:
        return {
            "side": "LONG",
            "label": "MODERATE LONG",
            "action": "Half size, or wait for one more confirmation.",
            "size_mult": 0.5,
        }
    if short_score == 4 and short_score > long_score:
        return {
            "side": "SHORT",
            "label": "MODERATE SHORT",
            "action": "Half size, or wait for one more confirmation.",
            "size_mult": 0.5,
        }
    return {
        "side": "HOLD",
        "label": "NO TRADE",
        "action": "No edge. Wait.",
        "size_mult": 0.0,
    }


def run_confluence(
    funding_pct: Optional[float] = None,
    rsi: Optional[float] = None,
    long_share_pct: Optional[float] = None,
    oi_chg_pct: Optional[float] = None,
    price_chg_pct: Optional[float] = None,
    cluster_above: Optional[float] = None,
    cluster_below: Optional[float] = None,
    pa_long: bool = False,
    pa_short: bool = False,
) -> Dict[str, Any]:
    """Full confluence evaluation for both sides."""
    regime = funding_regime(funding_pct) if funding_pct is not None else "UNKNOWN"
    long_n, long_hits = score_long(
        funding_pct, rsi, long_share_pct, oi_chg_pct, price_chg_pct,
        cluster_above, cluster_below, pa_long,
    )
    short_n, short_hits = score_short(
        funding_pct, rsi, long_share_pct, oi_chg_pct, price_chg_pct,
        cluster_above, cluster_below, pa_short,
    )
    v = verdict(long_n, short_n)
    return {
        "regime": regime,
        "regime_bias": REGIME_BIAS.get(regime, ""),
        "long_score": long_n,
        "short_score": short_n,
        "long_hits": long_hits,
        "short_hits": short_hits,
        "verdict": v["label"],
        "side": v["side"],
        "action": v["action"],
        "size_mult": v["size_mult"],
    }


def position_size(
    equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    leverage: float = 1.0,
) -> Dict[str, Any]:
    """
    Risk-based size. risk_pct e.g. 1.0 = 1% of equity.
    Returns notional, margin, and distance checks.
    """
    if entry <= 0 or stop <= 0 or equity <= 0:
        return {"error": "Invalid inputs", "notional": 0, "margin": 0, "risk_usd": 0}
    risk_usd = equity * (risk_pct / 100.0)
    stop_dist = abs(entry - stop) / entry
    if stop_dist < 1e-8:
        return {"error": "Stop too close to entry", "notional": 0, "margin": 0, "risk_usd": risk_usd}
    notional = risk_usd / stop_dist
    margin = notional / max(leverage, 1.0)
    # rough isolated liq distance ≈ 1/L (ignore mm for simplicity)
    liq_dist_pct = (100.0 / max(leverage, 1.0)) if leverage >= 1 else 100.0
    stop_dist_pct = stop_dist * 100.0
    stop_inside_liq = stop_dist_pct < liq_dist_pct * 0.85
    return {
        "risk_usd": round(risk_usd, 2),
        "stop_dist_pct": round(stop_dist_pct, 3),
        "notional": round(notional, 2),
        "margin": round(margin, 2),
        "liq_dist_approx_pct": round(liq_dist_pct, 2),
        "stop_inside_liq": stop_inside_liq,
        "warning": None if stop_inside_liq else "Stop is near/beyond approx liquidation — reduce leverage or tighten stop",
    }
