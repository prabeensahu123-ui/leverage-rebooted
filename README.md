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

### Latest live snapshot (2026-10-29 ~04:00 IST / ~22:30 UTC prior day)

- Last ~$81,200–$81,300
- 48h range: ~$79,630 – $81,540 (pos **~80%+** — upper range, width ~2.3%) [RANGE-BOUND] [NEAR RESIST]
- 24h pos ~mid-upper / 7d pos lower-mid
- Trend: **mixed / short-term bullish** (price near/above short MAs but daily still below some longer averages)
- RSI(14): **~55–60** (neutral-elevated on short TF)  ATR(14): ~400 (~0.5%)
- Vol ratio: weak / normal (participation still modest)
- Regime: MIXED / TREND ADX mid-20s [COMPRESSION/RANGE]
- Funding: mild positive (~+0.008% to +0.010% / 8h)
- Liq / positioning: ~65–67% accounts long; OI stable-to-slightly up; recent liqs mixed
- Context: Upper half of tight 48h range near resistance, elevated short-term RSI, modest volume, range-bound compression. Short-term MAs supportive but participation low and daily structure not fully confirmed. **Bias: WAIT / CAUTION LONGS — range-bound / compression near resist, prefer break or volume confirm before directional leverage.** Mild positive funding, longs somewhat crowded. Avoid chasing longs without volume expansion. Event risk (FOMC aftermath) still relevant.

Educational only — not financial advice.
