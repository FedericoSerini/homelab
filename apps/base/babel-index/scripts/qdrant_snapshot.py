"""Create a Qdrant snapshot, download it to /backups/qdrant, prune old ones."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

base = os.environ.get("BABEL_QDRANT_URL", "http://qdrant:6333").rstrip("/")
alias = os.environ.get("BABEL_QDRANT_ALIAS", "chunks")
headers = {"api-key": os.environ["BABEL_QDRANT_API_KEY"]}
dest = Path("/backups/qdrant")
dest.mkdir(parents=True, exist_ok=True)
keep = 3


def call(method, path, timeout=3600):
    req = urllib.request.Request(base + path, method=method, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


snap = json.load(call("POST", f"/collections/{alias}/snapshots"))["result"]["name"]
target = dest / f"{alias}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.snapshot"
tmp = target.with_suffix(".part")
with call("GET", f"/collections/{alias}/snapshots/{snap}") as resp, tmp.open("wb") as out:
    while block := resp.read(1 << 20):
        out.write(block)
if tmp.stat().st_size == 0:
    sys.exit("empty snapshot downloaded")
tmp.rename(target)
call("DELETE", f"/collections/{alias}/snapshots/{snap}")
old = sorted(dest.glob(f"{alias}-*.snapshot"))[:-keep]
for f in old:
    f.unlink()
print(f"snapshot ok: {target.name} ({target.stat().st_size} bytes), pruned {len(old)}")
