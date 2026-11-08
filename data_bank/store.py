"""CSV persistence for OHLCV history used by forecasting + signals."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent


def bank_dir() -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    return ROOT


def csv_path(symbol: str, resolution: str) -> Path:
    safe = f"{symbol.upper().replace('/', '')}_{resolution}_ohlcv.csv"
    return bank_dir() / safe


def list_bank_files() -> List[str]:
    return sorted(p.name for p in bank_dir().glob("*_ohlcv.csv"))


def save_ohlcv_csv(symbol: str, resolution: str, rows: List[Dict[str, Any]]) -> Path:
    path = csv_path(symbol, resolution)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        for c in rows:
            w.writerow(
                [
                    c.get("time") or c.get("timestamp"),
                    c.get("open"),
                    c.get("high"),
                    c.get("low"),
                    c.get("close"),
                    c.get("volume") or c.get("base_volume") or 0,
                ]
            )
    return path


def load_ohlcv_csv(
    symbol: str,
    resolution: str,
    path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    p = Path(path) if path else csv_path(symbol, resolution)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with p.open() as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                out.append(
                    {
                        "time": int(float(row["time"])),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row.get("volume") or 0),
                    }
                )
            except (KeyError, ValueError, TypeError):
                continue
    out.sort(key=lambda x: x["time"])
    return out
