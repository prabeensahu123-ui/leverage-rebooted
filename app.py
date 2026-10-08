"""app.py - plain multi-part loader (no zlib)."""
import pathlib
_root = pathlib.Path(__file__).resolve().parent
_src = "".join((_root / ("_app_p%d.py" % i)).read_text(encoding="utf-8") for i in range(4))
exec(compile(_src, str(_root / "app.py"), "exec"), globals())
