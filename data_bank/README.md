# Data Bank

Local OHLCV CSV store for forecasting and offline research.

## Files
- `{SYMBOL}_{TF}_ohlcv.csv` — columns: time,open,high,low,close,volume

## Refresh
```bash
python fetch_ohlcv.py BTCUSD 90 1h
```

Sources (auto): Delta India → CCXT (Binance) if installed → existing CSV.

## Note
GitHub `ccxt` fork is the full upstream monorepo. The app uses the **PyPI `ccxt` package** (same API), not the entire JS/TS tree.
