"""Leverage Signal — core + Funding Confluence Matrix + live chart + paper trading."""
import sys, os
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import requests
import numpy as np
import time
import json
from datetime import datetime, timezone, timedelta

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

st.set_page_config(page_title="Leverage Signal", layout="centered", initial_sidebar_state="collapsed")
IST = timezone(timedelta(hours=5, minutes=30))
def now_ist():
    return datetime.now(IST)

DELTA = "https://api.india.delta.exchange"
ASSETS = ["BTCUSD", "ETHUSD", "SOLUSD", "XAUTUSD", "PAXGUSD"]
LABELS = {"BTCUSD": "BTC", "ETHUSD": "ETH", "SOLUSD": "SOL", "XAUTUSD": "XAUT", "PAXGUSD": "PAXG"}
STATE_FILE = "algo_bot/state.json"
TRADE_LOG = "algo_bot/trades.csv"

CONF_TFS = {
    "15m": {"resolution": "15m", "days": 5, "label": "15 Minutes"},
    "1h": {"resolution": "1h", "days": 7, "label": "1 Hour"},
    "4h": {"resolution": "4h", "days": 30, "label": "4 Hours"},
}

try:
    from funding_confluence import run_confluence, position_size, funding_regime, REGIME_BIAS
except Exception as e:
    run_confluence = None
    position_size = None
    funding_regime = None
    REGIME_BIAS = {}
    st.error("funding_confluence load failed: %s" % e)

try:
    from chart_read import snapshot as chart_snapshot, caption as chart_caption
except Exception:
    chart_snapshot = None
    chart_caption = None

if "symbol" not in st.session_state:
    st.session_state.symbol = "BTCUSD"
if "conf_result" not in st.session_state:
    st.session_state.conf_result = None
if "paper_msg" not in st.session_state:
    st.session_state.paper_msg = ""
if "conf_tf" not in st.session_state:
    st.session_state.conf_tf = "1h"
if "liq_band_pct" not in st.session_state:
    st.session_state.liq_band_pct = 2.0

st.markdown("### Leverage Signal")
st.caption("%s IST · Funding Confluence Matrix v2 + Paper Bot" % now_ist().strftime("%Y-%m-%d %H:%M:%S"))

cols = st.columns(len(ASSETS))
for col, sym in zip(cols, ASSETS):
    with col:
        if st.button(LABELS.get(sym, sym), key="a_%s" % sym, use_container_width=True):
            st.session_state.symbol = sym
            st.rerun()

symbol = st.session_state.symbol

@st.cache_data(ttl=20, show_spinner=False)
def fetch_ticker(s):
    try:
        return requests.get("%s/v2/tickers/%s" % (DELTA, s), timeout=8).json().get("result", {})
    except Exception:
        return {}

@st.cache_data(ttl=60, show_spinner=False)
def fetch_candles(s, res, days):
    end = int(time.time())
    start = end - days * 86400
    try:
        r = requests.get(
            "%s/v2/history/candles" % DELTA,
            params={"resolution": res, "symbol": s, "start": start, "end": end},
            timeout=15,
        ).json()
        rows = r.get("result", []) if isinstance(r, dict) else r
        return list(reversed(rows)) if isinstance(rows, list) else []
    except Exception:
        return []

def load_paper_state():
    if not os.path.exists(STATE_FILE):
        return {"open_trades": [], "history": []}
    try:
        with open(STATE_FILE) as f:
            stt = json.load(f)
        ot = stt.get("open_trades", [])
        if isinstance(ot, dict):
            ot = list(ot.values()) if ot else []
        stt["open_trades"] = ot
        stt.setdefault("history", [])
        return stt
    except Exception:
        return {"open_trades": [], "history": []}

def rsi_from_closes(closes, period=14):
    if closes is None or len(closes) < period + 1:
        return None
    c = np.asarray(closes, dtype=float)
    d = np.diff(c)
    gains = np.where(d > 0, d, 0.0)
    losses = np.where(d < 0, -d, 0.0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + float(gains[i])) / period
        avg_loss = (avg_loss * (period - 1) + float(losses[i])) / period
    if avg_loss < 1e-12:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))

def tf_price_change(candles):
    if not candles or len(candles) < 2:
        return None
    a = float(candles[-2].get("close") or 0)
    b = float(candles[-1].get("close") or 0)
    if a <= 0:
        return None
    return float((b - a) / a * 100.0)

def _macd_bias(closes):
    if closes is None or len(closes) < 35:
        return "—"
    c = np.asarray(closes, dtype=float)
    def ema_s(arr, period):
        k = 2.0 / (period + 1.0)
        out = np.empty(len(arr))
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = arr[i] * k + out[i - 1] * (1 - k)
        return out
    ef = ema_s(c, 12)
    es = ema_s(c, 26)
    macd = ef - es
    sig = float(np.mean(macd[-9:]))
    return "bull" if macd[-1] > sig else "bear"

def _trend_bias(closes):
    if closes is None or len(closes) < 20:
        return "—"
    c = np.asarray(closes, dtype=float)
    px = float(c[-1])
    sma20 = float(np.mean(c[-20:]))
    sma50 = float(np.mean(c[-50:])) if len(c) >= 50 else float(np.mean(c))
    if px > sma20 > sma50:
        return "bullish"
    if px < sma20 < sma50:
        return "bearish"
    return "mixed"

def _tech_score_parts(chg, rsi, trend, macd):
    score = 0
    if chg is not None:
        if chg > 0.15: score += 1
        elif chg < -0.15: score -= 1
    if rsi is not None:
        if rsi < 35: score += 1
        elif rsi > 65: score -= 1
    if trend == "bullish": score += 1
    elif trend == "bearish": score -= 1
    if macd == "bull": score += 1
    elif macd == "bear": score -= 1
    return score

def _tech_decision(score):
    if score >= 2: return "LONG"
    if score <= -2: return "SHORT"
    return "HOLD"

def _confidence_pct(score):
    return int(28 + abs(int(score)) * 15.5)

def _color_side(side):
    if side == "LONG": return "🟢 LONG"
    if side == "SHORT": return "🔴 SHORT"
    if side == "HOLD": return "⚪ HOLD"
    return side or "—"

def _color_reconcile(rec):
    if rec == "AGREE": return "✅ AGREE"
    if rec == "CONFLICT": return "❌ CONFLICT"
    if rec == "WAIT": return "⏸️ WAIT"
    return rec or "—"

def build_tf_row(symbol, tf_key, conf_result=None):
    cfg = CONF_TFS[tf_key]
    candles = fetch_candles(symbol, cfg["resolution"], cfg["days"])
    closes = [float(x["close"] for x in candles] if candles else []
