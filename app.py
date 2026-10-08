"""app.py"""
import pathlib, base64
_r=pathlib.Path(__file__).resolve().parent
_b="".join((_r/("_u%d.b64"%i)).read_text().strip() for i in range(4))
exec(compile(base64.b64decode(_b).decode(),"app.py","exec"),globals())
