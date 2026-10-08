"""app.py - loads plain parts (no zlib)."""
import pathlib
_root = pathlib.Path(__file__).resolve().parent
_src = (_root / "_app_part1.py").read_text(encoding="utf-8") + (_root / "_app_part2.py").read_text(encoding="utf-8")
exec(compile(_src, str(_root / "app.py"), "exec"), globals())
