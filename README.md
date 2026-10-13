# Leverage Rebooted

Clean rebuild of the Leverage signal / paper-trading engine.

Migrated from `prabeensahu123-ui/Leverage-`.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
python -m algo_bot.bot once
```

## Secrets (GitHub Actions / local env)

- `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID`
- `COINGLASS_API_KEY` (optional)

## Notes

- Models (`models/*.joblib`) are produced by `python -m algo_bot.train_daily` or the Daily Model Train workflow.
- Paper bot: `python -m algo_bot.bot once`
- BTC chart logs now include multi-lookback range position (48h/24h/7d), SMA20/50, RSI, ATR(14), trend bias, volume ratio + trend (median-based for robustness), and caution flags (e.g. upper/lower-range low-vol) for faster context.
- Bot also prints a compact market-context line (funding, session, DVOL, VIX, OI quadrant, CoinGlass liq summary + any vetoes).

## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot feeds symmetric caution vetoes:
  - LONG entries blocked on upper-range + low-volume or high range_pos + elevated RSI (chase risk).
  - SHORT entries blocked on lower-range + low-volume or low range_pos + depressed RSI (chase risk).
- Volume uses median (last 20 / last 5 vs prior) to reduce impact of single-bar spikes.
- Volume trend and confirmation flags added for better context.

### Latest live snapshot (2026-10-13 ~22:40 UTC / ~04:10 IST next day)

- Last ~$83,466.5
- 48h range: $80,987.5 – $84,320 (pos **74.4%** — upper range)
- 24h pos ~78.8% / 7d pos ~59.6%
- Trend: **bullish** (px > SMA20 > SMA50)
- RSI(14): **47.2** (neutral)
- ATR(14): ~378
- Vol ratio: **0.06** (very low, falling) → **LONG caution: upper-range low-vol (avoid chase)** + VOL WEAK
- Funding: mild positive (~0.003% /8h average)
- Context: consolidating near upper end of recent range after recovery from ~81k; wait for volume confirmation / pullback before chasing longs. Shorts not favoured by trend/regime either.

Educational only — not financial advice.
