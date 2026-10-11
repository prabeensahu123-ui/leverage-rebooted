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
- BTC chart logs now include range position, SMA20/50, RSI, ATR(14), trend bias, volume ratio, and caution flags (e.g. upper-range low-vol) for faster context.


## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot now feeds a caution veto: LONG entries are blocked on upper-range + low-volume or high range_pos + elevated RSI to reduce chase risk.
- Current snapshot example: bullish SMA stack, RSI ~69, range pos ~68%, volx 0.24 → very low volume caution.
