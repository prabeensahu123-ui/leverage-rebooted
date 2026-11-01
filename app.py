import zlib, base64
from pathlib import Path
b = "".join(Path(__file__).with_name(f"_r{i}.txt").read_text().strip() for i in range(24))
exec(zlib.decompress(base64.b64decode(b)), {"__name__": "__main__", "__file__": str(Path(__file__).resolve())})
