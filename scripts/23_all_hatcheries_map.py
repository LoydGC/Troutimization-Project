"""Appendix map: all 13 PFBC state fish hatcheries, marking the 9 the model ships from and the 4 it does not.

In the model = hatcheries with stream fish on PFBC's 2026 stocking schedule (hatchery_schedule_supply.csv, stream_fish_2026 > 0), numbered 1-9 by
trout sent, the same numbers as scripts/20_allocation_map.py. Not in the model = the other 4 (Linesville and Pleasant Mount are on the schedule but
stock no streams; Fairview and Union City are not on it), lettered A-D. Locations: PFBC's State Fish Hatcheries layer (13 points). Stocked stream
sections are drawn pale grey for context. Markers that would overlap are nudged apart (relative positions kept; noted on the slide). No title on
purpose: it is added in PowerPoint.

Inputs : data/raw/pa_hatcheries.gpkg, data/processed/hatchery_schedule_supply.csv, sections.parquet, pa_trout.gpkg (sections layer),
         data/raw/pa_boundary.gpkg
Outputs: outputs/figures/allocation_problem/all_hatcheries_map.png   (16:9, 300 dpi)
         logs/23_all_hatcheries_map.log

    python scripts/23_all_hatcheries_map.py
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
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
HATCH, HATCH_EDGE, OTHER_FILL, OTHER_EDGE, STREAM = "#f5ae00", "#2b2100", "#d9d8d2", "#6d6b64", "#d3d2cb"
setup_logging("23_all_hatcheries_map")
log = logging.getLogger("23_all_hatcheries_map")
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

# %% Load
hat = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")[["NAME", "COUNTY", "geometry"]].rename(columns={"NAME": "hatchery", "COUNTY": "county"})
hat["hatchery"] = hat.hatchery.str.strip()
assert len(hat) == 13, "PFBC's State Fish Hatcheries layer has 13 hatcheries"
supply = pd.read_csv(PROCESSED_DIR / "hatchery_schedule_supply.csv").set_index("hatchery").stream_fish_2026
hat["fish"] = hat.hatchery.map(supply).fillna(0)
hat["in_model"] = hat.fish > 0
assert hat.in_model.sum() == 9
hat = pd.concat([hat[hat.in_model].sort_values("fish", ascending=False), hat[~hat.in_model].sort_values("hatchery")], ignore_index=True)
hat["label"] = [str(i + 1) for i in range(9)] + list("ABCD")
log.info("in the model: %s | not in the model: %s", list(hat[hat.in_model].hatchery), list(hat[~hat.in_model].hatchery))
tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
sec = sec[sec.section_id.isin(set(tab.loc[tab.total_2026.fillna(0) > 0, "section_id"]))]
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")

# Nudge overlapping markers apart (in inches on the page), keeping relative positions
XLIM, YLIM, AX_W_IN = (-81.0, -74.45), (39.6, 42.45), 0.61 * 13.333
IN_PER_LON = AX_W_IN / (XLIM[1] - XLIM[0])
IN_PER_LAT = IN_PER_LON / np.cos(np.radians(41))
MIN_GAP_IN = 0.31
xy = np.column_stack([hat.geometry.x * IN_PER_LON, hat.geometry.y * IN_PER_LAT])
true_xy = xy.copy()
for _ in range(500):
    moved = False
    for i in range(len(xy)):
        for j in range(i + 1, len(xy)):
            d = xy[j] - xy[i]
            dist = np.hypot(*d)
            if dist < MIN_GAP_IN:
                xy[i] -= (d / dist if dist > 1e-9 else np.array([1.0, 0.0])) * (MIN_GAP_IN - dist) / 2
                xy[j] += (d / dist if dist > 1e-9 else np.array([1.0, 0.0])) * (MIN_GAP_IN - dist) / 2
                moved = True
    if not moved:
        break
hat["mx"], hat["my"] = xy[:, 0] / IN_PER_LON, xy[:, 1] / IN_PER_LAT
log.info("marker nudge (inches on the slide): %s", {n: round(float(v), 2) for n, v in zip(hat.hatchery, np.hypot(*(xy - true_xy).T)) if v > 0})

# %% Draw
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})
fig = plt.figure(figsize=(13.333, 7.5))
# No title on purpose: added in PowerPoint. The space above the map is left clear for it.
ax = fig.add_axes([0.02, 0.06, 0.61, 0.82])
pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
sec.plot(ax=ax, color=STREAM, lw=0.8, zorder=1)
ax.set_xlim(*XLIM)
ax.set_ylim(*YLIM)
ax.set_aspect(1 / np.cos(np.radians(41)))
ax.set_axis_off()
for _, r in hat.iterrows():
    fc, ec = (HATCH, HATCH_EDGE) if r.in_model else (OTHER_FILL, OTHER_EDGE)
    ax.scatter([r.mx], [r.my], s=360, c=fc, edgecolors=ec, linewidths=1.5, zorder=6)
    ax.text(r.mx, r.my, r.label, color=INK, fontsize=11, fontweight="bold", ha="center", va="center", zorder=7)

# %% Right panel: the 13, grouped
pan = fig.add_axes([0.655, 0.06, 0.325, 0.82])
pan.set_axis_off()
pan.set_xlim(0, 1)
pan.set_ylim(0, 1)


def chip(y, label, in_model):
    pan.text(0.03, y, label, fontsize=8.5, color=INK, fontweight="bold", ha="center", va="center",
             bbox=dict(boxstyle="circle,pad=0.28", fc=HATCH if in_model else OTHER_FILL, ec=HATCH_EDGE if in_model else OTHER_EDGE, lw=0.9))


pan.text(0, 0.985, "In the model (9)", fontsize=13, fontweight="bold", va="center")
pan.text(0, 0.935, "Send trout to streams on the 2026 schedule", fontsize=10, color=INK2, va="center")
for i, r in hat[hat.in_model].reset_index(drop=True).iterrows():
    y = 0.865 - i * 0.058
    chip(y, r.label, True)
    pan.text(0.10, y, r.hatchery, fontsize=12, va="center")
    pan.text(0.98, y, f"{r.county} Co.", fontsize=10.5, color=INK2, va="center", ha="right")
pan.text(0, 0.30, "Not in the model (4)", fontsize=13, fontweight="bold", va="center")
pan.text(0, 0.25, "No stream fish on the 2026 schedule", fontsize=10, color=INK2, va="center")
for i, r in hat[~hat.in_model].reset_index(drop=True).iterrows():
    y = 0.19 - i * 0.058
    chip(y, r.label, False)
    pan.text(0.10, y, r.hatchery, fontsize=12, va="center")
    pan.text(0.98, y, f"{r.county} Co.", fontsize=10.5, color=INK2, va="center", ha="right")
fig.text(0.5, 0.02, "Source: PFBC State Fish Hatcheries layer and 2026 stocking schedule. Markers are nudged apart where hatcheries are close together.",
         fontsize=9, color=INK2, ha="center")

out = FIG_DIR / "all_hatcheries_map.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
