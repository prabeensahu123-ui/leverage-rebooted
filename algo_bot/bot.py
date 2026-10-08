"""
algo_bot/bot.py
Paper bot — PAPER_TRADE_SYMBOLS only for new entries; manages all open.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algo_bot import config as cfg
from algo_bot.model_engine import get_signal, fetch_ticker, fetch_candles
from algo_bot.notifier import notify_trade_opened, notify_trade_closed
from algo_bot.exits import (
    closed_bar_levels,
    trial_fights_sma,
    trial_sl_near_range_high,
    trial_range_broken,
)

try:
    from algo_bot.econ_calendar import in_news_blackout, summary_lines
except Exception:
    def in_news_blackout(*a, **k):
        return False, None

    def summary_lines(*a, **k):
        return []

SYMBOLS = list(getattr(cfg, "TRADE_SYMBOLS", None) or [getattr(cfg, "SYMBOL", "BTCUSD")])
PAPER_SYMBOLS = list(getattr(cfg, "PAPER_TRADE_SYMBOLS", None) or SYMBOLS)
TIMEFRAMES = cfg.TIMEFRAMES
TRADE_LOG_FILE = cfg.TRADE_LOG_FILE
STATE_FILE = cfg.STATE_FILE
CHECK_INTERVAL_MINUTES = cfg.CHECK_INTERVAL_MINUTES
MODE = cfg.MODE
ROUND_TRIP_COST_PCT = cfg.ROUND_TRIP_COST_PCT
K_PROFIT = getattr(cfg, "K_PROFIT", 2.0)
K_STOP = getattr(cfg, "K_STOP", 2.0)
FORCE_DAILY_TRIAL = getattr(cfg, "FORCE_DAILY_TRIAL", False)
MIN_TRIAL_PROBA = getattr(cfg, "MIN_TRIAL_PROBA", 0.55)
ASSET_LABELS = getattr(cfg, "ASSET_LABELS", {})
NEWS_BLACKOUT = getattr(cfg, "NEWS_BLACKOUT", True)
NEWS_MINUTES_BEFORE = getattr(cfg, "NEWS_MINUTES_BEFORE", 90)
NEWS_MINUTES_AFTER = getattr(cfg, "NEWS_MINUTES_AFTER", 30)
CLOSE_TRIAL_AGAINST_SMA = getattr(cfg, "CLOSE_TRIAL_AGAINST_SMA", True)

IST = timezone(timedelta(hours=5, minutes=30))

TRADE_COLS = [
    "id", "symbol", "timeframe", "side", "entry", "take_profit", "stop_loss",
    "entry_time", "bars_held", "confidence", "max_holding", "mode",
    "qty_btc", "regime", "exit_price", "exit_time", "exit_reason",
    "pnl_pct", "pnl_pct_net", "win"
]

LONG_SIDES = {"LONG", "BUY"}
SHORT_SIDES = {"SHORT", "SELL"}


def is_long(side):
    return side in LONG_SIDES


def now_ist():
    return datetime.now(IST)


def today_ist():
    return now_ist().date()


def slot_key(symbol, tf_key):
    return f"{symbol}_{tf_key}"


def ensure_dirs():
    os.makedirs("algo_bot", exist_ok=True)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    else:
        state = {"open_trades": {}}
    open_trades = state.get("open_trades", {}) or {}
    migrated = {}
    for k, t in open_trades.items():
        if "_" not in str(k) and str(k) in TIMEFRAMES:
            sym = t.get("symbol") or "BTCUSD"
            nk = slot_key(sym, k)
            t = dict(t)
            t["symbol"] = sym
            t["timeframe"] = k
            migrated[nk] = t
        else:
            migrated[k] = t
    state["open_trades"] = migrated
    return state


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_trades():
    if not os.path.exists(TRADE_LOG_FILE):
        return pd.DataFrame(columns=TRADE_COLS)
    try:
        return pd.read_csv(TRADE_LOG_FILE, on_bad_lines="skip")
    except Exception as e:
        print(f"  trade log read warning: {e}")
        return pd.DataFrame(columns=TRADE_COLS)


def log_trade(trade: dict):
    row = {c: trade.get(c, "") for c in TRADE_COLS}
    df = load_trades()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(TRADE_LOG_FILE, index=False)


def parse_day(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).date()
    except Exception:
        return None


def count_used_today(symbol, tf_key, open_trades, trades_df):
    used = 0
    today = today_ist()
    sk = slot_key(symbol, tf_key)
    ot = open_trades.get(sk)
    if ot and parse_day(ot.get("entry_time")) == today:
        used += 1
    if trades_df is None or trades_df.empty or "timeframe" not in trades_df.columns:
        return used
    subset = trades_df[trades_df["timeframe"].astype(str) == str(tf_key)]
    if "symbol" in subset.columns:
        subset = subset[subset["symbol"].astype(str) == str(symbol)]
    seen = set()
    for _, row in subset.iterrows():
        day = parse_day(row.get("entry_time")) or parse_day(row.get("exit_time"))
        if day != today:
            continue
        tid = str(row.get("id", ""))
        if tid in seen:
            continue
        seen.add(tid)
        used += 1
    return used


def slot_full(symbol, tf_key, tf_cfg, open_trades, trades_df):
    cap = int(tf_cfg.get("max_trades_per_day", 1) or 1)
    used = count_used_today(symbol, tf_key, open_trades, trades_df)
    return used >= cap, used, cap


def levels_for_side(side, price, vol):
    vol = vol if vol and vol > 0 else 0.01
    price = float(price)
    if side in SHORT_SIDES:
        tp = price * (1 - K_PROFIT * vol)
        sl = price * (1 + K_STOP * vol)
    else:
        tp = price * (1 + K_PROFIT * vol)
        sl = price * (1 - K_STOP * vol)
    return tp, sl


def close_trade(trade, exit_price, reason):
    entry = float(trade["entry"])
    side = trade["side"]
    gross = (exit_price - entry) / entry * 100 if is_long(side) else (entry - exit_price) / entry * 100
    net = gross - (ROUND_TRIP_COST_PCT * 100)
    result = {
        **trade,
        "exit_price": round(exit_price, 2),
        "exit_time": datetime.now(timezone.utc).isoformat(),
        "exit_reason": reason,
        "pnl_pct": round(gross, 3),
        "pnl_pct_net": round(net, 3),
        "win": bool(net > 0),
    }
    log_trade(result)
    try:
        notify_trade_closed(result)
    except Exception:
        pass
    return result


def candle_snapshot(symbol, resolution, days=3):
    candles = fetch_candles(symbol, resolution, days)
    levels = closed_bar_levels(candles) if candles else None
    if not levels:
        t = fetch_ticker(symbol)
        px = float(t.get("close", t.get("mark_price", 0)) or 0)
        return None, px, px, px, candles or []
    ts, last, hi, lo = levels
    return ts, last, hi, lo, candles


def print_btc_chart(symbol, candles):
    if symbol != "BTCUSD" or not candles:
        return
    try:
        from chart_read import snapshot, caption
        snap = snapshot(candles)
        print(f"  chart | {caption(snap)}")
    except Exception as e:
        print(f"  chart skipped: {e}")


def manage_open(trade, cfg):
    symbol = trade.get("symbol") or "BTCUSD"
    ts, last, hi, lo, candles = candle_snapshot(symbol, cfg["resolution"])
    if last <= 0:
        return trade, False, "no price"

    prev_ts = trade.get("last_candle_ts")
    if ts is not None and prev_ts is not None and ts != prev_ts:
        trade["bars_held"] = int(trade.get("bars_held", 0)) + 1
    trade["last_candle_ts"] = ts
    bars = int(trade.get("bars_held", 0))

    side = trade["side"]
    tp = float(trade["take_profit"])
    sl = float(trade["stop_loss"])

    if CLOSE_TRIAL_AGAINST_SMA and candles:
        closes = [float(c.get("close", 0) or 0) for c in candles]
        highs = [float(c.get("high", c.get("close", 0)) or 0) for c in candles]
        wh = max(highs) if highs else None
        prior = None
        try:
            from chart_read import snapshot as chart_snap
            prior = (chart_snap(candles) or {}).get("prior_range_high")
        except Exception:
            prior = None
        if trial_fights_sma(trade, closes):
            return close_trade(trade, last, "Trial vs SMA"), True, "TRIAL-SMA"
        if trial_sl_near_range_high(trade, wh):
            return close_trade(trade, last, "Trial SL at range high"), True, "TRIAL-RANGE"
        if trial_range_broken(trade, last, prior):
            return close_trade(trade, last, "Trial range break"), True, "TRIAL-BREAK"

    if is_long(side):
        if lo <= sl:
            return close_trade(trade, sl, "Stop Loss"), True, "SL"
        if hi >= tp:
            return close_trade(trade, tp, "Take Profit"), True, "TP"
    else:
        if hi >= sl:
            return close_trade(trade, sl, "Stop Loss"), True, "SL"
        if lo <= tp:
            return close_trade(trade, tp, "Take Profit"), True, "TP"

    if bars >= cfg["max_holding_bars"]:
        return close_trade(trade, last, "Max Holding"), True, "TIME"
    return trade, False, f"open bars={bars} last={last:.1f} hi={hi:.1f} lo={lo:.1f}"


def pick_trial_side(signal):
    long_p = float(signal.get("long_proba", signal.get("buy_proba", 0)) or 0)
    short_p = float(signal.get("short_proba", signal.get("sell_proba", 0)) or 0)
    if max(long_p, short_p) < MIN_TRIAL_PROBA:
        return None, 0.0
    if short_p > long_p:
        return "SHORT", short_p
    return "LONG", long_p


def open_trade(symbol, tf_key, cfg_tf, side, price, vol, confidence, regime, note):
    tp, sl = levels_for_side(side, price, vol)
    ts, _, _, _, _ = candle_snapshot(symbol, cfg_tf["resolution"])
    return {
        "id": f"{symbol}_{tf_key}_{int(time.time())}",
        "symbol": symbol,
        "timeframe": tf_key,
        "side": side,
        "entry": round(float(price), 2),
        "take_profit": round(float(tp), 2),
        "stop_loss": round(float(sl), 2),
        "qty_btc": 0.0,
        "regime": regime or "",
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "bars_held": 0,
        "last_candle_ts": ts,
        "confidence": round(float(confidence or 0), 3),
        "max_holding": cfg_tf["max_holding_bars"],
        "mode": MODE,
        "note": note,
    }


def run_once():
    print(f"\n[{now_ist().strftime('%Y-%m-%d %H:%M:%S')} IST] Algo Bot Check | Mode: {MODE}")
    print(f"Manage symbols: {', '.join(SYMBOLS)}")
    print(f"New paper entries: {', '.join(PAPER_SYMBOLS)}")

    blocked, hit = (False, None)
    if NEWS_BLACKOUT:
        blocked, hit = in_news_blackout(
            minutes_before=NEWS_MINUTES_BEFORE,
            minutes_after=NEWS_MINUTES_AFTER,
            min_impact="High",
            currencies=("USD",),
        )
        for line in summary_lines(36)[:8]:
            print(f"  cal | {line}")
        if blocked and hit:
            when = hit["dt_ist"].strftime("%H:%M IST") if hit.get("dt_ist") else "?"
            print(f"  NEWS BLACKOUT: {hit['title']} @ {when} — manage open only")

    state = load_state()
    open_trades = state.get("open_trades", {})
    trades_df = load_trades()

    for symbol in SYMBOLS:
        label = ASSET_LABELS.get(symbol, symbol.replace("USD", ""))
        ticker = fetch_ticker(symbol)
        live_price = float(ticker.get("close", ticker.get("mark_price", 0)) or 0)
        print(f"\n=== {label} ({symbol}) ${live_price:,.2f} ===")
        allow_new = symbol in PAPER_SYMBOLS

        if symbol == "BTCUSD":
            try:
                h1 = fetch_candles(symbol, "1h", 90)
                print_btc_chart(symbol, h1)
            except Exception as e:
                print(f"  chart skipped: {e}")

        for tf_key, tf_cfg in TIMEFRAMES.items():
            sk = slot_key(symbol, tf_key)
            print(f"\n> {label} {tf_cfg['label']} ({tf_key})")
            try:
                if sk in open_trades:
                    trade, closed, note = manage_open(open_trades[sk], tf_cfg)
                    if closed:
                        print(f"  closed {note} net {trade.get('pnl_pct_net', 0):+.3f}%")
                        del open_trades[sk]
                        trades_df = load_trades()
                    else:
                        open_trades[sk] = trade
                        print(f"  {note}")
                        continue

                if not allow_new:
                    print("  skip new — not in PAPER_TRADE_SYMBOLS")
                    continue

                if blocked:
                    print("  skip new — USD news blackout")
                    continue

                if not tf_cfg.get("trade_enabled", True):
                    print("  watch only")
                    continue

                full, used, cap = slot_full(symbol, tf_key, tf_cfg, open_trades, trades_df)
                if full:
                    print(f"  daily cap {used}/{cap}")
                    continue

                signal = get_signal(symbol, tf_cfg["resolution"], tf_cfg["days"], tf_cfg["max_holding_bars"])
                if signal is None:
                    print("  no data")
                    continue

                long_p = signal.get("long_proba", signal.get("buy_proba", 0))
                short_p = signal.get("short_proba", signal.get("sell_proba", 0))
                print(
                    f"  LONG {long_p:.2f} | SHORT {short_p:.2f} | HOLD {signal['hold_proba']:.2f} | "
                    f"{signal.get('regime')} {signal.get('veto_reason') or ''} | slot {used+1}/{cap}"
                )

                side = signal.get("side")
                conf = signal.get("confidence") or 0
                price = signal.get("price") or live_price
                vol = signal.get("volatility") or 0.01

                if side and signal.get("take_profit") and signal.get("stop_loss"):
                    trade = open_trade(
                        symbol, tf_key, tf_cfg, side, price, vol, conf,
                        signal.get("regime"), "signal"
                    )
                    trade["take_profit"] = round(float(signal["take_profit"]), 2)
                    trade["stop_loss"] = round(float(signal["stop_loss"]), 2)
                    trade["qty_btc"] = round(signal.get("qty_btc", 0) or 0, 6)
                elif FORCE_DAILY_TRIAL:
                    side, conf = pick_trial_side(signal)
                    if side is None or live_price <= 0:
                        print("  trial skipped — no lean")
                        continue
                    trade = open_trade(
                        symbol, tf_key, tf_cfg, side, live_price, vol, conf,
                        signal.get("regime"), "daily-trial"
                    )
                    print("  trial fill because filters blocked a clean setup")
                else:
                    print("  no trigger")
                    continue

                open_trades[sk] = trade
                try:
                    notify_trade_opened(trade)
                except Exception:
                    pass
                print(
                    f"  NEW {trade['side']} @ {trade['entry']} "
                    f"TP {trade['take_profit']} SL {trade['stop_loss']}"
                )
            except Exception as e:
                print(f"  skip {symbol} {tf_key}: {e}")

    state["open_trades"] = open_trades
    save_state(state)
    print(f"\nOpen trades: {list(open_trades.keys())}")


def show_status():
    try:
        state = load_state()
        open_trades = state.get("open_trades", {})
        print(f"Mode {MODE} | Open {len(open_trades)}")
        for sk, t in open_trades.items():
            print(
                f"  {t.get('symbol', '?')} {t.get('timeframe', sk)} "
                f"{t.get('side')} @ {t.get('entry')} TP {t.get('take_profit')} SL {t.get('stop_loss')}"
            )
        df = load_trades()
        if not df.empty and "pnl_pct" in df.columns:
            col = "pnl_pct_net" if "pnl_pct_net" in df.columns else "pnl_pct"
            print(f"Closed {len(df)} | {col} sum {pd.to_numeric(df[col], errors='coerce').sum():+.3f}")
    except Exception as e:
        print(f"status skipped: {e}")


def show_performance():
    df = load_trades()
    if df.empty:
        print("No closed trades yet.")
        return
    print(df.tail(12).to_string(index=False))


def main():
    ensure_dirs()
    if len(sys.argv) < 2:
        print("python -m algo_bot.bot once|start|status|performance")
        return
    cmd = sys.argv[1].lower()
    if cmd == "start":
        while True:
            try:
                run_once()
                show_status()
                time.sleep(CHECK_INTERVAL_MINUTES * 60)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(60)
    elif cmd == "once":
        run_once()
        show_status()
    elif cmd == "status":
        show_status()
    elif cmd == "performance":
        show_performance()
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
