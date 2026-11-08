"""Forecast + Data Bank page — Delta/CCXT → CSV bank → ensemble forecast."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import streamlit as st

st.set_page_config(page_title="Forecast · Data Bank", layout="wide")
st.title("Forecast & Data Bank")
st.caption(
    "OHLCV bank: Delta India primary, CCXT fallback (Binance) when installed. "
    "Forecast = Damped Holt + log-trend ensemble (spec v1.2). Educational only."
)

try:
    from data_bank.feed import fetch_ohlcv_unified, refresh_symbol
    from data_bank.store import list_bank_files
    from forecasting import ensemble_forecast
except Exception as e:
    st.error(f"Import failed: {e}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
with c1:
    symbol = st.selectbox("Symbol", ["BTCUSD", "ETHUSD", "SOLUSD"], index=0)
with c2:
    resolution = st.selectbox("TF", ["15m", "1h", "4h"], index=1)
with c3:
    days = st.number_input("Days", min_value=7, max_value=180, value=60)
with c4:
    source = st.selectbox("Source", ["auto", "delta", "ccxt", "csv"], index=0)

if st.button("Refresh data bank", use_container_width=True):
    try:
        meta = refresh_symbol(symbol, resolution, int(days))
        st.success(f"Refreshed {meta['n']} bars · last close {meta['last_close']}")
    except Exception as e:
        st.error(str(e))

files = list_bank_files()
st.write("**Bank files:**", ", ".join(files) if files else "_(empty — hit Refresh)_")

try:
    candles = fetch_ohlcv_unified(symbol, resolution, int(days), source=source, use_cache=True)
except Exception as e:
    st.error(str(e))
    st.stop()

if not candles:
    st.warning("No candles")
    st.stop()

closes = np.asarray([c["close"] for c in candles], dtype=float)
last = float(closes[-1])
st.metric("Last close", f"${last:,.2f}")
st.caption(f"Bars: {len(candles)} · last ts {datetime.fromtimestamp(candles[-1]['time'], tz=timezone.utc)}")

steps = st.slider("Forecast horizon (bars)", 1, 12, 3)
fc = ensemble_forecast(closes, steps=steps)

bias = fc["bias"]
color = {"LONG": "green", "SHORT": "red", "HOLD": "gray"}.get(bias, "gray")
st.markdown(
    f"**Ensemble bias:** :{color}[{bias}] · point **${fc['point_forecast']:,.2f}** ({fc['chg_pct']:+.2f}%)"
)

rows = []
for i in range(steps):
    rows.append(
        {
            "Step": i + 1,
            "Forecast": round(float(fc["forecast"][i]), 2),
            "Lower": round(float(fc["lower_band"][i]), 2),
            "Upper": round(float(fc["upper_band"][i]), 2),
            "Holt": round(float(fc["holt_only"][i]), 2),
            "Trend": round(float(fc["trend_only"][i]), 2),
        }
    )
st.dataframe(rows, use_container_width=True, hide_index=True)

st.info(
    "Bands = empirical residual σ (Holt) ± disagreement spread. "
    "Not a trade signal by itself — combine with confluence / structure / risk rules."
)

try:
    import pandas as pd
    from pathlib import Path

    tpath = Path("algo_bot/trades.csv")
    if tpath.exists():
        df = pd.read_csv(tpath)
        st.subheader("Paper trade log (data bank)")
        st.dataframe(df.tail(20), use_container_width=True, hide_index=True)
        if len(df):
            wins = int(df["win"].astype(str).str.lower().isin(["true", "1"]).sum())
            st.caption(f"Closed rows: {len(df)} · wins marked: {wins}")
except Exception:
    pass
