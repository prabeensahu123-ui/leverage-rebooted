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
- BTC chart logs now include range position, SMA20/50, RSI, ATR(14), trend bias, volume ratio, and caution flags (e.g. upper/lower-range low-vol) for faster context.


## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot feeds symmetric caution vetoes:
  - LONG entries blocked on upper-range + low-volume or high range_pos + elevated RSI (chase risk).
  - SHORT entries blocked on lower-range + low-volume or low range_pos + depressed RSI (chase risk).
- Current snapshot (2026-10-13 ~04:00 IST): last ~$82,576, prior range $82,276–$84,320, pos 14.7%, trend bearish, RSI 35.2, volx 0.16 → lower-range low-vol caution (wait for volume). Funding mild positive (~0.004–0.008% /8h). Recent long liquidations > shorts; price near recent lows after pullback.
