"""
candle_patterns.py
Last-bar and multi-bar patterns. Reversal names need a short local trend.
"""


def _bar(open_, high, low, close, i):
    o, h, l, c = float(open_[i]), float(high[i]), float(low[i]), float(close[i])
    body = abs(c - o)
    rng = max(h - l, 1e-12)
    upper = h - max(o, c)
    lower = min(o, c) - l
    bull = c > o
    bear = c < o
    mid = (o + c) / 2.0
    return {
        "o": o, "h": h, "l": l, "c": c,
        "body": body, "rng": rng, "up": upper, "lo": lower,
        "bull": bull, "bear": bear, "mid": mid,
    }


def _local_trend(close, lookback=5):
    if len(close) < lookback + 1:
        return "FLAT"
    start = float(close[-1 - lookback])
    end = float(close[-2]) if len(close) > 1 else float(close[-1])
    if start <= 0:
        return "FLAT"
    chg = (end - start) / start
    if chg <= -0.004:
        return "DOWN"
    if chg >= 0.004:
        return "UP"
    return "FLAT"


def detect_candle_pattern(open_, high, low, close):
    """Returns (pattern_name, bias) where bias is LONG / SHORT / HOLD."""
    n = len(close)
    if n < 3:
        return "None", "HOLD"

    trend = _local_trend(close)
    a = _bar(open_, high, low, close, -1)
    b = _bar(open_, high, low, close, -2)
    c = _bar(open_, high, low, close, -3) if n >= 3 else None

    if n >= 3 and c is not None:
        if (
            c["bear"] and c["body"] / c["rng"] > 0.45
            and a["bull"] and a["body"] / a["rng"] > 0.45
            and b["body"] / b["rng"] < 0.35
            and a["c"] > (c["o"] + c["c"]) / 2.0
            and trend == "DOWN"
        ):
            return "Morning Star", "LONG"

        if (
            c["bull"] and c["body"] / c["rng"] > 0.45
            and a["bear"] and a["body"] / a["rng"] > 0.45
            and b["body"] / b["rng"] < 0.35
            and a["c"] < (c["o"] + c["c"]) / 2.0
            and trend == "UP"
        ):
            return "Evening Star", "SHORT"

        if (
            c["bull"] and b["bull"] and a["bull"]
            and c["body"] / c["rng"] > 0.55
            and b["body"] / b["rng"] > 0.55
            and a["body"] / a["rng"] > 0.55
            and b["c"] > c["c"] and a["c"] > b["c"]
            and min(b["o"], b["c"]) >= min(c["o"], c["c"])
            and min(a["o"], a["c"]) >= min(b["o"], b["c"])
        ):
            return "Three White Soldiers", "LONG"

        if (
            c["bear"] and b["bear"] and a["bear"]
            and c["body"] / c["rng"] > 0.55
            and b["body"] / b["rng"] > 0.55
            and a["body"] / a["rng"] > 0.55
            and b["c"] < c["c"] and a["c"] < b["c"]
            and max(b["o"], b["c"]) <= max(c["o"], c["c"])
            and max(a["o"], a["c"]) <= max(b["o"], b["c"])
        ):
            return "Three Black Crows", "SHORT"

    if b["bear"] and a["bull"] and a["body"] > b["body"] * 1.05 and a["c"] >= b["o"] and a["o"] <= b["c"]:
        return "Bull Engulf", "LONG"
    if b["bull"] and a["bear"] and a["body"] > b["body"] * 1.05 and a["o"] >= b["c"] and a["c"] <= b["o"]:
        return "Bear Engulf", "SHORT"

    if (
        b["bear"] and a["bull"]
        and a["o"] < b["c"]
        and a["c"] > b["mid"]
        and a["c"] < b["o"]
        and trend != "UP"
    ):
        return "Piercing Line", "LONG"

    if (
        b["bull"] and a["bear"]
        and a["o"] > b["c"]
        and a["c"] < b["mid"]
        and a["c"] > b["o"]
        and trend != "DOWN"
    ):
        return "Dark Cloud Cover", "SHORT"

    if b["bear"] and a["bull"] and a["body"] < b["body"] * 0.7 and a["o"] > b["c"] and a["c"] < b["o"]:
        return "Bull Harami", "LONG"
    if b["bull"] and a["bear"] and a["body"] < b["body"] * 0.7 and a["c"] > b["o"] and a["o"] < b["c"]:
        return "Bear Harami", "SHORT"

    wick_tol = max(b["rng"], a["rng"]) * 0.12
    if abs(b["l"] - a["l"]) <= wick_tol and trend != "UP":
        return "Tweezer Bottom", "LONG"
    if abs(b["h"] - a["h"]) <= wick_tol and trend != "DOWN":
        return "Tweezer Top", "SHORT"

    if a["body"] / a["rng"] < 0.12:
        return "Doji", "HOLD"

    long_lower = a["lo"] >= 2.0 * a["body"] and a["up"] <= a["body"] * 0.6 and a["body"] / a["rng"] < 0.40
    long_upper = a["up"] >= 2.0 * a["body"] and a["lo"] <= a["body"] * 0.6 and a["body"] / a["rng"] < 0.40

    if long_lower:
        if trend == "UP" or b["bull"]:
            return "Hanging Man", "SHORT"
        return "Hammer", "LONG"
    if long_upper:
        if trend == "UP" or b["bull"]:
            return "Shooting Star", "SHORT"
        return "Inverted Hammer", "LONG"

    if a["bull"] and a["body"] / a["rng"] > 0.75 and a["up"] / a["rng"] < 0.12 and a["lo"] / a["rng"] < 0.12:
        return "Bull Marubozu", "LONG"
    if a["bear"] and a["body"] / a["rng"] > 0.75 and a["up"] / a["rng"] < 0.12 and a["lo"] / a["rng"] < 0.12:
        return "Bear Marubozu", "SHORT"

    return "No clear pattern", "HOLD"
