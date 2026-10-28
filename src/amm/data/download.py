"""Download and validate the raw source files.

Sources (all public, no account needed):

* Capital Bikeshare system trip data (one zip per year 2011-2017, one per
  month from 2018). Listing: https://s3.amazonaws.com/capitalbikeshare-data/
* NOAA ISD-Lite hourly observations for Ronald Reagan Washington National
  Airport (DCA), USAF 724050 / WBAN 13743, via NOAA's AWS open-data bucket.
* UCI Bike Sharing (Fanaee-T 2013), used only to cross-check our hourly
  aggregation for 2011-2012.

Behaviour:
* Each file is streamed to ``<name>.part`` with a socket timeout and retries,
  then atomically renamed. Existing files are reused (local cache) after
  validation, so a second run works offline.
* Expected sizes / MD5 ETags are taken from the S3 bucket listing when it is
  reachable, and every file's SHA-256 is recorded in ``data/raw/SOURCES.json``.
* If a download fails, a copy placed in ``data/raw/manual/<filename>`` is used
  instead (manual-file fallback). Raw files are never modified.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from amm import paths

TRIP_BUCKET = "https://s3.amazonaws.com/capitalbikeshare-data/"
ISD_URL = "https://noaa-isd-pds.s3.amazonaws.com/isd-lite/data/{year}/724050-13743-{year}.gz"
UCI_URL = "https://archive.ics.uci.edu/static/public/275/bike%2Bsharing%2Bdataset.zip"

USER_AGENT = "amm-capstone/0.1 (research replay; contact: local user)"


class DownloadError(RuntimeError):
    pass


@dataclass
class SourceFile:
    kind: str  # trips | weather | uci
    name: str
    url: str
    dest: Path
    expected_size: int | None = None
    expected_md5: str | None = None

    def manual_path(self) -> Path:
        return paths.MANUAL / self.name


@dataclass
class FileRecord:
    kind: str
    name: str
    url: str
    path: str
    size: int
    sha256: str
    origin: str  # downloaded | cache | manual
    validated_against: list[str] = field(default_factory=list)
    recorded_at: str = ""


def trip_file_names(first_year: int, last_year: int) -> list[str]:
    names = []
    for y in range(first_year, last_year + 1):
        if y <= 2017:
            names.append(f"{y}-capitalbikeshare-tripdata.zip")
        else:
            names.extend(f"{y}{m:02d}-capitalbikeshare-tripdata.zip" for m in range(1, 13))
    return names


def _open(url: str, timeout: float):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_bucket_listing(timeout: float = 30.0) -> dict[str, tuple[int, str]]:
    """Return {key: (size, etag)} from the public S3 listing, or {} if unreachable."""
    try:
        with _open(TRIP_BUCKET, timeout) as resp:
            body = resp.read()
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        print(f"[download] bucket listing unavailable ({exc}); sizes will not be pre-validated")
        return {}
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    root = ET.fromstring(body)
    out = {}
    for c in root.findall("s3:Contents", ns):
        key = c.findtext("s3:Key", namespaces=ns)
        size = int(c.findtext("s3:Size", default="0", namespaces=ns))
        etag = (c.findtext("s3:ETag", default="", namespaces=ns) or "").strip('"')
        out[key] = (size, etag)
    return out


def _hash(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate(src: SourceFile, path: Path) -> list[str]:
    """Raise DownloadError if the file contradicts known metadata."""
    checks = []
    size = path.stat().st_size
    if size == 0:
        raise DownloadError(f"{src.name}: empty file")
    if src.expected_size is not None:
        if size != src.expected_size:
            raise DownloadError(f"{src.name}: size {size} != expected {src.expected_size}")
        checks.append("size")
    if src.expected_md5 and "-" not in src.expected_md5:  # multipart ETags are not MD5s
        md5 = _hash(path, "md5")
        if md5 != src.expected_md5:
            raise DownloadError(f"{src.name}: md5 {md5} != ETag {src.expected_md5}")
        checks.append("md5-etag")
    with open(path, "rb") as f:
        magic = f.read(4)
    if path.suffix == ".zip" and magic[:2] != b"PK":
        raise DownloadError(f"{src.name}: not a zip archive")
    if path.suffix == ".gz" and magic[:2] != b"\x1f\x8b":
        raise DownloadError(f"{src.name}: not a gzip file")
    checks.append("magic")
    return checks


def _download_once(src: SourceFile, timeout: float) -> None:
    tmp = src.dest.with_suffix(src.dest.suffix + ".part")
    with _open(src.url, timeout) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
    tmp.replace(src.dest)


def obtain(src: SourceFile, timeout: float = 60.0, retries: int = 3, backoff: float = 1.0) -> FileRecord:
    src.dest.parent.mkdir(parents=True, exist_ok=True)
    origin = None
    if src.dest.exists():
        try:
            checks = _validate(src, src.dest)
            origin = "cache"
        except DownloadError as exc:
            print(f"[download] cached {src.name} invalid ({exc}); re-downloading")
            src.dest.unlink()
    if origin is None:
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                _download_once(src, timeout)
                checks = _validate(src, src.dest)
                origin = "downloaded"
                break
            except (urllib.error.URLError, socket.timeout, OSError, DownloadError) as exc:
                last_exc = exc
                if src.dest.exists():
                    src.dest.unlink()
                time.sleep(backoff * min(2**attempt, 10))
        if origin is None:
            manual = src.manual_path()
            if manual.exists():
                shutil.copy2(manual, src.dest)
                checks = _validate(src, src.dest)
                origin = "manual"
            else:
                raise DownloadError(
                    f"Could not download {src.name} from {src.url} after {retries} attempts "
                    f"({last_exc}). Download it manually and place it at {manual}"
                )
    return FileRecord(
        kind=src.kind,
        name=src.name,
        url=src.url,
        path=str(src.dest.relative_to(paths.ROOT)),
        size=src.dest.stat().st_size,
        sha256=_hash(src.dest, "sha256"),
        origin=origin,
        validated_against=checks,
        recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def plan_sources(first_year: int, last_year: int, listing: dict[str, tuple[int, str]]) -> list[SourceFile]:
    srcs = []
    for name in trip_file_names(first_year, last_year):
        size, etag = listing.get(name, (None, None))
        srcs.append(SourceFile("trips", name, TRIP_BUCKET + name, paths.RAW_TRIPS / name, size, etag))
    for y in range(first_year, last_year + 1):
        name = f"724050-13743-{y}.gz"
        srcs.append(SourceFile("weather", name, ISD_URL.format(year=y), paths.RAW_WEATHER / name))
    srcs.append(SourceFile("uci", "bike_sharing_dataset.zip", UCI_URL, paths.RAW_UCI / "bike_sharing_dataset.zip"))
    return srcs


def download_all(first_year: int = 2011, last_year: int = 2024, workers: int = 4, timeout: float = 60.0) -> dict:
    paths.ensure_dirs()
    listing = fetch_bucket_listing()
    srcs = plan_sources(first_year, last_year, listing)
    records: list[FileRecord] = []
    failures: list[str] = []

    def job(s: SourceFile):
        try:
            rec = obtain(s, timeout=timeout)
            print(f"[download] {rec.origin:10s} {s.name} ({rec.size/1e6:.1f} MB) checks={rec.validated_against}")
            return rec, None
        except DownloadError as exc:
            print(f"[download] FAILED {s.name}: {exc}")
            return None, f"{s.kind}:{s.name}: {exc}"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for rec, err in pool.map(job, srcs):
            if rec:
                records.append(rec)
            if err:
                failures.append(err)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "years": [first_year, last_year],
        "bucket_listing_available": bool(listing),
        "files": [asdict(r) for r in sorted(records, key=lambda r: (r.kind, r.name))],
        "failures": failures,
    }
    (paths.RAW / "SOURCES.json").write_text(json.dumps(manifest, indent=2))
    return manifest
