"""Leverage Signal — home. Use sidebar → Position Size for auto equity/risk sizing."""
import streamlit as st

st.set_page_config(page_title="Leverage Signal", layout="centered", initial_sidebar_state="expanded")

st.markdown("### Leverage Signal")
st.caption("Educational only — not financial advice.")
st.info(
    "**Position size auto-fill** is on the **Position Size** page (sidebar).\n\n"
    "Enter account equity + risk % → system fills entry (live), SL (ATR / optional liq), TP (2R), notional & margin."
)
st.markdown(
    """
#### How to use
1. Open **Position Size** from the left sidebar  
2. Set **equity** and **risk %** (default 1%)  
3. Pick side LONG/SHORT  
4. Optional: paste CoinGlass liq peaks for tighter SL  
5. Read Entry / SL / TP / Notional / Margin

Main confluence + paper bot UI is being restored to this home page in a follow-up.
"""
)
st.success("Go to **Position Size** in the sidebar to calculate size from capital + risk.")
