"""Co-op nursery inputs with fallbacks, so a missing raw file never stops a pipeline script.

Co-ops are not in the model (team decision 2026-09-27); these inputs only feed the coop_stocked flag, co-op distances and
maps. Each loader tries, in order:
  1. the local file (data/raw is git-ignored, so a fresh clone does not have it),
  2. a copy saved by an earlier download under data/raw/<source>/<date>/,
  3. a polite download (1 request per second, backoff; common.PoliteSession) from the public source below, saved untouched with
     a row in data/raw/manifest.csv (CLAUDE.md rules 2 and 3).
If all three fail it logs a warning and returns None, and the caller skips its co-op step.

Sources:
  nursery locations   PFBC Cooperative Nurseries layer on PASDA, dataset 970 (2020 release)
                      https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=970
  stocking listings   PFBC's co-op nursery stocking spreadsheet (cnu-stockings-website.xlsx)
"""
from __future__ import annotations

import io
import logging
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from common import RAW_DIR, PoliteSession, save_raw

PASDA_ZIP = "https://www.pasda.psu.edu/download/pafish/CooperativeNurseries202002.zip"
PFBC_XLSX = ("https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/fishing/stocking/coop-nurseries/"
             "cnu-stockings-website.xlsx")
LOCAL_NURSERIES = "Coop_nurseries.geojson"

log = logging.getLogger("coop_inputs")


def _get(url: str) -> bytes:
    return PoliteSession(min_interval=1.0).get(url).content


def _normalize(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Upper-case the field names (shapefiles and geojson differ) and make sure the columns the scripts use exist."""
    g = g.rename(columns={c: c.upper() for c in g.columns if c != "geometry"})
    for need in ("NURSERY_NA", "SPONSOR_NA"):
        if need not in g.columns:
            raise ValueError(f"co-op nursery layer has no {need} field (has {sorted(g.columns)})")
    if "COUNTY" not in g.columns:
        g["COUNTY"] = ""
    if "ID" not in g.columns:
        g["ID"] = range(1, len(g) + 1)
    return g


def load_coop_nurseries(raw_dir: Path = RAW_DIR, download: bool = True, fetch=_get) -> gpd.GeoDataFrame | None:
    """Co-op nursery points (fields NURSERY_NA, SPONSOR_NA, COUNTY, ID, geometry), or None if no source works."""
    local = raw_dir / LOCAL_NURSERIES
    if local.exists():
        return _normalize(gpd.read_file(local))
    saved = sorted((raw_dir / "pasda_coop_nurseries").glob("*/*.zip"))
    try:
        if saved:
            log.info("co-op nurseries: using the earlier download %s", saved[-1].relative_to(raw_dir))
            return _normalize(gpd.read_file(saved[-1]))
        if not download:
            log.warning("co-op nurseries: %s not found and downloading is off", LOCAL_NURSERIES)
            return None
        log.info("co-op nurseries: %s not found; downloading %s", LOCAL_NURSERIES, PASDA_ZIP)
        data = fetch(PASDA_ZIP)
        if data[:2] != b"PK" or not zipfile.is_zipfile(io.BytesIO(data)):
            raise ValueError("the download is not a zip file")
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.zip"
            probe.write_bytes(data)
            g = _normalize(gpd.read_file(probe))
        save_raw("pasda_coop_nurseries", PASDA_ZIP.rsplit("/", 1)[-1], data, PASDA_ZIP, records=len(g), raw_dir=raw_dir)
        return g
    except Exception as e:  # noqa: BLE001 - any failure means "unavailable", never a crash
        log.warning("co-op nurseries unavailable (%s: %s); the caller will skip its co-op step", type(e).__name__, e)
        return None


def latest_coop_stockings(raw_dir: Path = RAW_DIR, download: bool = True, fetch=_get) -> Path | None:
    """Path to the latest co-op stocking spreadsheet under data/raw/pfbc_coop/<date>/, downloading it if absent; None if unavailable."""
    found = sorted((raw_dir / "pfbc_coop").glob("*/cnu-stockings-website.xlsx"))
    if found:
        return found[-1]
    if not download:
        log.warning("co-op stockings spreadsheet not found and downloading is off")
        return None
    try:
        log.info("co-op stockings spreadsheet not found; downloading %s", PFBC_XLSX)
        data = fetch(PFBC_XLSX)
        if data[:2] != b"PK":
            raise ValueError("the download is not an xlsx file")
        n = len(pd.read_excel(io.BytesIO(data), header=3))
        return save_raw("pfbc_coop", "cnu-stockings-website.xlsx", data, PFBC_XLSX, records=n, raw_dir=raw_dir)
    except Exception as e:  # noqa: BLE001
        log.warning("co-op stockings spreadsheet unavailable (%s: %s); the caller will skip the co-op step", type(e).__name__, e)
        return None
