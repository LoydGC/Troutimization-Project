"""Slide map: which hatcheries serve the sections one hatchery used to supply, under the model's plan.

Takes every section the hatchery supplied in PFBC's 2026 schedule (run "baseline" in the model's saved plans: 198 for Bellefonte) and colours it by the
hatchery that supplies most of its fish in the model's plan ("none|dominance": more benefit at PFBC's 2026 cost and wild-trout impact). Sections it still
supplies at all keep its own colour (so its count matches script 35's "in both plans"); a section it no longer supplies takes the colour of the
hatchery with the larger share (4 sections are split between hatcheries in the plan).
Reads outputs/tables/optimization/flows.parquet (scripts/optimization.py). No title on purpose.

Inputs : outputs/tables/optimization/flows.parquet, data/processed/{hatcheries,sections}.parquet, pa_trout.gpkg, data/raw/pa_hatcheries.gpkg, pa_boundary.gpkg
Outputs: outputs/figures/allocation_problem/<hatchery>_who_replaced_map.png   logs/36_who_replaced_hatchery_map.log

    python scripts/36_who_replaced_hatchery_map.py [hatchery] [run_id]       (defaults: Bellefonte, none|dominance)
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

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

NAME = sys.argv[1] if len(sys.argv) > 1 else "Bellefonte"
RUN = sys.argv[2] if len(sys.argv) > 2 else "none|dominance"
FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2, OTHER = "#ffffff", "#0b0b0b", "#52514e", "#dddcd6"
COLOR = {"Bellefonte": "#f5ae00", "Benner Spring": "#2a78d6", "Tylersville": "#1baf7a", "Oswayo": "#a6192e", "Pleasant Gap": "#7b4fb0",
         "Tionesta": "#d81b7c", "Reynoldsdale": "#56b4e9", "Corry": "#8c9a1b", "Huntsdale": "#8a5d00"}
setup_logging("36_who_replaced_hatchery_map")
log = logging.getLogger("36_who_replaced_hatchery_map")
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

# %% Who serves the old sections
flows = pd.read_parquet(ROOT / "outputs" / "tables" / "optimization" / "flows.parquet")
old = flows[(flows.run_id == "baseline") & (flows.hatchery == NAME)].groupby("section_id").x.sum()
old = old[old > 0.5]
new = flows[(flows.run_id == RUN) & flows.section_id.isin(old.index) & (flows.x > 0.5)]
assert set(new.section_id) == set(old.index), "every section the hatchery used to supply is still stocked in the plan"
main = new.sort_values("x", ascending=False).drop_duplicates("section_id").set_index("section_id").hatchery
keeps = set(new.loc[new.hatchery == NAME, "section_id"])               # sections it still supplies at all (matches script 35's "in both plans")
main = main.where(~main.index.isin(keeps), NAME)
tab = new.groupby("hatchery").agg(sections=("section_id", "nunique"), fish=("x", "sum")).reindex(list(COLOR)).fillna(0)
main_n = main.value_counts().reindex(list(COLOR)).fillna(0).astype(int)
log.info("%s: %d sections in PFBC 2026; main supplier in the plan: %s; fish from each: %s", NAME, len(old), main_n.to_dict(), tab.fish.round(0).to_dict())
assert main_n.sum() == len(old)

sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
tabs = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
sec = sec[sec.section_id.isin(set(tabs.loc[tabs.total_2026.fillna(0) > 0, "section_id"]))].set_index("section_id")
hats = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")
hats["NAME"] = hats.NAME.str.strip()
hats = hats[hats.NAME.isin(COLOR)].set_index("NAME")
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")

# %% Draw
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.02, 0.06, 0.61, 0.76])
fig.suptitle(f"Who Supplies {NAME}'s Old Sections", x=0.012, y=0.985, ha="left", fontsize=40, color="#a6192e")
fig.text(0.014, 0.865, "Model plan: more angler benefit at PFBC's 2026 transport cost and wild-trout impact. Compared with PFBC's 2026 stocking schedule.", fontsize=13, color=INK2, va="center")
pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
sec.loc[sec.index.difference(old.index)].plot(ax=ax, color=OTHER, lw=0.8, zorder=1)
for h, c in COLOR.items():
    ids = main.index[main == h]
    if len(ids):
        sec.loc[ids].plot(ax=ax, color=c, lw=3.0, zorder=3 if h != NAME else 4)
ax.set_xlim(-80.85, -74.45)
ax.set_ylim(39.6, 42.45)
ax.set_aspect(1 / np.cos(np.radians(41)))
ax.set_axis_off()
NUDGE = {"Benner Spring": (-0.13, -0.10), "Pleasant Gap": (0.12, -0.12), "Bellefonte": (-0.02, 0.07)}               # the Centre County trio sits within a few miles
halo = [pe.withStroke(linewidth=3, foreground="white")]
for h, c in COLOR.items():
    g = hats.loc[h].geometry
    dx, dy = NUDGE.get(h, (0, 0))
    ax.scatter([g.x + dx], [g.y + dy], s=330 if h == NAME else 190, c=c, edgecolors="#1a1a1a", linewidths=1.6, zorder=6)

pan = fig.add_axes([0.655, 0.06, 0.325, 0.73])
pan.set_axis_off()
pan.set_xlim(0, 1)
pan.set_ylim(0, 1)
pan.text(0, 1.0, f"{len(old)} sections", fontsize=24, fontweight="bold", color="#0b0b0b", va="top")
pan.text(0, 0.90, f"supplied by {NAME} in 2026 are now\nsupplied by (hatchery with the most fish):", fontsize=11.5, color=INK2, va="top", linespacing=1.3)
order = main_n.sort_values(ascending=False)
for i, (h, n) in enumerate(order.items()):
    y = 0.78 - i * 0.082
    pan.scatter([0.03], [y], s=230, c=COLOR[h], edgecolors="#1a1a1a", linewidths=1.2)
    pan.text(0.10, y, h + (" (stays)" if h == NAME else ""), fontsize=12.5, fontweight="bold" if h == NAME else "normal", va="center")
    pan.text(0.98, y, f"{n}", fontsize=13, fontweight="bold", color=INK, ha="right", va="center")
pan.plot([0, 1], [0.78 - len(order) * 0.082 + 0.04] * 2, color="#e6e5e0", lw=1.2)
out = FIG_DIR / f"{NAME.lower().replace(' ', '_')}_who_replaced_map.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
