"""
DEPRECATED — do not add new logic here.

The only paper-trading system is algo_bot.
This file is kept so old commands still work.
"""

print("paper_trade_step.py is frozen.")
print("Use:  python -m algo_bot.bot once|start|status|performance")
print("Redirecting this run to algo_bot.bot once ...\n")

from algo_bot.bot import run_once, show_status

if __name__ == "__main__":
    run_once()
    show_status()
