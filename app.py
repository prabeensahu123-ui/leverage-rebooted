"""app.py"""
import pathlib
_r=pathlib.Path(__file__).resolve().parent
_src="".join((_r/("_r%d.py"%i)).read_text(encoding="utf-8") for i in range(8))
exec(compile(_src, str(_r/"app.py"), "exec"), globals())
