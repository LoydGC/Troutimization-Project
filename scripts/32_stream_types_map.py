"""Slide map: every stream category in the project, overlaid. Stocked sections (the model's destinations) on top of the wild-trout layers.

Layers (all from data/processed/pa_trout.gpkg, rebuilt from PFBC / PASDA by scripts 01-02; counts are features in each layer):
  Natural reproduction waters (PASDA PAFishBoat #25, 6,224)  wild trout reproduce here (presence only)       drawn first, light teal
  Class A wild trout streams  (PASDA #9, 1,361)              highest wild-trout class; stocking only by Commission approval
  Wilderness trout streams    (PASDA #31, 134)               never stocked
  Stocked stream sections     (2026 layer, 1,022 with fish)  the model's destinations                          drawn last, blue
Overlap between stocked sections and the wild layers is what the wild-trout impact objective scores (docs/model_design.md). No title on purpose.

Inputs : data/processed/pa_trout.gpkg (sections, nat_repro, class_a, wilderness layers), sections.parquet, data/raw/pa_boundary.gpkg
Outputs: outputs/figures/allocation_problem/stream_types_map.png   logs/32_stream_types_map.log

    python scripts/32_stream_types_map.py
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

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
NAT, CLASS_A, WILD, STOCK = "#8fd3bd", "#1a8f5e", "#7b4fb0", "#2a78d6"
setup_logging("32_stream_types_map")
log = logging.getLogger("32_stream_types_map")
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
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})

# %% Load
gpkg = PROCESSED_DIR / "pa_trout.gpkg"
tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
stocked = set(tab.loc[tab.total_2026.fillna(0) > 0, "section_id"])
sec = gpd.read_file(gpkg, layer="sections")[["section_id", "geometry"]]
sec = sec[sec.section_id.isin(stocked)]
nat, ca, wild = (gpd.read_file(gpkg, layer=l)[["geometry"]] for l in ("nat_repro", "class_a", "wilderness"))
assert (len(sec), len(nat), len(ca), len(wild)) == (1022, 6224, 1361, 134)
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")
log.info("layers: stocked %d, natural reproduction %d, Class A %d, wilderness %d", len(sec), len(nat), len(ca), len(wild))

# %% Draw
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.02, 0.13, 0.96, 0.85])
pa.plot(ax=ax, facecolor="white", edgecolor=INK2, lw=1.2, zorder=0)
nat.plot(ax=ax, color=NAT, lw=0.9, zorder=1)
ca.plot(ax=ax, color=CLASS_A, lw=1.6, zorder=2)
wild.plot(ax=ax, color=WILD, lw=1.8, zorder=3)
sec.plot(ax=ax, color=STOCK, lw=1.7, zorder=4)
ax.set_xlim(-80.65, -74.45)
ax.set_ylim(39.65, 42.45)
ax.set_aspect(1 / np.cos(np.radians(41)))
ax.set_axis_off()
items = [(STOCK, 3.0, f"Stocked stream sections ({len(sec):,})"), (NAT, 2.2, f"Natural reproduction waters ({len(nat):,})"),
         (CLASS_A, 3.0, f"Class A wild trout streams ({len(ca):,})"), (WILD, 3.0, f"Wilderness trout streams ({len(wild):,})")]
fig.legend([Line2D([], [], color=c, lw=lw) for c, lw, _ in items], [t for _, _, t in items], loc="lower center", ncol=2, frameon=False, fontsize=12.5,
           handlelength=2.2, columnspacing=3.0, bbox_to_anchor=(0.5, 0.005))
out = FIG_DIR / "stream_types_map.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
