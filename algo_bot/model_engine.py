"""
algo_bot/model_engine.py
Uses daily pre-trained RF when available; falls back to fit-on-the-fly.
"""

import numpy as np
import requests
from sklearn.ensemble import RandomForestClassifier

from ml_features import build_features, FEATURE_NAMES, WINNING_FEATURES
from triple_barrier import triple_barrier_labels, apply_cost_filter
from market_context import build_market_context, apply_context_filter
from structure_entry import plan_entry
from regime import classify_regime, apply_regime_filter
from squeeze_scanner import squeeze_handoff
from algo_bot.config import (
    DELTA_BASE, K_PROFIT, K_STOP,
    MIN_BUY_PROBA, MIN_SELL_PROBA, MIN_EDGE,
    MIN_LABEL_MOVE_PCT, ACCOUNT_INR, LEVERAGE, USD_INR, RISK_FRACTION
)
from algo_bot.model_store import load_model

WINNING_FEATURE_INDICES = [FEATURE_NAMES.index(f) for f in WINNING_FEATURES]


def _as_candle_list(payload):
    if isinstance(payload, dict):
        payload = payload.get("result", [])
    if not isinstance(payload, list):
        return []
    return payload


def fetch_candles(symbol: str, resolution: str, days: int):
    end = int(__import__("time").time())
    start = end - days * 86400
    try:
        raw = requests.get(
            f"{DELTA_BASE}/v2/history/candles",
            params={"resolution": resolution, "symbol": symbol, "start": start, "end": end},
            timeout=14
        ).json()
        rows = _as_candle_list(raw)
        return list(reversed(rows))
    except Exception as e:
        print(f"[Model] Candle fetch error: {e}")
        return []


def fetch_ticker(symbol: str):
    try:
        return requests.get(f"{DELTA_BASE}/v2/tickers/{symbol}", timeout=5).json().get("result", {})
    except Exception:
        return {}


def _sma(arr, n):
    if len(arr) < n:
        return float(arr[-1]) if len(arr) else 0.0
    return float(np.mean(arr[-n:]))


def position_qty_btc(entry, stop):
    risk_inr = ACCOUNT_INR * RISK_FRACTION
    stop_dist = abs(entry - stop)
    if stop_dist <= 0 or entry <= 0:
        return 0.0
    qty = (risk_inr / USD_INR) / stop_dist
    max_qty = (ACCOUNT_INR * LEVERAGE / USD_INR) / entry
    return float(min(qty, max_qty))


def _fit_or_load(symbol, resolution, ohlcv, close, high, low, max_holding):
    model, meta = load_model(symbol, resolution)
    if model is not None:
        return model, True

    labels, valid, vol, exit_prices, _ = triple_barrier_labels(
        close, K_PROFIT, K_STOP, max_holding, high=high, low=low
    )
    labels = apply_cost_filter(labels, close, exit_prices, valid, MIN_LABEL_MOVE_PCT)
    X, y = [], []
    for i in range(55, len(close) - 1):
        if valid[i]:
            X.append(build_features(ohlcv, i))
            y.append(labels[i])
    if len(X) < 90:
        return None, False
    X = np.array(X)[:, WINNING_FEATURE_INDICES]
    y = np.array(y)
    model = RandomForestClassifier(
        n_estimators=120, max_depth=6, min_samples_leaf=8,
        class_weight="balanced", random_state=42, n_jobs=-1
    )
    model.fit(X, y)
    return model, False


def get_signal(symbol: str, resolution: str, days: int, max_holding: int):
    candles = fetch_candles(symbol, resolution, days)
    if len(candles) < 80:
        return None

    close = np.array([c["close"] for c in candles], dtype=float)
    high = np.array([c["high"] for c in candles], dtype=float)
    low = np.array([c["low"] for c in candles], dtype=float)
    volume = np.array([c["volume"] for c in candles], dtype=float)
    open_ = np.array([c.get("open", c["close"]) for c in candles], dtype=float)
    ohlcv = {"open": open_, "high": high, "low": low, "close": close, "volume": volume}

    labels, valid, vol, exit_prices, _ = triple_barrier_labels(
        close, K_PROFIT, K_STOP, max_holding, high=high, low=low
    )
    cur_vol = float(vol[-1]) if len(vol) and vol[-1] > 0 else float(np.std(np.diff(np.log(close[-15:]))))

    model, from_disk = _fit_or_load(symbol, resolution, ohlcv, close, high, low, max_holding)
    if model is None:
        return None

    current_feats = np.array([build_features(ohlcv, len(close)-1)])[:, WINNING_FEATURE_INDICES]
    proba = model.predict_proba(current_feats)[0]
    classes = list(model.classes_)

    long_p = float(proba[classes.index(1)]) if 1 in classes else 0.0
    short_p = float(proba[classes.index(-1)]) if -1 in classes else 0.0
    hold_p = float(proba[classes.index(0)]) if 0 in classes else 0.0

    sma200 = _sma(close, min(200, len(close)))
    price_now = float(close[-1])
    regime = "UP" if price_now >= sma200 else "DOWN"
    vol_reg = classify_regime(high, low, close)
    squeeze = squeeze_handoff(high, low, close)

    ticker = fetch_ticker(symbol)
    live_price = float(ticker.get("close", ticker.get("mark_price", close[-1])))
    ctx = build_market_context(symbol)

    side = None
    confidence = 0.0
    if long_p >= MIN_BUY_PROBA and long_p > short_p + MIN_EDGE and regime == "UP":
        side = "LONG"
        confidence = long_p
    elif short_p >= MIN_SELL_PROBA and short_p > long_p + MIN_EDGE and regime == "DOWN":
        side = "SHORT"
        confidence = short_p

    squeeze_used = False
    if side is None and squeeze.get("handoff"):
        d = squeeze.get("direction")
        if d == "LONG" and regime == "UP" and long_p >= short_p:
            side = "LONG"
            confidence = max(long_p, 0.51)
            squeeze_used = True
        elif d == "SHORT" and regime == "DOWN" and short_p >= long_p:
            side = "SHORT"
            confidence = max(short_p, 0.51)
            squeeze_used = True

    side, veto_reason = apply_context_filter(side, ctx, resolution)

    plan = None
    if side:
        plan = plan_entry(side, high, low, close, live_price, cur_vol)
        if plan is None and squeeze_used:
            px = float(live_price)
            width = max(abs(squeeze["prior_high"] - squeeze["prior_low"]), px * 0.004)
            if side == "LONG":
                plan = {
                    "style": "squeeze resistance break",
                    "entry": px,
                    "stop": float(squeeze["prior_low"]),
                    "target": px + width,
                    "support": float(squeeze["prior_low"]),
                    "resistance": float(squeeze["prior_high"]),
                }
            else:
                plan = {
                    "style": "squeeze support break",
                    "entry": px,
                    "stop": float(squeeze["prior_high"]),
                    "target": px - width,
                    "support": float(squeeze["prior_low"]),
                    "resistance": float(squeeze["prior_high"]),
                }
        if plan is None:
            veto_reason = (veto_reason + "; " if veto_reason else "") + "mid-range — wait for S/R or break"
            side = None

    if side:
        vol_state = vol_reg.get("vol_state")
        if squeeze_used:
            vol_state = "EXPANSION"
            if plan and "break" not in (plan.get("style") or "").lower():
                plan["style"] = ("squeeze " + (plan.get("style") or "break")).strip()
        side, regime_veto = apply_regime_filter(side, vol_state, plan.get("style") if plan else None)
        if regime_veto:
            veto_reason = (veto_reason + "; " if veto_reason else "") + regime_veto
            if side is None:
                plan = None

    base = {
        "side": side,
        "buy_proba": long_p,
        "sell_proba": short_p,
        "long_proba": long_p,
        "short_proba": short_p,
        "hold_proba": hold_p,
        "price": live_price,
        "volatility": cur_vol,
        "regime": regime,
        "vol_state": vol_reg.get("vol_state"),
        "adx": vol_reg.get("adx"),
        "atr_ratio": vol_reg.get("atr_ratio"),
        "sma200": sma200,
        "context": ctx,
        "veto_reason": veto_reason,
        "squeeze": squeeze,
        "entry_style": plan["style"] if plan else None,
        "support": plan["support"] if plan else None,
        "resistance": plan["resistance"] if plan else None,
        "model_source": "disk" if from_disk else "live_fit",
    }
    if side is None or plan is None:
        return base

    entry = float(plan["entry"])
    sl = float(plan["stop"])
    tp = float(plan["target"])
    qty = position_qty_btc(entry, sl)
    base.update({
        "confidence": confidence,
        "price": entry,
        "take_profit": tp,
        "stop_loss": sl,
        "qty_btc": qty,
    })
    return base
