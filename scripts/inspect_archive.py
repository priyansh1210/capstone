"""List every CSV inside a trip archive (descending into nested zips) with its size, row count,
first/last data line and start-time range, and flag members whose content repeats another's.
Read-only.

    .venv\\Scripts\\python scripts\\inspect_archive.py data\\raw\\nyc\\trips\\2018-citibike-tripdata.zip
"""

from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from pathlib import Path


def walk(zf: zipfile.ZipFile, prefix: str = ""):
    for info in zf.infolist():
        n = info.filename
        if n.endswith("/") or n.startswith("__MACOSX") or Path(n).name.startswith("."):
            continue
        if n.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(zf.read(n))) as inner:
                yield from walk(inner, prefix + n + "/")
        elif n.lower().endswith(".csv"):
            yield prefix + n, info.file_size, zf.read(n)


def main(path: str) -> None:
    rows_total, seen = 0, {}
    print(f"archive: {path}", flush=True)
    print("member | MB | rows | first start | last start | sha1-12 | duplicate of")
    with zipfile.ZipFile(path) as zf:
        for name, size, data in walk(zf):
            lines = data.splitlines()
            body = lines[1:]
            rows = len(body)
            rows_total += rows
            first = body[0].decode("utf-8", "replace")[:80] if body else ""
            last = body[-1].decode("utf-8", "replace")[:80] if body else ""
            starts = [b.split(b",")[1].decode("utf-8", "replace").strip('"')[:19] for b in (body[0], body[-1])] if body else ["", ""]
            digest = hashlib.sha1(b"\n".join(sorted(body[:2000]))).hexdigest()[:12]  # order-insensitive sample fingerprint
            dup = seen.get((rows, digest), "")
            seen.setdefault((rows, digest), name)
            print(f"{name} | {size / 1e6:.1f} | {rows:,} | {starts[0]} | {starts[1]} | {digest} | {dup}")
            print(f"    header: {lines[0].decode('utf-8', 'replace')[:160]}")
            print(f"    first:  {first}")
            print(f"    last:   {last}")
    print(f"total data rows: {rows_total:,}")


if __name__ == "__main__":
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        del args[i : i + 2]
    if out:  # UTF-8 regardless of the console (Windows PowerShell 5.1 redirection writes UTF-16)
        sys.stdout = open(out, "w", encoding="utf-8")
    main(args[0] if args else r"data\raw\nyc\trips\2018-citibike-tripdata.zip")
