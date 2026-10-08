"""
market_context.py
Funding, OI (Delta + CoinGlass), dollar, yields, session, DVOL/VIX.
"""

from datetime import datetime, timezone
import time
import requests

DELTA_BASE = "https://api.india.delta.exchange"
DERIBIT = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
HEADERS = {"User-Agent": "Mozilla/5.0 LeverageSignal/1.0"}

LONG_SIDES = {"LONG", "BUY"}
SHORT_SIDES = {"SHORT", "SELL"}


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def fetch_delta_derivatives(symbol="BTCUSD"):
    out = {
        "funding_rate": 0.0, "oi_btc": 0.0, "oi_usd": 0.0,
        "oi_change_usd_6h": 0.0, "mark_price": 0.0, "ok": False,
    }
    try:
        r = requests.get(f"{DELTA_BASE}/v2/tickers/{symbol}", timeout=5).json().get("result", {})
        out["funding_rate"] = _f(r.get("funding_rate"))
        out["oi_btc"] = _f(r.get("oi_value", r.get("oi")))
        out["oi_usd"] = _f(r.get("oi_value_usd"))
        out["oi_change_usd_6h"] = _f(r.get("oi_change_usd_6h"))
        out["mark_price"] = _f(r.get("mark_price", r.get("close")))
        out["ok"] = True
    except Exception:
        pass
    return out


def fetch_yahoo_change(symbol):
    try:
        r = requests.get(
            YAHOO_CHART.format(sym=symbol),
            headers=HEADERS,
            params={"interval": "1d", "range": "5d"},
            timeout=6,
        ).json()
        res = r["chart"]["result"][0]
        meta = res.get("meta", {})
        px = _f(meta.get("regularMarketPrice"))
        prev = _f(meta.get("chartPreviousClose") or meta.get("previousClose"))
        if px and prev:
            return {"price": px, "change_pct": (px - prev) / prev * 100.0}
        closes = (res.get("indicators", {}).get("quote", [{}])[0].get("close") or [])
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2:
            return {"price": closes[-1], "change_pct": (closes[-1] - closes[-2]) / closes[-2] * 100.0}
    except Exception:
        pass
    return None


def fetch_dvol():
    try:
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - 6 * 3600 * 1000
        r = requests.get(
            DERIBIT,
            params={"currency": "BTC", "resolution": 3600, "start_timestamp": start_ms, "end_timestamp": end_ms},
            timeout=8,
        ).json()
        rows = (r.get("result") or {}).get("data") or []
        if not rows:
            return None
        last = rows[-1]
        return _f(last[4] if len(last) > 4 else last[-1])
    except Exception:
        return None


def session_label(now=None):
    h = (now or datetime.now(timezone.utc)).hour
    if 0 <= h < 7:
        return "ASIA"
    if 7 <= h < 13:
        return "LONDON"
    if 13 <= h < 21:
        return "US"
    return "ASIA"


def vol_bucket(dvol):
    if dvol is None:
        return "UNKNOWN"
    if dvol < 42:
        return "LOW"
    if dvol >= 70:
        return "HIGH"
    return "MID"


def build_market_context(symbol="BTCUSD"):
    deriv = fetch_delta_derivatives(symbol)
    dxy = fetch_yahoo_change("DX-Y.NYB")
    tnx = fetch_yahoo_change("%5ETNX")
    vix = fetch_yahoo_change("%5EVIX")
    dvol = fetch_dvol()

    funding = deriv["funding_rate"]
    funding_pct = funding * 100.0 if abs(funding) < 0.05 else funding
    oi_chg = deriv["oi_change_usd_6h"]
    dxy_chg = dxy["change_pct"] if dxy else 0.0
    tnx_chg = tnx["change_pct"] if tnx else 0.0
    session = session_label()
    vb = vol_bucket(dvol)
    mark = deriv["mark_price"] or 0.0

    cg = {}
    try:
        from coinglass_client import build_coinglass_snapshot
        btc_y = fetch_yahoo_change("BTC-USD") if symbol.startswith("BTC") else None
        px_chg = btc_y["change_pct"] if btc_y else 0.0
        cg = build_coinglass_snapshot(symbol, price=mark, price_chg_pct=px_chg)
    except Exception as e:
        cg = {"ok": False, "error": str(e)}

    crowded_long = funding_pct >= 0.03 and oi_chg > 0
    crowded_short = funding_pct <= -0.03 and oi_chg > 0
    dollar_strong = dxy_chg >= 0.25 or tnx_chg >= 1.0
    dollar_weak = dxy_chg <= -0.25 or tnx_chg <= -1.0
    equity_fear = bool(vix and vix["price"] >= 25)

    veto_long = []
    veto_short = []
    if crowded_long:
        veto_long.append("crowded longs (funding+OI)")
    if crowded_short:
        veto_short.append("crowded shorts (funding+OI)")
    if dollar_strong:
        veto_long.append("DXY/yields up")
    if dollar_weak:
        veto_short.append("DXY/yields down")
    if equity_fear:
        veto_long.append("VIX elevated")

    quadrant = cg.get("oi_price_quadrant") or "UNKNOWN"
    if quadrant == "BEAR_CONTINUATION":
        veto_long.append("OI up price down bear continuation")
    if quadrant == "BULL_CONTINUATION":
        veto_short.append("OI up price up bull continuation")

    return {
        "funding_pct": round(funding_pct, 4),
        "oi_btc": deriv["oi_btc"],
        "oi_usd": deriv["oi_usd"],
        "oi_change_usd_6h": oi_chg,
        "dxy": dxy["price"] if dxy else None,
        "dxy_change_pct": round(dxy_chg, 3) if dxy else None,
        "us10y": tnx["price"] if tnx else None,
        "us10y_change_pct": round(tnx_chg, 3) if tnx else None,
        "vix": vix["price"] if vix else None,
        "dvol": round(dvol, 2) if dvol is not None else None,
        "vol_regime": vb,
        "session": session,
        "crowded_long": crowded_long,
        "crowded_short": crowded_short,
        "dollar_strong": dollar_strong,
        "dollar_weak": dollar_weak,
        "veto_buy": veto_long,
        "veto_sell": veto_short,
        "veto_long": veto_long,
        "veto_short": veto_short,
        "deriv_ok": deriv["ok"],
        "macro_ok": bool(dxy or tnx),
        "cg_ok": bool(cg.get("ok")),
        "cg_error": cg.get("error") or "",
        "cg_oi_now": cg.get("oi_now"),
        "cg_oi_chg_pct": cg.get("oi_chg_pct"),
        "cg_long_liq_usd": cg.get("long_liq_usd"),
        "cg_short_liq_usd": cg.get("short_liq_usd"),
        "cg_short_band": cg.get("nearest_short_band"),
        "cg_long_band": cg.get("nearest_long_band"),
        "oi_price_quadrant": quadrant,
    }


def apply_context_filter(side, ctx, resolution="1h"):
    if side is None:
        return None, ""
    short_tf = resolution in ("15m", "30m", "1h")
    if short_tf and ctx.get("vol_regime") == "LOW":
        return None, "DVOL compressed — 15m/1h squeeze risk"
    if short_tf and ctx.get("vol_regime") == "HIGH":
        return None, "DVOL high — short-TF noise"
    if side in LONG_SIDES and (ctx.get("veto_long") or ctx.get("veto_buy")):
        return None, "; ".join(ctx.get("veto_long") or ctx.get("veto_buy") or [])
    if side in SHORT_SIDES and (ctx.get("veto_short") or ctx.get("veto_sell")):
        return None, "; ".join(ctx.get("veto_short") or ctx.get("veto_sell") or [])
    return side, ""
