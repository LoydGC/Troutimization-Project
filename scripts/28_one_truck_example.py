"""Slide visual for the transport cost objective: one real truckload, from a hatchery to a cluster, priced the way the model prices it.

Example = k-medoids cluster B015 (Dents Run, Hicks Run, West Branch Hicks Run): 3 sections, all supplied by Bellefonte in 2026, all on ONE real
pre-season truck run (checked in the script). Cost as the model counts it (docs/model_formulation.md, Transport):
    one truck trip costs  2 x miles[h,g] x $1.90   with miles[h,g] = the cluster's average one-way road miles from the hatchery
    trips = round's fish for the cluster / 3,500, rounded up when scored.
The line from hatchery to cluster is schematic (straight), the miles are OSRM road miles. No title on purpose: it is added in the deck.

Inputs : data/processed/stocking_events.parquet, section_medoid_clusters.parquet, cluster_hatchery_distance.parquet, sections.parquet,
         parameters.csv, pa_trout.gpkg (sections layer), data/raw/pa_hatcheries.gpkg, data/raw/pa_boundary.gpkg
Outputs: outputs/figures/kmedoids/one_truck_example.png   logs/28_one_truck_example.log

    python scripts/28_one_truck_example.py
"""
# %% Setup
from __future__ import annotations

import logging
import math

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from shapely.geometry import LineString
from shapely.ops import nearest_points

from common import PROCESSED_DIR, RAW_DIR, ROOT, PoliteSession, full_url, save_raw, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "kmedoids"
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
BLUE, AMBER, AMBER_EDGE, BERRY, OTHER = "#2a78d6", "#f5ae00", "#2b2100", "#a6192e", "#d6d5cf"
CLUSTER, HATCHERY = "B015", "Bellefonte"
setup_logging("28_one_truck_example")
log = logging.getLogger("28_one_truck_example")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Open Sans (the deck's font; SIL Open Font License), local only: see scripts/20_allocation_map.py. Falls back to DejaVu Sans if absent.
FONT_DIR = ROOT / "data" / "references" / "fonts"
if (FONT_DIR / "OpenSans.ttf").exists():
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    from matplotlib import font_manager
    for style, wght in (("Regular", 400), ("Bold", 700)):
        cut = FONT_DIR / f"OpenSans-{style}.ttf"
        if not cut.exists():
            instancer.instantiateVariableFont(TTFont(FONT_DIR / "OpenSans.ttf"), {"wght": wght, "wdth": 100}, updateFontNames=True).save(cut)
        font_manager.fontManager.addfont(str(cut))
else:
    log.warning("data/references/fonts/OpenSans.ttf not found: falling back to DejaVu Sans")
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK, "mathtext.fontset": "cm"})

# %% The example, from the data
par = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter").value
t_cost, cap = float(par["cost_per_truck_mile"]), float(par["truck_capacity"])
km = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet").set_index("section_id").silhouette_best_cluster_id
members = km[km == CLUSTER].index.tolist()
names = pd.read_parquet(PROCESSED_DIR / "sections.parquet").set_index("section_id").water_name
ev = pd.read_parquet(PROCESSED_DIR / "stocking_events.parquet")
pre = ev[(ev.water_type == "stream") & ev.section_id.isin(members) & (ev.season == "P")]
assert set(pre.section_id) == set(members) and set(pre.hatchery) == {HATCHERY}, "every member is supplied by Bellefonte in the pre-season"
assert pre.run_id.nunique() == 1, "the three sections rode one real pre-season truck run"
fish = pre.groupby("section_id").alloc_fish.sum()
total = float(fish.sum())
cd = pd.read_parquet(PROCESSED_DIR / "cluster_hatchery_distance.parquet")
miles = float(cd[(cd.method == "kmedoids_best_silhouette") & (cd.cluster_id == CLUSTER) & (cd.hatchery == HATCHERY)].avg_road_mi.iloc[0])
trucks = math.ceil(total / cap)
one_truck = 2 * miles * t_cost
log.info("cluster %s %s: fish %.0f (%s), avg %.1f road mi, trucks %d, cost per truck $%.0f, per fish $%.3f, if each section sent its own truck: $%.0f",
         CLUSTER, [names[s] for s in members], total, fish.round().to_dict(), miles, trucks, one_truck, one_truck * trucks / total, one_truck * len(members))
assert trucks == 1

sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
mem = sec[sec.section_id.isin(members)]
hat = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")
hat = hat[hat.NAME.str.strip() == HATCHERY].iloc[0].geometry
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")
cx, cy = mem.geometry.union_all().centroid.x, mem.geometry.union_all().centroid.y
log.info("cluster centre (%.2f, %.2f); hatchery (%.2f, %.2f); straight-line %.0f mi",
         cx, cy, hat.x, hat.y, math.hypot((cx - hat.x) * 52.4, (cy - hat.y) * 69.0))

# %% The road route to the nearest stream of the cluster: ONE request to the OSRM route service (CLAUDE.md rule 3 waiver; saved untouched, rule 2)
mem_m = mem.to_crs(26918)
hat_m = gpd.GeoSeries([hat], crs=4326).to_crs(26918).iloc[0]
near_m = nearest_points(hat_m, mem_m.geometry.union_all())[1]
near = gpd.GeoSeries([near_m], crs=26918).to_crs(4326).iloc[0]
ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/"
coords = f"{hat.x:.6f},{hat.y:.6f};{near.x:.6f},{near.y:.6f}"
resp = PoliteSession(min_interval=1.5).get(ROUTE_URL + coords, params={"overview": "full", "geometries": "geojson"})
data = resp.json()
assert data["code"] == "Ok" and len(data["routes"]) == 1, data.get("code")
save_raw("osrm_route", f"bellefonte_to_{CLUSTER}_nearest_stream.json", resp.text, full_url(ROUTE_URL + coords, {"overview": "full", "geometries": "geojson"}), records=1)
route = LineString(data["routes"][0]["geometry"]["coordinates"])
route_mi = data["routes"][0]["distance"] / 1609.344
log.info("route to the nearest point of the cluster: %.1f road miles, %d vertices (the table's cluster average is %.1f mi, per-section %s)",
         route_mi, len(route.coords), miles, "see log above")

# %% Draw
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.02, 0.07, 0.96, 0.90])
x0, x1 = -80.60, -74.50                                                  # the whole state, so the outline is never cut off
y0, y1 = 39.65, 42.40
pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
sec[sec.section_id.isin(set(pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet").section_id))].plot(ax=ax, color=OTHER, lw=1.0, zorder=1)
mem.plot(ax=ax, color=BLUE, lw=6, zorder=4)
bx0, by0, bx1, by1 = mem.total_bounds
ax.add_patch(plt.Rectangle((bx0 - 0.06, by0 - 0.05), bx1 - bx0 + 0.12, by1 - by0 + 0.10, fill=False, ec=BLUE, lw=1.6, zorder=5))
rx, ry = route.xy
ax.plot(rx, ry, color=INK, lw=3.2, solid_capstyle="round", zorder=3)                     # the actual road route (OSRM)
ax.scatter([rx[-1]], [ry[-1]], s=60, c=INK, zorder=4)
ax.scatter([hat.x], [hat.y], s=700, c=AMBER, edgecolors=AMBER_EDGE, linewidths=1.8, zorder=6)
halo = [pe.withStroke(linewidth=4, foreground="white")]
ax.text(hat.x + 0.10, hat.y - 0.02, HATCHERY, fontsize=15, fontweight="bold", ha="left", va="center", zorder=7, path_effects=halo)
mp = route.interpolate(0.55, normalized=True)
mx, my = mp.x, mp.y
ax.text(mx + 0.14, my + 0.06, f"{miles:.0f} road miles", fontsize=17, fontweight="bold", color=INK, ha="left", va="center", zorder=7, path_effects=halo)
ax.text(mx + 0.14, my - 0.07, f"${one_truck:,.0f} per truck round trip", fontsize=17, fontweight="bold", color=BERRY, ha="left", va="center", zorder=7, path_effects=halo)
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)
ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)), adjustable="box", anchor="E")
ax.set_axis_off()

ins = fig.add_axes([0.012, 0.56, 0.122, 0.30])                      # zoom on the three sections (the cluster is a speck at this scale)
ins.set_facecolor("white")
mem.plot(ax=ins, color=BLUE, lw=3.6, zorder=3)
for sid, g in mem.set_index("section_id").geometry.items():
    frac, ha, dy, va = {"West Branch Hicks Run": (0.12, "left", 7, "bottom"), "Hicks Run": (0.7, "left", 0, "center"),
                        "Dents Run": (0.5, "center", -9, "top")}[names[sid]]               # label beside its own line, clear of the others
    pt = g.interpolate(frac, normalized=True)
    ins.annotate(names[sid], (pt.x, pt.y), xytext=(12 if va == "center" else 0, dy), textcoords="offset points", ha=ha, va=va, fontsize=8, fontweight="bold",
                 color=INK, path_effects=halo, zorder=6)
ins.set_xlim(bx0 - 0.015, bx1 + 0.075)                                  # room on the right for the Hicks Run label
ins.set_ylim(by0 - 0.05, by1 + 0.03)
ins.set_aspect(1 / np.cos(np.radians(cy)), adjustable="box", anchor="NW")      # box shrinks to the data, so nothing is clipped
ins.set_xticks([])
ins.set_yticks([])
for sp_ in ins.spines.values():
    sp_.set_color(BLUE)
    sp_.set_linewidth(1.6)
out = FIG_DIR / "one_truck_example.png"
fig.text(0.5, 0.025, f"Cost of one trip = 2 (round trip) x {miles:.0f} mi (average road miles, hatchery to the cluster's sections) x \${t_cost:.2f} per mile = \${one_truck:,.0f}. "
         f"The cluster's {total:,.0f} fish fit one {cap:,.0f}-fish truck. Route (OSRM) drawn to the cluster's nearest stream, {route_mi:.0f} mi.", fontsize=8.5, color=INK2, ha="center")
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)


# %% Tall crop for a narrow slide area: just the route and the cluster (4:5 portrait), with a tiny state locator
fig2 = plt.figure(figsize=(6.0, 7.5))
bx = fig2.add_axes([0.03, 0.10, 0.94, 0.86])
rx0, ry0, rx1, ry1 = route.bounds
cxm, cym = (rx0 + rx1) / 2, (ry0 + ry1) / 2
hh = 0.98                                                                # window height in degrees of latitude
ww = hh * (0.94 * 6.0) / (0.86 * 7.5) / np.cos(np.radians(cym))        # width in degrees that matches the axes' shape
bx.set_xlim(cxm - ww / 2, cxm + ww / 2)
bx.set_ylim(cym - hh / 2, cym + hh / 2)
bx.set_aspect(1 / np.cos(np.radians(cym)))
sec[sec.section_id.isin(set(pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet").section_id))].plot(ax=bx, color="#d9d8d2", lw=1.2, zorder=1)
bx.set_facecolor("#ffffff")
bx.plot(rx, ry, color=INK, lw=3.4, solid_capstyle="round", zorder=3)
mem.plot(ax=bx, color=BLUE, lw=5, zorder=4)
bx.scatter([rx[-1]], [ry[-1]], s=60, c=INK, zorder=5)
bx.scatter([hat.x], [hat.y], s=700, c=AMBER, edgecolors=AMBER_EDGE, linewidths=1.8, zorder=6)
bx.text(hat.x + 0.045, hat.y - 0.05, HATCHERY, fontsize=14, fontweight="bold", ha="left", va="top", zorder=7, path_effects=halo)
mp = route.interpolate(0.5, normalized=True)
bx.text(mp.x - 0.07, mp.y + 0.05, f"{miles:.0f} road miles", fontsize=16, fontweight="bold", color=INK, ha="right", va="center", zorder=7, path_effects=halo)
bx.text(mp.x - 0.07, mp.y - 0.03, f"${one_truck:,.0f} per truck\nround trip", fontsize=16, fontweight="bold", color=BERRY, ha="right", va="center", zorder=7, path_effects=halo, linespacing=1.15)
bx.text(bx1 + 0.03, (by0 + by1) / 2, "\n".join(names[s] for s in ["2777_3", "2783_1", "4363_3"] if s in names.index) if False else
        "Dents Run\nHicks Run\nWest Branch Hicks Run", fontsize=10.5, fontweight="bold", color=BLUE, ha="left", va="center", zorder=7, path_effects=halo, linespacing=1.3)
bx.set_xticks([])
bx.set_yticks([])
for sp_ in bx.spines.values():
    sp_.set_color("#d9d8d2")
loc = fig2.add_axes([0.05, 0.80, 0.33, 0.14])
pa.plot(ax=loc, facecolor="#ffffff", edgecolor=INK2, lw=0.8)
loc.scatter([hat.x], [hat.y], s=34, c=AMBER, edgecolors=AMBER_EDGE, linewidths=0.8, zorder=5)
loc.add_patch(plt.Rectangle((cxm - ww / 2, cym - hh / 2), ww, hh, fill=False, ec=BLUE, lw=1.2))
loc.set_aspect(1 / np.cos(np.radians(41)))
loc.set_axis_off()
fig2.text(0.5, 0.045, f"2 x {miles:.0f} mi x \\${t_cost:.2f} = \\${one_truck:,.0f}", fontsize=10, color=INK2, ha="center", va="center")
out2 = FIG_DIR / "one_truck_example_tall.png"
fig2.savefig(out2, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out2)
