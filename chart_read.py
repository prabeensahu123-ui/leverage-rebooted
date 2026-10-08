"""
chart_read.py — lightweight chart snapshot helpers for the paper bot.
"""


def snapshot(candles):
    if not candles:
        return {}
    closes = [float(c.get("close", 0) or 0) for c in candles]
    highs = [float(c.get("high", c.get("close", 0)) or 0) for c in candles]
    lows = [float(c.get("low", c.get("close", 0)) or 0) for c in candles]
    px = closes[-1] if closes else 0.0
    prior_range_high = max(highs[-48:]) if len(highs) >= 2 else (max(highs) if highs else px)
    prior_range_low = min(lows[-48:]) if len(lows) >= 2 else (min(lows) if lows else px)
    return {
        "last": px,
        "prior_range_high": prior_range_high,
        "prior_range_low": prior_range_low,
        "n": len(candles),
    }


def caption(snap):
    if not snap:
        return "no chart"
    return (
        f"last={snap.get('last')} "
        f"range_hi={snap.get('prior_range_high')} "
        f"range_lo={snap.get('prior_range_low')} "
        f"n={snap.get('n')}"
    )
