"""Leverage Signal bootstrap."""
import zlib, base64
from pathlib import Path
_root = Path(__file__).resolve().parent
parts = sorted(_root.glob("_c*.b64"))
if not parts:
    raise SystemExit("missing _c*.b64 — redeploy full app")
b64 = "".join(p.read_text().strip() for p in parts)
code = zlib.decompress(base64.b64decode(b64))
exec(code, {"__name__": "__main__", "__file__": str(Path(__file__).resolve())})
