"""Download the PFBC stocked-section, wild-trout and hatchery GIS layers.

Raw pages -> data/raw/pfbc_gis/<date>/ (+ data/raw/manifest.csv); parsed layers -> data/interim/pfbc_gis/<name>.parquet.
Layers already parsed are skipped unless --refresh (which also bypasses the HTTP cache).

    .venv/bin/python scripts/01_download_pfbc_layers.py [--refresh] [--only stocked_2026 class_a ...]
"""
from __future__ import annotations

import argparse
import logging

import geopandas as gpd

from common import INTERIM_DIR, PoliteSession, ServerRefused, fetch_layer, setup_logging

FBWEB = "https://fbweb.pa.gov/arcgis/rest/services/PFBC_Map_Services"
PASDA = "https://mapservices.pasda.psu.edu/server/rest/services/pasda/PAFishBoat/MapServer"
SOURCE = "pfbc_gis"

LAYERS = {
    # stocked stream sections with per-species counts (fbweb; PASDA's stocked layer has no counts)
    "stocked_2026": f"{FBWEB}/TroutStockedSections_2026/MapServer/0",
    "stocked_2025": f"{FBWEB}/TroutStocked2025/MapServer/2",
    "stocked_2024": f"{FBWEB}/TroutStocked2024/MapServer/0",
    # wild-trout context (PASDA mirror of PFBC layers)
    "class_a": f"{PASDA}/9",
    "nat_repro": f"{PASDA}/25",
    "wilderness": f"{PASDA}/31",
    # PFBC state fish hatchery locations: the authoritative hatchery set (decision 2026-09-29). Published on
    # PennMAP as "State Fish Hatcheries" (hub item 25b8cd8915674873add59c31c5bdfc12, owner PFBC_GIS_Admin2)
    "hatcheries": f"{FBWEB}/Hatcheries/MapServer/0",
}

log = logging.getLogger(__name__)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download even if already parsed")
    ap.add_argument("--only", nargs="+", choices=LAYERS, help="subset of layers")
    args = ap.parse_args()
    setup_logging("01_download_pfbc_layers")

    out_dir = INTERIM_DIR / SOURCE
    out_dir.mkdir(parents=True, exist_ok=True)
    session = PoliteSession()

    for name in args.only or LAYERS:
        out = out_dir / f"{name}.parquet"
        if out.exists() and not args.refresh:
            log.info("%s: already parsed at %s, skipping (use --refresh)", name, out.relative_to(INTERIM_DIR.parent.parent))
            continue
        try:
            if args.refresh and hasattr(session.http, "cache_disabled"):
                with session.http.cache_disabled():
                    fc = fetch_layer(LAYERS[name], SOURCE, name, session=session)
            else:
                fc = fetch_layer(LAYERS[name], SOURCE, name, session=session)
        except ServerRefused as e:
            log.error("STOP: server refused (%s). Not retrying further; report before continuing.", e)
            raise SystemExit(1)
        gdf = gpd.GeoDataFrame.from_features(fc["features"], crs="EPSG:4326")
        n_null_geom = int(gdf.geometry.isna().sum() + gdf.geometry.is_empty.sum())
        gdf.to_parquet(out)
        log.info("%s: %d rows, %d columns, %d null/empty geometries, geom types %s -> %s", name, len(gdf),
                 gdf.shape[1], n_null_geom, gdf.geom_type.value_counts().to_dict(), out.name)


if __name__ == "__main__":
    main()
