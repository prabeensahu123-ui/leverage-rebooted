"""Trade Analysis helpers: RSI already in app; ADX + RSI×ADX gate."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np


def adx_di_from_candles(candles, period: int = 14) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Wilder ADX, +DI, -DI. Returns (adx, plus_di, minus_di)."""
    if not candles or len(candles) < period + 3:
        return None, None, None
    high = np.asarray([float(x.get("high") or 0) for x in candles], dtype=float)
    low = np.asarray([float(x.get("low") or 0) for x in candles], dtype=float)
    close = np.asarray([float(x.get("close") or 0) for x in candles], dtype=float)
    if np.any(high <= 0) or np.any(low <= 0) or np.any(close <= 0):
        return None, None, None
    n = len(close)
    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        h, l, pc = high[i], low[i], close[i - 1]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
        up = high[i] - high[i - 1]
        dn = low[i - 1] - low[i]
        plus_dm[i] = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
    atr = np.zeros(n)
    pdm = np.zeros(n)
    mdm = np.zeros(n)
    atr[period] = float(np.mean(tr[1 : period + 1]))
    pdm[period] = float(np.mean(plus_dm[1 : period + 1]))
    mdm[period] = float(np.mean(minus_dm[1 : period + 1]))
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        pdm[i] = (pdm[i - 1] * (period - 1) + plus_dm[i]) / period
        mdm[i] = (mdm[i - 1] * (period - 1) + minus_dm[i]) / period
    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    dx = np.zeros(n)
    for i in range(period, n):
        if atr[i] < 1e-12:
            continue
        plus_di[i] = 100.0 * pdm[i] / atr[i]
        minus_di[i] = 100.0 * mdm[i] / atr[i]
        s = plus_di[i] + minus_di[i]
        if s > 1e-12:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / s
    adx_s = np.zeros(n)
    start = period * 2 - 1
    if start >= n:
        return float(dx[-1]), float(plus_di[-1]), float(minus_di[-1])
    adx_s[start] = float(np.mean(dx[period : start + 1]))
    for i in range(start + 1, n):
        adx_s[i] = (adx_s[i - 1] * (period - 1) + dx[i]) / period
    return float(adx_s[-1]), float(plus_di[-1]), float(minus_di[-1])


def apply_rsi_adx_gate(
    tech: str,
    conf_pct: int,
    rsi: Optional[float],
    adx: Optional[float],
    pdi: Optional[float],
    mdi: Optional[float],
):
    """
    RSI × ADX gate:
    - ADX < 18 → chop → HOLD, lower confidence
    - RSI < 25 + ADX >= 30 + -DI > +DI → block LONG
    - RSI > 75 + ADX >= 30 + +DI > -DI → block SHORT
    """
    gate = "—"
    if adx is None or rsi is None:
        return tech, conf_pct, gate
    pdi = float(pdi or 0.0)
    mdi = float(mdi or 0.0)

    if adx < 18.0:
        conf_pct = max(15, int(conf_pct * 0.65))
        if tech in ("LONG", "SHORT"):
            return "HOLD", conf_pct, "chop→HOLD"
        return tech, conf_pct, "chop ADX<18"

    if adx >= 30.0 and mdi > pdi and rsi < 25.0 and tech == "LONG":
        return "HOLD", max(20, int(conf_pct * 0.5)), "RSI<25+ADX↑ block LONG"

    if adx >= 30.0 and pdi > mdi and rsi > 75.0 and tech == "SHORT":
        return "HOLD", max(20, int(conf_pct * 0.5)), "RSI>75+ADX↑ block SHORT"

    if adx >= 30.0 and mdi > pdi and rsi < 30.0 and tech == "LONG":
        return tech, max(20, int(conf_pct * 0.75)), "caution LONG (downtrend)"
    if adx >= 30.0 and pdi > mdi and rsi > 70.0 and tech == "SHORT":
        return tech, max(20, int(conf_pct * 0.75)), "caution SHORT (uptrend)"

    if adx >= 25.0:
        gate = "trend ADX%.0f" % adx
        if pdi > mdi and tech == "LONG":
            conf_pct = min(100, conf_pct + 5)
        elif mdi > pdi and tech == "SHORT":
            conf_pct = min(100, conf_pct + 5)
    else:
        gate = "ADX%.0f" % adx
    return tech, conf_pct, gate


def enrich_row_with_adx(
    row: Dict[str, Any],
    candles,
    tech: str,
    conf_pct: int,
    rsi: Optional[float],
) -> Dict[str, Any]:
    adx_v, pdi, mdi = adx_di_from_candles(candles)
    tech2, conf2, gate = apply_rsi_adx_gate(tech, conf_pct, rsi, adx_v, pdi, mdi)
    di_txt = "—"
    if pdi is not None and mdi is not None:
        di_txt = "+%.0f/-%.0f" % (pdi, mdi)
    row = dict(row)
    row["ADX"] = ("%.1f" % adx_v) if adx_v is not None else "—"
    row["+DI/-DI"] = di_txt
    row["Tech bias"] = (
        "🟢 LONG" if tech2 == "LONG" else "🔴 SHORT" if tech2 == "SHORT" else "⚪ HOLD" if tech2 == "HOLD" else tech2
    )
    row["Confidence %"] = conf2
    row["RSI×ADX gate"] = gate
    conf_disp = str(row.get("Confluence / Liq") or "")
    conf_side = None
    if conf_disp.startswith("🟢") or ("LONG" in conf_disp[:24] and "SHORT" not in conf_disp[:24]):
        conf_side = "LONG"
    if conf_disp.startswith("🔴") or conf_disp.strip().startswith("SHORT"):
        conf_side = "SHORT"
    if conf_disp.startswith("⚪") or "HOLD" in conf_disp[:28]:
        conf_side = "HOLD"
    if conf_side is None and "score 6-pt" in conf_disp:
        row["Reconcile"] = row.get("Reconcile") or "—"
    elif conf_side is None:
        pass
    elif conf_side == "HOLD" or tech2 == "HOLD":
        row["Reconcile"] = "⏸️ WAIT"
    elif tech2 == conf_side:
        row["Reconcile"] = "✅ AGREE"
    else:
        row["Reconcile"] = "❌ CONFLICT"
    return row
