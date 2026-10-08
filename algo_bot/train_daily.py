"""
Train RandomForest once per day with walk-forward OOS metrics.
  python -m algo_bot.train_daily
"""

import os
import sys
from collections import Counter

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algo_bot import config as cfg
from algo_bot.model_engine import fetch_candles
from algo_bot.model_store import save_model, ensure_dir
from ml_features import build_features, FEATURE_NAMES, WINNING_FEATURES
from triple_barrier import triple_barrier_labels, apply_cost_filter

WINNING_FEATURE_INDICES = [FEATURE_NAMES.index(f) for f in WINNING_FEATURES]

SYMBOLS = list(getattr(cfg, "TRADE_SYMBOLS", None) or [getattr(cfg, "SYMBOL", "BTCUSD")])
TIMEFRAMES = cfg.TIMEFRAMES
K_PROFIT = getattr(cfg, "K_PROFIT", 2.0)
K_STOP = getattr(cfg, "K_STOP", 2.0)
MIN_LABEL_MOVE_PCT = getattr(cfg, "MIN_LABEL_MOVE_PCT", 0.0015)
OOS_FRACTION = getattr(cfg, "OOS_FRACTION", 0.20)
PURGE_MULTIPLIER = getattr(cfg, "PURGE_MULTIPLIER", 1)


def walk_forward_score(X, y, idxs, max_holding, oos_frac=0.20):
    n = len(y)
    if n < 120:
        return {"oos_ok": False, "reason": f"n={n}<120"}

    order = np.argsort(np.asarray(idxs))
    X = np.asarray(X)[order]
    y = np.asarray(y)[order]
    idxs = np.asarray(idxs)[order]

    cut = int(n * (1.0 - oos_frac))
    if cut < 80 or (n - cut) < 25:
        return {"oos_ok": False, "reason": "split too small"}

    oos_start_idx = int(idxs[cut])
    embargo = int(max_holding * PURGE_MULTIPLIER)

    train_mask = np.array([i < (oos_start_idx - embargo) for i in idxs[:cut]])
    X_tr = X[:cut][train_mask]
    y_tr = y[:cut][train_mask]
    X_te = X[cut:]
    y_te = y[cut:]

    if len(y_tr) < 60 or len(y_te) < 20:
        return {"oos_ok": False, "reason": f"after purge train={len(y_tr)} oos={len(y_te)}"}

    if len(set(y_tr)) < 2:
        return {"oos_ok": False, "reason": "train single class"}

    m = RandomForestClassifier(
        n_estimators=120, max_depth=6, min_samples_leaf=8,
        class_weight="balanced", random_state=42, n_jobs=-1
    )
    m.fit(X_tr, y_tr)
    pred = m.predict(X_te)

    long_p = precision_score(y_te, pred, labels=[1], average="micro", zero_division=0)
    short_p = precision_score(y_te, pred, labels=[-1], average="micro", zero_division=0)
    long_r = recall_score(y_te, pred, labels=[1], average="micro", zero_division=0)
    short_r = recall_score(y_te, pred, labels=[-1], average="micro", zero_division=0)

    return {
        "oos_ok": True,
        "oos_n": int(len(y_te)),
        "train_n_purged": int(len(y_tr)),
        "embargo_bars": embargo,
        "oos_accuracy": float(accuracy_score(y_te, pred)),
        "oos_long_n": int((y_te == 1).sum()),
        "oos_short_n": int((y_te == -1).sum()),
        "oos_hold_n": int((y_te == 0).sum()),
        "oos_long_precision": float(long_p),
        "oos_short_precision": float(short_p),
        "oos_long_recall": float(long_r),
        "oos_short_recall": float(short_r),
        "oos_pred_dist": {str(k): int(v) for k, v in Counter(pred).items()},
        "oos_true_dist": {str(k): int(v) for k, v in Counter(y_te).items()},
    }


def train_one(symbol: str, resolution: str, days: int, max_holding: int):
    candles = fetch_candles(symbol, resolution, days)
    if len(candles) < 80:
        print(f"  skip {symbol} {resolution}: not enough candles ({len(candles)})")
        return False, {}

    close = np.array([c["close"] for c in candles], dtype=float)
    high = np.array([c["high"] for c in candles], dtype=float)
    low = np.array([c["low"] for c in candles], dtype=float)
    volume = np.array([c["volume"] for c in candles], dtype=float)
    open_ = np.array([c.get("open", c["close"]) for c in candles], dtype=float)
    ohlcv = {"open": open_, "high": high, "low": low, "close": close, "volume": volume}

    labels, valid, vol, exit_prices, _ = triple_barrier_labels(
        close, K_PROFIT, K_STOP, max_holding, high=high, low=low
    )
    labels = apply_cost_filter(labels, close, exit_prices, valid, MIN_LABEL_MOVE_PCT)

    X, y, idxs = [], [], []
    for i in range(55, len(close) - 1):
        if valid[i]:
            X.append(build_features(ohlcv, i))
            y.append(labels[i])
            idxs.append(i)

    if len(X) < 90:
        print(f"  skip {symbol} {resolution}: train rows {len(X)}")
        return False, {}

    X_arr = np.array(X)[:, WINNING_FEATURE_INDICES]
    y_arr = np.array(y)

    oos = walk_forward_score(X_arr, y_arr, idxs, max_holding, OOS_FRACTION)
    print(
        f"  OOS: ok={oos.get('oos_ok')} n={oos.get('oos_n')} "
        f"acc={oos.get('oos_accuracy')} "
        f"L_prec={oos.get('oos_long_precision')} S_prec={oos.get('oos_short_precision')}"
    )

    model = RandomForestClassifier(
        n_estimators=120, max_depth=6, min_samples_leaf=8,
        class_weight="balanced", random_state=42, n_jobs=-1
    )
    model.fit(X_arr, y_arr)
    extra = {
        "n_samples": int(len(y_arr)),
        "days": days,
        "max_holding": max_holding,
        "label_dist": {str(k): int(v) for k, v in Counter(y_arr).items()},
        **{k: v for k, v in oos.items() if k != "reason"},
    }
    if not oos.get("oos_ok"):
        extra["oos_reason"] = oos.get("reason")

    path = save_model(symbol, resolution, model, extra=extra)
    print(f"  saved {path} samples={len(y_arr)} classes={list(model.classes_)}")
    return True, extra


def main():
    ensure_dir()
    print(f"Daily train + walk-forward | symbols={SYMBOLS} | OOS={OOS_FRACTION}")
    ok, fail = 0, 0
    report = []
    for symbol in SYMBOLS:
        for tf_key, tf in TIMEFRAMES.items():
            res = tf["resolution"]
            print(f"\n> {symbol} {tf_key} ({res})")
            try:
                good, meta = train_one(symbol, res, tf["days"], tf["max_holding_bars"])
                if good:
                    ok += 1
                    report.append({
                        "symbol": symbol,
                        "tf": tf_key,
                        "oos_acc": meta.get("oos_accuracy"),
                        "long_prec": meta.get("oos_long_precision"),
                        "short_prec": meta.get("oos_short_precision"),
                        "oos_n": meta.get("oos_n"),
                    })
                else:
                    fail += 1
            except Exception as e:
                print(f"  error: {e}")
                fail += 1

    print("\n======== OOS SUMMARY ========")
    for r in report:
        print(
            f"{r['symbol']:8} {r['tf']:4} n={r['oos_n']} "
            f"acc={r['oos_acc']} L_p={r['long_prec']} S_p={r['short_prec']}"
        )
    print(f"\nDone. ok={ok} fail={fail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
