"""Build the hatchery -> section distance tables: road (OSRM), straight-line, and co-op nearest sections.

This script builds the data; notebooks/travel_arcs.ipynb only loads these tables to draw maps and validate.

Inputs : data/processed/trout_hatcheries.gpkg        10 trout hatcheries (from notebooks/01_data_prep.ipynb)
         data/processed/sections.parquet             Nate's 1,045 stocked sections, keyed on section_id
         data/processed/pa_trout.gpkg (sections)     section lines (gitignored; rebuilt by Nate's scripts 01-02)
         data/raw/Coop_nurseries.geojson             165 co-op nurseries
Outputs: data/processed/hatchery_to_section_road_distance.{parquet,csv}   road table (model input, committed)
         data/interim/hatchery_to_section_road_mi_matrix.csv              road DISTANCE (miles), wide
         data/interim/hatchery_to_section_road_min_matrix.csv             DRIVE TIME (minutes), wide
         data/interim/hatchery_to_section_distance_long.csv               straight-line distance, long
         data/interim/hatchery_to_section_distance_matrix.csv             straight-line distance (km), wide
         data/interim/coop_nurseries_nearest_streams.csv                  2 nearest sections per co-op
         logs/06_road_distances.log

Run it with VS Code's "Run Python File" button, or cell by cell with the "Run Cell" links above each # %%.
The road table comes from the public OSRM server (router.project-osrm.org). It's queried only when the
processed parquet doesn't exist yet, or when REFRESH = True below.
"""
# %% Setup
import logging
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

REFRESH = False       # True = re-query OSRM even if the road table already exists
CRS_M = 5070          # CONUS Albers, meters (straight-line distances)
N_NEAREST = 2         # nearest sections kept per co-op nursery
KM_PER_MI = 1.609344
OSRM_URL = "https://router.project-osrm.org/table/v1/driving/"
BATCH = 100           # sections per request (10 hatcheries + 100 points fits the server limit)
PAUSE_S = 1.5         # server policy: at most 1 request per second

try:
    ROOT = Path(__file__).resolve().parents[1]
except NameError:     # running cell by cell in VS Code's interactive window: find the repo root
    ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / ".git").exists())
RAW, INTERIM, PROCESSED = ROOT / "data" / "raw", ROOT / "data" / "interim", ROOT / "data" / "processed"
LOG_DIR = ROOT / "logs"
ROAD_PARQUET = PROCESSED / "hatchery_to_section_road_distance.parquet"
ROAD_CSV = PROCESSED / "hatchery_to_section_road_distance.csv"   # csv copy of the same rows

LOG_DIR.mkdir(exist_ok=True)
log = logging.getLogger("06_road_distances")
log.setLevel(logging.INFO)
log.handlers.clear()
for handler in (logging.FileHandler(LOG_DIR / "06_road_distances.log", mode="w", encoding="utf-8"),
                logging.StreamHandler()):
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)


# %% Load inputs (all in the same projected CRS)
hatcheries = gpd.read_file(PROCESSED / "trout_hatcheries.gpkg").to_crs(CRS_M)
coop_nurseries = gpd.read_file(RAW / "Coop_nurseries.geojson").to_crs(CRS_M)
sections = gpd.read_file(PROCESSED / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]].merge(
    pd.read_parquet(PROCESSED / "sections.parquet"), on="section_id", validate="one_to_one"
).to_crs(CRS_M)
log.info("loaded %d hatcheries, %d co-op nurseries, %d sections", len(hatcheries), len(coop_nurseries), len(sections))


# %% Straight-line distance: every hatchery to every section (nearest point on the section line)
frames = []
for h in hatcheries.itertuples():
    d_km = sections.distance(h.geometry) / 1000
    frames.append(pd.DataFrame({
        "hatchery_id": h.ID,
        "hatchery": h.NAME,
        "county": h.COUNTY,
        "section_id": sections["section_id"].values,
        "water_name": sections["water_name"].values,
        "dist_km": d_km.round(3).values,
        "dist_mi": (d_km / KM_PER_MI).round(3).values,
    }))
hatchery_dist_long = pd.concat(frames, ignore_index=True)
hatchery_dist_long.to_csv(INTERIM / "hatchery_to_section_distance_long.csv", index=False)
hatchery_dist_long.pivot(index="hatchery", columns="section_id", values="dist_km").to_csv(
    INTERIM / "hatchery_to_section_distance_matrix.csv"
)
log.info("straight-line table: %d rows (%d hatcheries x %d sections)",
         len(hatchery_dist_long), len(hatcheries), len(sections))


# %% Co-op nurseries: the N nearest sections to each (straight-line; context for maps, not a model input)
rows = []
for h in coop_nurseries.itertuples():
    d = sections.distance(h.geometry)                      # meters, to nearest point on each section line
    near = sections.assign(dist_m=d).sort_values("dist_m").head(N_NEAREST)
    for rank, s in enumerate(near.itertuples(), start=1):
        rows.append({
            "nursery_id": h.ID,
            "nursery": h.NURSERY_NA,
            "county": h.COUNTY,
            "section_id": s.section_id,
            "water_name": s.water_name,
            "rank": rank,
            "dist_km": round(s.dist_m / 1000, 2),
        })
coop_nearest = pd.DataFrame(rows)
coop_nearest.to_csv(INTERIM / "coop_nurseries_nearest_streams.csv", index=False)
log.info("co-op nearest sections: %d rows (%d nurseries x %d)", len(coop_nearest), len(coop_nurseries), N_NEAREST)


# %% Road distance and drive time: every hatchery to every section, via the OSRM table service
# Column guide (road_mi and road_min look alike but are different measures):
#   road_km / road_mi = DISTANCE of the route (kilometers / miles)
#   road_min          = DRIVE TIME of the same route (minutes), from OSRM's passenger-car speeds


def osrm_table(src_lonlat, dst_lonlat):
    """Distances (m) and durations (s) from each source to each destination, as OSRM JSON."""
    coords = ";".join(f"{x:.6f},{y:.6f}" for x, y in src_lonlat + dst_lonlat)
    n_src = len(src_lonlat)
    r = requests.get(
        OSRM_URL + coords,
        params={
            "sources": ";".join(map(str, range(n_src))),
            "destinations": ";".join(map(str, range(n_src, n_src + len(dst_lonlat)))),
            "annotations": "distance,duration",
        },
        timeout=60,
    )
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "Ok":
        raise RuntimeError(f"OSRM error: {j.get('code')} {j.get('message')}")
    return j


if ROAD_PARQUET.exists() and not REFRESH:
    road = pd.read_parquet(ROAD_PARQUET)
    log.info("road table: loaded the saved copy (%d rows); set REFRESH = True to re-query OSRM", len(road))
else:
    src = list(zip(hatcheries["Long_"], hatcheries["Lat"]))
    road_frames = []
    for start in range(0, len(sections), BATCH):
        batch = sections.iloc[start:start + BATCH]
        j = osrm_table(src, list(zip(batch["mid_lon"], batch["mid_lat"])))

        dist_m = np.array(j["distances"], dtype=float)   # route DISTANCE in meters; rows = hatcheries, cols = sections; no route -> NaN
        dur_s = np.array(j["durations"], dtype=float)    # route DRIVE TIME in seconds
        snap_m = [d["distance"] for d in j["destinations"]]

        for i, h in enumerate(hatcheries.itertuples()):
            road_frames.append(pd.DataFrame({
                "hatchery_id": h.ID,
                "hatchery": h.NAME,
                "county": h.COUNTY,
                "section_id": batch["section_id"].values,
                "water_name": batch["water_name"].values,
                "road_km": (dist_m[i] / 1000).round(3),                   # DISTANCE, kilometers
                "road_mi": (dist_m[i] / 1000 / KM_PER_MI).round(3),       # DISTANCE, miles (model cost input)
                "road_min": (dur_s[i] / 60).round(1),                     # DRIVE TIME, minutes (not miles)
                "snap_m": np.round(snap_m, 1),                            # section midpoint -> nearest road, meters
                "hatchery_snap_m": round(j["sources"][i]["distance"], 1),  # hatchery -> nearest road, meters
            }))
        log.info("OSRM: sections %d-%d done", start, start + len(batch) - 1)
        time.sleep(PAUSE_S)

    road = pd.concat(road_frames, ignore_index=True)
    road.to_parquet(ROAD_PARQUET, index=False)
    road.to_csv(ROAD_CSV, index=False)
    log.info("road table: queried OSRM and wrote %d rows to %s (+ csv)", len(road), ROAD_PARQUET.relative_to(ROOT))

log.info("road table: %d pairs with no route", road["road_km"].isna().sum())


# %% Wide road matrices: one row per hatchery, one column per section_id (views of the road table)
road.pivot(index="hatchery", columns="section_id", values="road_mi").to_csv(      # DISTANCE (miles)
    INTERIM / "hatchery_to_section_road_mi_matrix.csv"
)
road.pivot(index="hatchery", columns="section_id", values="road_min").to_csv(     # DRIVE TIME (minutes)
    INTERIM / "hatchery_to_section_road_min_matrix.csv"
)
log.info("wrote the road distance (mi) and drive time (min) matrices to data/interim")
