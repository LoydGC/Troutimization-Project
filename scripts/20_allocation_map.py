"""Slide map of the starting point: the hatcheries PFBC supplies from and the stream sections it stocks (no model language).

Hatcheries = the 9 PFBC state fish hatcheries that put fish into streams on the 2026 schedule (hatchery_schedule_supply.csv, stream_fish_2026 > 0).
Every hatchery gets the same numbered marker (number = rank by 2026 stream fish), so the map shows location only; the amounts are in a ranked bar
chart in the side panel. The three Centre County hatcheries sit within a few miles of each other, so overlapping markers are nudged apart just
enough to clear each other (relative positions kept; the nudge is logged and noted on the slide). Streams = the 1,022 stream sections PFBC stocks in 2026 (sections.total_2026 > 0); line width shows how many trout
each got in 2026. Nothing is modelled here; it is a picture of what PFBC has today.

Inputs : data/processed/sections.parquet, data/processed/hatchery_schedule_supply.csv, data/processed/pa_trout.gpkg (sections layer; gitignored,
         rebuilt by scripts 01-02), data/raw/pa_hatcheries.gpkg (PFBC State Fish Hatcheries layer, 13 points), data/raw/pa_boundary.gpkg
Outputs: outputs/figures/allocation_problem/starting_point_map.png   (16:9, 300 dpi)
         logs/20_allocation_map.log

    python scripts/20_allocation_map.py
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

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2, TITLE = "#ffffff", "#0b0b0b", "#52514e", "#a6192e"      # TITLE = the deck's dark red berry
BLUE, HATCH, HATCH_EDGE = "#2a78d6", "#f5ae00", "#2b2100"  # sections = blue; hatcheries = amber, blue's complement (hue ~210 vs ~42), dark ring for the pale ground
setup_logging("20_allocation_map")
log = logging.getLogger("20_allocation_map")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Open Sans (the deck's font; SIL Open Font License). Local only, data/references is gitignored: download Google Fonts' variable file
# https://github.com/google/fonts/tree/main/ofl/opensans -> data/references/fonts/OpenSans.ttf (this script cuts Regular and Bold from it).
# If the file is absent the figure falls back to DejaVu Sans.
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

# %% Load
tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
stocked = set(tab.loc[tab.total_2026.fillna(0) > 0, "section_id"])
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
sec = sec[sec.section_id.isin(stocked)]
assert len(sec) == 1022, "docs say the candidate set is the 1,022 sections stocked in 2026"
sec = sec.merge(tab[["section_id", "total_2026"]], on="section_id")
BINS = [(0, 1000, 0.5, "under 1,000"), (1000, 2500, 1.0, "1,000 to 2,500"), (2500, 5000, 1.7, "2,500 to 5,000"), (5000, 1e9, 2.6, "over 5,000")]
supply = pd.read_csv(PROCESSED_DIR / "hatchery_schedule_supply.csv")[["hatchery", "stream_fish_2026"]]
supply = supply[supply.stream_fish_2026 > 0]
hat = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")[["NAME", "COUNTY", "geometry"]].rename(columns={"NAME": "hatchery"})
hat["hatchery"] = hat.hatchery.str.strip()
hat = hat.merge(supply, on="hatchery")
assert len(hat) == 9 == len(supply), "9 hatcheries put fish into streams on the 2026 schedule"
hat = hat.sort_values("stream_fish_2026", ascending=False).reset_index(drop=True)
hat["rank"] = hat.index + 1
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")
total = hat.stream_fish_2026.sum()
log.info("%d hatcheries, %d sections, %.0f stream fish in 2026", len(hat), len(sec), total)

# Markers that would overlap (the three Centre County hatcheries sit within a few miles of each other) are nudged apart just enough to clear each
# other, keeping their relative positions. Done in inches on the page, so the nudge is the same in every direction.
XLIM, YLIM, AX_W_IN = (-80.85, -74.45), (39.6, 42.45), 0.61 * 13.333
IN_PER_LON = AX_W_IN / (XLIM[1] - XLIM[0])
IN_PER_LAT = IN_PER_LON / np.cos(np.radians(41))
MIN_GAP_IN = 0.31                                                    # centre-to-centre; marker diameter is about 0.26 in
xy = np.column_stack([hat.geometry.x * IN_PER_LON, hat.geometry.y * IN_PER_LAT])
true_xy = xy.copy()
for _ in range(500):
    moved = False
    for i in range(len(xy)):
        for j in range(i + 1, len(xy)):
            d = xy[j] - xy[i]
            dist = np.hypot(*d)
            if dist < MIN_GAP_IN:
                push = (d / dist if dist > 1e-9 else np.array([1.0, 0.0])) * (MIN_GAP_IN - dist) / 2
                xy[i] -= push
                xy[j] += push
                moved = True
    if not moved:
        break
hat["mx"], hat["my"] = xy[:, 0] / IN_PER_LON, xy[:, 1] / IN_PER_LAT
shift = np.hypot(*(xy - true_xy).T)
log.info("marker nudge (inches on the slide): %s", {n: round(float(v), 2) for n, v in zip(hat.hatchery, shift) if v > 0})

# %% Draw
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})
fig = plt.figure(figsize=(13.333, 7.5))
# No title on purpose: it is added in PowerPoint (Open Sans 40, TITLE colour), e.g. "9 trout hatcheries and 1,022 stocked streams". The space above the map is left clear for it.
ax = fig.add_axes([0.02, 0.06, 0.61, 0.82])
pa.plot(ax=ax, facecolor="#f4f3ef", edgecolor=INK2, lw=1.2, zorder=0)
for lo, hi, lw, _ in BINS:
    sec[(sec.total_2026 >= lo) & (sec.total_2026 < hi)].plot(ax=ax, color=BLUE, lw=lw, alpha=0.95, zorder=2)
ax.set_xlim(*XLIM)
ax.set_ylim(*YLIM)
ax.set_aspect(1 / np.cos(np.radians(41)))
ax.set_axis_off()
for _, r in hat.iterrows():
    ax.scatter([r.mx], [r.my], s=360, c=HATCH, edgecolors=HATCH_EDGE, linewidths=1.4, zorder=6)
    ax.text(r.mx, r.my, str(r["rank"]), color=INK, fontsize=11, fontweight="bold", ha="center", va="center", zorder=7)

# %% Right panel: total, ranked bars, key
pan = fig.add_axes([0.655, 0.06, 0.325, 0.82])
pan.set_axis_off()
pan.set_xlim(0, 1)
pan.set_ylim(0, 1)
pan.text(0, 1.0, f"{total / 1e6:.1f}M", fontsize=30, fontweight="bold", color=BLUE, va="top")
pan.text(0, 0.905, "trout a year produced in hatcheries\nto be distributed", fontsize=11.5, color=INK2, va="top", linespacing=1.25)

BAX = (0.795, 0.30, 0.17, 0.37)                                            # left, bottom, width, height of the bar axes (figure fractions)
bax = fig.add_axes(BAX)
vals = hat.stream_fish_2026.to_numpy() / 1000
y = np.arange(len(hat))[::-1]
bax.barh(y, vals, color=HATCH, edgecolor=HATCH_EDGE, linewidth=0.8, height=0.68)
for yi, v in zip(y, vals):
    bax.text(v + 6, yi, f"{v:,.0f}k", va="center", fontsize=10.5, color=INK)
bax.set_xlim(0, vals.max() * 1.22)
bax.set_ylim(-0.6, len(hat) - 0.4)
bax.set_yticks([])
bax.set_xticks([])
for s in bax.spines.values():
    s.set_visible(False)
fig.text(0.655, 0.675, "Trout sent to streams, 2026", fontsize=12, fontweight="bold", ha="left")
for yi, (_, r) in zip(y, hat.iterrows()):                                                    # numbered chip + name, left of each bar
    yy = BAX[1] + BAX[3] * (yi + 0.6) / (len(hat) + 0.2)
    fig.text(0.668, yy, str(r["rank"]), fontsize=8.5, color=INK, fontweight="bold", ha="center", va="center",
             bbox=dict(boxstyle="circle,pad=0.28", fc=HATCH, ec=HATCH_EDGE, lw=0.9))
    fig.text(0.685, yy, r.hatchery, fontsize=10.5, ha="left", va="center")

pan.text(0, 0.235, "Stocked stream section (thicker = more trout in 2026)", fontsize=10.5, va="center")
for i, (_, _, lw, name) in enumerate(BINS):
    y0 = 0.175 - i * 0.045
    pan.plot([0.0, 0.07], [y0, y0], color=BLUE, lw=lw + 0.4, solid_capstyle="butt")
    pan.text(0.09, y0, name + " trout", fontsize=10, color=INK2, va="center")
fig.text(0.5, 0.02, "Source: PFBC hatcheries layer, 2024-26 stocked sections and 2026 schedule. Centre County markers are nudged apart to avoid overlap.", fontsize=9, color=INK2, ha="center")

out = FIG_DIR / "starting_point_map.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
