"""Leverage Signal dashboard — loads app_body.py (plain source, no zlib)."""
from pathlib import Path
_body = Path(__file__).with_name("app_body.py")
_code = _body.read_text(encoding="utf-8")
exec(compile(_code, str(_body), "exec"), {"__name__": "__main__", "__file__": str(Path(__file__).resolve())})
