"""Leverage Signal dashboard — plain multi-part source (no zlib)."""
from pathlib import Path
_code = "".join(Path(__file__).with_name(f"_app_src_{i}.txt").read_text() for i in range(4))
exec(compile(_code, str(Path(__file__).with_name("app_body.py")), "exec"), {"__name__": "__main__", "__file__": str(Path(__file__).resolve())})
