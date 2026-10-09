"""Slide map of the optimization model's result: where one hatchery's trout go under a model plan, coloured by trout per stream section.

Reads x[h, s] from the model's saved plans (outputs/tables/optimization/flows.parquet, written by scripts/optimization.py; one run_id per plan).
Default plan = "none|dominance": the best plan that is no worse than PFBC's 2026 plan on transport cost and wild-trout impact (the "more benefit" way to
beat PFBC; no change limit). Same colour scale, map frame and style as scripts/figures/21_hatchery_heat_maps.py (which draws PFBC's 2026 schedule), so the two
can be set side by side. No title on purpose.

Checks asserted: the hatchery ships exactly its 2026 supply, and every section it supplies is one of the 1,022 candidates.

Inputs : outputs/tables/optimization/{flows.parquet,runs.csv}, data/processed/{hatcheries.parquet,sections.parquet,pa_trout.gpkg},
         data/raw/pa_hatcheries.gpkg, data/raw/pa_boundary.gpkg
Outputs: outputs/figures/<hatchery>_results/1_model_plan_heat_map.png   logs/34_model_plan_heat_map.log

    python scripts/figures/34_model_plan_heat_map.py [hatchery] [run_id]       (defaults: Bellefonte, none|dominance)
"""
# %% Setup
from __future__ import annotations

import logging
import sys

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, PowerNorm

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/, where common.py lives
from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging, register_open_sans

NAME = sys.argv[1] if len(sys.argv) > 1 else "Bellefonte"
RUN = sys.argv[2] if len(sys.argv) > 2 else "none|dominance"
OPT = ROOT / "outputs" / "tables" / "optimization"
FIG_DIR = ROOT / "outputs" / "figures" / f"{NAME.lower().replace(' ', '_')}_results"
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
BLUE, HATCH, HATCH_EDGE, OTHER = "#2a78d6", "#f5ae00", "#2b2100", "#cdccc5"
setup_logging("34_model_plan_heat_map")
log = logging.getLogger("34_model_plan_heat_map")
FIG_DIR.mkdir(parents=True, exist_ok=True)

register_open_sans()

# %% Load and check
flows = pd.read_parquet(OPT / "flows.parquet")
assert RUN in set(flows.run_id), f"unknown run {RUN}"
fish = flows[(flows.run_id == RUN) & (flows.hatchery == NAME)].groupby("section_id").x.sum().astype(float)
fish = fish[fish > 0.5]
supply = pd.read_parquet(PROCESSED_DIR / "hatcheries.parquet").set_index("hatchery").supply[NAME]
assert abs(fish.sum() - supply) < 5, "the hatchery ships exactly its 2026 supply"
tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
stocked = set(tab.loc[tab.total_2026.fillna(0) > 0, "section_id"])
assert set(fish.index) <= stocked
base = flows[(flows.run_id == "baseline") & (flows.hatchery == NAME)].groupby("section_id").x.sum()
gained, dropped = len(set(fish.index) - set(base.index)), len(set(base.index) - set(fish.index))
log.info("%s, run %s: %d sections, %.0f fish (supply %.0f); PFBC 2026 had %d sections; %d new, %d dropped; per-section median %.0f, max %.0f, %d above 10,000",
         NAME, RUN, len(fish), fish.sum(), supply, len(base), gained, dropped, fish.median(), fish.max(), (fish > 10000).sum())

sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
sec = sec[sec.section_id.isin(stocked)].merge(fish.rename("fish"), left_on="section_id", right_index=True, how="left")
hat = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")
hat = hat[hat.NAME.str.strip() == NAME].iloc[0].geometry
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")

# %% Draw
cmap = LinearSegmentedColormap.from_list("heat", ["#9cc0ee", BLUE, "#0a2a5e"])
norm = PowerNorm(0.5, vmin=300, vmax=10000, clip=True)
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.02, 0.06, 0.61, 0.76])
fig.suptitle(f"Where the Model Sends {NAME}'s Trout", x=0.012, y=0.985, ha="left", fontsize=40, color="#a6192e")
fig.text(0.014, 0.865, "Model plan: more angler benefit at PFBC's 2026 transport cost and wild-trout impact.", fontsize=13, color=INK2, va="center")
pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
sec[sec.fish.isna()].plot(ax=ax, color=OTHER, lw=0.8, zorder=1)
sec[sec.fish.notna()].sort_values("fish").plot(ax=ax, column="fish", cmap=cmap, norm=norm, lw=2.8, zorder=2)
ax.set_xlim(-80.85, -74.45)
ax.set_ylim(39.6, 42.45)
ax.set_aspect(1 / np.cos(np.radians(41)))
ax.set_axis_off()
ax.scatter([hat.x], [hat.y], s=520, c=HATCH, edgecolors=HATCH_EDGE, linewidths=1.6, zorder=6)
ax.text(hat.x + 0.19, hat.y, NAME, fontsize=13, fontweight="bold", ha="left", va="center", zorder=7, path_effects=[pe.withStroke(linewidth=3.5, foreground="white")])

pan = fig.add_axes([0.655, 0.06, 0.325, 0.73])
pan.set_axis_off()
pan.set_xlim(0, 1)
pan.set_ylim(0, 1)
pan.text(0, 1.0, f"{fish.sum() / 1000:,.0f}k", fontsize=30, fontweight="bold", color=BLUE, va="top")
pan.text(0, 0.905, f"trout a year from {NAME} to\n{len(fish)} stream sections", fontsize=11.5, color=INK2, va="top", linespacing=1.25)
pan.text(0, 0.71, "Trout a section receives", fontsize=12, fontweight="bold", va="center")
cax = fig.add_axes([0.665, 0.527, 0.29, 0.026])
cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
cb.set_ticks([300, 1000, 2500, 5000, 10000])
cb.set_ticklabels(["300", "1,000", "2,500", "5,000", "10,000+"])
cb.ax.tick_params(labelsize=10, colors=INK2, length=3)
cb.outline.set_visible(False)
pan.plot([0.0, 0.07], [0.47, 0.47], color=OTHER, lw=2.0, solid_capstyle="butt")
pan.text(0.09, 0.47, f"Sections {NAME} does not supply", fontsize=10.5, color=INK2, va="center")
pan.scatter([0.035], [0.395], s=260, c=HATCH, edgecolors=HATCH_EDGE, linewidths=1.4)
pan.text(0.09, 0.395, f"{NAME} hatchery", fontsize=10.5, color=INK2, va="center")
out = FIG_DIR / "1_model_plan_heat_map.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
