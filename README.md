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
- BTC chart logs now include multi-lookback range position (48h/24h/7d), SMA/EMA20/50, RSI, ATR(14)+%, trend bias, volume ratio + trend + confirm + strength, near-high/low flags, ADX/regime context, dist-to-SMA20, and improved caution flags for faster context.
- Bot also prints a compact market-context line (funding, session, DVOL, VIX, OI quadrant, CoinGlass liq summary + any vetoes).

## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot feeds symmetric caution vetoes:
  - LONG entries flagged on upper/near-high range + (low-volume or weak ADX), or elevated range_pos + RSI without volume confirm (chase risk).
  - SHORT entries flagged on lower/near-low range + (low-volume or weak ADX), or depressed range_pos + RSI without volume confirm (chase risk).
- Volume uses median (last 20 / last 5 vs prior) to reduce impact of single-bar spikes; added vol_confirm (last bar expansion) and vol_strength.
- Added EMAs, ATR%, range width, near_24h_high/low, dist_sma20_pct, and optional ADX/regime (from regime.py) for richer context.
- Caution logic tightened: requires location extreme *and* weak participation or weak trend strength.

### Latest live snapshot (2026-10-18 ~04:07 IST / ~22:37 UTC prev)

- Last ~$81,294.5
- 48h range: $80,767.0 – $82,900.5 (pos **24.7%** — lower range, width 2.6%)
- 24h pos ~51.8% / 7d pos ~34.0%
- Trend: **bearish** (SMA20=81,480 SMA50=81,727 | EMA20=81,460 | dist SMA20 -0.2%)
- RSI(14): **39.2**  ATR(14): ~227 (~0.28%)
- Vol ratio: **0.64** (falling, normal)
- Regime: **COMPRESSION**  ADX: 18.1
- SHORT caution: lower/near-low range + low-vol or weak ADX (avoid chase)
- Funding: mild-to-elevated positive (~0.29% if scaled)
- Context: low-volatility compression in lower half of 48h range; weak ADX, mild RSI oversold lean — prefer waiting for volume expansion or break of range extremes rather than chasing shorts. Longs not favoured without structure reclaim.

Educational only — not financial advice.
