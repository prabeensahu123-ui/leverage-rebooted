"""
app.py - Leverage Signal (Streamlit)
TFs: 15m, 1h, 4h only.
Background context: CoinGlass OI + liq heatmap, RSI, funding, ADX.
"""

import sys
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import requests
import pandas as pd
import numpy as np
import time
import json
import traceback
from datetime import datetime, timezone, timedelta

st.set_page_config(
    page_title="Leverage Signal",
    layout="centered",
    initial_sidebar_state="collapsed",
)

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    return datetime.now(IST)


BOOT_ERRORS = []

try:
    from sklearn.ensemble import RandomForestClassifier
except Exception as e:
    RandomForestClassifier = None
    BOOT_ERRORS.append("sklearn: %s" % e)

try:
    from ml_features import build_features, FEATURE_NAMES, WINNING_FEATURES
except Exception as e:
    build_features = None
    FEATURE_NAMES, WINNING_FEATURES = [], []
    BOOT_ERRORS.append("ml_features: %s" % e)

try:
    from triple_barrier import triple_barrier_labels, apply_cost_filter
except Exception as e:
    triple_barrier_labels = None
    apply_cost_filter = None
    BOOT_ERRORS.append("triple_barrier: %s" % e)

try:
    from candle_patterns import detect_candle_pattern
except Exception as e:

    def detect_candle_pattern(o, h, l, c):
        return "None", "HOLD"

    BOOT_ERRORS.append("candle_patterns: %s" % e)

try:
    from signal_engine import rsi as rsi_fn
except Exception:

    def rsi_fn(prices, period=14):
        return 50.0

try:
    from features import adx as adx_fn
except Exception:

    def adx_fn(h, l, c, period=14):
        return 20.0

try:
    from algo_bot.config import (
        DELTA_BASE,
        K_PROFIT,
        K_STOP,
        MIN_BUY_PROBA,
        MIN_SELL_PROBA,
        MIN_EDGE,
        MIN_LABEL_MOVE_PCT,
        DASHBOARD_TIMEFRAMES,
        TRADE_SYMBOLS,
    )
    TIMEFRAMES = DASHBOARD_TIMEFRAMES
    ASSETS = list(TRADE_SYMBOLS)
except Exception as e:
    BOOT_ERRORS.append("config: %s" % e)
    DELTA_BASE = "https://api.india.delta.exchange"
    K_PROFIT, K_STOP = 2.0, 2.0
    MIN_BUY_PROBA = MIN_SELL_PROBA = 0.56
    MIN_EDGE = 0.15
    MIN_LABEL_MOVE_PCT = 0.0015
    TIMEFRAMES = {
        "15m": {"resolution": "15m", "days": 30, "max_holding_bars": 32, "label": "15m", "hold": "~8h"},
        "1h": {"resolution": "1h", "days": 90, "max_holding_bars": 24, "label": "1h", "hold": "~24h"},
        "4h": {"resolution": "4h", "days": 180, "max_holding_bars": 18, "label": "4h", "hold": "~3d"},
    }
    ASSETS = ["BTCUSD", "ETHUSD", "SOLUSD", "XAUTUSD", "PAXGUSD"]

try:
    from algo_bot.model_store import load_model
except Exception as e:
    BOOT_ERRORS.append("model_store: %s" % e)

    def load_model(symbol, resolution, max_age_hours=168):
        return None, None

if FEATURE_NAMES and WINNING_FEATURES:
    try:
        WINNING_FEATURE_INDICES = [FEATURE_NAMES.index(f) for f in WINNING_FEATURES]
    except Exception as e:
        WINNING_FEATURE_INDICES = []
        BOOT_ERRORS.append("feature index: %s" % e)
else:
    WINNING_FEATURE_INDICES = []

LONG_SIDES = {"LONG", "BUY"}
SHORT_SIDES = {"SHORT", "SELL"}
STATE_FILES = ["algo_bot/state.json", "paper_state.json"]
TRADE_FILES = ["algo_bot/trades.csv", "paper_trades.csv"]
ASSET_LABELS = {
    "BTCUSD": "BTC",
    "ETHUSD": "ETH",
    "SOLUSD": "SOL",
    "XAUTUSD": "XAUT",
    "PAXGUSD": "PAXG",
}

if "symbol" not in st.session_state:
    st.session_state.symbol = "BTCUSD"
if "paper_msg" not in st.session_state:
    st.session_state.paper_msg = ""

st.markdown("### Leverage Signal")
st.caption("%s IST · TF focus: 15m · 1h · 4h" % now_ist().strftime("%Y-%m-%d %H:%M:%S"))

if BOOT_ERRORS:
    st.error("Boot warnings (limited mode):")
    for err in BOOT_ERRORS:
        st.code(err)
else:
    st.caption("Modules loaded OK")


def _max_hold(cfg):
    return cfg.get("max_holding_bars", cfg.get("max_holding", 24))


def levels_for_side(side, price, vol):
    vol = vol if vol and vol > 0 else 0.01
    if side in SHORT_SIDES:
        return price * (1 - K_PROFIT * vol), price * (1 + K_STOP * vol)
    return price * (1 + K_PROFIT * vol), price * (1 - K_STOP * vol)


@st.cache_data(ttl=20, show_spinner=False)
def fetch_ticker(symbol):
    try:
        return requests.get(
            "%s/v2/tickers/%s" % (DELTA_BASE, symbol), timeout=8
        ).json().get("result", {})
    except Exception:
        return {}


@st.cache_data(ttl=120, show_spinner=False)
def fetch_candles(symbol, resolution, days):
    end = int(time.time())
    start = end - days * 86400
    try:
        r = requests.get(
            "%s/v2/history/candles" % DELTA_BASE,
            params={"resolution": resolution, "symbol": symbol, "start": start, "end": end},
            timeout=15,
        ).json()
        rows = r.get("result", []) if isinstance(r, dict) else r
        if not isinstance(rows, list):
            return []
        return list(reversed(rows))
    except Exception:
        return []


@st.cache_data(ttl=180, show_spinner=False)
def fetch_market_context(symbol, price, chg_pct):
    """OI + heatmap (CoinGlass) + funding (Delta) — runs once per refresh."""
    ctx = {}
    try:
        from market_context import build_market_context
        ctx = build_market_context(symbol) or {}
    except Exception as e:
        ctx = {"error": str(e)}
    try:
        from coinglass_client import build_coinglass_snapshot
        cg = build_coinglass_snapshot(symbol, price=float(price or 0), price_chg_pct=float(chg_pct or 0))
        ctx["cg"] = cg
        # prefer CG fields when present
        if cg.get("ok"):
            ctx["cg_ok"] = True
            ctx["cg_oi_now"] = cg.get("oi_now")
            ctx["cg_oi_chg_pct"] = cg.get("oi_chg_pct")
            ctx["cg_long_liq_usd"] = cg.get("long_liq_usd")
            ctx["cg_short_liq_usd"] = cg.get("short_liq_usd")
            ctx["cg_short_band"] = cg.get("nearest_short_band")
            ctx["cg_long_band"] = cg.get("nearest_long_band")
            ctx["oi_price_quadrant"] = cg.get("oi_price_quadrant")
            ctx["cg_error"] = cg.get("error") or ""
        else:
            ctx["cg_ok"] = False
            ctx["cg_error"] = cg.get("error") or "CoinGlass unavailable"
    except Exception as e:
        ctx["cg_ok"] = False
        ctx["cg_error"] = str(e)
    return ctx


@st.cache_data(ttl=300, show_spinner=False)
def run_balanced_model(symbol, resolution, close_t, high_t, low_t, open_t, vol_t, max_holding):
    if not build_features or not triple_barrier_labels or not RandomForestClassifier:
        return None, None, None, None
    if not WINNING_FEATURE_INDICES:
        return None, None, None, None

    close = np.array(close_t, dtype=float)
    high = np.array(high_t, dtype=float)
    low = np.array(low_t, dtype=float)
    open_ = np.array(open_t, dtype=float)
    volume = np.array(vol_t, dtype=float)
    ohlcv = {"open": open_, "high": high, "low": low, "close": close, "volume": volume}

    labels, valid, vol, exit_prices, _ = triple_barrier_labels(
        close, K_PROFIT, K_STOP, max_holding, high=high, low=low
    )
    if len(vol) and vol[-1] > 0:
        cur_vol = float(vol[-1])
    else:
        cur_vol = float(np.std(np.diff(np.log(np.clip(close[-15:], 1e-12, None)))))

    model, meta = load_model(symbol, resolution)
    if model is None:
        if apply_cost_filter:
            labels = apply_cost_filter(labels, close, exit_prices, valid, MIN_LABEL_MOVE_PCT)
        X, y = [], []
        for i in range(55, len(close) - 1, 3):
            if valid[i]:
                try:
                    X.append(build_features(ohlcv, i))
                    y.append(labels[i])
                except Exception:
                    continue
        if len(X) < 40:
            return None, None, None, None
        X = np.array(X)[:, WINNING_FEATURE_INDICES]
        y = np.array(y)
        model = RandomForestClassifier(
            n_estimators=30, max_depth=4, min_samples_leaf=12,
            class_weight="balanced", random_state=42, n_jobs=1,
        )
        model.fit(X, y)

    try:
        current_feats = np.array([build_features(ohlcv, len(close) - 1)])[:, WINNING_FEATURE_INDICES]
        proba = model.predict_proba(current_feats)[0]
        classes = list(model.classes_)
        long_proba = float(proba[classes.index(1)]) if 1 in classes else 0.0
        short_proba = float(proba[classes.index(-1)]) if -1 in classes else 0.0
        hold_proba = float(proba[classes.index(0)]) if 0 in classes else 0.0
        return long_proba, short_proba, hold_proba, cur_vol
    except Exception:
        return None, None, None, None


def decide_signal(long_p, short_p, hold_p):
    if long_p is None:
        return "N/A", 0.0
    if long_p >= MIN_BUY_PROBA and long_p > short_p + MIN_EDGE:
        return "LONG", long_p * 100
    if short_p >= MIN_SELL_PROBA and short_p > long_p + MIN_EDGE:
        return "SHORT", short_p * 100
    return "HOLD", max(long_p, short_p, hold_p or 0) * 100


def load_bot_state():
    for path in STATE_FILES:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return {"open_trades": {}}


def load_bot_trades():
    for path in TRADE_FILES:
        if os.path.exists(path):
            try:
                return pd.read_csv(path)
            except Exception:
                pass
    return pd.DataFrame()


def agree_label(model_sig, candle_sig):
    if model_sig in ("N/A", "ERR", None) or candle_sig in (None,):
        return "-"
    if model_sig == candle_sig:
        return "AGREE"
    if "HOLD" in (model_sig, candle_sig):
        return "MIXED"
    return "CONFLICT"


def make_colored_table(df):
    html = "<table style='width:100%; border-collapse: collapse; font-size: 0.82rem;'>"
    html += "<thead><tr style='background:#1e293b; color:white;'>"
    for col in df.columns:
        html += "<th style='padding:7px; text-align:center; border:1px solid #334155;'>%s</th>" % col
    html += "</tr></thead><tbody>"
    signal_cols = ["Signal", "Model", "Candle", "Side"]
    for _, row in df.iterrows():
        html += "<tr>"
        for col in df.columns:
            val = row[col]
            style = "padding:7px; text-align:center; border:1px solid #334155;"
            if col in signal_cols:
                if val in LONG_SIDES:
                    style += "background-color:#16a34a; color:white; font-weight:bold;"
                elif val in SHORT_SIDES:
                    style += "background-color:#dc2626; color:white; font-weight:bold;"
                elif val == "HOLD":
                    style += "background-color:#ea580c; color:white; font-weight:bold;"
            html += "<td style='%s'>%s</td>" % (style, val)
        html += "</tr>"
    html += "</tbody></table>"
    return html


cols = st.columns(len(ASSETS))
for col, sym in zip(cols, ASSETS):
    with col:
        if st.button(
            ASSET_LABELS.get(sym, sym.replace("USD", "")),
            key="a_%s" % sym,
            use_container_width=True,
        ):
            st.session_state.symbol = sym
            st.rerun()

symbol = st.session_state.symbol
ticker = fetch_ticker(symbol)
live_price = float(ticker.get("close", ticker.get("mark_price", 0)) or 0)
chg = float(ticker.get("price_change_24h", 0.0) or 0.0) * 100
name = ASSET_LABELS.get(symbol, symbol.replace("USD", ""))

if live_price <= 0:
    st.warning("Live price unavailable from Delta API right now.")
else:
    st.markdown("## %s  $%s" % (name, "{:,.2f}".format(live_price)))
    st.markdown("%s%.2f%% (24h)" % ("+" if chg >= 0 else "", chg))

# ---- Market context (OI, heatmap, RSI, funding) — background layer ----
ctx = fetch_market_context(symbol, live_price, chg)
h1_candles = fetch_candles(symbol, "1h", 14)
rsi_val = None
adx_val = None
if h1_candles and len(h1_candles) >= 20:
    closes = np.array([c["close"] for c in h1_candles], dtype=float)
    highs = np.array([c["high"] for c in h1_candles], dtype=float)
    lows = np.array([c["low"] for c in h1_candles], dtype=float)
    try:
        rsi_val = float(rsi_fn(closes, 14))
    except Exception:
        rsi_val = None
    try:
        adx_val = float(adx_fn(highs, lows, closes, 14))
    except Exception:
        adx_val = None

st.markdown("---")
st.subheader("Market context")
st.caption("Open interest · liquidation heatmap (CoinGlass) · RSI · funding · ADX")

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("RSI (1h)", "%.1f" % rsi_val if rsi_val is not None else "—")
with m2:
    st.metric("ADX (1h)", "%.1f" % adx_val if adx_val is not None else "—")
with m3:
    fp = ctx.get("funding_pct")
    st.metric("Funding %", "%.4f" % fp if fp is not None else "—")
with m4:
    st.metric("Session", ctx.get("session") or "—")

cg_ok = ctx.get("cg_ok")
oi_now = ctx.get("cg_oi_now") or ctx.get("oi_usd")
oi_chg = ctx.get("cg_oi_chg_pct")
quad = ctx.get("oi_price_quadrant") or "UNKNOWN"

m5, m6, m7 = st.columns(3)
with m5:
    if oi_now is not None:
        st.metric("Open Interest", "{:,.0f}".format(float(oi_now)))
    else:
        st.metric("Open Interest", "—")
with m6:
    st.metric("OI change %", "%.2f" % oi_chg if oi_chg is not None else "—")
with m7:
    st.metric("OI × Price", quad.replace("_", " "))

# Heatmap bands
short_band = ctx.get("cg_short_band")
long_band = ctx.get("cg_long_band")
long_liq = ctx.get("cg_long_liq_usd") or 0
short_liq = ctx.get("cg_short_liq_usd") or 0

ha, hb = st.columns(2)
with ha:
    st.write("**Liq heatmap (above = short fuel)**")
    if short_band:
        st.write("Nearest short-liq band: **$%s**" % "{:,.0f}".format(float(short_band)))
    else:
        st.write("Short band: —")
    st.write("Recent short liq USD: **%s**" % ("{:,.0f}".format(float(short_liq)) if short_liq else "—"))
with hb:
    st.write("**Liq heatmap (below = long fuel)**")
    if long_band:
        st.write("Nearest long-liq band: **$%s**" % "{:,.0f}".format(float(long_band)))
    else:
        st.write("Long band: —")
    st.write("Recent long liq USD: **%s**" % ("{:,.0f}".format(float(long_liq)) if long_liq else "—"))

if not cg_ok:
    st.info(
        "CoinGlass: %s — add secret **COINGLASS_API_KEY** in Streamlit Cloud "
        "(App settings → Secrets) for live OI + heatmap."
        % (ctx.get("cg_error") or "not connected")
    )

# RSI quick read
if rsi_val is not None:
    if rsi_val >= 70:
        st.caption("RSI elevated (≥70) — exhaustion risk for longs")
    elif rsi_val <= 30:
        st.caption("RSI washed (≤30) — bounce risk for shorts")

# ---- Model loop (15m / 1h / 4h only) ----
model_rows, candle_rows, compare_rows = [], [], []
progress = st.progress(0)
status = st.empty()

for i, (tf_key, cfg) in enumerate(TIMEFRAMES.items()):
    status.caption("Analyzing %s..." % cfg["label"])
    candles = fetch_candles(symbol, cfg["resolution"], cfg["days"])
    if not candles or len(candles) < 70:
        model_rows.append({
            "Timeframe": cfg["label"], "Signal": "N/A", "Confidence": "-",
            "LONG %": "-", "SHORT %": "-", "Entry": "-",
            "Take Profit": "-", "Stop Loss": "-", "Hold": cfg.get("hold", "-"),
        })
        candle_rows.append({"Timeframe": cfg["label"], "Pattern": "-", "Candle": "N/A"})
        compare_rows.append({"Timeframe": cfg["label"], "Model": "N/A", "Candle": "N/A", "Agree": "-"})
        progress.progress((i + 1) / max(len(TIMEFRAMES), 1))
        continue

    close = np.array([c["close"] for c in candles], dtype=float)
    high = np.array([c["high"] for c in candles], dtype=float)
    low = np.array([c["low"] for c in candles], dtype=float)
    volume = np.array([c["volume"] for c in candles], dtype=float)
    open_ = np.array([c.get("open", c["close"]) for c in candles], dtype=float)

    try:
        long_p, short_p, hold_p, cur_vol = run_balanced_model(
            symbol, cfg["resolution"],
            tuple(close), tuple(high), tuple(low), tuple(open_), tuple(volume),
            _max_hold(cfg),
        )
        signal, conf = decide_signal(long_p, short_p, hold_p)
        pattern, candle_bias = detect_candle_pattern(open_, high, low, close)
    except Exception as e:
        model_rows.append({
            "Timeframe": cfg["label"], "Signal": "ERR", "Confidence": "-",
            "LONG %": "-", "SHORT %": "-", "Entry": "-",
            "Take Profit": "-", "Stop Loss": "-", "Hold": cfg.get("hold", "-"),
        })
        candle_rows.append({"Timeframe": cfg["label"], "Pattern": str(e)[:32], "Candle": "N/A"})
        compare_rows.append({"Timeframe": cfg["label"], "Model": "ERR", "Candle": "N/A", "Agree": "-"})
        progress.progress((i + 1) / max(len(TIMEFRAMES), 1))
        continue

    if signal in LONG_SIDES or signal in SHORT_SIDES:
        if live_price > 0 and cur_vol is not None:
            tp, sl = levels_for_side(signal, live_price, cur_vol)
            tp_txt = "$%s" % "{:,.0f}".format(tp)
            sl_txt = "$%s" % "{:,.0f}".format(sl)
        else:
            tp_txt, sl_txt = "-", "-"
        entry_txt = "$%s" % "{:,.0f}".format(live_price) if live_price > 0 else "-"
    else:
        tp_txt, sl_txt, entry_txt = "-", "-", "-"

    model_rows.append({
        "Timeframe": cfg["label"],
        "Signal": signal,
        "Confidence": "%.0f" % conf if long_p is not None else "-",
        "LONG %": "%.0f" % (long_p * 100) if long_p is not None else "-",
        "SHORT %": "%.0f" % (short_p * 100) if short_p is not None else "-",
        "Entry": entry_txt,
        "Take Profit": tp_txt,
        "Stop Loss": sl_txt,
        "Hold": cfg.get("hold", "-"),
    })
    candle_rows.append({"Timeframe": cfg["label"], "Pattern": pattern, "Candle": candle_bias})
    compare_rows.append({
        "Timeframe": cfg["label"],
        "Model": signal,
        "Candle": candle_bias,
        "Agree": agree_label(signal, candle_bias),
    })
    progress.progress((i + 1) / max(len(TIMEFRAMES), 1))

status.empty()
progress.empty()

st.markdown("---")
st.subheader("1) Model Predictions")
st.caption("Only 15m · 1h · 4h. TP/SL only on LONG or SHORT.")
st.markdown(make_colored_table(pd.DataFrame(model_rows)), unsafe_allow_html=True)

st.markdown("---")
st.subheader("2) Candlestick Patterns")
st.markdown(make_colored_table(pd.DataFrame(candle_rows)), unsafe_allow_html=True)

st.markdown("---")
st.subheader("3) Agreement")
st.markdown(make_colored_table(pd.DataFrame(compare_rows)), unsafe_allow_html=True)

st.markdown("---")
st.subheader("Paper Trading")

if st.button("Run Paper Check Now", use_container_width=True):
    try:
        from algo_bot.bot import run_once
        run_once()
        st.session_state.paper_msg = "Paper check finished at %s IST" % now_ist().strftime("%H:%M:%S")
    except Exception as e:
        st.session_state.paper_msg = "Paper check failed: %s" % e
        st.session_state.paper_msg += "\n" + traceback.format_exc()[-500:]
    st.rerun()

if st.session_state.paper_msg:
    st.info(st.session_state.paper_msg)

state = load_bot_state()
open_trades = state.get("open_trades", {})
trades_df = load_bot_trades()

st.markdown("#### Open paper trades")
if open_trades:
    rows = []
    for sk, t in open_trades.items():
        rows.append({
            "Asset": ASSET_LABELS.get(t.get("symbol", ""), t.get("symbol", sk)),
            "TF": t.get("timeframe", sk),
            "Side": t.get("side", "-"),
            "Entry": t.get("entry"),
            "TP": t.get("take_profit"),
            "SL": t.get("stop_loss"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.write("No open paper trades.")

st.markdown("#### Closed trades")
if trades_df is not None and not trades_df.empty:
    st.metric("Closed", len(trades_df))
    if "win" in trades_df.columns:
        st.metric("Win Rate", "%.1f%%" % (trades_df["win"].mean() * 100))
else:
    st.write("No closed paper trades yet.")

if st.button("Refresh signals now", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
