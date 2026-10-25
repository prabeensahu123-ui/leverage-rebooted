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
- BTC chart logs now include multi-lookback range position (48h/24h/7d), SMA/EMA20/50, RSI, ATR(14)+%, trend bias, volume ratio + trend + confirm + strength, near-high/low flags, near-support/resistance proximity, ADX/regime context, dist-to-SMA20, range-bound detection, breakout_watch, actionable bias, and improved caution flags for faster context.
- Bot also prints a compact market-context line (funding, session, DVOL, VIX, OI quadrant, CoinGlass liq summary + any vetoes).

## Chart-aware filters (Oct 2026)

- BTC 1h chart snapshot feeds symmetric caution vetoes:
  - LONG entries flagged on upper/near-high range + (low-volume or weak ADX or range-bound), or elevated range_pos + RSI without volume confirm (chase risk).
  - SHORT entries flagged on lower/near-low range / near-support + (low-volume or weak ADX or range-bound), or depressed range_pos + RSI without volume confirm (chase risk).
  - Additional mid-range caution in tight consolidations (range width <=2.6% + ADX<26) to prefer waiting for breaks or volume expansion.
  - Enhanced bounce awareness on weak-volume lower ranges / near 48h support (mean-reversion / liq magnet risk).
  - Breakout watch when near range edge + volume/ADX building.
- Volume uses median (last 15 / last 3 vs prior) for better recent sensitivity; added vol_confirm (last bar expansion) and vol_strength.
- Added EMAs, ATR%, range width, near_24h_high/low, near_support/resistance, dist_sma20_pct, range_bound flag, breakout_watch, bias recommendation, and optional ADX/regime (from regime.py) for richer context.
- Caution logic tightened: requires location extreme *and* weak participation or weak trend strength or range-bound conditions.

### Latest live snapshot (2026-10-26 ~04:00 IST / ~22:30 UTC)

- Last ~$80,489
- 48h range: ~$79,179 – $81,191 (pos **~65.1%** — upper range, width ~2.5%) [RANGE-BOUND]
- 24h pos ~45.6% / 7d pos ~23.0%
- Trend: **bearish** (SMA20~80,535 SMA50~80,610 | dist SMA20 -0.1%)
- RSI(14): **~53.1**  ATR(14): ~286 (~0.36%) [LOW ATR]
- Vol ratio: **~0.51** (falling, weak, no confirm)
- Regime: TREND ADX ~23.4 [COMPRESSION/RANGE]
- Funding: mild positive (~+0.003% to +0.005% / 8h across venues)
- Liq / positioning: ~68% accounts long; recent 24h liquidations balanced/slightly short-sided (~$10-18M); OI ~$30-36B slight down
- Context: Stabilized in upper half of very tight 48h range after earlier dump toward ~79.2k. Neutral RSI, slightly bearish MAs, very low ATR, weak volume. Range-bound compression. **Bias: WAIT — prefer break or volume expansion before directional leverage.** Mild positive funding, no extreme location caution yet. Decision zone ahead of Fed (28 Oct). Avoid chasing either side without confirmation.

Educational only — not financial advice.
