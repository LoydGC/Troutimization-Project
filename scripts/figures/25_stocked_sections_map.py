"""Slide map: the stocked stream sections only (no hatcheries, no schedule). A clean picture of the model's destinations.

The 1,022 stream sections PFBC stocks in 2026 (sections.total_2026 > 0), drawn as one colour over the state outline. A small key gives the
count and the river miles (sections.length_mi). No title on purpose: it is added in the deck.

Inputs : data/processed/sections.parquet, data/processed/pa_trout.gpkg (sections layer; gitignored, rebuilt by scripts 01-02),
         data/raw/pa_boundary.gpkg
Outputs: outputs/figures/allocation_problem/stocked_sections_map.png   (16:9, 300 dpi)
         logs/25_stocked_sections_map.log

    python scripts/figures/25_stocked_sections_map.py
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
from matplotlib.lines import Line2D

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/, where common.py lives
from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging, register_open_sans

FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
BLUE = "#2a78d6"
setup_logging("25_stocked_sections_map")
log = logging.getLogger("25_stocked_sections_map")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Open Sans (the deck's font; SIL Open Font License), local only: see common.register_open_sans. Falls back to DejaVu Sans if absent.
register_open_sans()

# %% Load
tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026", "length_mi"])
tab = tab[tab.total_2026.fillna(0) > 0]
assert len(tab) == 1022, "docs say the candidate set is the 1,022 sections stocked in 2026"
miles = float(tab.length_mi.sum())
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
sec = sec[sec.section_id.isin(set(tab.section_id))]
assert len(sec) == 1022
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")
log.info("%d stocked stream sections, %.0f river miles (length_mi), %d with missing length", len(sec), miles, tab.length_mi.isna().sum())

# %% Draw
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})
fig = plt.figure(figsize=(13.333, 7.5))
# No title on purpose: added in the deck. The space above the map is left clear for it.
ax = fig.add_axes([0.03, 0.09, 0.94, 0.79])
pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.3, zorder=0)
sec.plot(ax=ax, color=BLUE, lw=1.6, zorder=2)
ax.set_xlim(-80.75, -74.55)
ax.set_ylim(39.6, 42.35)
ax.set_aspect(1 / np.cos(np.radians(41)))
ax.set_axis_off()
fig.legend([Line2D([], [], color=BLUE, lw=3.2)], [f"Stocked stream section ({len(sec):,} sections, about {miles:,.0f} river miles)"],
           loc="lower center", bbox_to_anchor=(0.5, 0.02), frameon=False, fontsize=13, handlelength=2.2)

out = FIG_DIR / "stocked_sections_map.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
