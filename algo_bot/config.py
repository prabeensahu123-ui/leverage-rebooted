"""
algo_bot/config.py
Single source of truth for the bot and the dashboard.
"""

SYMBOL = "BTCUSD"

TRADE_SYMBOLS = [
    "BTCUSD",
    "ETHUSD",
    "SOLUSD",
    "XAUTUSD",
    "PAXGUSD",
]

# Paper entries allowed only for these (models still train for all).
PAPER_TRADE_SYMBOLS = [
    "BTCUSD",
    "ETHUSD",
    "SOLUSD",
]

ASSET_LABELS = {
    "BTCUSD": "BTC",
    "ETHUSD": "ETH",
    "SOLUSD": "SOL",
    "XAUTUSD": "XAUT",
    "PAXGUSD": "PAXG",
}

MODE = "PAPER"

TIMEFRAMES = {
    "15m": {
        "resolution": "15m",
        "days": 30,
        "max_holding_bars": 32,
        "label": "15 Minutes",
        "hold": "~8h",
        "trade_enabled": False,
        "max_trades_per_day": 4,
    },
    "30m": {
        "resolution": "30m",
        "days": 45,
        "max_holding_bars": 28,
        "label": "30 Minutes",
        "hold": "~14h",
        "trade_enabled": True,
        "max_trades_per_day": 2,
    },
    "1h": {
        "resolution": "1h",
        "days": 90,
        "max_holding_bars": 24,
        "label": "1 Hour",
        "hold": "~24h",
        "trade_enabled": True,
        "max_trades_per_day": 2,
    },
    "4h": {
        "resolution": "4h",
        "days": 180,
        "max_holding_bars": 18,
        "label": "4 Hours",
        "hold": "~3d",
        "trade_enabled": True,
        "max_trades_per_day": 1,
    },
    "1D": {
        "resolution": "1d",
        "days": 300,
        "max_holding_bars": 15,
        "label": "Daily",
        "hold": "~15d",
        "trade_enabled": True,
        "max_trades_per_day": 1,
    },
}

DASHBOARD_TIMEFRAMES = {
    "15m": {
        "resolution": "15m",
        "days": 30,
        "max_holding_bars": 32,
        "label": "15m",
        "hold": "~8h",
    },
    "30m": {
        "resolution": "30m",
        "days": 45,
        "max_holding_bars": 28,
        "label": "30m",
        "hold": "~14h",
    },
    "1h": {
        "resolution": "1h",
        "days": 90,
        "max_holding_bars": 24,
        "label": "1h",
        "hold": "~24h",
    },
    "4h": {
        "resolution": "4h",
        "days": 180,
        "max_holding_bars": 18,
        "label": "4h",
        "hold": "~3d",
    },
    "1D": {
        "resolution": "1d",
        "days": 300,
        "max_holding_bars": 15,
        "label": "Daily",
        "hold": "~15d",
    },
}

K_PROFIT = 2.0
K_STOP = 2.0

MIN_BUY_PROBA = 0.56
MIN_SELL_PROBA = 0.56
MIN_EDGE = 0.15

FORCE_DAILY_TRIAL = False
MIN_TRIAL_PROBA = 0.55
CLOSE_TRIAL_AGAINST_SMA = True

ROUND_TRIP_COST_PCT = 0.00118
MIN_LABEL_MOVE_PCT = 0.00150

OOS_FRACTION = 0.20
PURGE_MULTIPLIER = 1

ACCOUNT_INR = 15000.0
LEVERAGE = 10.0
USD_INR = 88.0
RISK_FRACTION = 0.01

NEWS_BLACKOUT = True
NEWS_MINUTES_BEFORE = 90
NEWS_MINUTES_AFTER = 30

TRADE_LOG_FILE = "algo_bot/trades.csv"
STATE_FILE = "algo_bot/state.json"
LOG_FILE = "algo_bot/bot.log"

CHECK_INTERVAL_MINUTES = 15
DELTA_BASE = "https://api.india.delta.exchange"
