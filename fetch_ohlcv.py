"""
fetch_ohlcv.py — CLI + library entry for OHLCV.

Uses data_bank (Delta primary, CCXT fallback when installed).
"""
from __future__ import annotations

import sys

from data_bank.feed import fetch_ohlcv_unified
from data_bank.store import csv_path


def fetch_ohlcv(symbol: str, days: int = 90, resolution: str = "1h"):
    return fetch_ohlcv_unified(symbol, resolution, days, source="auto", persist=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_ohlcv.py SYMBOL [days] [resolution]")
        sys.exit(1)

    symbol = sys.argv[1].upper()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    resolution = sys.argv[3] if len(sys.argv) > 3 else "1h"

    print(f"Fetching {days}d {symbol} {resolution} (delta→ccxt→csv)...")
    candles = fetch_ohlcv(symbol, days, resolution)
    path = csv_path(symbol, resolution)
    print(f"Saved {len(candles)} candles → {path}")
