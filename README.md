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

### Latest live snapshot (2026-10-25 ~04:00 IST / ~22:30 UTC)

- Last ~$80,568
- 48h range: ~$79,179 – $82,035 (pos **~48.6%** — mid range, width ~3.5%)
- 24h pos ~69% / 7d pos ~mid
- Trend: **mixed** (SMA20~80,529 SMA50~81,098 | dist SMA20 +0.05%)
- RSI(14): **~47.9**  ATR(14): ~367 (~0.46%)
- Vol ratio: **~0.65** (normal/weak, no strong confirm)
- Funding: mild positive (~+0.005% to +0.007% / 8h)
- Liq / positioning: ~68% accounts long; recent 24h liquidations heavily long-sided ($200M+); OI ~$30B slight up
- Context: Stabilized in mid-48h range after earlier dump toward ~79.2k. Neutral RSI, mixed MAs, moderate ATR, weak-normal volume. No extreme location caution. Prefer waiting for volume expansion or break of mid-range / SMA50 reclaim before directional leverage. Decision zone ahead of Fed (28 Oct hold base case but hawkish tone risk). Avoid chasing either side without confirmation.

Educational only — not financial advice.
