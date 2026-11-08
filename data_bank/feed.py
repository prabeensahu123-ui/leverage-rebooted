"""
Unified OHLCV feed for leverage app.

Primary: Delta India REST (existing stack)
Fallback: CCXT (Binance/Bybit public) when installed — mirrors data into data_bank CSVs
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

import requests

from data_bank.store import load_ohlcv_csv, save_ohlcv_csv

DELTA_BASE = "https://api.india.delta.exchange"

CCXT_SYMBOL_MAP = {
    "BTCUSD": "BTC/USDT",
    "ETHUSD": "ETH/USDT",
    "SOLUSD": "SOL/USDT",
}

TF_MAP = {
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def _delta_fetch(symbol: str, resolution: str, days: int) -> List[Dict[str, Any]]:
    end = int(time.time())
    start = end - days * 86400
    r = requests.get(
        f"{DELTA_BASE}/v2/history/candles",
        params={"symbol": symbol, "resolution": resolution, "start": start, "end": end},
        timeout=25,
    )
    r.raise_for_status()
    data = r.json().get("result") or []
    rows = []
    for c in reversed(data):
        rows.append(
            {
                "time": int(c["time"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c.get("volume") or 0),
            }
        )
    return rows


def _ccxt_fetch(symbol: str, resolution: str, days: int, exchange_id: str = "binance") -> List[Dict[str, Any]]:
    try:
        import ccxt
    except ImportError as e:
        raise RuntimeError("ccxt not installed — pip install ccxt") from e

    unified = CCXT_SYMBOL_MAP.get(symbol.upper(), symbol)
    tf = TF_MAP.get(resolution, resolution)
    ex_class = getattr(ccxt, exchange_id, None)
    if ex_class is None:
        raise RuntimeError(f"Unknown ccxt exchange: {exchange_id}")
    ex = ex_class({"enableRateLimit": True})
    since = int((time.time() - days * 86400) * 1000)
    limit = min(1000, max(50, days * 24 if resolution == "1h" else days * 6))
    raw = ex.fetch_ohlcv(unified, timeframe=tf, since=since, limit=limit)
    rows = []
    for t, o, h, l, c, v in raw:
        rows.append(
            {
                "time": int(t // 1000),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v or 0),
            }
        )
    rows.sort(key=lambda x: x["time"])
    return rows


def fetch_ohlcv_unified(
    symbol: str,
    resolution: str = "1h",
    days: int = 90,
    source: str = "auto",
    use_cache: bool = True,
    persist: bool = True,
) -> List[Dict[str, Any]]:
    """source: auto | delta | ccxt | csv"""
    symbol = symbol.upper()
    source = (source or "auto").lower()

    if source == "csv" or (use_cache and source == "auto"):
        cached = load_ohlcv_csv(symbol, resolution)
        if source == "csv":
            return cached
        if cached and source == "auto":
            age = time.time() - cached[-1]["time"]
            if age < 2 * 3600 and len(cached) > 50:
                return cached

    errors = []
    rows: List[Dict[str, Any]] = []

    if source in ("auto", "delta"):
        try:
            rows = _delta_fetch(symbol, resolution, days)
        except Exception as e:
            errors.append(f"delta: {e}")

    if not rows and source in ("auto", "ccxt"):
        try:
            rows = _ccxt_fetch(symbol, resolution, days)
        except Exception as e:
            errors.append(f"ccxt: {e}")

    if not rows and use_cache:
        rows = load_ohlcv_csv(symbol, resolution)
        if rows:
            return rows

    if not rows:
        raise RuntimeError("OHLCV fetch failed: " + (" | ".join(errors) or "unknown"))

    if persist:
        save_ohlcv_csv(symbol, resolution, rows)
    return rows


def refresh_symbol(symbol: str, resolution: str = "1h", days: int = 90) -> Dict[str, Any]:
    rows = fetch_ohlcv_unified(symbol, resolution, days, source="auto", use_cache=False, persist=True)
    return {
        "symbol": symbol,
        "resolution": resolution,
        "n": len(rows),
        "last_close": rows[-1]["close"] if rows else None,
        "last_time": rows[-1]["time"] if rows else None,
    }
