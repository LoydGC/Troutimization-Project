"""Road distance and drive time between every pair of 2026-stocked sections, via the public OSRM table service.

Why: clustering sections by truck run under a distance cap, and a real detour charge, need section-to-section
distances. Nate's script 10 approximates them as straight-line miles between section midpoints x circuity_factor (1.3).

Inputs : data/processed/sections.parquet     section_id, mid_lat, mid_lon, latest_year (Nate's midpoints; the 1,022
                                             sections stocked in 2026, the same points 11_road_distances.py routes to)
         data/processed/hatchery_to_section_road_distance.parquet   only to check OSRM's snapping is unchanged
Outputs: data/processed/section_to_section_road_distance.parquet   one row per ordered pair (1,022 x 1,022 = 1,044,484
             rows: from_section_id, to_section_id, road_km, road_mi, road_min). Parquet only: a csv copy would be ~50 MB
         outputs/tables/section_road_distance/validation.csv, circuity_by_distance.csv
         data/interim/section_road_blocks/    one file per request (gitignored), so an interrupted run resumes
         logs/12_section_road_distances.log

Requests: 11 x 11 = 121 blocks of 100 x 100 sections to router.project-osrm.org (the server takes up to ~200
coordinates per request), 1.5 s apart (its policy is at most 1 per second). Distances are for OSRM's fastest route.
Routes run between the road points the midpoints snap to (snap distance is in the hatchery table's snap_m).

    python scripts/12_section_road_distances.py [--limit N] [--refresh]
      --limit N   use only the first N sections and write to data/interim (a quick test; its blocks are reused)
      --refresh   re-query blocks even if they're already cached
"""
# %% Setup
from __future__ import annotations

import argparse
import logging
import math
import sys

import numpy as np
import pandas as pd

from common import INTERIM_DIR, LOG_DIR, PROCESSED_DIR, ROOT, PoliteSession, ServerRefused, setup_logging

OSRM_URL = "https://router.project-osrm.org/table/v1/driving/"
BLOCK = 100            # sections per side of a block: 100 sources + 100 destinations = 200 coordinates
PAUSE_S = 1.5          # server policy: at most 1 request per second
KM_PER_MI = 1.609344
BLOCK_DIR = INTERIM_DIR / "section_road_blocks"
TABLE_DIR = ROOT / "outputs" / "tables" / "section_road_distance"
OUT = PROCESSED_DIR / "section_to_section_road_distance.parquet"

log = logging.getLogger("12_section_road_distances")

ap = argparse.ArgumentParser()
ap.add_argument("--limit", type=int, help="use only the first N sections (test run; output goes to data/interim)")
ap.add_argument("--refresh", action="store_true", help="re-query blocks even if cached")
args = ap.parse_args()
setup_logging("12_section_road_distances")


# %% Sections (the 2026-stocked ones, in file order)
sections = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "mid_lat", "mid_lon", "latest_year"])
sections = sections[sections["latest_year"] == 2026].reset_index(drop=True)
if args.limit:
    sections = sections.iloc[: args.limit].reset_index(drop=True)
n = len(sections)
ids = sections["section_id"].to_numpy()
lonlat = list(zip(sections["mid_lon"], sections["mid_lat"]))
n_blocks = math.ceil(n / BLOCK)
log.info("%d sections -> %d x %d = %d blocks of up to %d x %d", n, n_blocks, n_blocks, n_blocks ** 2, BLOCK, BLOCK)
BLOCK_DIR.mkdir(parents=True, exist_ok=True)


# %% Query OSRM, one block (BLOCK sources x BLOCK destinations) per request; each block is cached to disk
session = PoliteSession(min_interval=PAUSE_S, cache_path=None)   # 1 request per 1.5 s, retries with backoff; no HTTP cache


def fetch_block(i: int, j: int) -> dict:
    src, dst = slice(i * BLOCK, (i + 1) * BLOCK), slice(j * BLOCK, (j + 1) * BLOCK)
    pts = lonlat[src] + lonlat[dst]
    ns = len(lonlat[src])
    coords = ";".join(f"{x:.6f},{y:.6f}" for x, y in pts)
    r = session.get(OSRM_URL + coords, {
        "sources": ";".join(map(str, range(ns))),
        "destinations": ";".join(map(str, range(ns, len(pts)))),
        "annotations": "distance,duration",
    })
    j_ = r.json()
    if j_.get("code") != "Ok":
        raise RuntimeError(f"OSRM error for block {i},{j}: {j_.get('code')} {j_.get('message')}")
    return dict(
        dist=np.array(j_["distances"], dtype=float),          # meters; None (no route) becomes nan
        dur=np.array(j_["durations"], dtype=float),           # seconds
        src_snap=np.array([w["distance"] for w in j_["sources"]]),
        dst_snap=np.array([w["distance"] for w in j_["destinations"]]),
        src_ids=ids[src], dst_ids=ids[dst],
    )


D = np.full((n, n), np.nan); T = np.full((n, n), np.nan); snap = np.full(n, np.nan)
n_new = 0
try:
    for i in range(n_blocks):
        for j in range(n_blocks):
            f = BLOCK_DIR / f"{i:02d}_{j:02d}.npz"
            b = None
            if f.exists() and not args.refresh:
                z = np.load(f, allow_pickle=True)
                if np.array_equal(z["src_ids"], ids[i * BLOCK:(i + 1) * BLOCK]) and np.array_equal(z["dst_ids"], ids[j * BLOCK:(j + 1) * BLOCK]):
                    b = {k: z[k] for k in z.files}          # cached block for the same sections
            if b is None:
                b = fetch_block(i, j)
                np.savez_compressed(f, **b)
                n_new += 1
                log.info("block %02d,%02d queried (%d queried so far)", i, j, n_new)
            D[i * BLOCK:(i + 1) * BLOCK, j * BLOCK:(j + 1) * BLOCK] = b["dist"]
            T[i * BLOCK:(i + 1) * BLOCK, j * BLOCK:(j + 1) * BLOCK] = b["dur"]
            snap[j * BLOCK:(j + 1) * BLOCK] = b["dst_snap"]
except (ServerRefused, RuntimeError, KeyboardInterrupt) as e:
    log.error("STOPPED: %r. Finished blocks are cached in %s; rerun to resume.", e, BLOCK_DIR.relative_to(ROOT))
    sys.exit(1)
log.info("requests made this run: %d (rest came from the block cache)", n_new)


# %% Assemble the long table
km = D / 1000
long = pd.DataFrame({
    "from_section_id": np.repeat(ids, n),
    "to_section_id": np.tile(ids, n),
    "road_km": km.ravel().round(3).astype("float32"),
    "road_mi": (km / KM_PER_MI).ravel().round(3).astype("float32"),
    "road_min": (T / 60).ravel().round(1).astype("float32"),
})
out = INTERIM_DIR / "section_to_section_road_distance_TEST.parquet" if args.limit else OUT
long.to_parquet(out, index=False)
log.info("wrote %d rows to %s (%.1f MB)", len(long), out.relative_to(ROOT), out.stat().st_size / 1e6)


# %% Validation
off = ~np.eye(n, dtype=bool)
# straight-line miles between the same midpoints (projected, meters)
from pyproj import Transformer
xy = np.array(Transformer.from_crs("EPSG:4326", "EPSG:26918", always_xy=True).transform(sections["mid_lon"].to_numpy(), sections["mid_lat"].to_numpy())).T
straight_km = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1)) / 1000
tol_km = (snap[:, None] + snap[None, :]) / 1000     # a route starts and ends at the snapped road points
ratio = km[off] / straight_km[off]
sym = np.abs(km - km.T)[off] / np.maximum(km, km.T)[off].clip(min=0.05)
rng = np.random.default_rng(0)
a, b_, c = (rng.integers(0, n, 50_000) for _ in range(3))
tri = T[a, c] > T[a, b_] + T[b_, c] + 30            # drive time (s): a shortcut through b shouldn't beat the direct route
hatch = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet", columns=["section_id", "snap_m"]).drop_duplicates("section_id").set_index("section_id").snap_m
snap_diff = np.abs(pd.Series(snap, index=ids).reindex(hatch.index).sub(hatch)).max()


def status(ok, warn_only=False):
    return "PASS" if ok else ("WARN" if warn_only else "FAIL")


checks = [
    ("Row count (sections squared)", f"{n * n:,}", f"{len(long):,}", status(len(long) == n * n)),
    ("Duplicate ordered pairs", "0", int(long.duplicated(["from_section_id", "to_section_id"]).sum()), None),
    ("Pairs with no road route", "0", int(np.isnan(D).sum()), None),
    ("Diagonal (section to itself) is 0", "0", float(np.nanmax(np.abs(np.diag(D)))), None),
    ("Snap distances match the hatchery road table (max diff, m)", "under 1", round(float(snap_diff), 2), None),
    ("Road shorter than straight-line (beyond snap)", "0", int((km[off] < straight_km[off] - tol_km[off]).sum()), None),
    ("Median road / straight-line ratio", "1.2 to 1.8", f"{np.median(ratio):.2f}", status(1.2 <= np.median(ratio) <= 1.8)),
    ("Median asymmetry |A to B - B to A| / larger", "under 5%", f"{100 * np.median(sym):.1f}%", status(np.median(sym) < 0.05, True)),
    ("Triangle check on drive time (share of 50,000 random triples that fail)", "under 0.1%", f"{100 * tri.mean():.3f}%", status(tri.mean() < 0.001, True)),
]
checks = [(c_, e, r_, s_ if s_ else status(str(r_) in ("0", "0.0") or (c_.startswith("Snap") and r_ < 1))) for c_, e, r_, s_ in checks]
validation = pd.DataFrame(checks, columns=["check", "expected", "result", "status"])
print(validation.to_string(index=False))

bucket = pd.cut(straight_km[off] / KM_PER_MI, [0, 5, 10, 20, 40, 80, 500], labels=["< 5 mi", "5-10", "10-20", "20-40", "40-80", "80+"])
circ = (pd.DataFrame({"straight_mi": straight_km[off] / KM_PER_MI, "road_mi": km[off] / KM_PER_MI, "ratio": ratio, "b": bucket})
        .groupby("b", observed=True).agg(pairs=("ratio", "size"), median_ratio=("ratio", "median"),
                                         p10=("ratio", lambda x: x.quantile(.1)), p90=("ratio", lambda x: x.quantile(.9))).round(2).reset_index()
        .rename(columns={"b": "straight_line_distance"}))
print(circ.to_string(index=False))
if not args.limit:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    validation.to_csv(TABLE_DIR / "validation.csv", index=False)
    circ.to_csv(TABLE_DIR / "circuity_by_distance.csv", index=False)
for _, row in validation.iterrows():
    log.info("%s | expected %s | result %s | %s", *row)
