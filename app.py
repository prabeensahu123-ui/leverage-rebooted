"""
app.py - Leverage Signal (Streamlit)
TFs: 15m, 1h, 4h only.
Manual Market Calculator for OI / liq heatmap (user types values from CoinGlass website).
Auto: RSI, ADX, funding from price APIs.
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
if "manual_ctx_result" not in st.session_state:
    st.session_state.manual_ctx_result = None

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


def oi_price_quadrant(price_chg_pct, oi_chg_pct):
    if oi_chg_pct is None:
        return "UNKNOWN"
    up_p = price_chg_pct >= 0
    up_o = oi_chg_pct >= 0
    if up_p and up_o:
        return "BULL_CONTINUATION"
    if up_p and not up_o:
        return "BULL_FLUSH"
    if not up_p and up_o:
        return "BEAR_CONTINUATION"
    return "BEAR_FLUSH"


def run_manual_calculator(
    price,
    price_chg_pct,
    oi_now,
    oi_chg_pct,
    long_liq_usd,
    short_liq_usd,
    short_band,
    long_band,
    funding_pct,
    rsi_val,
    adx_val,
):
    """Calculator: numbers in → conclusion table out."""
    quad = oi_price_quadrant(price_chg_pct, oi_chg_pct)

    # Heatmap bias
    heat_note = []
    heat_bias = "NEUTRAL"
    if short_band and price > 0:
        dist_up = (short_band - price) / price * 100.0
        heat_note.append("Short-liq band $%.0f is %.2f%% above price (squeeze fuel up)" % (short_band, dist_up))
        if dist_up <= 1.5:
            heat_bias = "LONG_SQUEEZE_NEAR"
    if long_band and price > 0:
        dist_dn = (price - long_band) / price * 100.0
        heat_note.append("Long-liq band $%.0f is %.2f%% below price (flush fuel down)" % (long_band, dist_dn))
        if dist_dn <= 1.5 and heat_bias == "NEUTRAL":
            heat_bias = "SHORT_FLUSH_NEAR"
        elif dist_dn <= 1.5 and heat_bias == "LONG_SQUEEZE_NEAR":
            heat_bias = "BOTH_NEAR"

    # Liq flow
    liq_bias = "NEUTRAL"
    if long_liq_usd or short_liq_usd:
        if long_liq_usd > short_liq_usd * 1.5:
            liq_bias = "LONGS_FLUSHED"  # longs already liquidated → often bounce risk
        elif short_liq_usd > long_liq_usd * 1.5:
            liq_bias = "SHORTS_FLUSHED"  # shorts liquidated → often dip risk

    # Funding
    fund_bias = "NEUTRAL"
    if funding_pct is not None:
        if funding_pct >= 0.03:
            fund_bias = "CROWDED_LONG"
        elif funding_pct <= -0.03:
            fund_bias = "CROWDED_SHORT"

    # RSI
    rsi_bias = "NEUTRAL"
    if rsi_val is not None:
        if rsi_val >= 70:
            rsi_bias = "OVERBOUGHT"
        elif rsi_val <= 30:
            rsi_bias = "OVERSOLD"

    # Combined score for LONG vs SHORT
    long_score = 0
    short_score = 0
    reasons_long = []
    reasons_short = []

    if quad == "BULL_CONTINUATION":
        long_score += 2
        reasons_long.append("OI up + price up (new longs)")
    elif quad == "BEAR_CONTINUATION":
        short_score += 2
        reasons_short.append("OI up + price down (new shorts)")
    elif quad == "BULL_FLUSH":
        short_score += 1
        reasons_short.append("Price up but OI down (short cover / weak rally)")
    elif quad == "BEAR_FLUSH":
        long_score += 1
        reasons_long.append("Price down but OI down (long flush / weak dump)")

    if heat_bias == "LONG_SQUEEZE_NEAR":
        long_score += 2
        reasons_long.append("Short-liq cluster nearby above")
    if heat_bias == "SHORT_FLUSH_NEAR":
        short_score += 2
        reasons_short.append("Long-liq cluster nearby below")

    if liq_bias == "LONGS_FLUSHED":
        long_score += 1
        reasons_long.append("Recent long liquidations dominant")
    if liq_bias == "SHORTS_FLUSHED":
        short_score += 1
        reasons_short.append("Recent short liquidations dominant")

    if fund_bias == "CROWDED_LONG":
        short_score += 1
        reasons_short.append("Funding crowded long")
    if fund_bias == "CROWDED_SHORT":
        long_score += 1
        reasons_long.append("Funding crowded short")

    if rsi_bias == "OVERSOLD":
        long_score += 1
        reasons_long.append("RSI oversold")
    if rsi_bias == "OVERBOUGHT":
        short_score += 1
        reasons_short.append("RSI overbought")

    if adx_val is not None and adx_val >= 25:
        if long_score > short_score:
            long_score += 1
            reasons_long.append("ADX strong trend (≥25)")
        elif short_score > long_score:
            short_score += 1
            reasons_short.append("ADX strong trend (≥25)")

    if long_score > short_score + 1:
        bias = "LONG"
        conf = min(95, 50 + long_score * 8)
    elif short_score > long_score + 1:
        bias = "SHORT"
        conf = min(95, 50 + short_score * 8)
    else:
        bias = "HOLD"
        conf = 40 + max(long_score, short_score) * 5

    summary_rows = [
        {"Field": "Price", "Value": "$%s" % "{:,.0f}".format(price) if price else "—"},
        {"Field": "Price change %", "Value": "%.2f" % price_chg_pct},
        {"Field": "Open Interest", "Value": "{:,.0f}".format(oi_now) if oi_now else "—"},
        {"Field": "OI change %", "Value": "%.2f" % oi_chg_pct if oi_chg_pct is not None else "—"},
        {"Field": "OI × Price quadrant", "Value": quad.replace("_", " ")},
        {"Field": "Long liq USD", "Value": "{:,.0f}".format(long_liq_usd) if long_liq_usd else "—"},
        {"Field": "Short liq USD", "Value": "{:,.0f}".format(short_liq_usd) if short_liq_usd else "—"},
        {"Field": "Short-liq band (above)", "Value": "$%s" % "{:,.0f}".format(short_band) if short_band else "—"},
        {"Field": "Long-liq band (below)", "Value": "$%s" % "{:,.0f}".format(long_band) if long_band else "—"},
        {"Field": "Funding %", "Value": "%.4f" % funding_pct if funding_pct is not None else "—"},
        {"Field": "RSI (1h)", "Value": "%.1f" % rsi_val if rsi_val is not None else "—"},
        {"Field": "ADX (1h)", "Value": "%.1f" % adx_val if adx_val is not None else "—"},
        {"Field": "Heatmap note", "Value": "; ".join(heat_note) if heat_note else "—"},
        {"Field": "Context bias", "Value": bias},
        {"Field": "Context confidence", "Value": "%d" % conf},
        {"Field": "Why LONG", "Value": "; ".join(reasons_long) if reasons_long else "—"},
        {"Field": "Why SHORT", "Value": "; ".join(reasons_short) if reasons_short else "—"},
    ]
    return {
        "bias": bias,
        "confidence": conf,
        "quadrant": quad,
        "summary": summary_rows,
        "long_score": long_score,
        "short_score": short_score,
    }


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
def fetch_funding_session(symbol):
    out = {"funding_pct": None, "session": "—"}
    try:
        from market_context import build_market_context
        ctx = build_market_context(symbol) or {}
        out["funding_pct"] = ctx.get("funding_pct")
        out["session"] = ctx.get("session") or "—"
    except Exception:
        try:
            t = requests.get("%s/v2/tickers/%s" % (DELTA_BASE, symbol), timeout=5).json().get("result", {})
            fr = float(t.get("funding_rate") or 0)
            out["funding_pct"] = fr * 100.0 if abs(fr) < 0.05 else fr
        except Exception:
            pass
        h = datetime.now(timezone.utc).hour
        out["session"] = "ASIA" if h < 7 or h >= 21 else ("LONDON" if h < 13 else "US")
    return out


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
    signal_cols = ["Signal", "Model", "Candle", "Side", "Context bias"]
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

# Auto RSI / ADX / funding
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

fund_sess = fetch_funding_session(symbol)
auto_funding = fund_sess.get("funding_pct")

st.markdown("---")
st.subheader("Market context (auto)")
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("RSI (1h)", "%.1f" % rsi_val if rsi_val is not None else "—")
with m2:
    st.metric("ADX (1h)", "%.1f" % adx_val if adx_val is not None else "—")
with m3:
    st.metric("Funding %", "%.4f" % auto_funding if auto_funding is not None else "—")
with m4:
    st.metric("Session", fund_sess.get("session") or "—")

# ========== MANUAL CALCULATOR (like a calculator) ==========
st.markdown("---")
st.subheader("Manual OI / Liquidation calculator")
st.caption(
    "Open CoinGlass in another tab → copy numbers → type here → press **Calculate**. "
    "No paid API needed."
)

with st.form("manual_ctx_form", clear_on_submit=False):
    st.write("**From CoinGlass / chart (editable)**")
    c1, c2 = st.columns(2)
    with c1:
        in_price = st.number_input(
            "Price (USD)",
            min_value=0.0,
            value=float(live_price) if live_price > 0 else 0.0,
            step=1.0,
            format="%.2f",
        )
        in_price_chg = st.number_input(
            "Price change % (e.g. 24h)",
            value=float(chg),
            step=0.1,
            format="%.2f",
        )
        in_oi = st.number_input(
            "Open Interest (contracts or USD — your choice)",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.0f",
        )
        in_oi_chg = st.number_input(
            "OI change %",
            value=0.0,
            step=0.1,
            format="%.2f",
            help="Positive = OI rising, negative = OI falling",
        )
    with c2:
        in_long_liq = st.number_input(
            "Recent long liquidation USD",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.0f",
        )
        in_short_liq = st.number_input(
            "Recent short liquidation USD",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.0f",
        )
        in_short_band = st.number_input(
            "Nearest short-liq band (price ABOVE)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            format="%.0f",
            help="Yellow cluster above current price on heatmap",
        )
        in_long_band = st.number_input(
            "Nearest long-liq band (price BELOW)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            format="%.0f",
            help="Yellow cluster below current price on heatmap",
        )

    st.write("**Optional overrides (leave as auto if unsure)**")
    o1, o2 = st.columns(2)
    with o1:
        in_funding = st.number_input(
            "Funding %",
            value=float(auto_funding) if auto_funding is not None else 0.0,
            step=0.001,
            format="%.4f",
        )
        in_rsi = st.number_input(
            "RSI",
            min_value=0.0,
            max_value=100.0,
            value=float(rsi_val) if rsi_val is not None else 50.0,
            step=0.5,
            format="%.1f",
        )
    with o2:
        in_adx = st.number_input(
            "ADX",
            min_value=0.0,
            value=float(adx_val) if adx_val is not None else 20.0,
            step=0.5,
            format="%.1f",
        )

    submitted = st.form_submit_button("Calculate context bias", use_container_width=True)

if submitted:
    st.session_state.manual_ctx_result = run_manual_calculator(
        price=in_price,
        price_chg_pct=in_price_chg,
        oi_now=in_oi if in_oi > 0 else None,
        oi_chg_pct=in_oi_chg,
        long_liq_usd=in_long_liq,
        short_liq_usd=in_short_liq,
        short_band=in_short_band if in_short_band > 0 else None,
        long_band=in_long_band if in_long_band > 0 else None,
        funding_pct=in_funding,
        rsi_val=in_rsi,
        adx_val=in_adx,
    )

result = st.session_state.manual_ctx_result
if result:
    st.markdown("#### Calculator result")
    bcol1, bcol2, bcol3 = st.columns(3)
    with bcol1:
        st.metric("Context bias", result["bias"])
    with bcol2:
        st.metric("Confidence", "%d" % result["confidence"])
    with bcol3:
        st.metric("OI × Price", result["quadrant"].replace("_", " "))

    st.dataframe(
        pd.DataFrame(result["summary"]),
        use_container_width=True,
        hide_index=True,
    )

    if result["bias"] == "LONG":
        st.success("Manual context leans **LONG**. Compare with model table below.")
    elif result["bias"] == "SHORT":
        st.error("Manual context leans **SHORT**. Compare with model table below.")
    else:
        st.warning("Manual context is **HOLD** (mixed scores). Prefer model + candle AGREE only.")
else:
    st.info("Fill the numbers from CoinGlass and press **Calculate context bias**.")

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
