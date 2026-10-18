"""
algo_bot/bot.py
Background paper trading runner.
Commands: once | start | status | performance

- Opens new paper trades from model + technical filters (chart/regime/structure)
- Every cycle checks open trades for SL / TP hits and closes them
- Telegram notify on open and close (if secrets set)
"""

from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone

from algo_bot.config import (
    PAPER_TRADE_SYMBOLS,
    TIMEFRAMES,
    STATE_FILE,
    TRADE_LOG_FILE,
    CHECK_INTERVAL_MINUTES,
    DELTA_BASE,
)
from algo_bot.model_engine import get_signal, fetch_ticker
from algo_bot.notifier import (
    notify_trade_opened,
    notify_trade_closed,
    notify_status,
    is_configured,
)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                st = json.load(f)
            # normalize: open_trades always a list
            ot = st.get("open_trades", [])
            if isinstance(ot, dict):
                ot = list(ot.values()) if ot else []
            st["open_trades"] = ot
            st.setdefault("history", [])
            return st
        except Exception:
            pass
    return {"open_trades": [], "history": []}


def _save_state(st):
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, indent=2)


def _append_trade_log(row: dict):
    os.makedirs(os.path.dirname(TRADE_LOG_FILE) or ".", exist_ok=True)
    exists = os.path.exists(TRADE_LOG_FILE)
    fields = [
        "closed_at", "symbol", "tf", "side", "entry", "exit_price",
        "stop_loss", "take_profit", "pnl_pct", "win", "exit_reason", "opened_at",
    ]
    with open(TRADE_LOG_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerow(row)


def _check_exit(trade: dict) -> dict | None:
    """Return close result if SL or TP hit on last price, else None."""
    sym = trade.get("symbol")
    side = trade.get("side")
    entry = float(trade.get("entry") or 0)
    sl = float(trade.get("stop_loss") or 0)
    tp = float(trade.get("take_profit") or 0)
    if not sym or entry <= 0:
        return None

    ticker = fetch_ticker(sym)
    px = float(ticker.get("close", ticker.get("mark_price", 0)) or 0)
    if px <= 0:
        return None

    reason = None
    if side in ("LONG", "BUY"):
        if sl > 0 and px <= sl:
            reason = "stop_loss"
        elif tp > 0 and px >= tp:
            reason = "take_profit"
    elif side in ("SHORT", "SELL"):
        if sl > 0 and px >= sl:
            reason = "stop_loss"
        elif tp > 0 and px <= tp:
            reason = "take_profit"

    if not reason:
        return None

    if side in ("LONG", "BUY"):
        pnl_pct = (px - entry) / entry * 100.0
    else:
        pnl_pct = (entry - px) / entry * 100.0

    return {
        "timeframe": trade.get("tf"),
        "side": side,
        "entry": entry,
        "exit_price": px,
        "stop_loss": sl,
        "take_profit": tp,
        "pnl_pct": round(pnl_pct, 3),
        "win": pnl_pct > 0,
        "exit_reason": reason,
        "symbol": sym,
        "tf": trade.get("tf"),
        "opened_at": trade.get("opened_at"),
        "closed_at": _now_iso(),
    }


def _manage_open_trades(state: dict) -> int:
    """Close any open trades that hit SL/TP. Returns number closed."""
    still_open = []
    closed_n = 0
    for t in state.get("open_trades", []):
        result = _check_exit(t)
        if result is None:
            still_open.append(t)
            continue
        closed_n += 1
        state.setdefault("history", []).append(result)
        _append_trade_log(result)
        notify_trade_closed(result)
        print(
            f"  CLOSED {result['symbol']} {result['tf']} {result['side']} "
            f"@ {result['exit_price']:.1f} PnL={result['pnl_pct']:+.2f}% ({result['exit_reason']})"
        )
    state["open_trades"] = still_open
    return closed_n


def run_once():
    print(f"[Bot] once @ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    state = _load_state()

    # 1) Manage exits first
    closed_n = _manage_open_trades(state)
    if closed_n:
        print(f"[Bot] closed {closed_n} trade(s)")

    # 2) Scan for new entries (model + technical filters inside get_signal)
    signals = []
    for sym in PAPER_TRADE_SYMBOLS:
        for tf_name, tf in TIMEFRAMES.items():
            if not tf.get("trade_enabled", True):
                continue
            sig = get_signal(sym, tf["resolution"], tf["days"], tf["max_holding_bars"])
            if not sig:
                continue
            signals.append((sym, tf_name, sig))
            side = sig.get("side")
            print(
                f"  {sym} {tf_name}: {side or 'HOLD'} "
                f"L={sig.get('long_proba', 0):.2f} S={sig.get('short_proba', 0):.2f} "
                f"px={sig.get('price', 0):.1f} veto={sig.get('veto_reason') or '-'} "
                f"src={sig.get('model_source', '?')}"
            )
            if not side:
                continue
            # one open position per symbol+tf
            if any(
                t.get("symbol") == sym and t.get("tf") == tf_name
                for t in state["open_trades"]
            ):
                continue
            trade = {
                "symbol": sym,
                "tf": tf_name,
                "side": side,
                "entry": sig.get("price"),
                "stop_loss": sig.get("stop_loss"),
                "take_profit": sig.get("take_profit"),
                "qty_btc": sig.get("qty_btc"),
                "opened_at": _now_iso(),
                "confidence": sig.get("confidence"),
                "entry_style": sig.get("entry_style"),
                "model_source": sig.get("model_source"),
            }
            state["open_trades"].append(trade)
            notify_trade_opened(
                {
                    "timeframe": tf_name,
                    "side": side,
                    "entry": trade["entry"],
                    "take_profit": trade["take_profit"],
                    "stop_loss": trade["stop_loss"],
                    "confidence": trade.get("confidence", 0),
                }
            )
            print(f"    -> OPENED paper {side} @ {trade['entry']}")

    _save_state(state)
    print(f"[Bot] open trades: {len(state['open_trades'])}")
    return signals


def show_status():
    state = _load_state()
    print(f"Open trades: {len(state.get('open_trades', []))}")
    for t in state.get("open_trades", []):
        print(
            f"  {t.get('symbol')} {t.get('tf')} {t.get('side')} "
            f"entry={t.get('entry')} SL={t.get('stop_loss')} TP={t.get('take_profit')}"
        )
    if is_configured():
        notify_status(len(state.get("open_trades", [])))


def show_performance():
    state = _load_state()
    hist = state.get("history", [])
    print(f"Closed trades: {len(hist)}")
    if not hist:
        print("No history yet")
        return
    wins = sum(1 for h in hist if h.get("win"))
    pnls = [float(h.get("pnl_pct") or 0) for h in hist]
    print(f"Wins: {wins}/{len(hist)} ({100.0 * wins / len(hist):.1f}%)")
    print(f"Avg PnL: {sum(pnls) / len(pnls):+.2f}%  Sum: {sum(pnls):+.2f}%")


def start():
    print(f"[Bot] starting loop every {CHECK_INTERVAL_MINUTES} min (Ctrl+C to stop)")
    try:
        while True:
            run_once()
            time.sleep(CHECK_INTERVAL_MINUTES * 60)
    except KeyboardInterrupt:
        print("[Bot] stopped")


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "once"
    if cmd == "once":
        run_once()
    elif cmd == "start":
        start()
    elif cmd == "status":
        show_status()
    elif cmd == "performance":
        show_performance()
    else:
        print("Usage: python -m algo_bot.bot once|start|status|performance")
