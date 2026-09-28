"""Shared helpers: a polite cached HTTP session, raw-file saving with a manifest, and an ArcGIS REST pager.

Rules from CLAUDE.md enforced here: max 1 request/second per host, exponential backoff, cache so re-runs
don't re-fetch, every raw response saved untouched with its URL/timestamp/count in data/raw/manifest.csv,
and a STOP (ServerRefused) when a server keeps failing.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
import requests_cache

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"
PROCESSED_DIR = ROOT / "data" / "processed"
LOG_DIR = ROOT / "logs"
CACHE_PATH = INTERIM_DIR / "http_cache"

USER_AGENT = "PA trout stocking class project (github.com/LoydGC/Troutimization-Project)"
RETRY_STATUS = {429, 500, 502, 503, 504}
MANIFEST_FIELDS = ["retrieved_at", "source", "path", "url", "records", "bytes", "sha256"]

log = logging.getLogger(__name__)


class ServerRefused(RuntimeError):
    """A server kept failing after retries. Per CLAUDE.md: stop and report, don't push harder."""


class ArcGISError(RuntimeError):
    """ArcGIS returned HTTP 200 with an {"error": ...} body."""


def _arcgis_error(response) -> dict | None:
    if "json" not in response.headers.get("Content-Type", "") and not response.content.lstrip().startswith(b"{"):
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return body.get("error") if isinstance(body, dict) else None


def _cacheable(response) -> bool:
    return response.status_code == 200 and _arcgis_error(response) is None


class PoliteSession:
    """requests-cache session with a per-host minimum interval and retries with exponential backoff."""

    def __init__(self, min_interval: float = 1.0, max_retries: int = 4, backoff: float = 2.0,
                 cache_path: Path | str | None = CACHE_PATH, timeout: float = 120):
        self.min_interval, self.max_retries, self.backoff, self.timeout = min_interval, max_retries, backoff, timeout
        if cache_path is None:
            self.http = requests.Session()
        else:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            self.http = requests_cache.CachedSession(
                str(cache_path), backend="sqlite", expire_after=requests_cache.NEVER_EXPIRE, filter_fn=_cacheable)
        self.http.headers["User-Agent"] = USER_AGENT
        self._last_network: dict[str, float] = {}

    def get(self, url: str, params: dict | None = None) -> requests.Response:
        host = urlparse(url).netloc
        problem = None
        for attempt in range(self.max_retries + 1):
            wait = self._last_network.get(host, float("-inf")) + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.http.get(url, params=params, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as e:
                r, problem = None, repr(e)
            if r is None or not getattr(r, "from_cache", False):
                self._last_network[host] = time.monotonic()
            if r is not None:
                if r.status_code == 200:
                    err = _arcgis_error(r)
                    if err is None:
                        return r
                    problem = f"ArcGIS error {err}"
                elif r.status_code in RETRY_STATUS:
                    problem = f"HTTP {r.status_code}"
                else:
                    r.raise_for_status()
            if attempt < self.max_retries:
                delay = self.backoff ** attempt
                log.warning("%s (attempt %d/%d): %s; retrying in %.0fs",
                            url, attempt + 1, self.max_retries + 1, problem, delay)
                time.sleep(delay)
        raise ServerRefused(f"{url} params={params} failed after {self.max_retries + 1} attempts: {problem}")


def full_url(url: str, params: dict | None = None) -> str:
    return requests.Request("GET", url, params=params).prepare().url


def save_raw(source: str, name: str, content: bytes | str, url: str, records: int | None = None,
             raw_dir: Path = RAW_DIR, date: str | None = None) -> Path:
    """Write content untouched to raw_dir/<source>/<date>/<name> and append a row to raw_dir/manifest.csv.

    Idempotent: if the file already exists with identical bytes, nothing is rewritten or re-logged.
    """
    data = content.encode("utf-8") if isinstance(content, str) else content
    date = date or datetime.now().strftime("%Y-%m-%d")
    path = raw_dir / source / date / name
    digest = hashlib.sha256(data).hexdigest()
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    manifest = raw_dir / "manifest.csv"
    new = not manifest.exists()
    with manifest.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if new:
            w.writeheader()
        w.writerow({
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "path": path.relative_to(raw_dir).as_posix(),
            "url": url,
            "records": "" if records is None else records,
            "bytes": len(data),
            "sha256": digest,
        })
    return path


def fetch_layer(layer_url: str, source: str, name: str, session: PoliteSession | None = None,
                raw_dir: Path = RAW_DIR, where: str = "1=1") -> dict:
    """Download every feature of an ArcGIS MapServer/FeatureServer layer as one GeoJSON FeatureCollection.

    Saves the layer metadata and each page raw, pages with resultOffset/resultRecordCount ordered by the
    object-id field, and asserts the downloaded count equals the server's count with no duplicate ids.
    """
    session = session or PoliteSession()
    layer_url = layer_url.rstrip("/")

    meta_params = {"f": "pjson"}
    r = session.get(layer_url, meta_params)
    meta = r.json()
    save_raw(source, f"{name}_meta.json", r.content, full_url(layer_url, meta_params), raw_dir=raw_dir)

    formats = meta.get("supportedQueryFormats", "").lower()
    if "geojson" not in formats:
        raise ArcGISError(f"{layer_url} does not support f=geojson (supportedQueryFormats={formats!r})")
    if not meta.get("advancedQueryCapabilities", {}).get("supportsPagination", False):
        raise ArcGISError(f"{layer_url} does not support pagination; needs an objectIds-based fetch")
    oid_field = meta.get("objectIdField") or next(
        (f["name"] for f in meta.get("fields", []) if f.get("type") == "esriFieldTypeOID"), None)
    if oid_field is None:
        raise ArcGISError(f"{layer_url} has no object-id field")
    page_size = int(meta.get("maxRecordCount") or 1000)

    query_url = f"{layer_url}/query"
    count_params = {"where": where, "returnCountOnly": "true", "f": "json"}
    r = session.get(query_url, count_params)
    expected = int(r.json()["count"])
    save_raw(source, f"{name}_count.json", r.content, full_url(query_url, count_params), records=expected,
             raw_dir=raw_dir)

    features: list[dict] = []
    offset, page = 0, 0
    while offset < expected:
        params = {"where": where, "outFields": "*", "outSR": "4326", "f": "geojson",
                  "orderByFields": oid_field, "resultOffset": offset, "resultRecordCount": page_size}
        r = session.get(query_url, params)
        batch = r.json().get("features", [])
        save_raw(source, f"{name}_page{page:03d}.geojson", r.content, full_url(query_url, params),
                 records=len(batch), raw_dir=raw_dir)
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
        page += 1

    ids = [f.get("id", f.get("properties", {}).get(oid_field)) for f in features]
    if len(features) != expected or len(set(ids)) != expected:
        raise AssertionError(f"{name}: server count {expected}, downloaded {len(features)} "
                             f"({len(set(ids))} unique {oid_field})")
    log.info("%s: %d features in %d page(s) from %s", name, len(features), page, layer_url)
    return {"type": "FeatureCollection", "features": features,
            "_meta": {"url": layer_url, "count": expected, "oid_field": oid_field, "fields": meta.get("fields", [])}}


def code_version() -> str:
    """Current commit, plus any scripts/ files that differ from it, so a committed log says what code made it."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.rstrip()
    try:
        head = git("rev-parse", "--short", "HEAD")
        changed = git("status", "--porcelain", "--", "scripts").splitlines()
    except (OSError, subprocess.CalledProcessError):
        return "unknown (not a git checkout)"
    if not changed:
        return f"commit {head}"
    return f"commit {head} + uncommitted changes to {', '.join(line[3:] for line in changed)}"


def setup_logging(script_name: str) -> Path:
    """Log to stdout and logs/<script_name>.log (overwritten each run). The first line is the code version."""
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"{script_name}.log"
    version = code_version()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(path, mode="w")], force=True)
    log.info("%s run from %s", script_name, version)
    return path


def dump_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))
