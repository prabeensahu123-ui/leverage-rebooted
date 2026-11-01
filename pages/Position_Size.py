"""Position size auto-fill page — equity + risk → entry/SL/TP/size."""
import streamlit as st
import requests
import time
import numpy as np

st.set_page_config(page_title="Position size auto", layout="centered")
DELTA = "https://api.india.delta.exchange"

@st.cache_data(ttl=20, show_spinner=False)
def fetch_ticker(s):
    try:
        return requests.get("%s/v2/tickers/%s" % (DELTA, s), timeout=8).json().get("result", {})
    except Exception:
        return {}

@st.cache_data(ttl=60, show_spinner=False)
def fetch_candles(s, res="1h", days=7):
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

def atr_pct(candles, period=14):
    if not candles or len(candles) < period + 2:
        return None
    trs = []
    for i in range(1, len(candles)):
        h = float(candles[i].get("high") or 0)
        l = float(candles[i].get("low") or 0)
        pc = float(candles[i - 1].get("close") or 0)
        if h <= 0 or l <= 0 or pc <= 0:
            continue
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    atr = float(sum(trs[-period:]) / period)
    last = float(candles[-1].get("close") or 0)
    return (atr / last * 100.0) if last > 0 else None

st.markdown("### Position size — auto (equity + risk)")
st.caption("Capital + risk % → entry (live), SL (ATR or manual liq), TP (2R), size. Educational only.")

sym = st.selectbox("Symbol", ["BTCUSD", "ETHUSD", "SOLUSD", "XAUTUSD", "PAXGUSD"], index=0)
ticker = fetch_ticker(sym)
price = float(ticker.get("close", ticker.get("mark_price", 0)) or 0)
h1 = fetch_candles(sym)

if price > 0:
    st.metric("Live price", "$%s" % "{:,.2f}".format(price))
else:
    st.warning("Price unavailable")

c1, c2, c3 = st.columns(3)
with c1:
    equity = st.number_input("Account equity (USD)", value=2000.0, min_value=1.0, step=50.0)
with c2:
    risk_pct = st.number_input("Risk % per trade", value=1.0, min_value=0.25, max_value=5.0, step=0.25)
with c3:
    lev = st.number_input("Leverage", value=10.0, min_value=1.0, max_value=50.0, step=1.0)

s1, s2, s3 = st.columns(3)
with s1:
    side = st.selectbox("Side", ["LONG", "SHORT"])
with s2:
    rr = st.number_input("R:R (TP multiple)", value=2.0, min_value=1.0, max_value=5.0, step=0.5)
with s3:
    atr_p = atr_pct(h1)
    st.caption("ATR(1h)~%s" % (("%.2f%%" % atr_p) if atr_p else "—"))

st.markdown("##### Optional liquidation peaks (from CoinGlass)")
la, lb = st.columns(2)
with la:
    liq_below = st.number_input("Liq peak BELOW (for LONG SL)", value=0.0, step=1.0)
with lb:
    liq_above = st.number_input("Liq peak ABOVE (for SHORT SL)", value=0.0, step=1.0)

if price <= 0:
    st.stop()

if atr_p is not None:
    default_dist = min(max(1.2, 1.5 * atr_p), 4.0) / 100.0
    note = "ATR(1h)~%.2f%%" % atr_p
else:
    default_dist = 0.015
    note = "default 1.5% stop"

entry = price
sl = None
sl_src = "ATR/default"
if side == "LONG":
    if liq_below > 0 and liq_below < entry:
        cand = liq_below * 0.998
        dist = (entry - cand) / entry
        if 0.004 <= dist <= 0.08:
            sl = cand
            sl_src = "liq peak BELOW"
    if sl is None:
        sl = entry * (1.0 - default_dist)
    stop_dist = (entry - sl) / entry
    tp = entry * (1.0 + stop_dist * rr)
else:
    if liq_above > 0 and liq_above > entry:
        cand = liq_above * 1.002
        dist = (cand - entry) / entry
        if 0.004 <= dist <= 0.08:
            sl = cand
            sl_src = "liq peak ABOVE"
    if sl is None:
        sl = entry * (1.0 + default_dist)
    stop_dist = (sl - entry) / entry
    tp = entry * (1.0 - stop_dist * rr)

risk_usd = equity * (risk_pct / 100.0)
notional = risk_usd / stop_dist if stop_dist > 1e-8 else 0
margin = notional / max(lev, 1.0)
if margin > equity:
    margin = equity
    notional = margin * max(lev, 1.0)
    risk_usd = notional * stop_dist
    note += " · margin capped"

if side == "LONG":
    st.success("**LONG** · SL: %s" % sl_src)
else:
    st.error("**SHORT** · SL: %s" % sl_src)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Entry", "$%s" % "{:,.2f}".format(entry))
m2.metric("Stop loss", "$%s" % "{:,.2f}".format(sl))
m3.metric("Take profit", "$%s" % "{:,.2f}".format(tp))
m4.metric("Stop dist", "%.2f%%" % (stop_dist * 100))
n1, n2, n3 = st.columns(3)
n1.metric("Risk $", "$%.2f" % risk_usd)
n2.metric("Notional", "$%s" % "{:,.0f}".format(notional))
n3.metric("Margin @ %.0fx" % lev, "$%s" % "{:,.0f}".format(margin))
st.caption("%s · R:R 1:%.1f · Educational only — not financial advice." % (note, rr))
