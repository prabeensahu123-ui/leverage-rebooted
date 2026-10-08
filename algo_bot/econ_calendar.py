"""
algo_bot/econ_calendar.py
USD high/medium impact events from FF-compatible weekly XML feed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from functools import lru_cache

import requests

FF_WEEK_XML = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
IST = timezone(timedelta(hours=5, minutes=30))
ET = timezone(timedelta(hours=-4))

IMPACT_RANK = {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0}


def _parse_et_datetime(date_s: str, time_s: str):
    date_s = (date_s or "").strip()
    time_s = (time_s or "").strip()
    if not date_s:
        return None
    try:
        d = datetime.strptime(date_s, "%m-%d-%Y").date()
    except ValueError:
        return None
    if not time_s or time_s.lower() in ("all day", "tentative", ""):
        return datetime(d.year, d.month, d.day, 12, 0, tzinfo=ET)
    m = re.match(r"^(\d{1,2}):(\d{2})(am|pm)$", time_s.lower().replace(" ", ""))
    if not m:
        return datetime(d.year, d.month, d.day, 12, 0, tzinfo=ET)
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return datetime(d.year, d.month, d.day, h, mi, tzinfo=ET)


@lru_cache(maxsize=1)
def _raw_events(cache_bucket: str):
    r = requests.get(FF_WEEK_XML, timeout=12, headers={"User-Agent": "LeverageSignal/1.0"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for ev in root.findall("event"):
        title = (ev.findtext("title") or "").strip()
        country = (ev.findtext("country") or "").strip()
        date_s = (ev.findtext("date") or "").strip()
        time_s = (ev.findtext("time") or "").strip()
        impact = (ev.findtext("impact") or "").strip()
        forecast = (ev.findtext("forecast") or "").strip()
        previous = (ev.findtext("previous") or "").strip()
        dt = _parse_et_datetime(date_s, time_s)
        out.append({
            "title": title,
            "currency": country,
            "impact": impact,
            "forecast": forecast,
            "previous": previous,
            "date": date_s,
            "time_et": time_s,
            "dt_et": dt,
            "dt_utc": dt.astimezone(timezone.utc) if dt else None,
            "dt_ist": dt.astimezone(IST) if dt else None,
        })
    return tuple(out)


def fetch_events(currencies=("USD",), min_impact="Medium"):
    bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    try:
        raw = list(_raw_events(bucket))
    except Exception as e:
        print(f"[econ_calendar] fetch failed: {e}")
        return []
    min_rank = IMPACT_RANK.get(min_impact, 2)
    curset = {c.upper() for c in currencies}
    out = []
    for e in raw:
        if e["currency"].upper() not in curset and e["currency"] not in curset:
            if e["currency"] not in curset:
                continue
        if IMPACT_RANK.get(e["impact"], 0) < min_rank:
            continue
        out.append(e)
    out.sort(key=lambda x: x["dt_utc"] or datetime.min.replace(tzinfo=timezone.utc))
    return out


def upcoming_usd(hours_ahead=48, min_impact="High"):
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours_ahead)
    rows = []
    for e in fetch_events(currencies=("USD",), min_impact=min_impact):
        dt = e.get("dt_utc")
        if dt is None:
            continue
        if now - timedelta(hours=1) <= dt <= end:
            rows.append(e)
    return rows


def in_news_blackout(
    now=None,
    minutes_before=90,
    minutes_after=30,
    min_impact="High",
    currencies=("USD",),
):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    hits = []
    for e in fetch_events(currencies=currencies, min_impact=min_impact):
        dt = e.get("dt_utc")
        if dt is None:
            continue
        start = dt - timedelta(minutes=minutes_before)
        end = dt + timedelta(minutes=minutes_after)
        if start <= now <= end:
            hits.append(e)
    if not hits:
        return False, None
    hits.sort(key=lambda x: abs((x["dt_utc"] - now).total_seconds()))
    return True, hits[0]


def summary_lines(hours_ahead=36):
    lines = []
    for e in upcoming_usd(hours_ahead=hours_ahead, min_impact="Medium"):
        ist = e["dt_ist"].strftime("%a %H:%M IST") if e.get("dt_ist") else "?"
        lines.append(f"{ist} | {e['impact']:6} | {e['title']}")
    return lines
