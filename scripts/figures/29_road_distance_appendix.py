"""Appendix slide: what we calculated with road distances, and how (no road network is drawn: the project never stored it; OSRM holds it).

Left  = every place we computed from or to: 2,567 county subdivision centres (demand origins), the 1,045 stocked sections' midpoints (destinations),
        the 13 State Fish Hatcheries (supply nodes).
Right = the four-step method and the three tables it produced (row counts read from the saved tables), with checks and snap distances computed here.
Routing: OSRM table service, driving profile, on OpenStreetMap data (c) OpenStreetMap contributors; scripts 11, 12 and 19 (docs/data_methods.md § Road
distances). No title on purpose: it is added in the deck.

Inputs : data/processed/{county_subdivisions,sections}.parquet, {hatchery,section,subdivision}_to_section_road_distance.parquet,
         data/raw/pa_hatcheries.gpkg, data/raw/pa_boundary.gpkg, outputs/tables/subdivision_road_distance/{validation,circuity_by_distance}.csv
Outputs: outputs/figures/allocation_problem/road_distance_appendix.png   logs/29_road_distance_appendix.log

    python scripts/figures/29_road_distance_appendix.py
"""
# %% Setup
from __future__ import annotations

import logging

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/, where common.py lives
from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging, register_open_sans

FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
TAB = ROOT / "outputs" / "tables" / "subdivision_road_distance"
SURFACE, INK, INK2, GRID = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, AMBER, AMBER_EDGE, DOT = "#2a78d6", "#f5ae00", "#2b2100", "#9a9993"
setup_logging("29_road_distance_appendix")
log = logging.getLogger("29_road_distance_appendix")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Open Sans (the deck's font; SIL Open Font License), local only: see common.register_open_sans. Falls back to DejaVu Sans if absent.
register_open_sans()
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})

# %% Numbers, read from the saved tables
sub = pd.read_parquet(PROCESSED_DIR / "county_subdivisions.parquet")
sec = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "mid_lat", "mid_lon"])
hat = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")
h_tab = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet", columns=["hatchery", "section_id", "snap_m"])
n_h, n_s2s, n_sub = len(h_tab), len(pd.read_parquet(PROCESSED_DIR / "section_to_section_road_distance.parquet", columns=["road_mi"])), \
    len(pd.read_parquet(PROCESSED_DIR / "subdivision_to_section_road_distance.parquet", columns=["road_mi"]))
assert (len(hat), sub.shape[0], sec.shape[0]) == (13, 2567, 1045), "13 hatcheries, 2,567 subdivisions, 1,045 sections"
total = n_h + n_s2s + n_sub
snap_sec, snap_sub = float(h_tab.drop_duplicates("section_id").snap_m.median()), float(sub.road_snap_m.median())
val = pd.read_csv(TAB / "validation.csv")
n_pass = int((val.status == "PASS").sum())
circ = pd.read_csv(TAB / "circuity_by_distance.csv")
circ_short, circ_long = float(circ.median_ratio.iloc[0]), float(circ.median_ratio.iloc[-1])
log.info("tables: hatchery %d, section-section %d, subdivision-section %d, total %d; median snap sections %.0f m, subdivisions %.0f m; %d of %d checks pass; "
         "road/straight %.2f (under 5 mi) to %.2f (80+ mi)", n_h, n_s2s, n_sub, total, snap_sec, snap_sub, n_pass, len(val), circ_short, circ_long)

# %% Draw
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.02, 0.05, 0.58, 0.88])
pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
ax.scatter(sub.centroid_lon, sub.centroid_lat, s=3, c=DOT, alpha=0.8, linewidths=0, zorder=1)
ax.scatter(sec.mid_lon, sec.mid_lat, s=9, c=BLUE, alpha=0.9, linewidths=0, zorder=2)
ax.scatter(hat.geometry.x, hat.geometry.y, s=130, c=AMBER, edgecolors=AMBER_EDGE, linewidths=1.3, zorder=4)
ax.set_xlim(-80.7, -74.45)
ax.set_ylim(39.6, 42.45)
ax.set_aspect(1 / np.cos(np.radians(41)))
ax.set_axis_off()
# key under the map
key = fig.add_axes([0.03, 0.005, 0.57, 0.05])
key.set_axis_off()
key.set_xlim(0, 1)
key.set_ylim(0, 1)
for x, c, s_, lab in ((0.00, DOT, 28, f"{len(sub):,} subdivision centres"), (0.34, BLUE, 40, f"{len(sec):,} stocked sections"),
                      (0.64, AMBER, 90, f"{len(hat)} hatcheries")):
    key.scatter([x + 0.008], [0.5], s=s_, c=c, edgecolors=AMBER_EDGE if c == AMBER else "none", linewidths=1)
    key.text(x + 0.03, 0.5, lab, fontsize=10.5, va="center", color=INK)

pan = fig.add_axes([0.63, 0.05, 0.355, 0.88])
pan.set_axis_off()
pan.set_xlim(0, 1)
pan.set_ylim(0, 1)
pan.text(0, 0.99, f"{total / 1e6:.1f}M", fontsize=34, fontweight="bold", color=BLUE, va="top")
pan.text(0, 0.885, "road distances, from OpenStreetMap\nroads via the OSRM routing service", fontsize=12, color=INK2, va="top", linespacing=1.3)
steps = [("1", "Snap each point to the nearest road", f"median {snap_sec:.0f} m (sections), {snap_sub:.0f} m (subdivisions)"),
         ("2", "Ask for driving miles", "OSRM table service, blocks of 100 x 100 points"),
         ("3", "Check every table", f"{n_pass} of {len(val)} checks pass: no gaps, road never shorter than a straight line"),
         ("4", "Save miles, km and drive minutes", "one row per origin and destination pair")]
for i, (n, head, sub_) in enumerate(steps):
    y = 0.72 - i * 0.115
    pan.text(0.0, y, n, fontsize=13, fontweight="bold", color="white", ha="center", va="center", bbox=dict(boxstyle="circle,pad=0.35", fc=BLUE, ec="none"))
    pan.text(0.075, y + 0.018, head, fontsize=13, fontweight="bold", va="center")
    pan.text(0.075, y - 0.027, sub_, fontsize=9.8, color=INK2, va="center")
pan.plot([0, 1], [0.25, 0.25], color=GRID, lw=1.2)
pan.text(0, 0.215, "Three tables", fontsize=12, fontweight="bold", va="center")
for i, (num, lab) in enumerate(((n_h, "hatchery to section"), (n_s2s, "section to section"), (n_sub, "subdivision to section"))):
    y = 0.15 - i * 0.055
    pan.text(0.40, y, f"{num:,}", fontsize=13, fontweight="bold", color=BLUE, ha="right", va="center")
    pan.text(0.43, y, lab, fontsize=11, color=INK2, va="center")
pan.text(0, -0.035, "Roads: (c) OpenStreetMap contributors. Driving profile, fastest route.", fontsize=8.5, color="#6b6a66", va="center")
out = FIG_DIR / "road_distance_appendix.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
