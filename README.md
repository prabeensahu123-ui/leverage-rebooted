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
- BTC chart logs now include multi-lookback range position (48h/24h/7d), SMA/EMA20/50, RSI, ATR(14)+%, trend bias, volume ratio + trend + confirm + strength, near-high/low flags, near-support/resistance proximity, ADX/regime context, dist-to-SMA20, range-bound detection (now ATR-adaptive), breakout_watch, actionable bias, and improved caution flags for faster context.
- Bot also prints a compact market-context line (funding, session, DVOL, VIX, OI quadrant, CoinGlass liq summary + any vetoes).

## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot feeds symmetric caution vetoes:
  - LONG entries flagged on upper/near-high range + (low-volume or weak ADX or range-bound), or elevated range_pos + RSI + weak volume (chase / crowded long risk).
  - SHORT entries flagged on lower/near-low range / near-support + (low-volume or weak ADX or range-bound), or depressed range_pos + RSI without volume confirm (chase risk).
  - Additional mid-range caution in tight consolidations (ATR-adaptive range width + ADX<26) to prefer waiting for breaks or volume expansion.
  - Enhanced bounce awareness on weak-volume lower ranges / near 48h support (mean-reversion / liq magnet risk).
  - Breakout watch when near range edge + meaningful volume participation (ratio >=0.65 or confirm) + ADX support (stricter to avoid false watches in quiet ranges).
- Volume uses median (last 15 / last 3 vs prior) for better recent sensitivity; added vol_confirm (last bar expansion) and vol_strength.
- Added EMAs, ATR%, range width, near_24h_high/low, near_support/resistance, dist_sma20_pct, range_bound flag, breakout_watch, bias recommendation, and optional ADX/regime (from regime.py) for richer context.
- Caution logic tightened: requires location extreme *and* weak participation or weak trend strength or range-bound conditions. ATR-adaptive width for better compression detection.
- Oct 30 update: Strong volume participation (ratio >=1.15 or last-bar confirm) softens pure range-bound caution on extremes, allowing high-participation moves more room while still protecting against weak-vol chases.

### Latest live snapshot (2026-10-31 ~04:07 IST)

- Last ~$76,926.0
- 48h range: $76,270.0 - $81,954.0 (pos **11.5%** — lower range, width 7.4%)
- 24h pos ~24.1% / 7d pos ~11.5%
- Trend: **bearish** (SMA20=77516 SMA50=78977 | EMA20=77504 | dist SMA20 -0.8%)
- RSI(14): **34.7**  ATR(14): ~567 (0.74%) [BOUNCE POTENTIAL]
- BB pos: 0.25  Mom4: +0.41%
- Vol ratio: **0.39** (falling, weak) -> VOL WEAK
- Regime: **TREND**  ADX: 32.5 (DI bias: bearish, -DI dominant)
- SHORT caution: lower/near-low range + low-vol/weak ADX/low-ATR or range-bound (avoid chase) + bounce potential (RSI low + weak vol)
- Bias: CAUTION SHORTS — avoid chase
- Context: Deep lower range of recent 48h after further pullback, short-term trend bearish with ADX confirming (-DI > +DI), RSI oversold-ish, volume participation weak. High bounce/mean-reversion risk — strong caution on shorts. Prefer waiting for volume expansion or clear reclaim rather than chasing.

Educational only — not financial advice.
