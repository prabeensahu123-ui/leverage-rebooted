"""app.py"""
import pathlib
_r=pathlib.Path(__file__).resolve().parent
exec(compile("".join((_r/("_q%d.py"%i)).read_text(encoding="utf-8") for i in range(4)), str(_r/"app.py"), "exec"), globals())
