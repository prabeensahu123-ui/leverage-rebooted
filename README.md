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
- BTC chart logs now include multi-lookback range position (48h/24h/7d), SMA20/50, RSI, ATR(14), trend bias, volume ratio + trend, and caution flags (e.g. upper/lower-range low-vol) for faster context.

## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot feeds symmetric caution vetoes:
  - LONG entries blocked on upper-range + low-volume or high range_pos + elevated RSI (chase risk).
  - SHORT entries blocked on lower-range + low-volume or low range_pos + depressed RSI (chase risk).
- Volume trend and confirmation flags added for better context.

### Latest snapshot (2026-10-14 ~04:00 IST)

- Last ~$83,473
- 48h range: $80,988 – $84,320 (pos **74.6%** — upper range)
- Trend: **bullish** (px > SMA20 > SMA50)
- RSI(14): **47.4** (neutral)
- ATR(14): ~378
- Vol ratio: **0.06** (very low) → **LONG caution: upper-range low-vol (avoid chase)**
- Funding: mild positive (~0.003–0.007% /8h)
- Context: consolidating near upper end of recent range after recovery from ~81k; wait for volume confirmation before chasing longs.

Educational only — not financial advice.
