"""app.py loader - reconstructs from chunks."""
import pathlib
_root = pathlib.Path(__file__).resolve().parent
_parts = []
for i in range(4):
    _parts.append((_root / ("_app_chunk_%d.py" % i)).read_text(encoding="utf-8"))
exec(compile("".join(_parts), str(_root / "app.py"), "exec"), globals())
