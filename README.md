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

### Latest live snapshot (2026-11-01 ~04:10 IST)

- Last ~$77,511.3
- 48h range: $76,141.0 - $78,880.8 (pos **50.0%** — mid range, width 3.5%)
- 24h pos ~85.2% / 7d pos ~23.8%
- Trend: **mixed** (SMA20=77336 SMA50=77399 | EMA20=77397 | dist SMA20 +0.2%)
- RSI(14): **63.4**  ATR(14): ~184 (0.24%) [LOW ATR] [REJECTION POTENTIAL]
- BB pos: 0.78  Mom4: +0.03%
- Vol ratio: **0.70** (falling, normal)
- Regime: **COMPRESSION**  ADX: 10.7 (DI: +20/-19 neutral)
- LONG caution: upper/near-high range + low-vol/weak ADX/low-ATR or range-bound or bearish DI (avoid chase)
- Near 24h high
- Bias: CAUTION LONGS — avoid chase (upper range / weak participation)
- Context: Mid-48h but near 24h high in low-ATR compression. Elevated RSI with only normal/falling volume raises rejection risk. Prefer waiting for clear volume expansion or DI confirmation before longs.

## Chart R&D amendments (Nov 2026)

- Added explicit DI bias (+DI/-DI) from regime for directional context in caution and caption.
- Symmetric rejection_potential flag (elevated RSI + weak vol near upper range) mirroring bounce_potential.
- Long caution now also triggers on bearish DI bias at upper extremes.
- Bias includes REJECTION WATCH state.
- Improves filtering in quiet post-pullback consolidations without loosening the conservative philosophy.

Educational only — not financial advice.
