"""
DEPRECATED — do not add new logic here.

The only paper-trading system is algo_bot.
This file is kept so old commands still work.
"""

import sys

print("paper_trading.py is frozen.")
print("Use:  python -m algo_bot.bot once|start|status|performance")
print("Redirecting this run to algo_bot.bot once ...\n")

from algo_bot.bot import run_once, show_status, show_performance

if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--performance" in args or "performance" in args:
        show_performance()
    else:
        run_once()
        show_status()
