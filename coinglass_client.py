"""
coinglass_client.py
CoinGlass API v4 — optional. Needs COINGLASS_API_KEY.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE = "https://open-api-v4.coinglass.com"

COIN_MAP = {
    "BTCUSD": ("BTC", "BTCUSDT"),
    "ETHUSD": ("ETH", "ETHUSDT"),
    "SOLUSD": ("SOL", "SOLUSDT"),
    "XAUTUSD": ("XAU", "XAUUSDT"),
    "PAXGUSD": ("PAXG", "PAXGUSDT"),
}


def _key() -> str:
    return (os.environ.get("COINGLASS_API_KEY") or "").strip()


def _headers() -> Dict[str, str]:
    return {"CG-API-KEY": _key(), "accept": "application/json"}


def _get(path: str, params: Optional[dict] = None) -> Tuple[bool, Any, str]:
    if not _key():
        return False, None, "COINGLASS_API_KEY not set"
    try:
        r = requests.get(BASE + path, headers=_headers(), params=params or {}, timeout=14)
        j = r.json() if r.text else {}
        code = str(j.get("code", r.status_code))
        msg = str(j.get("msg", ""))
        if code != "0":
            return False, None, msg or f"code={code}"
        return True, j.get("data"), "ok"
    except Exception as e:
        return False, None, str(e)


def coin_pair(symbol: str) -> Tuple[str, str]:
    return COIN_MAP.get(symbol, ("BTC", "BTCUSDT"))


def oi_price_quadrant(price_chg_pct: float, oi_chg_pct: Optional[float]) -> str:
    if oi_chg_pct is None:
        return "UNKNOWN"
    up_p = price_chg_pct >= 0
    up_o = oi_chg_pct >= 0
    if up_p and up_o:
        return "BULL_CONTINUATION"
    if up_p and not up_o:
        return "BULL_FLUSH"
    if not up_p and up_o:
        return "BEAR_CONTINUATION"
    return "BEAR_FLUSH"


def build_coinglass_snapshot(symbol: str = "BTCUSD", price: float = 0.0, price_chg_pct: float = 0.0) -> Dict[str, Any]:
    """Soft stub when key missing — returns ok=False so market_context falls back."""
    if not _key():
        return {"ok": False, "error": "COINGLASS_API_KEY not set", "oi_price_quadrant": "UNKNOWN"}
    coin, _ = coin_pair(symbol)
    ok, data, msg = _get(
        "/api/futures/open-interest/aggregated-history",
        {"symbol": coin, "interval": "1h", "limit": 48},
    )
    oi_now = oi_prev = oi_chg = None
    if ok and isinstance(data, list) and len(data) >= 2:
        def oi_val(row):
            for k in ("close", "o", "oi", "open_interest", "c"):
                if k in row and row[k] is not None:
                    try:
                        return float(row[k])
                    except (TypeError, ValueError):
                        pass
            return None
        oi_now = oi_val(data[-1])
        oi_prev = oi_val(data[-2])
        if oi_now and oi_prev and oi_prev != 0:
            oi_chg = (oi_now - oi_prev) / oi_prev * 100.0
    return {
        "ok": bool(ok),
        "error": msg if not ok else "",
        "oi_now": oi_now,
        "oi_chg_pct": oi_chg,
        "long_liq_usd": 0,
        "short_liq_usd": 0,
        "nearest_short_band": None,
        "nearest_long_band": None,
        "oi_price_quadrant": oi_price_quadrant(price_chg_pct, oi_chg),
    }
