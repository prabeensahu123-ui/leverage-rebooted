import zlib, base64
from pathlib import Path
_root = Path(__file__).resolve().parent
_b = "".join((_root / f"_p{i}.b64").read_text().strip() for i in range(3))
exec(zlib.decompress(base64.b64decode(_b)), {"__name__": "__main__", "__file__": str(Path(__file__).resolve())})
