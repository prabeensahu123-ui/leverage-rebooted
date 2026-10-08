"""app.py - plain 3-part loader."""
import pathlib
_root = pathlib.Path(__file__).resolve().parent
_src = "".join((_root / ("_mp%d.py" % i)).read_text(encoding="utf-8") for i in range(3))
exec(compile(_src, str(_root / "app.py"), "exec"), globals())
