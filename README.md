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

### Latest live snapshot (2026-10-15 ~22:40 UTC / ~04:10 IST next day)

- Last ~$82,426
- 48h range: $79,737 – $84,113.5 (pos **61.4%** — mid-upper range)
- 24h pos ~93.6% (near highs) / 7d pos ~58.7%
- Trend: **mixed** (px > SMA20 but SMA20 < SMA50; EMAs similar)
- RSI(14): **61.6** (mildly elevated)
- ATR(14): ~601 (~0.73%)
- Vol ratio: **0.34** (falling, weak) → VOL WEAK, no strong chase caution yet but near 24h high + low vol suggests wait for volume confirmation
- Funding: mild positive (~0.0044%)
- Context: consolidating after dip/recovery toward upper 24h; mixed trend + low volume — prefer pullback to SMA20 or volume-backed break of highs before chasing. Shorts not strongly favoured.

Educational only — not financial advice.
