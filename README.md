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
- BTC chart logs now include multi-lookback range position (48h/24h/7d), SMA/EMA20/50, RSI, ATR(14)+%, trend bias, volume ratio + trend + confirm + strength, near-high/low flags, ADX/regime context, dist-to-SMA20, range-bound detection, and improved caution flags for faster context.
- Bot also prints a compact market-context line (funding, session, DVOL, VIX, OI quadrant, CoinGlass liq summary + any vetoes).

## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot feeds symmetric caution vetoes:
  - LONG entries flagged on upper/near-high range + (low-volume or weak ADX or range-bound), or elevated range_pos + RSI without volume confirm (chase risk).
  - SHORT entries flagged on lower/near-low range + (low-volume or weak ADX or range-bound), or depressed range_pos + RSI without volume confirm (chase risk).
  - Additional mid-range caution in tight consolidations (range width <2.5% + ADX<25) to prefer waiting for breaks or volume expansion.
- Volume uses median (last 20 / last 5 vs prior) to reduce impact of single-bar spikes; added vol_confirm (last bar expansion) and vol_strength.
- Added EMAs, ATR%, range width, near_24h_high/low, dist_sma20_pct, range_bound flag, and optional ADX/regime (from regime.py) for richer context.
- Caution logic tightened: requires location extreme *and* weak participation or weak trend strength or range-bound conditions.

### Latest live snapshot (2026-10-19 ~04:00 IST / ~22:30 UTC)

- Last ~$81,575.0
- 48h range: $80,647.5 – $82,269.0 (pos **57.2%** — mid range, width 2.0%) [RANGE-BOUND]
- 24h pos ~57.2% / 7d pos ~40.1%
- Trend: **mixed** (SMA20=81,508 SMA50=81,513 | EMA20=81,378 | dist SMA20 +0.1%)
- RSI(14): **47.7**  ATR(14): ~338 (~0.41%)
- Vol ratio: **1.15** (rising, normal)
- Regime: **TREND**  ADX: 20.7 [COMPRESSION/RANGE]
- LONG/SHORT caution: tight range-bound mid-position — wait for break or volume expansion
- Funding: mild positive (~0.33% scaled)
- Context: tight 2% consolidation near key 50-day SMA support (~81.4k) and 20-day resistance zone (~82.6k). Neutral RSI, borderline ADX, mild positive funding. Prefer waiting for volume-confirmed break of 80.6k or 82.3k rather than mid-range entries. Decision point ahead of Fed (28 Oct).

Educational only — not financial advice.
