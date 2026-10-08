"""
structure_entry.py
Do not enter at random mid-range last price.
LONG near support or on a resistance break. SHORT near resistance or on a support break.
TP/SL are always oriented to the side.
"""

import numpy as np

LONG_SIDES = {"LONG", "BUY"}
SHORT_SIDES = {"SHORT", "SELL"}


def _swings(high, low, lookback=40, left=2, right=2):
    sh, sl = [], []
    start = max(len(high) - lookback - right, left)
    end = len(high) - right
    for i in range(start, end):
        w_hi = high[i - left:i + right + 1]
        w_lo = low[i - left:i + right + 1]
        if high[i] == np.max(w_hi):
            sh.append(float(high[i]))
        if low[i] == np.min(w_lo):
            sl.append(float(low[i]))
    return sh, sl


def structure_levels(high, low, close):
    sh, sl = _swings(high, low)
    price = float(close[-1])
    resistance = min([x for x in sh if x >= price], default=max(sh) if sh else price)
    support = max([x for x in sl if x <= price], default=min(sl) if sl else price)
    if resistance <= support:
        resistance = price * 1.004
        support = price * 0.996
    mid = (support + resistance) / 2.0
    width = max(resistance - support, price * 0.002)
    return {
        "support": support,
        "resistance": resistance,
        "mid": mid,
        "width": width,
        "price": price,
    }


def orient_levels(side, entry, stop, target):
    entry = float(entry)
    stop = float(stop)
    target = float(target)
    min_gap = max(entry * 0.0018, 1.0)

    if side in LONG_SIDES:
        if target <= entry:
            target = entry + min_gap
        if stop >= entry:
            stop = entry - min_gap
        if stop >= entry or target <= entry:
            return None
    elif side in SHORT_SIDES:
        if target >= entry:
            target = entry - min_gap
        if stop <= entry:
            stop = entry + min_gap
        if stop <= entry or target >= entry:
            return None
    else:
        return None

    if abs(target - entry) / entry < 0.0018:
        return None
    return entry, stop, target


def plan_entry(side, high, low, close, live_price, atr_pct):
    lv = structure_levels(high, low, close)
    px = float(live_price or lv["price"])
    if px <= 0:
        return None
    sup, res, width = lv["support"], lv["resistance"], lv["width"]
    band = max(width * 0.18, px * 0.0006, abs(atr_pct or 0.003) * px * 0.25)

    near_sup = abs(px - sup) <= band
    near_res = abs(px - res) <= band
    broke_res = px > res and (px - res) <= band * 1.6
    broke_sup = px < sup and (sup - px) <= band * 1.6

    plan = {
        "support": round(sup, 2),
        "resistance": round(res, 2),
        "live": round(px, 2),
        "style": None,
        "entry": None,
        "stop": None,
        "target": None,
    }

    if side in LONG_SIDES:
        if near_sup:
            plan.update(style="support bounce", entry=px, stop=sup - band, target=res)
        elif broke_res:
            plan.update(style="resistance break", entry=px, stop=res - band, target=px + width)
        else:
            return None
    elif side in SHORT_SIDES:
        if near_res:
            plan.update(style="resistance fade", entry=px, stop=res + band, target=sup)
        elif broke_sup:
            plan.update(style="support break", entry=px, stop=sup + band, target=px - width)
        else:
            return None
    else:
        return None

    oriented = orient_levels(side, plan["entry"], plan["stop"], plan["target"])
    if oriented is None:
        return None
    entry, stop, target = oriented
    plan["entry"] = round(entry, 2)
    plan["stop"] = round(stop, 2)
    plan["target"] = round(target, 2)
    return plan
