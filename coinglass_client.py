"""
coinglass_client.py
CoinGlass API v4 — Open Interest + liquidation history + heatmap clusters.
Needs COINGLASS_API_KEY (Streamlit secrets or env).
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
    # Streamlit secrets first, then env
    try:
        import streamlit as st
        k = st.secrets.get("COINGLASS_API_KEY", "")
        if k:
            return str(k).strip()
    except Exception:
        pass
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


def fetch_oi_history(symbol: str = "BTCUSD", interval: str = "1h", limit: int = 48) -> Dict[str, Any]:
    coin, _ = coin_pair(symbol)
    ok, data, msg = _get(
        "/api/futures/open-interest/aggregated-history",
        {"symbol": coin, "interval": interval, "limit": limit},
    )
    out: Dict[str, Any] = {
        "ok": ok, "error": msg if not ok else "",
        "oi_now": None, "oi_prev": None, "oi_chg_pct": None,
    }
    if not ok or not isinstance(data, list) or len(data) < 1:
        return out

    def oi_val(row):
        for k in ("close", "o", "oi", "open_interest", "aggregated_open_interest", "c"):
            if isinstance(row, dict) and row.get(k) is not None:
                try:
                    return float(row[k])
                except (TypeError, ValueError):
                    pass
        return None

    out["oi_now"] = oi_val(data[-1])
    if len(data) >= 2:
        out["oi_prev"] = oi_val(data[-2])
        if out["oi_now"] and out["oi_prev"] and out["oi_prev"] != 0:
            out["oi_chg_pct"] = (out["oi_now"] - out["oi_prev"]) / out["oi_prev"] * 100.0
    return out


def fetch_liquidation_history(symbol: str = "BTCUSD", interval: str = "1h", limit: int = 24) -> Dict[str, Any]:
    coin, _ = coin_pair(symbol)
    ok, data, msg = _get(
        "/api/futures/liquidation/aggregated-history",
        {"exchange_list": "Binance,OKX,Bybit", "symbol": coin, "interval": interval, "limit": limit},
    )
    out: Dict[str, Any] = {
        "ok": ok, "error": msg if not ok else "",
        "long_liq_usd": 0.0, "short_liq_usd": 0.0,
    }
    if not ok or not isinstance(data, list):
        return out
    long_s = short_s = 0.0
    for row in data[-6:]:
        if not isinstance(row, dict):
            continue
        long_s += float(row.get("aggregated_long_liquidation_usd") or row.get("longLiquidation_usd") or 0)
        short_s += float(row.get("aggregated_short_liquidation_usd") or row.get("shortLiquidation_usd") or 0)
    out["long_liq_usd"] = long_s
    out["short_liq_usd"] = short_s
    return out


def fetch_liq_map_clusters(symbol: str = "BTCUSD", price: float = 0.0, range_: str = "1d") -> Dict[str, Any]:
    """Bands ABOVE = short liq (squeeze fuel). BELOW = long liq (flush fuel)."""
    _, pair = coin_pair(symbol)
    ok, data, msg = _get(
        "/api/futures/liquidation/map",
        {"exchange": "Binance", "symbol": pair, "range": range_},
    )
    out: Dict[str, Any] = {
        "ok": ok, "error": msg if not ok else "",
        "nearest_short_band": None,
        "nearest_long_band": None,
        "short_band_size": 0.0,
        "long_band_size": 0.0,
    }
    if not ok or not data or price <= 0:
        return out

    raw = data.get("data") if isinstance(data, dict) and "data" in data else data
    if not isinstance(raw, dict):
        return out

    levels: List[Tuple[float, float]] = []
    for k, v in raw.items():
        try:
            px = float(k)
        except (TypeError, ValueError):
            continue
        size = 0.0
        if isinstance(v, list):
            for item in v:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    try:
                        size += float(item[1])
                    except (TypeError, ValueError):
                        pass
                elif isinstance(item, dict):
                    size += float(item.get("usd_value") or item.get("value") or 0)
        levels.append((px, size))

    levels.sort(key=lambda x: x[0])
    above = [(p, s) for p, s in levels if p > price * 1.0005]
    below = [(p, s) for p, s in levels if p < price * 0.9995]
    if above:
        near = sorted(above, key=lambda x: x[0])[:8]
        best = max(near, key=lambda x: x[1])
        out["nearest_short_band"] = best[0]
        out["short_band_size"] = best[1]
    if below:
        near = sorted(below, key=lambda x: -x[0])[:8]
        best = max(near, key=lambda x: x[1])
        out["nearest_long_band"] = best[0]
        out["long_band_size"] = best[1]
    return out


def build_coinglass_snapshot(
    symbol: str = "BTCUSD",
    price: float = 0.0,
    price_chg_pct: float = 0.0,
) -> Dict[str, Any]:
    oi = fetch_oi_history(symbol, interval="1h", limit=48)
    if not oi.get("ok"):
        oi = fetch_oi_history(symbol, interval="4h", limit=24)
    liq = fetch_liquidation_history(symbol, interval="1h", limit=24)
    heat = fetch_liq_map_clusters(symbol, price=price, range_="1d") if price > 0 else {"ok": False}

    oi_chg = oi.get("oi_chg_pct")
    quadrant = oi_price_quadrant(price_chg_pct, oi_chg)

    return {
        "ok": bool(oi.get("ok") or liq.get("ok") or heat.get("ok")),
        "oi_ok": bool(oi.get("ok")),
        "liq_ok": bool(liq.get("ok")),
        "heat_ok": bool(heat.get("ok")),
        "error": oi.get("error") or liq.get("error") or heat.get("error") or "",
        "oi_now": oi.get("oi_now"),
        "oi_chg_pct": oi_chg,
        "long_liq_usd": liq.get("long_liq_usd", 0),
        "short_liq_usd": liq.get("short_liq_usd", 0),
        "nearest_short_band": heat.get("nearest_short_band"),
        "nearest_long_band": heat.get("nearest_long_band"),
        "short_band_size": heat.get("short_band_size", 0),
        "long_band_size": heat.get("long_band_size", 0),
        "oi_price_quadrant": quadrant,
    }
