"""Leverage Signal — core + Funding Confluence Matrix scorer + live chart."""
import sys, os
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import requests
import numpy as np
import time
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

st.markdown("### Leverage Signal")
st.caption("%s IST · Funding Confluence Matrix v2" % now_ist().strftime("%Y-%m-%d %H:%M:%S"))

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

@st.cache_data(ttl=120, show_spinner=False)
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

ticker = fetch_ticker(symbol)
price = float(ticker.get("close", ticker.get("mark_price", 0)) or 0)
chg24 = float(ticker.get("price_change_24h", 0) or 0) * 100
name = LABELS.get(symbol, symbol)
funding_raw = ticker.get("funding_rate")
funding_pct = None
if funding_raw is not None:
    try:
        fr = float(funding_raw)
        funding_pct = fr * 100.0 if abs(fr) < 0.05 else fr
    except Exception:
        pass

if price > 0:
    st.markdown("## %s  $%s" % (name, "{:,.2f}".format(price)))
    st.markdown("%s%.2f%% (24h)" % ("+" if chg24 >= 0 else "", chg24))
else:
    st.warning("Price unavailable")

h1 = fetch_candles(symbol, "1h", 7)
chg1 = chg4 = None
rsi_est = None
if h1 and len(h1) >= 5:
    c = np.array([x["close"] for x in h1], float)
    if c[-2] > 0:
        chg1 = float((c[-1] - c[-2]) / c[-2] * 100)
    if c[-5] > 0:
        chg4 = float((c[-1] - c[-5]) / c[-5] * 100)
    if len(c) >= 16:
        d = np.diff(c)
        up = np.where(d > 0, d, 0.0)
        dn = np.where(d < 0, -d, 0.0)
        ru = np.mean(up[-14:]) if len(up) >= 14 else 0
        rd = np.mean(dn[-14:]) if len(dn) >= 14 else 1e-9
        rs = ru / (rd if rd > 0 else 1e-9)
        rsi_est = 100 - (100 / (1 + rs))

auto_chg = chg1 if chg1 is not None else chg24
st.caption(
    "Auto — 1h: %s · 4h: %s · 24h: %.2f · Funding: %s · RSI~: %s"
    % (
        ("%.2f" % chg1) if chg1 is not None else "—",
        ("%.2f" % chg4) if chg4 is not None else "—",
        chg24,
        ("%.4f%%" % funding_pct) if funding_pct is not None else "—",
        ("%.1f" % rsi_est) if rsi_est is not None else "—",
    )
)
if funding_pct is not None and funding_regime:
    reg = funding_regime(funding_pct)
    st.info("**%s** — %s" % (reg.replace("_", " "), REGIME_BIAS.get(reg, "")))

# Live chart
if h1 and HAS_PLOTLY and len(h1) > 10:
    st.markdown("#### 1h Chart")
    fig = go.Figure(data=[go.Candlestick(
        x=[datetime.fromtimestamp(c.get("time", 0), tz=timezone.utc) for c in h1],
        open=[c.get("open", c["close"]) for c in h1],
        high=[c["high"] for c in h1],
        low=[c["low"] for c in h1],
        close=[c["close"] for c in h1],
        name=name,
    )])
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{name} 1h · last {len(h1)} bars",
    )
    st.plotly_chart(fig, use_container_width=True)

# Live chart snapshot
if h1 and chart_snapshot:
    snap = chart_snapshot(h1)
    if snap:
        st.markdown("#### Chart Snapshot (1h)")
        st.code(chart_caption(snap) if chart_caption else str(snap), language=None)
        if snap.get("long_caution") or snap.get("short_caution") or snap.get("caution"):
            st.warning("Caution active — see flags above")

st.markdown("---")
st.subheader("6-Point Confluence Scorer")
st.caption("From BTC Funding Matrix v2. Count how many conditions met — not any single signal.")

with st.form("confluence_form"):
    c1, c2 = st.columns(2)
    with c1:
        f_fund = st.number_input(
            "Funding % (8h)",
            value=float(funding_pct) if funding_pct is not None else 0.0,
            step=0.001, format="%.4f",
            help="Binance-style 8h. Extreme long squeeze risk if sustained > +0.05%",
        )
        f_rsi = st.number_input(
            "RSI (14)",
            value=float(rsi_est) if rsi_est is not None else 50.0,
            step=0.1, format="%.1f",
        )
        f_share = st.number_input(
            "Long share % (24h volume)",
            value=50.0, step=1.0, format="%.1f",
            help="From CoinGlass / exchange long-short ratio. Optional but important.",
        )
        f_price_chg = st.number_input(
            "Price change % (match OI window)",
            value=float(auto_chg) if auto_chg is not None else 0.0,
            step=0.1, format="%.2f",
        )
    with c2:
        f_oi_chg = st.number_input("OI change % (same window)", value=0.0, step=0.1, format="%.2f")
        f_above = st.number_input(
            "Liq cluster ABOVE (USD or size)",
            value=0.0, step=1000.0, format="%.0f",
            help="Short-liq pile size above price",
        )
        f_below = st.number_input(
            "Liq cluster BELOW (USD or size)",
            value=0.0, step=1000.0, format="%.0f",
            help="Long-liq pile size below price",
        )
        f_pa_long = st.checkbox("PA confirm LONG (support held / reclaim)", value=False)
        f_pa_short = st.checkbox("PA confirm SHORT (resistance rejection)", value=False)
    go = st.form_submit_button("Score confluence", use_container_width=True)

if go and run_confluence:
    share = f_share if f_share > 0 else None
    above = f_above if f_above > 0 else None
    below = f_below if f_below > 0 else None
    res = run_confluence(
        funding_pct=f_fund,
        rsi=f_rsi,
        long_share_pct=share,
        oi_chg_pct=f_oi_chg,
        price_chg_pct=f_price_chg,
        cluster_above=above,
        cluster_below=below,
        pa_long=f_pa_long,
        pa_short=f_pa_short,
    )
    st.session_state.conf_result = res

if st.session_state.conf_result:
    r = st.session_state.conf_result
    st.markdown("#### Verdict: **%s**" % r["verdict"])
    st.write("Long score: **%d / 6** · Short score: **%d / 6**" % (r["long_score"], r["short_score"]))
    st.write(r["action"])
    if r["side"] == "LONG":
        st.success("Side bias: LONG (size mult %.1fx)" % r["size_mult"])
    elif r["side"] == "SHORT":
        st.error("Side bias: SHORT (size mult %.1fx)" % r["size_mult"])
    else:
        st.info("Side bias: HOLD")
    with st.expander("Long checklist"):
        for h in r["long_hits"]:
            st.write("•", h)
    with st.expander("Short checklist"):
        for h in r["short_hits"]:
            st.write("•", h)

st.markdown("---")
st.subheader("Position size (risk rules)")
st.caption("Risk ≤1% of account. Stop BEFORE entry. Stop must sit inside liquidation.")
with st.form("size_form"):
    s1, s2 = st.columns(2)
    with s1:
        eq = st.number_input("Account equity (USD)", value=14600.0, step=100.0)
        risk = st.number_input("Risk % per trade", value=1.0, step=0.25, format="%.2f")
        lev = st.number_input("Leverage", value=10.0, step=1.0)
    with s2:
        ent = st.number_input("Entry", value=float(price) if price else 0.0, step=1.0)
        stp = st.number_input("Stop loss", value=0.0, step=1.0)
    sz_go = st.form_submit_button("Calculate size", use_container_width=True)

if sz_go and position_size:
    mult = 1.0
    if st.session_state.conf_result:
        mult = float(st.session_state.conf_result.get("size_mult") or 1.0)
    ps = position_size(eq, risk * mult, ent, stp, lev)
    if ps.get("error"):
        st.error(ps["error"])
    else:
        st.write("Risk USD: **%.2f** (after size mult)" % ps["risk_usd"])
        st.write("Stop distance: **%.3f%%**" % ps["stop_dist_pct"])
        st.write("Notional: **$%s** · Margin: **$%s**" % ("{:,.0f}".format(ps["notional"]), "{:,.0f}".format(ps["margin"])))
        st.write("Approx liq distance: **%.1f%%**" % ps["liq_dist_approx_pct"])
        if ps.get("warning"):
            st.warning(ps["warning"])
        else:
            st.success("Stop is inside approx liquidation band.")

st.markdown("---")
st.caption("Educational only. Matrix thresholds are rules of thumb, not tested probabilities. Never trade on one signal.")
if st.button("Refresh", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
