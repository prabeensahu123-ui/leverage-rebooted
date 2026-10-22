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
- BTC chart logs now include multi-lookback range position (48h/24h/7d), SMA/EMA20/50, RSI, ATR(14)+%, trend bias, volume ratio + trend + confirm + strength, near-high/low flags, near-support proximity, ADX/regime context, dist-to-SMA20, range-bound detection, and improved caution flags for faster context.
- Bot also prints a compact market-context line (funding, session, DVOL, VIX, OI quadrant, CoinGlass liq summary + any vetoes).

## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot feeds symmetric caution vetoes:
  - LONG entries flagged on upper/near-high range + (low-volume or weak ADX or range-bound), or elevated range_pos + RSI without volume confirm (chase risk).
  - SHORT entries flagged on lower/near-low range / near-support + (low-volume or weak ADX or range-bound), or depressed range_pos + RSI without volume confirm (chase risk).
  - Additional mid-range caution in tight consolidations (range width <2.5% + ADX<25) to prefer waiting for breaks or volume expansion.
  - Enhanced bounce awareness on weak-volume lower ranges / near 48h support (mean-reversion / liq magnet risk).
- Volume uses median (last 20 / last 5 vs prior) to reduce impact of single-bar spikes; added vol_confirm (last bar expansion) and vol_strength.
- Added EMAs, ATR%, range width, near_24h_high/low, near_support, dist_sma20_pct, range_bound flag, and optional ADX/regime (from regime.py) for richer context.
- Caution logic tightened: requires location extreme *and* weak participation or weak trend strength or range-bound conditions.

### Latest live snapshot (2026-10-23 ~03:30 IST / ~22:00 UTC)

- Last ~$81,402
- 48h range: ~$80,894 – $84,866 (pos **~12.8%** — lower range, width ~4.9%) [NEAR SUPPORT]
- 24h pos ~14% / 7d pos ~18%
- Trend: **bearish** (SMA20~81,838 SMA50~82,889 | dist SMA20 -0.5%)
- RSI(14): **~40.5**  ATR(14): ~387 (~0.48%)
- Vol ratio: **~0.28** (falling, weak)
- Funding: mild positive (~+0.005% to +0.01% / 8h)
- Liq clusters: heavier long-fuel below near ~80.3-81.5k; shorts higher (e.g. ~85k+)
- Context: Post-dump into lower 48h range on very weak volume. Bearish structure but low participation and proximity to support / long-liq magnets raise bounce risk. Prefer waiting for volume-confirmed break of ~80.9k support or reclaim of SMA20 / mid-range. Avoid chasing shorts. Decision zone ahead of Fed (28 Oct).

Educational only — not financial advice.
