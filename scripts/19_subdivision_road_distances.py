"""Road distance and drive time from the centroid of every Pennsylvania county subdivision to every stream section.

County subdivisions are PA's municipalities (townships, boroughs, cities, towns): Census's "county subdivision"
level, the minor civil divisions (the geography the 2010 PA state guide describes). The newest vintage is
boundaries as of 1 January 2026, from Census's TIGERweb service tigerWMS_ACS2026 (layer 22). Census's downloadable
TIGER/Line shapefiles stop at 2025 (no TIGER2026 yet, checked 2026-10-03); for PA the two vintages are identical.
The service is pinned to 2026 on purpose: tigerWMS_Current rolls over to the next vintage.

Inputs : https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2026/MapServer/22  (STATE = '42')
             saved untouched to data/raw/census_cousub/<date>/ with manifest rows (CLAUDE.md rule 2)
         data/processed/sections.parquet                 section_id, mid_lat, mid_lon: all 1,045 sections stocked 2024-26
                                                         (the same midpoints, in the same order, as 11_road_distances.py)
         data/processed/county_anglers.csv               county name for each county FIPS
         data/processed/hatchery_to_section_road_distance.parquet   only to check OSRM's snapping is unchanged
Outputs: data/processed/subdivision_to_section_road_distance.parquet   one row per (subdivision, section): 2,567 x 1,045 =
             2,682,515 rows: subdivision_id, section_id, road_km, road_mi, road_min. Parquet only: a csv would be ~150 MB
         data/processed/county_subdivisions.{parquet,csv}    the 2,567 subdivisions: name, county, centroid, Census internal point,
             area, how far the centroid is from a road (road_snap_m)
         data/interim/subdivision_to_section_road_mi_matrix.csv, ..._road_min_matrix.csv   wide views (rows = subdivision_id)
         outputs/tables/subdivision_road_distance/validation.csv, circuity_by_distance.csv
         data/interim/subdivision_road_blocks/    one file per OSRM request (gitignored), so an interrupted run resumes
         logs/19_subdivision_road_distances.log

Centroid: the geometric (area-weighted) centroid of each subdivision's polygon, computed in EPSG:26918 and stored in
EPSG:4326. It can fall outside an oddly shaped subdivision (a township wrapped around a borough): `centroid_in_polygon`
flags those, and Census's internal point (`intpt_lat`, `intpt_lon`, always inside) is kept beside it. OSRM snaps every
point to the nearest road; `road_snap_m` is how far. Direction: from the subdivision (home) to the section (stream).
If a centroid has no route to any section (it snapped to a road fragment cut off from the rest of the network: Pine township,
Armstrong), the script routes from the point of a 250 m grid inside the polygon that is nearest the centroid and does route,
and records it: `origin_lat`/`origin_lon` are the point routed from, `origin_point` says which kind, `origin_shift_m` how far from the centroid.
One row of the Census layer, "County subdivisions not defined" (Lake Erie open water, no land), has nowhere to travel
from and is left out (logged).

Requests: 26 x 11 = 286 blocks of 100 x 100 to router.project-osrm.org, 1.5 s apart (its policy is at most 1 per second),
the same demo server and waiver as script 12 (docs/known_gaps.md § OSRM). Distances are for OSRM's fastest route.

    python scripts/19_subdivision_road_distances.py [--limit N] [--refresh]
      --limit N   use only the first N subdivisions and the first N sections and write to data/interim (a quick test;
                  its blocks are reused by the full run)
      --refresh   re-query OSRM blocks even if they're already cached
"""
# %% Setup
from __future__ import annotations

import argparse
import json
import logging
import math
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point

from common import (INTERIM_DIR, PROCESSED_DIR, RAW_DIR, ROOT, PoliteSession, ServerRefused, fetch_layer, full_url, save_raw,
                    setup_logging)

SERVICE_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2026/MapServer"
LAYER_URL = f"{SERVICE_URL}/22"            # County Subdivisions
VINTAGE_TEXT = "January 1, 2026"           # the service's own description; the script stops if Census changes it
SOURCE = "census_cousub"
PA_FIPS = "42"
CRS_M = 26918                              # NAD83 / UTM 18N, meters (CLAUDE.md: lengths and distances)
OSRM_URL = "https://router.project-osrm.org/table/v1/driving/"
BLOCK = 100                                # points per side of a block: 100 sources + 100 destinations = 200 coordinates
PAUSE_S = 1.5                              # OSRM server policy: at most 1 request per second
KM_PER_MI = 1.609344
BLOCK_DIR = INTERIM_DIR / "subdivision_road_blocks"
TABLE_DIR = ROOT / "outputs" / "tables" / "subdivision_road_distance"
ROAD_OUT = PROCESSED_DIR / "subdivision_to_section_road_distance.parquet"
LOOKUP_OUT = PROCESSED_DIR / "county_subdivisions"          # .parquet and .csv

log = logging.getLogger("19_subdivision_road_distances")

ap = argparse.ArgumentParser()
ap.add_argument("--limit", type=int, help="use only the first N subdivisions and sections (test run; output goes to data/interim)")
ap.add_argument("--refresh", action="store_true", help="re-query OSRM blocks even if cached")
args = ap.parse_args()
setup_logging("19_subdivision_road_distances")


# %% Download the PA county subdivisions (Census TIGERweb, vintage 1 Jan 2026)
census = PoliteSession(min_interval=1.0)         # cached, 1 request/s, backoff; reruns don't re-fetch
r = census.get(SERVICE_URL, {"f": "pjson"})
description = r.json().get("serviceDescription", "")
save_raw(SOURCE, "service_meta.json", r.content, full_url(SERVICE_URL, {"f": "pjson"}))
assert VINTAGE_TEXT in description, f"Census service no longer says '{VINTAGE_TEXT}': {description!r}"
log.info("service: %s", description)
fc = fetch_layer(LAYER_URL, SOURCE, "cousub_pa", session=census, where=f"STATE='{PA_FIPS}'", page_size=250)
cs = gpd.GeoDataFrame.from_features(fc["features"], crs="EPSG:4326")
log.info("downloaded %d PA county subdivisions in %d counties; %d unique GEOID", len(cs), cs["COUNTY"].nunique(), cs["GEOID"].nunique())
assert len(cs) == 2568 and cs["GEOID"].is_unique, "documented count: 2,568 rows (2,567 subdivisions + 1 Lake Erie placeholder)"

placeholder = cs["COUSUB"] == "00000"      # "County subdivisions not defined": Erie County's share of Lake Erie
assert placeholder.sum() == 1 and (cs.loc[placeholder, "AREALAND"] == 0).all()
log.info("left out %d row(s) with no land to travel from: %s (%s, water area %.0f km2)", placeholder.sum(),
         cs.loc[placeholder, "NAME"].iloc[0], cs.loc[placeholder, "GEOID"].iloc[0], cs.loc[placeholder, "AREAWATER"].iloc[0] / 1e6)
cs = cs[~placeholder].sort_values("GEOID").reset_index(drop=True)
log.info("kept %d subdivisions", len(cs))


# %% Centroids (computed in EPSG:26918), and how they compare with Census's own points
m = cs.to_crs(CRS_M)
log.info("invalid polygons: %d; multi-part polygons: %d", int((~m.geometry.is_valid).sum()), int((m.geometry.geom_type == "MultiPolygon").sum()))
cent_m = m.geometry.centroid
lonlat = cent_m.to_crs(4326)
cs["centroid_lon"], cs["centroid_lat"] = lonlat.x.round(6), lonlat.y.round(6)
cs["centroid_in_polygon"] = m.geometry.contains(cent_m).to_numpy()
to_m = Transformer.from_crs("EPSG:4326", f"EPSG:{CRS_M}", always_xy=True)
for pre, lon_c, lat_c in (("cent", "CENTLON", "CENTLAT"), ("intpt", "INTPTLON", "INTPTLAT")):
    x, y = to_m.transform(cs[lon_c].astype(float).to_numpy(), cs[lat_c].astype(float).to_numpy())
    cs[f"_{pre}_off_m"] = np.hypot(x - cent_m.x.to_numpy(), y - cent_m.y.to_numpy())
cs["intpt_lon"], cs["intpt_lat"] = cs["INTPTLON"].astype(float), cs["INTPTLAT"].astype(float)
cs["centroid_to_intpt_m"] = cs["_intpt_off_m"].round(0)
log.info("our centroid vs Census CENTLAT/CENTLON: median %.1f m, max %.1f m", cs["_cent_off_m"].median(), cs["_cent_off_m"].max())
log.info("centroids outside their own polygon: %d of %d (kept, flagged); distance to Census's internal point: median %.0f m, 90th pct %.0f m, max %.0f m",
         int((~cs["centroid_in_polygon"]).sum()), len(cs), cs["centroid_to_intpt_m"].median(), cs["centroid_to_intpt_m"].quantile(.9), cs["centroid_to_intpt_m"].max())

counties = pd.read_csv(PROCESSED_DIR / "county_anglers.csv", usecols=["county", "county_fips"]).assign(county_fips=lambda d: d["county_fips"].astype(str))
cs["county_fips"] = PA_FIPS + cs["COUNTY"]
cs = cs.merge(counties, on="county_fips", how="left", validate="many_to_one")
assert cs["county"].notna().all(), "every county FIPS should match county_anglers.csv"
subs = pd.DataFrame({
    "subdivision_id": cs["GEOID"],                                    # state(2) + county(3) + county subdivision(5)
    "name": cs["NAME"],
    "basename": cs["BASENAME"],
    "type": [n.removeprefix(b).strip() for n, b in zip(cs["NAME"], cs["BASENAME"])],   # township, borough, city, town, municipality
    "county": cs["county"],
    "county_fips": cs["county_fips"],
    "funcstat": cs["FUNCSTAT"],
    "area_land_km2": (cs["AREALAND"].astype(float) / 1e6).round(3),
    "area_water_km2": (cs["AREAWATER"].astype(float) / 1e6).round(3),
    "centroid_lat": cs["centroid_lat"], "centroid_lon": cs["centroid_lon"],
    "centroid_in_polygon": cs["centroid_in_polygon"],
    "intpt_lat": cs["intpt_lat"], "intpt_lon": cs["intpt_lon"],
    "centroid_to_intpt_m": cs["centroid_to_intpt_m"],
    "origin_lat": cs["centroid_lat"], "origin_lon": cs["centroid_lon"],      # the point actually routed from: the centroid unless it has no route
    "origin_point": "centroid",
    "origin_shift_m": 0.0,
})
cent_off = cs["_cent_off_m"].to_numpy()
log.info("type counts: %s", subs["type"].value_counts().to_dict())


# %% Sections (all stocked 2024-26, in file order: the same points as script 11)
sections = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "mid_lat", "mid_lon"])
if args.limit:
    subs, cent_off = subs.iloc[: args.limit].reset_index(drop=True), cent_off[: args.limit]
    sections = sections.iloc[: args.limit].reset_index(drop=True)
n_sub, n_sec = len(subs), len(sections)
sub_ids, sec_ids = subs["subdivision_id"].to_numpy(), sections["section_id"].to_numpy()
src_ll = list(zip(subs["origin_lon"], subs["origin_lat"]))
dst_ll = list(zip(sections["mid_lon"], sections["mid_lat"]))
nb_i, nb_j = math.ceil(n_sub / BLOCK), math.ceil(n_sec / BLOCK)
log.info("%d subdivisions x %d sections = %d pairs -> %d x %d = %d blocks of up to %d x %d", n_sub, n_sec, n_sub * n_sec,
         nb_i, nb_j, nb_i * nb_j, BLOCK, BLOCK)
BLOCK_DIR.mkdir(parents=True, exist_ok=True)


# %% Query OSRM, one block (BLOCK subdivisions x BLOCK sections) per request; each block is cached to disk
osrm = PoliteSession(min_interval=PAUSE_S, cache_path=None)   # 1 request per 1.5 s, retries with backoff; no HTTP cache


def fetch_block(i: int, j: int) -> dict:
    src, dst = slice(i * BLOCK, (i + 1) * BLOCK), slice(j * BLOCK, (j + 1) * BLOCK)
    pts = src_ll[src] + dst_ll[dst]
    ns = len(src_ll[src])
    coords = ";".join(f"{x:.6f},{y:.6f}" for x, y in pts)
    resp = osrm.get(OSRM_URL + coords, {
        "sources": ";".join(map(str, range(ns))),
        "destinations": ";".join(map(str, range(ns, len(pts)))),
        "annotations": "distance,duration",
    }).json()
    if resp.get("code") != "Ok":
        raise RuntimeError(f"OSRM error for block {i},{j}: {resp.get('code')} {resp.get('message')}")
    return dict(
        dist=np.array(resp["distances"], dtype=float),         # meters; None (no route) becomes nan
        dur=np.array(resp["durations"], dtype=float),          # seconds
        src_snap=np.array([w["distance"] for w in resp["sources"]]),
        dst_snap=np.array([w["distance"] for w in resp["destinations"]]),
        src_ids=sub_ids[src], dst_ids=sec_ids[dst],
        src_xy=np.array(src_ll[src]), dst_xy=np.array(dst_ll[dst]),
    )


def cached_block(f, i: int, j: int):
    """The cached block if it was queried for the same ids at the same coordinates, else None."""
    if args.refresh or not f.exists():
        return None
    z = np.load(f, allow_pickle=True)
    same = (np.array_equal(z["src_ids"], sub_ids[i * BLOCK:(i + 1) * BLOCK]) and np.array_equal(z["dst_ids"], sec_ids[j * BLOCK:(j + 1) * BLOCK])
            and np.allclose(z["src_xy"], np.array(src_ll[i * BLOCK:(i + 1) * BLOCK])) and np.allclose(z["dst_xy"], np.array(dst_ll[j * BLOCK:(j + 1) * BLOCK])))
    return {k: z[k] for k in z.files} if same else None


GRID_M = 250                                                   # candidate spacing for the no-route fallback
to_ll = Transformer.from_crs(f"EPSG:{CRS_M}", "EPSG:4326", always_xy=True)


def find_routable_origin(k: int):
    """For a subdivision whose centroid has no route (it snaps to a disconnected road fragment): the point of a GRID_M grid inside
    the polygon, nearest to the centroid, that OSRM can route from (tested against the first section). Returns (lon, lat), shift in m."""
    poly, c = m.geometry.iloc[k], cent_m.iloc[k]
    x0, y0, x1, y1 = poly.bounds
    grid = (Point(x, y) for x in np.arange(x0, x1, GRID_M) for y in np.arange(y0, y1, GRID_M))
    pts = sorted((p for p in grid if poly.contains(p)), key=c.distance) or [poly.representative_point()]
    for s in range(0, len(pts), BLOCK):
        batch = pts[s:s + BLOCK]
        ll = [(round(x, 6), round(y, 6)) for x, y in zip(*to_ll.transform([p.x for p in batch], [p.y for p in batch]))]
        coords = ";".join(f"{x:.6f},{y:.6f}" for x, y in ll + dst_ll[:1])
        resp = osrm.get(OSRM_URL + coords, {"sources": ";".join(map(str, range(len(ll)))), "destinations": str(len(ll)),
                                           "annotations": "distance"}).json()
        if resp.get("code") != "Ok":
            raise RuntimeError(f"OSRM error while searching for a routable origin: {resp.get('code')} {resp.get('message')}")
        ok = [i for i, row in enumerate(resp["distances"]) if row[0] is not None]
        if ok:
            return ll[ok[0]], c.distance(batch[ok[0]])
    raise RuntimeError(f"no routable point found inside {sub_ids[k]}")


def run_blocks():
    """Fill D, T and the snap distances from the block cache, querying OSRM for blocks that aren't cached (or whose points changed)."""
    global D, T, src_snap, dst_snap, n_new
    D = np.full((n_sub, n_sec), np.nan); T = np.full((n_sub, n_sec), np.nan)
    src_snap = np.full(n_sub, np.nan); dst_snap = np.full(n_sec, np.nan)
    for i in range(nb_i):
        for j in range(nb_j):
            f = BLOCK_DIR / f"{i:02d}_{j:02d}.npz"
            b = cached_block(f, i, j)
            if b is None:
                b = fetch_block(i, j)
                np.savez_compressed(f, **b)
                n_new += 1
                log.info("block %02d,%02d queried (%d queried so far)", i, j, n_new)
            D[i * BLOCK:(i + 1) * BLOCK, j * BLOCK:(j + 1) * BLOCK] = b["dist"]
            T[i * BLOCK:(i + 1) * BLOCK, j * BLOCK:(j + 1) * BLOCK] = b["dur"]
            src_snap[i * BLOCK:(i + 1) * BLOCK] = b["src_snap"]
            dst_snap[j * BLOCK:(j + 1) * BLOCK] = b["dst_snap"]


FALLBACK_FILE = BLOCK_DIR / "origin_fallbacks.json"     # subdivision_id -> [lon, lat, shift_m]; saved so a rerun doesn't search (and re-query) again
fallbacks = json.loads(FALLBACK_FILE.read_text()) if FALLBACK_FILE.exists() and not args.refresh else {}
sub_row = {g: k for k, g in enumerate(sub_ids)}


def set_origin(k: int, lon: float, lat: float, shift: float):
    subs.loc[k, ["origin_lat", "origin_lon", "origin_point", "origin_shift_m"]] = [lat, lon, "nearest_routable_grid_point", round(shift)]
    src_ll[k] = (lon, lat)


for g, (lon, lat, shift) in fallbacks.items():
    if g in sub_row:
        set_origin(sub_row[g], lon, lat, shift)
n_new = 0
try:
    run_blocks()
    dead = np.flatnonzero(np.isnan(D).all(axis=1))     # origins with no route to any section
    for k in dead:
        (lon, lat), shift = find_routable_origin(k)
        log.warning("%s (%s, %s): no road route from its centroid (snapped %.0f m to a disconnected road); routing from the nearest routable "
                    "grid point instead, %.0f m away", subs["name"][k], subs["county"][k], sub_ids[k], src_snap[k], shift)
        set_origin(k, lon, lat, shift)
        fallbacks[sub_ids[k]] = [lon, lat, shift]
    if len(dead):
        FALLBACK_FILE.write_text(json.dumps(fallbacks))
        run_blocks()                                    # only the blocks holding a moved origin are re-queried
        assert not np.isnan(D).all(axis=1).any(), "an origin still has no route to any section"
except (ServerRefused, RuntimeError, KeyboardInterrupt) as e:
    log.error("STOPPED: %r. Finished blocks are cached in %s; rerun to resume.", e, BLOCK_DIR.relative_to(ROOT))
    sys.exit(1)
log.info("requests made this run: %d (rest came from the block cache)", n_new)


# %% Assemble the long table, the lookup and the wide matrices
km = D / 1000
long = pd.DataFrame({
    "subdivision_id": np.repeat(sub_ids, n_sec),
    "section_id": np.tile(sec_ids, n_sub),
    "road_km": km.ravel().round(3).astype("float32"),
    "road_mi": (km / KM_PER_MI).ravel().round(3).astype("float32"),
    "road_min": (T / 60).ravel().round(1).astype("float32"),
})
subs["road_snap_m"] = src_snap.round(1)        # origin point -> nearest road
if args.limit:
    road_out, lookup_out = INTERIM_DIR / "subdivision_to_section_road_distance_TEST.parquet", INTERIM_DIR / "county_subdivisions_TEST"
else:
    road_out, lookup_out = ROAD_OUT, LOOKUP_OUT
long.to_parquet(road_out, index=False)
subs.to_parquet(lookup_out.with_suffix(".parquet"), index=False)
subs.to_csv(lookup_out.with_suffix(".csv"), index=False)
if not args.limit:
    pd.DataFrame(km / KM_PER_MI, index=sub_ids, columns=sec_ids).round(3).rename_axis("subdivision_id").to_csv(INTERIM_DIR / "subdivision_to_section_road_mi_matrix.csv")
    pd.DataFrame(T / 60, index=sub_ids, columns=sec_ids).round(1).rename_axis("subdivision_id").to_csv(INTERIM_DIR / "subdivision_to_section_road_min_matrix.csv")
log.info("wrote %d rows to %s (%.1f MB) and %d subdivisions to %s (+ csv)", len(long), road_out.relative_to(ROOT),
         road_out.stat().st_size / 1e6, len(subs), lookup_out.with_suffix(".parquet").relative_to(ROOT))
assert road_out.stat().st_size < 50e6, "CLAUDE.md: keep each processed file under 50 MB"


# %% Validation
xy_sub = np.array(to_m.transform(subs["origin_lon"].to_numpy(), subs["origin_lat"].to_numpy())).T
xy_sec = np.array(to_m.transform(sections["mid_lon"].to_numpy(), sections["mid_lat"].to_numpy())).T
straight_km = np.sqrt(((xy_sub[:, None, :] - xy_sec[None, :, :]) ** 2).sum(-1)) / 1000
tol_km = (src_snap[:, None] + dst_snap[None, :]) / 1000        # a route starts and ends at the snapped road points
ratio = km / straight_km.clip(min=0.05)
hatch = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet", columns=["section_id", "snap_m"]).drop_duplicates("section_id").set_index("section_id").snap_m
snap_diff = float(np.abs(pd.Series(dst_snap, index=sec_ids).sub(hatch.reindex(sec_ids))).max())
far = subs.loc[subs["road_snap_m"] > 5000, "name"].tolist()
moved = subs.loc[subs["origin_point"] != "centroid", "name"].tolist()
worst = np.unravel_index(np.nanargmax(D), D.shape)

# Cross-check with the hatchery road table (script 11). A hatchery and the subdivision it sits in start almost from the same place, so by the
# triangle inequality their drive times to any section differ by at most the drive time between them: T[g,s] - T[h,s] <= T[g,h] and
# T[h,s] - T[g,s] <= T[h,g]. (Drive time, not miles: OSRM picks the fastest route, so its distances don't obey the inequality.)
# The gaps T[g,h] and T[h,g] come from one extra OSRM request (cached beside the blocks); 1 minute of slack covers turn penalties and rounding.
hatcheries = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")
hatcheries["NAME"] = hatcheries["NAME"].str.strip()
inside = gpd.sjoin(hatcheries.to_crs(CRS_M)[["NAME", "geometry"]], m[["GEOID", "geometry"]], predicate="within").set_index("NAME")
hroad = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet", columns=["hatchery", "section_id", "road_min"]).pivot(index="hatchery", columns="section_id", values="road_min")
pairs = [(name, sub_row[g]) for name, g in inside["GEOID"].items() if g in sub_row]       # skips hatcheries outside a --limit test run
over, n_cmp = 0, 0
if pairs:
    h_pts = [(float(hatcheries.loc[hatcheries["NAME"] == name, "Long_"].iloc[0]), float(hatcheries.loc[hatcheries["NAME"] == name, "Lat"].iloc[0])) for name, _ in pairs]
    o_pts = [src_ll[k] for _, k in pairs]
    gap_file, gap_pts = BLOCK_DIR / "hatchery_origin_gaps.npz", np.array(h_pts + o_pts)
    z = np.load(gap_file) if gap_file.exists() and not args.refresh else None
    if z is not None and z["pts"].shape == gap_pts.shape and np.allclose(z["pts"], gap_pts):
        gap_min = z["dur"]
    else:
        resp = osrm.get(OSRM_URL + ";".join(f"{x:.6f},{y:.6f}" for x, y in h_pts + o_pts), {"annotations": "duration"}).json()
        if resp.get("code") != "Ok":
            raise RuntimeError(f"OSRM error for the hatchery cross-check: {resp.get('code')} {resp.get('message')}")
        gap_min = np.array(resp["durations"], dtype=float) / 60
        np.savez_compressed(gap_file, pts=gap_pts, dur=gap_min)
    for i, (name, k) in enumerate(pairs):
        h_to_g, g_to_h = gap_min[i, len(pairs) + i], gap_min[len(pairs) + i, i]
        delta = T[k] / 60 - hroad.loc[name].reindex(sec_ids).to_numpy()                   # subdivision minus hatchery, minutes
        n_bad = int(((delta > g_to_h + 1) | (delta < -h_to_g - 1)).sum())
        over += n_bad
        n_cmp += len(delta)
        log.info("cross-check %s hatchery in %s: drive %.1f min to the origin, %.1f min back; %d of %d sections outside the bound",
                 name, subs["name"][k], h_to_g, g_to_h, n_bad, len(delta))


def status(ok, warn_only=False):
    return "PASS" if ok else ("WARN" if warn_only else "FAIL")


n_dup = int(long.duplicated(["subdivision_id", "section_id"]).sum())
n_noroute = int(np.isnan(D).sum())
n_short = int((km < straight_km - tol_km).sum())
checks = [
    ("Row count (subdivisions x sections)", f"{n_sub * n_sec:,}", f"{len(long):,}", status(len(long) == n_sub * n_sec)),
    ("Duplicate (subdivision, section) pairs", "0", n_dup, status(n_dup == 0)),
    ("Pairs with no road route", "0", n_noroute, status(n_noroute == 0)),
    ("Section snap distances match the hatchery road table (max diff, m)", "under 1", round(snap_diff, 2), status(snap_diff < 1)),
    ("Road shorter than straight-line (beyond snap)", "0", n_short, status(n_short == 0)),
    ("Median road / straight-line ratio", "1.2 to 1.8", f"{np.median(ratio):.2f}", status(1.2 <= np.median(ratio) <= 1.8, True)),
    ("Our centroid vs Census CENTLAT/CENTLON (median offset, m)", "under 50", round(float(np.median(cent_off)), 1), status(np.median(cent_off) < 50, True)),
    ("Origin points more than 5 km from a road", "0", len(far), status(not far, True)),
    ("Hatchery vs the subdivision it sits in: drive times to the sections beyond the triangle bound", "0", f"{over} of {n_cmp:,}", status(over == 0, True)),
]
validation = pd.DataFrame(checks, columns=["check", "expected", "result", "status"])
print(validation.to_string(index=False))
log.info("origin snap to road: median %.0f m, 90th pct %.0f m, max %.0f m; over 1 km: %d; over 5 km: %s",
         subs["road_snap_m"].median(), subs["road_snap_m"].quantile(.9), subs["road_snap_m"].max(), int((subs["road_snap_m"] > 1000).sum()), far or "none")
log.info("origins moved off the centroid because it had no route: %d %s", len(moved), moved)
log.info("longest route: %s (%s) to section %s: %.1f road mi", subs["name"][worst[0]], subs["county"][worst[0]], sec_ids[worst[1]], D[worst] / 1000 / KM_PER_MI)

bucket = pd.cut(straight_km.ravel() / KM_PER_MI, [0, 5, 10, 20, 40, 80, 500], labels=["< 5 mi", "5-10", "10-20", "20-40", "40-80", "80+"])
circ = (pd.DataFrame({"straight_mi": straight_km.ravel() / KM_PER_MI, "road_mi": km.ravel() / KM_PER_MI, "ratio": ratio.ravel(), "b": bucket})
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
