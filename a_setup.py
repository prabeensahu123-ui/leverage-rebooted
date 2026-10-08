"""
a_setup.py - A-setup filter: model + candle + context calculator must agree.
"""


def evaluate_a_setup(model_sig, candle_sig, context_bias):
    """A-setup = model + candle + manual calculator all same LONG or SHORT."""
    ctx = (context_bias or "HOLD").upper()
    model = (model_sig or "").upper()
    candle = (candle_sig or "").upper()
    if ctx not in ("LONG", "SHORT"):
        return False, "NO", "Calculator not LONG/SHORT (run Calculate or HOLD)"
    if model not in ("LONG", "SHORT"):
        return False, "NO", "Model is %s" % (model or "—")
    if model != ctx:
        return False, "NO", "Model %s ≠ context %s" % (model, ctx)
    if candle != ctx:
        return False, "NO", "Candle %s ≠ context %s" % (candle, ctx)
    return True, "YES", "A-SETUP %s (model + candle + context)" % ctx


def build_a_setup_tables(model_rows, candle_rows, compare_rows, ctx_bias):
    """Annotate rows and return (a_setup_rows, any_long, any_short, best_a)."""
    priority = {"4h": 3, "1h": 2, "15m": 1}
    a_setup_rows = []
    any_long_a = False
    any_short_a = False
    best_a = None

    for i, mrow in enumerate(model_rows):
        model_sig = mrow.get("Signal", "N/A")
        crow = candle_rows[i] if i < len(candle_rows) else {}
        candle_sig = crow.get("Candle", "HOLD")
        ok, flag, reason = evaluate_a_setup(model_sig, candle_sig, ctx_bias)
        mrow["A-Setup"] = flag
        mrow["A-Reason"] = reason
        if i < len(compare_rows):
            compare_rows[i]["A-Setup"] = flag
            compare_rows[i]["Context"] = ctx_bias
        a_setup_rows.append({
            "Timeframe": mrow.get("Timeframe"),
            "Model": model_sig,
            "Candle": candle_sig,
            "Context": ctx_bias,
            "A-Setup": flag,
            "Reason": reason,
            "Entry": mrow.get("Entry", "-"),
            "Take Profit": mrow.get("Take Profit", "-"),
            "Stop Loss": mrow.get("Stop Loss", "-"),
        })
        if ok:
            side = model_sig
            if side == "LONG":
                any_long_a = True
            if side == "SHORT":
                any_short_a = True
            tf_lab = str(mrow.get("Timeframe", ""))
            pr = 0
            for k, v in priority.items():
                if k.lower() in tf_lab.lower():
                    pr = v
            if best_a is None or pr > best_a[0]:
                best_a = (pr, side, tf_lab)

    return a_setup_rows, any_long_a, any_short_a, best_a
