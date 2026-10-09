"""Slide map: one hatchery's trout under PFBC's 2026 schedule versus under the model's plan, overlaid.

Each stream section is one of three kinds (colour): supplied by the hatchery in BOTH plans (purple), only in PFBC's 2026 schedule (berry: the model drops it),
only in the model's plan (blue: the model adds it). Sections the hatchery does not supply in either plan are light grey. Fish amounts are in the two heat maps
(scripts/21 and 34); this one is about which sections change.
PFBC 2026 = the run "baseline" in the model's saved plans (stocking schedule credits); model plan = "none|dominance" (more benefit at PFBC's 2026 cost and
wild-trout impact). Both read from outputs/tables/optimization/flows.parquet. No title on purpose.

Checks asserted: both plans ship exactly the hatchery's 2026 supply.

Inputs : outputs/tables/optimization/flows.parquet, data/processed/{hatcheries,sections}.parquet, pa_trout.gpkg, data/raw/pa_hatcheries.gpkg, pa_boundary.gpkg
Outputs: outputs/figures/allocation_problem/<hatchery>_model_vs_pfbc_map.png   logs/35_model_vs_pfbc_overlay_map.log

    python scripts/35_model_vs_pfbc_overlay_map.py [hatchery] [run_id]       (defaults: Bellefonte, none|dominance)
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
from matplotlib.lines import Line2D

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

NAME = sys.argv[1] if len(sys.argv) > 1 else "Bellefonte"
RUN = sys.argv[2] if len(sys.argv) > 2 else "none|dominance"
FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
BOTH, OLD, NEW, OTHER = "#7b4fb0", "#a6192e", "#2a78d6", "#d9d8d2"
HATCH, HATCH_EDGE = "#f5ae00", "#2b2100"
setup_logging("35_model_vs_pfbc_overlay_map")
log = logging.getLogger("35_model_vs_pfbc_overlay_map")
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

# %% Load and compare
flows = pd.read_parquet(ROOT / "outputs" / "tables" / "optimization" / "flows.parquet")
supply = pd.read_parquet(PROCESSED_DIR / "hatcheries.parquet").set_index("hatchery").supply[NAME]


def plan(run):
    s = flows[(flows.run_id == run) & (flows.hatchery == NAME)].groupby("section_id").x.sum().astype(float)
    assert abs(s.sum() - supply) < 5, f"{run}: {NAME} ships exactly its 2026 supply"
    return s[s > 0.5]


old, new = plan("baseline"), plan(RUN)
both, only_old, only_new = sorted(set(old.index) & set(new.index)), sorted(set(old.index) - set(new.index)), sorted(set(new.index) - set(old.index))
log.info("%s: PFBC 2026 %d sections, model %d; both %d, only PFBC %d (%.0f fish), only model %d (%.0f fish); in both: PFBC %.0f fish, model %.0f fish",
         NAME, len(old), len(new), len(both), len(only_old), old[only_old].sum(), len(only_new), new[only_new].sum(), old[both].sum(), new[both].sum())
assert len(both) + len(only_old) == len(old) and len(both) + len(only_new) == len(new)

tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
stocked = set(tab.loc[tab.total_2026.fillna(0) > 0, "section_id"])
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
sec = sec[sec.section_id.isin(stocked)].set_index("section_id")
hat = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")
hat = hat[hat.NAME.str.strip() == NAME].iloc[0].geometry
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")

# %% Draw
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.02, 0.06, 0.61, 0.76])
fig.suptitle(f"{NAME}'s Sections: Model Plan vs. PFBC 2026", x=0.012, y=0.985, ha="left", fontsize=40, color="#a6192e")
fig.text(0.014, 0.865, "Model plan: more angler benefit at PFBC's 2026 transport cost and wild-trout impact. Compared with PFBC's 2026 stocking schedule.", fontsize=13, color=INK2, va="center")
pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
rest = sec.index.difference(old.index.union(new.index))
sec.loc[rest].plot(ax=ax, color=OTHER, lw=0.8, zorder=1)
sec.loc[only_old].plot(ax=ax, color=OLD, lw=2.8, zorder=2)
sec.loc[only_new].plot(ax=ax, color=NEW, lw=2.8, zorder=3)
sec.loc[both].plot(ax=ax, color=BOTH, lw=3.2, zorder=4)
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
pan.text(0, 1.0, f"{len(both)} of {len(old)}", fontsize=30, fontweight="bold", color=BOTH, va="top")
pan.text(0, 0.905, f"sections {NAME} supplied in PFBC's 2026\nschedule are still supplied in the model's plan", fontsize=11.5, color=INK2, va="top", linespacing=1.25)
rows = [(BOTH, 3.4, f"In both plans ({len(both)})"), (OLD, 3.0, f"PFBC 2026 only: dropped by the model ({len(only_old)})"),
        (NEW, 3.0, f"Model only: added ({len(only_new)})"), (OTHER, 2.0, f"Not supplied by {NAME} in either plan")]
for i, (c, lw, t) in enumerate(rows):
    y = 0.66 - i * 0.085
    pan.plot([0.0, 0.08], [y, y], color=c, lw=lw + 0.6, solid_capstyle="butt")
    pan.text(0.11, y, t, fontsize=11.5, color=INK, va="center")
pan.scatter([0.04], [0.66 - 4 * 0.085], s=260, c=HATCH, edgecolors=HATCH_EDGE, linewidths=1.4)
pan.text(0.11, 0.66 - 4 * 0.085, f"{NAME} hatchery", fontsize=11.5, color=INK, va="center")
out = FIG_DIR / f"{NAME.lower().replace(' ', '_')}_model_vs_pfbc_map.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
