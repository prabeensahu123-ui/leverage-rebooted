"""
Save / load daily RandomForest models.
Compatible with Python 3.9+.
Dashboard/Cloud: allow models up to 7 days old (Actions may lag).
"""

import os
import json
from datetime import datetime, timezone, timedelta

try:
    import joblib
except ImportError:
    joblib = None

IST = timezone(timedelta(hours=5, minutes=30))
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
MAX_AGE_HOURS = 168  # 7 days


def model_path(symbol, resolution):
    safe = "%s_%s" % (symbol, resolution)
    safe = safe.replace("/", "_")
    return os.path.join(MODELS_DIR, "%s.joblib" % safe)


def meta_path(symbol, resolution):
    return model_path(symbol, resolution).replace(".joblib", ".json")


def ensure_dir():
    os.makedirs(MODELS_DIR, exist_ok=True)


def save_model(symbol, resolution, model, extra=None):
    if joblib is None:
        raise RuntimeError("joblib missing")
    ensure_dir()
    path = model_path(symbol, resolution)
    joblib.dump(model, path)
    meta = {
        "symbol": symbol,
        "resolution": resolution,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "trained_at_ist": datetime.now(IST).isoformat(),
        "classes": [int(c) for c in getattr(model, "classes_", [])],
    }
    if extra:
        meta.update(extra)
    with open(meta_path(symbol, resolution), "w") as f:
        json.dump(meta, f, indent=2)
    return path


def load_model(symbol, resolution, max_age_hours=None):
    if max_age_hours is None:
        max_age_hours = MAX_AGE_HOURS
    if joblib is None:
        return None, None
    path = model_path(symbol, resolution)
    mpath = meta_path(symbol, resolution)
    if not os.path.exists(path):
        return None, None
    meta = {}
    if os.path.exists(mpath):
        try:
            with open(mpath) as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    trained = meta.get("trained_at_utc")
    if trained:
        try:
            dt = datetime.fromisoformat(trained.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
            if age_h > max_age_hours:
                return None, meta
        except Exception:
            pass
    try:
        model = joblib.load(path)
        return model, meta
    except Exception:
        return None, None
