"""Reassemble and run full app from part_*.txt committed beside this file."""
from pathlib import Path
import sys, os
_root = Path(__file__).resolve().parent
parts = sorted(_root.glob("_app_part_*.txt"))
if not parts:
    raise SystemExit("Missing _app_part_*.txt files")
code = "".join(p.read_text() for p in parts)
g = {"__name__": "__main__", "__file__": str(Path(__file__).resolve())}
exec(code, g)
