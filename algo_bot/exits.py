"""
Closed-bar exits and leftover daily-trial flatten.
"""

SMA_FIGHT_BUFFER = 0.0035
RANGE_HIGH_SL_BUFFER = 0.012
PRIOR_RANGE_HIGH = 82275.0
RANGE_BREAK_BUFFER = 0.002


def closed_bar_levels(candles):
    if not candles:
        return None
    last = candles[-1]
    closed = candles[-2] if len(candles) >= 2 else last
    ts = last.get("time", last.get("timestamp"))
    last_px = float(last.get("close", 0) or 0)
    hi = float(closed.get("high", closed.get("close", 0)) or 0)
    lo = float(closed.get("low", closed.get("close", 0)) or 0)
    return ts, last_px, hi, lo


def trial_fights_sma(trade, close_series):
    if not trade or (trade.get("note") or "") != "daily-trial":
        return False
    if close_series is None or len(close_series) < 20:
        return False
    n = min(200, len(close_series))
    sma = float(sum(close_series[-n:]) / n)
    px = float(close_series[-1])
    if sma <= 0 or px <= 0:
        return False
    side = trade.get("side")
    if side in ("LONG", "BUY") and px < sma * (1.0 - SMA_FIGHT_BUFFER):
        return True
    if side in ("SHORT", "SELL") and px > sma * (1.0 + SMA_FIGHT_BUFFER):
        return True
    return False


def trial_sl_near_range_high(trade, window_high):
    if not trade or (trade.get("note") or "") != "daily-trial":
        return False
    if trade.get("side") not in ("SHORT", "SELL"):
        return False
    if not window_high:
        return False
    sl = float(trade.get("stop_loss") or 0)
    if sl <= 0:
        return False
    return sl >= float(window_high) * (1.0 - RANGE_HIGH_SL_BUFFER)


def trial_range_broken(trade, last_px, prior_high=None):
    if not trade or (trade.get("note") or "") != "daily-trial":
        return False
    if trade.get("side") not in ("SHORT", "SELL"):
        return False
    try:
        px = float(last_px or 0)
    except Exception:
        return False
    lid = float(prior_high or PRIOR_RANGE_HIGH)
    if px <= 0 or lid <= 0:
        return False
    return px >= lid * (1.0 + RANGE_BREAK_BUFFER)
