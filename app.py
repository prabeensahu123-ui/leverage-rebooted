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
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    ru = np.mean(up[-period:]) if len(up) >= period else 0.0
    rd = np.mean(dn[-period:]) if len(dn) >= period else 1e-9
    rs = ru / (rd if rd > 0 else 1e-9)
    return float(100 - (100 / (1 + rs)))

def tf_price_change(candles):
    if not candles or len(candles) < 2:
        return None
    a = float(candles[-2].get("close") or 0)
    b = float(candles[-1].get("close") or 0)
    if a <= 0:
        return None
    return float((b - a) / a * 100.0)

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
rsi_1h = None
if h1 and len(h1) >= 5:
    c = np.array([x["close"] for x in h1], float)
    if c[-2] > 0:
        chg1 = float((c[-1] - c[-2]) / c[-2] * 100)
    if len(c) >= 5 and c[-5] > 0:
        chg4 = float((c[-1] - c[-5]) / c[-5] * 100)
    rsi_1h = rsi_from_closes(c)

st.caption(
    "Overview — 1h: %s · ~4h: %s · 24h: %.2f · Funding: %s · RSI(1h)~: %s"
    % (
        ("%.2f" % chg1) if chg1 is not None else "—",
        ("%.2f" % chg4) if chg4 is not None else "—",
        chg24,
        ("%.4f%%" % funding_pct) if funding_pct is not None else "—",
        ("%.1f" % rsi_1h) if rsi_1h is not None else "—",
    )
)
if funding_pct is not None and funding_regime:
    reg = funding_regime(funding_pct)
    st.info("**%s** — %s" % (reg.replace("_", " "), REGIME_BIAS.get(reg, "")))

if h1 and HAS_PLOTLY and len(h1) > 10:
    st.markdown("#### 1h Chart")
    closes_arr = np.array([c["close"] for c in h1], float)
    times = [datetime.fromtimestamp(c.get("time", 0), tz=timezone.utc) for c in h1]
    fig = go.Figure(data=[go.Candlestick(
        x=times,
        open=[c.get("open", c["close"]) for c in h1],
        high=[c["high"] for c in h1],
        low=[c["low"] for c in h1],
        close=closes_arr,
        name=name,
    )])
    if len(closes_arr) >= 20:
        sma20 = np.convolve(closes_arr, np.ones(20) / 20, mode="valid")
        fig.add_trace(go.Scatter(
            x=times[-len(sma20):], y=sma20, mode="lines", name="SMA20",
            line=dict(color="yellow", width=1),
        ))
    if len(closes_arr) >= 50:
        sma50 = np.convolve(closes_arr, np.ones(50) / 50, mode="valid")
        fig.add_trace(go.Scatter(
            x=times[-len(sma50):], y=sma50, mode="lines", name="SMA50",
            line=dict(color="cyan", width=1),
        ))
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{name} 1h · last {len(h1)} bars + SMAs",
    )
    st.plotly_chart(fig, use_container_width=True)

if h1 and chart_snapshot:
    snap = chart_snapshot(h1)
    if snap:
        st.markdown("#### Chart Snapshot (1h)")
        st.code(chart_caption(snap) if chart_caption else str(snap), language=None)
        if snap.get("long_caution") or snap.get("short_caution") or snap.get("caution"):
            st.warning("Caution active — see flags above")
        if snap.get("bounce_potential"):
            st.info("Bounce potential flagged (low RSI + weak vol)")

st.markdown("---")
st.subheader("Background Paper Trading")
st.caption(
    "Model + technical filters (chart caution, regime, structure). "
    "GitHub Actions runs every 30 min. Telegram alerts if secrets are set."
)
paper = load_paper_state()
open_trades = paper.get("open_trades", [])
hist = paper.get("history", [])

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Open", len(open_trades))
with c2:
    wins = sum(1 for h in hist if h.get("win"))
    st.metric("Closed", len(hist))
with c3:
    wr = ("%.0f%%" % (100.0 * wins / len(hist))) if hist else "—"
    st.metric("Win rate", wr)

if open_trades:
    st.markdown("**Open paper trades**")
    rows = []
    for t in open_trades:
        rows.append({
            "Asset": LABELS.get(t.get("symbol", ""), t.get("symbol")),
            "TF": t.get("tf"),
            "Side": t.get("side"),
            "Entry": t.get("entry"),
            "SL": t.get("stop_loss"),
            "TP": t.get("take_profit"),
            "Style": t.get("entry_style") or "-",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.write("No open paper trades.")

if hist:
    with st.expander("Recent closed trades"):
        recent = list(reversed(hist[-10:]))
        st.dataframe(
            [{
                "Asset": LABELS.get(h.get("symbol", ""), h.get("symbol")),
                "TF": h.get("tf") or h.get("timeframe"),
                "Side": h.get("side"),
                "PnL %": h.get("pnl_pct"),
                "Reason": h.get("exit_reason"),
                "Win": h.get("win"),
            } for h in recent],
            use_container_width=True,
            hide_index=True,
        )

if st.button("Run paper check now", use_container_width=True):
    try:
        from algo_bot.bot import run_once
        run_once()
        st.session_state.paper_msg = "Paper check finished at %s IST" % now_ist().strftime("%H:%M:%S")
    except Exception as e:
        st.session_state.paper_msg = "Paper check failed: %s" % e
    st.rerun()

if st.session_state.paper_msg:
    st.info(st.session_state.paper_msg)

st.markdown("---")
st.subheader("6-Point Confluence Scorer")
st.caption(
    "From BTC Funding Matrix v2. Pick the data window (15m / 1h / 4h) — "
    "price change % and OI change % should match that same window."
)

tf_choice = st.radio(
    "Data window (price change + OI window)",
    options=list(CONF_TFS.keys()),
    index=list(CONF_TFS.keys()).index(st.session_state.conf_tf)
    if st.session_state.conf_tf in CONF_TFS else 1,
    horizontal=True,
    key="conf_tf_radio",
    help="Select 15m, 1h or 4h. Auto price change and RSI load from this timeframe.",
)
if tf_choice != st.session_state.conf_tf:
    st.session_state.conf_tf = tf_choice
    st.rerun()

conf_tf = st.session_state.conf_tf
tf_cfg = CONF_TFS[conf_tf]
tf_candles = fetch_candles(symbol, tf_cfg["resolution"], tf_cfg["days"])
auto_price_chg = tf_price_change(tf_candles)
tf_closes = [float(x["close"]) for x in tf_candles] if tf_candles else []
auto_rsi = rsi_from_closes(tf_closes) if tf_closes else rsi_1h

st.info(
    "Selected window: **%s** · Auto price change (1 bar): **%s** · RSI(%s)~: **%s**"
    % (
        tf_cfg["label"],
        ("%+.2f%%" % auto_price_chg) if auto_price_chg is not None else "—",
        conf_tf,
        ("%.1f" % auto_rsi) if auto_rsi is not None else "—",
    )
)

band_choice = st.radio(
    "Liq compare band (Rule B — same distance both sides)",
    options=[1.0, 2.0, 3.0],
    index=[1.0, 2.0, 3.0].index(st.session_state.liq_band_pct)
    if st.session_state.liq_band_pct in (1.0, 2.0, 3.0) else 1,
    format_func=lambda x: "±%.0f%%" % x,
    horizontal=True,
    key="liq_band_radio",
    help="Sum CoinGlass liquidation bars inside this %% band above and below price. Fair compare.",
)
if band_choice != st.session_state.liq_band_pct:
    st.session_state.liq_band_pct = band_choice
    st.rerun()

liq_band = float(st.session_state.liq_band_pct)
band_hi = band_lo = None
if price > 0:
    band_hi = price * (1.0 + liq_band / 100.0)
    band_lo = price * (1.0 - liq_band / 100.0)
    st.success(
        "Band guide @ $%s · **±%.0f%%** → ABOVE up to **$%s** · BELOW down to **$%s**\n\n"
        "On CoinGlass: sum all bars from current price up to the ABOVE limit, "
        "and all bars from current price down to the BELOW limit. "
        "Nearest point = first strong peak inside each side of the band."
        % (
            "{:,.0f}".format(price),
            liq_band,
            "{:,.0f}".format(band_hi),
            "{:,.0f}".format(band_lo),
        )
    )
else:
    st.warning("Price unavailable — band levels cannot be computed yet.")

with st.form("confluence_form"):
    st.markdown("##### Core inputs")
    c1, c2 = st.columns(2)
    with c1:
        f_fund = st.number_input(
            "Funding % (8h)",
            value=float(funding_pct) if funding_pct is not None else 0.0,
            step=0.001, format="%.4f",
            help="Binance-style 8h rate in percent. Mild positive ≈ +0.01 to +0.03.",
        )
        f_rsi = st.number_input(
            "RSI (14) — from selected TF",
            value=float(auto_rsi) if auto_rsi is not None else 50.0,
            step=0.1, format="%.1f",
        )
        f_share = st.number_input(
            "Long share % (24h volume)",
            value=50.0, step=1.0, format="%.1f",
            help="From CoinGlass / exchange long-short ratio.",
        )
        f_price_chg = st.number_input(
            "Price change %% (%s window)" % conf_tf,
            value=float(auto_price_chg) if auto_price_chg is not None else 0.0,
            step=0.01, format="%.2f",
            help="Auto-filled from last closed %s candle. OI must use same window." % conf_tf,
        )
    with c2:
        f_oi_chg = st.number_input(
            "OI change %% (same %s window)" % conf_tf,
            value=0.0, step=0.1, format="%.2f",
            help="OI %% change for the SAME window (%s). From CoinGlass." % conf_tf,
        )
        f_pa_long = st.checkbox("PA confirm LONG (support held / reclaim)", value=False)
        f_pa_short = st.checkbox("PA confirm SHORT (resistance rejection)", value=False)

    st.markdown("##### Liquidation map (Rule B: ±%.0f%% band)" % liq_band)
    st.caption(
        "ABOVE = short liquidations (price up). BELOW = long liquidations (price down). "
        "Enter nearest strong peak inside the band, and sum of bar amounts inside ±%.0f%%. "
        "Scoring compares the two amounts." % liq_band
    )
    if band_hi is not None:
        st.caption(
            "Price band: **$%s** ← current → **$%s**"
            % ("{:,.0f}".format(band_lo), "{:,.0f}".format(band_hi))
        )
    la, lb = st.columns(2)
    with la:
        st.markdown("**ABOVE** (short-liq fuel) · up to $%s" % (
            "{:,.0f}".format(band_hi) if band_hi else "—"
        ))
        f_liq_pt_above = st.number_input(
            "Nearest strong peak ABOVE (price)",
            value=0.0, step=1.0, format="%.1f",
            help="First clear short-liq cluster above mark, inside the ± band.",
        )
        f_liq_amt_above = st.number_input(
            "Amount in ±%.0f%% ABOVE band (USD / M)" % liq_band,
            value=0.0, step=1000.0, format="%.0f",
            help="Sum of CoinGlass bars from current price up to +%.0f%%." % liq_band,
        )
    with lb:
        st.markdown("**BELOW** (long-liq fuel) · down to $%s" % (
            "{:,.0f}".format(band_lo) if band_lo else "—"
        ))
        f_liq_pt_below = st.number_input(
            "Nearest strong peak BELOW (price)",
            value=0.0, step=1.0, format="%.1f",
            help="First clear long-liq cluster below mark, inside the ± band.",
        )
        f_liq_amt_below = st.number_input(
            "Amount in ±%.0f%% BELOW band (USD / M)" % liq_band,
            value=0.0, step=1000.0, format="%.0f",
            help="Sum of CoinGlass bars from current price down to -%.0f%%." % liq_band,
        )

    st.markdown("##### Cumulative leverage (accounts)")
    st.caption("From CoinGlass map curves / totals: aggregate leverage of longs vs shorts (not the band sum).")
    cl1, cl2 = st.columns(2)
    with cl1:
        f_cum_long_lev = st.number_input(
            "Cumulative LONG leverage (x)",
            value=0.0, step=0.1, format="%.2f",
            help="Aggregate leverage of open longs.",
        )
    with cl2:
        f_cum_short_lev = st.number_input(
            "Cumulative SHORT leverage (x)",
            value=0.0, step=0.1, format="%.2f",
            help="Aggregate leverage of open shorts.",
        )

    go = st.form_submit_button("Score confluence", use_container_width=True)

if go and run_confluence:
    share = f_share if f_share > 0 else None
    above = f_liq_amt_above if f_liq_amt_above > 0 else None
    below = f_liq_amt_below if f_liq_amt_below > 0 else None
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
    res["data_window"] = conf_tf
    res["liq_band_pct"] = liq_band
    res["band_hi"] = band_hi
    res["band_lo"] = band_lo
    res["liq_point_above"] = f_liq_pt_above if f_liq_pt_above > 0 else None
    res["liq_point_below"] = f_liq_pt_below if f_liq_pt_below > 0 else None
    res["liq_amt_above"] = above
    res["liq_amt_below"] = below
    res["cum_long_leverage"] = f_cum_long_lev if f_cum_long_lev > 0 else None
    res["cum_short_leverage"] = f_cum_short_lev if f_cum_short_lev > 0 else None
    if price > 0:
        if f_liq_pt_above > 0:
            res["dist_above_pct"] = round((f_liq_pt_above - price) / price * 100.0, 3)
        if f_liq_pt_below > 0:
            res["dist_below_pct"] = round((price - f_liq_pt_below) / price * 100.0, 3)
    st.session_state.conf_result = res

if st.session_state.conf_result:
    r = st.session_state.conf_result
    st.markdown("#### Verdict: **%s**" % r["verdict"])
    st.write(
        "Window: **%s** · Long score: **%d / 6** · Short score: **%d / 6**"
        % (r.get("data_window") or "—", r["long_score"], r["short_score"])
    )
    st.write(r["action"])
    if r["side"] == "LONG":
        st.success("Side bias: LONG (size mult %.1fx)" % r["size_mult"])
    elif r["side"] == "SHORT":
        st.error("Side bias: SHORT (size mult %.1fx)" % r["size_mult"])
    else:
        st.info("Side bias: HOLD")

    band_lbl = r.get("liq_band_pct")
    st.markdown(
        "##### Liquidation & leverage context"
        + ((" (band ±%.0f%%)" % band_lbl) if band_lbl else "")
    )
    if r.get("band_lo") and r.get("band_hi"):
        st.caption(
            "Band used: $%s – $%s"
            % ("{:,.0f}".format(r["band_lo"]), "{:,.0f}".format(r["band_hi"]))
        )
    liq_rows = [
        {
            "Side": "ABOVE (short liq)",
            "Nearest peak": r.get("liq_point_above") or "—",
            "Dist %": r.get("dist_above_pct") if r.get("dist_above_pct") is not None else "—",
            "Band amount": r.get("liq_amt_above") or "—",
        },
        {
            "Side": "BELOW (long liq)",
            "Nearest peak": r.get("liq_point_below") or "—",
            "Dist %": r.get("dist_below_pct") if r.get("dist_below_pct") is not None else "—",
            "Band amount": r.get("liq_amt_below") or "—",
        },
    ]
    st.dataframe(liq_rows, use_container_width=True, hide_index=True)
    a = r.get("liq_amt_above") or 0
    b = r.get("liq_amt_below") or 0
    if a and b:
        if a > b * 1.15:
            st.caption("Band amounts: ABOVE > BELOW → more short-liq fuel above (leans long on this point).")
        elif b > a * 1.15:
            st.caption("Band amounts: BELOW > ABOVE → more long-liq fuel below (leans short on this point).")
        else:
            st.caption("Band amounts roughly balanced — this point is neutral.")
    lev_rows = [
        {"Side": "Cumulative LONG leverage", "Value (x)": r.get("cum_long_leverage") or "—"},
        {"Side": "Cumulative SHORT leverage", "Value (x)": r.get("cum_short_leverage") or "—"},
    ]
    st.dataframe(lev_rows, use_container_width=True, hide_index=True)

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
        default_sl = 0.0
        if st.session_state.conf_result:
            cr = st.session_state.conf_result
            if cr.get("side") == "LONG" and cr.get("liq_point_below"):
                default_sl = float(cr["liq_point_below"])
            elif cr.get("side") == "SHORT" and cr.get("liq_point_above"):
                default_sl = float(cr["liq_point_above"])
        stp = st.number_input("Stop loss", value=default_sl, step=1.0)
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
        st.write(
            "Notional: **$%s** · Margin: **$%s**"
            % ("{:,.0f}".format(ps["notional"]), "{:,.0f}".format(ps["margin"]))
        )
        st.write("Approx liq distance: **%.1f%%**" % ps["liq_dist_approx_pct"])
        if ps.get("warning"):
            st.warning(ps["warning"])
        else:
            st.success("Stop is inside approx liquidation band.")

st.markdown("---")
st.caption("Educational only. Matrix thresholds are rules of thumb, not tested probabilities. Never trade on one signal.")
if st.button("Refresh data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
