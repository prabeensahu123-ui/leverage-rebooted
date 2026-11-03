"""
algo_bot/config.py
Paper-trading + model thresholds.
"""

# Symbols / TFs scanned by paper bot
PAPER_TRADE_SYMBOLS = ["BTCUSD", "ETHUSD", "SOLUSD"]

TIMEFRAMES = {
    "15m": {
        "resolution": "15m",
        "days": 21,
        "max_holding_bars": 16,
        "trade_enabled": True,
    },
    "1h": {
        "resolution": "1h",
        "days": 60,
        "max_holding_bars": 24,
        "trade_enabled": True,
    },
    "4h": {
        "resolution": "4h",
        "days": 120,
        "max_holding_bars": 18,
        "trade_enabled": True,
    },
}

K_PROFIT = 2.0
K_STOP = 2.0

# Slightly softer so borderline but real edges can fire (impulse path has its own 0.48 floor)
MIN_BUY_PROBA = 0.54
MIN_SELL_PROBA = 0.54
MIN_EDGE = 0.10

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
