"""
algo_bot/bot.py
Paper trading runner. Commands: once | start | status | performance
"""

import json
import os
import time
from datetime import datetime, timezone

from algo_bot.config import (
    PAPER_TRADE_SYMBOLS, TIMEFRAMES, STATE_FILE, TRADE_LOG_FILE,
    CHECK_INTERVAL_MINUTES
)
from algo_bot.model_engine import get_signal
from algo_bot.notifier import notify_trade_opened, notify_status, is_configured
from algo_bot.exits import closed_bar_levels


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"open_trades": [], "history": []}


def _save_state(st):
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, indent=2)


def run_once():
    print(f"[Bot] once @ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    state = _load_state()
    signals = []
    for sym in PAPER_TRADE_SYMBOLS:
        for tf_name, tf in TIMEFRAMES.items():
            if not tf.get("trade_enabled", True):
                continue
            sig = get_signal(sym, tf["resolution"], tf["days"], tf["max_holding_bars"])
            if sig:
                signals.append((sym, tf_name, sig))
                side = sig.get("side")
                print(f"  {sym} {tf_name}: {side or 'HOLD'} "
                      f"L={sig.get('long_proba',0):.2f} S={sig.get('short_proba',0):.2f} "
                      f"px={sig.get('price',0):.1f} veto={sig.get('veto_reason') or '-'}")
                if side and not any(t.get("symbol")==sym and t.get("tf")==tf_name for t in state["open_trades"]):
                    # open paper trade
                    trade = {
                        "symbol": sym,
                        "tf": tf_name,
                        "side": side,
                        "entry": sig.get("price"),
                        "stop_loss": sig.get("stop_loss"),
                        "take_profit": sig.get("take_profit"),
                        "qty_btc": sig.get("qty_btc"),
                        "opened_at": datetime.now(timezone.utc).isoformat(),
                        "confidence": sig.get("confidence"),
                    }
                    state["open_trades"].append(trade)
                    notify_trade_opened({
                        "timeframe": tf_name,
                        "side": side,
                        "entry": trade["entry"],
                        "take_profit": trade["take_profit"],
                        "stop_loss": trade["stop_loss"],
                        "confidence": trade.get("confidence", 0),
                    })
                    print(f"    -> OPENED paper {side} @ {trade['entry']}")
    _save_state(state)
    print(f"[Bot] open trades: {len(state['open_trades'])}")
    return signals


def show_status():
    state = _load_state()
    print(f"Open trades: {len(state.get('open_trades', []))}")
    for t in state.get("open_trades", []):
        print(f"  {t.get('symbol')} {t.get('tf')} {t.get('side')} entry={t.get('entry')} SL={t.get('stop_loss')} TP={t.get('take_profit')}")
    if is_configured():
        notify_status(len(state.get("open_trades", [])))


def show_performance():
    state = _load_state()
    hist = state.get("history", [])
    print(f"Closed trades: {len(hist)}")
    # placeholder — full PnL tracking can be extended
    wins = sum(1 for h in hist if h.get("win"))
    print(f"Wins: {wins}/{len(hist)}" if hist else "No history yet")


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
