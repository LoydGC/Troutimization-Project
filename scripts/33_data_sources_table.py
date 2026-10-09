"""Appendix slide: the data sources behind the model, as a clean three-column table (what, where from, what it does in the model).

Content is a hand-written summary of docs/source_inventory.md (sources, URLs and dates are there) and docs/model_design.md. Counts are checked against the
saved tables where one exists. No title on purpose: it is added in the deck.

Inputs : data/processed/sections.parquet, hatcheries.parquet, county_subdivisions.parquet
Outputs: outputs/figures/allocation_problem/data_sources_table.png   logs/33_data_sources_table.log

    python scripts/33_data_sources_table.py
"""
# %% Setup
from __future__ import annotations

import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from common import PROCESSED_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2, GRID, BLUE = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e0", "#2a78d6"
setup_logging("33_data_sources_table")
log = logging.getLogger("33_data_sources_table")
FIG_DIR.mkdir(parents=True, exist_ok=True)

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
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})

# %% Checks on the counts quoted in the table
sec = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
n_sec, n_2026 = len(sec), int((sec.total_2026.fillna(0) > 0).sum())
n_h = len(pd.read_parquet(PROCESSED_DIR / "hatcheries.parquet"))
n_sub = len(pd.read_parquet(PROCESSED_DIR / "county_subdivisions.parquet"))
assert (n_sec, n_2026, n_h, n_sub) == (1045, 1022, 13, 2567)
log.info("counts ok: %d sections (%d stocked in 2026), %d hatcheries, %d county subdivisions", n_sec, n_2026, n_h, n_sub)

ROWS = [
    ("Stocked stream sections", "PFBC stocked-sections layers, 2024 to 2026", f"The {n_2026:,} destinations, the baseline, density caps"),
    ("Stocking schedule", "PFBC 2026 trout stocking schedule", "Hatchery supply and which trucks serve which sections"),
    ("State fish hatcheries", f"PFBC State Fish Hatcheries layer ({n_h})", "Supply points: where the fish come from"),
    ("Wild trout waters", "PASDA: Class A, natural reproduction, wilderness", "The wild-trout impact objective and exclusions"),
    ("Stocking rates", "PFBC Operational Guidelines, 5th edition", "Maximum trout per acre, the cap on each section"),
    ("Angler survey", "PFBC 2023 trout angler survey", "Days fished, travel distance and favorite waters"),
    ("Angler counts", "PFBC 2024 license sales by county", "How many anglers live where"),
    ("Population", f"U.S. Census, {n_sub:,} county subdivisions", "Where anglers start their trips"),
    ("Road distances", "OpenStreetMap roads, routed with OSRM", "Truck miles and the clusters"),
    ("Truck cost", "Trucking industry cost report; PFBC pay rates", "$1.90 per truck-mile"),
]

# %% Draw
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_axis_off()
ax.set_xlim(0, 13.333)
ax.set_ylim(0, 7.5)
X = (0.7, 4.2, 8.3)
TOP, ROW_H = 6.55, 0.585
for x, h in zip(X, ("Data", "Source", "Used in the model for")):
    ax.text(x, TOP + 0.25, h, fontsize=13, fontweight="bold", color=BLUE, va="center")
ax.plot([0.6, 12.75], [TOP, TOP], color=BLUE, lw=2)
for i, (what, src, use) in enumerate(ROWS):
    y = TOP - (i + 0.5) * ROW_H
    ax.text(X[0], y, what, fontsize=13, fontweight="bold", va="center")
    ax.text(X[1], y, src, fontsize=12, color=INK2, va="center")
    ax.text(X[2], y, use, fontsize=12, color=INK2, va="center")
    ax.plot([0.6, 12.75], [TOP - (i + 1) * ROW_H] * 2, color=GRID, lw=1)
ax.text(0.7, 0.28, "All sources are official or public. Links and retrieval dates: docs/source_inventory.md.", fontsize=9.5, color="#6b6a66", va="center")
out = FIG_DIR / "data_sources_table.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
