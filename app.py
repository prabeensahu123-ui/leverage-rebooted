"""app.py"""
import pathlib
_r=pathlib.Path(__file__).resolve().parent
_h="".join((_r/("_h%d.hex"%i)).read_text(encoding="utf-8").strip() for i in range(8))
_src=bytes.fromhex(_h).decode("utf-8")
exec(compile(_src, str(_r/"app.py"), "exec"), globals())
