"""Slide maps: where one hatchery's fish go, coloured by the trout each stream section receives from it (a heat map over the sections).

Default is the three Centre County hatcheries (Bellefonte, Benner Spring, Pleasant Gap); pass hatchery names to make others
(e.g. `python scripts/figures/21_hatchery_heat_maps.py Corry`). One 16:9 image per hatchery.

Fish per section = the 2026 stocking schedule credit (scripts/09_stocking_schedule.py): each section's 2026 count is split equally over its scheduled
events and each event's share goes to the hatchery named for it; this sums stocking_events.alloc_fish over the hatchery's stream events. Sections
the hatchery does not supply are drawn in pale grey for context. All maps share one colour scale (300 to 10,000+ trout per section, sqrt scale) so
they can be compared side by side. Nothing is modelled here; it is a picture of the 2026 schedule. No title on purpose: it is added in PowerPoint.

Checks asserted: the per-section total equals hatchery_schedule_supply.csv for the hatchery (to rounding), and its sections are a subset of the
1,022 sections stocked in 2026.

Inputs : data/processed/stocking_events.parquet, sections.parquet, hatchery_schedule_supply.csv, hatchery_to_section_road_distance.parquet,
         pa_trout.gpkg (sections layer), data/raw/pa_hatcheries.gpkg, data/raw/pa_boundary.gpkg
Outputs: outputs/figures/allocation_problem/<hatchery>_heat_map.png   (16:9, 300 dpi)
         logs/21_hatchery_heat_maps.log

    python scripts/figures/21_hatchery_heat_maps.py [Hatchery name ...]
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

HATCHERIES = sys.argv[1:] or ["Bellefonte", "Benner Spring", "Pleasant Gap"]
FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
BLUE, HATCH, HATCH_EDGE, OTHER = "#2a78d6", "#f5ae00", "#2b2100", "#cdccc5"
setup_logging("21_hatchery_heat_maps")
log = logging.getLogger("21_hatchery_heat_maps")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Open Sans (the deck's font; SIL Open Font License), local only: see common.register_open_sans. Falls back to DejaVu Sans if absent.
register_open_sans()

# %% Load (once)
ev = pd.read_parquet(PROCESSED_DIR / "stocking_events.parquet")
ev = ev[ev.water_type == "stream"]
supply = pd.read_csv(PROCESSED_DIR / "hatchery_schedule_supply.csv").set_index("hatchery").stream_fish_2026
tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
stocked = set(tab.loc[tab.total_2026.fillna(0) > 0, "section_id"])
rd_all = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet", columns=["hatchery", "section_id", "road_mi"])
sec_all = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
sec_all = sec_all[sec_all.section_id.isin(stocked)]
hat_pts = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")
hat_pts["NAME"] = hat_pts.NAME.str.strip()
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")

VMIN, VMAX = 300, 10000                                                  # colour range (sqrt scale); sections above VMAX share the darkest shade
cmap = LinearSegmentedColormap.from_list("heat", ["#9cc0ee", BLUE, "#0a2a5e"])
norm = PowerNorm(0.5, vmin=VMIN, vmax=VMAX, clip=True)
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})


def draw(name: str):
    fish = ev[ev.hatchery == name].groupby("section_id").alloc_fish.sum().astype(float)
    fish = fish[fish > 0]
    assert len(fish) > 0, f"{name}: no stream fish on the 2026 schedule"
    assert abs(fish.sum() - supply[name]) < 5, f"{name}: per-section credits must add back to the hatchery's supply"
    assert set(fish.index) <= stocked, f"{name}: every section it supplies is one of the 1,022 stocked in 2026"
    rd = rd_all[(rd_all.hatchery == name) & rd_all.section_id.isin(fish.index)].road_mi
    assert len(rd) == len(fish)
    log.info("%s: %d sections, %.0f fish; road miles %.0f to %.0f, median %.0f; per-section fish median %.0f, max %.0f; %d sections above %d fish",
             name, len(fish), fish.sum(), rd.min(), rd.max(), rd.median(), fish.median(), fish.max(), (fish > VMAX).sum(), VMAX)
    sec = sec_all.merge(fish.rename("fish"), left_on="section_id", right_index=True, how="left")
    pt = hat_pts[hat_pts.NAME == name].iloc[0].geometry

    fig = plt.figure(figsize=(13.333, 7.5))
    ax = fig.add_axes([0.02, 0.06, 0.61, 0.82])
    pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
    sec[sec.fish.isna()].plot(ax=ax, color=OTHER, lw=0.8, zorder=1)
    sec[sec.fish.notna()].sort_values("fish").plot(ax=ax, column="fish", cmap=cmap, norm=norm, lw=2.8, zorder=2)   # biggest amounts on top
    ax.set_xlim(-80.85, -74.45)
    ax.set_ylim(39.6, 42.45)
    ax.set_aspect(1 / np.cos(np.radians(41)))
    ax.set_axis_off()
    ax.scatter([pt.x], [pt.y], s=520, c=HATCH, edgecolors=HATCH_EDGE, linewidths=1.6, zorder=6)
    ax.text(pt.x + 0.19, pt.y, name, fontsize=13, fontweight="bold", ha="left", va="center", zorder=7,
            path_effects=[pe.withStroke(linewidth=3.5, foreground="white")])

    pan = fig.add_axes([0.655, 0.06, 0.325, 0.82])
    pan.set_axis_off()
    pan.set_xlim(0, 1)
    pan.set_ylim(0, 1)
    pan.text(0, 1.0, f"{fish.sum() / 1000:,.0f}k", fontsize=30, fontweight="bold", color=BLUE, va="top")
    pan.text(0, 0.905, f"trout a year from {name} to\n{len(fish)} stream sections", fontsize=11.5, color=INK2, va="top", linespacing=1.25)
    pan.text(0, 0.71, "Trout a section receives", fontsize=12, fontweight="bold", va="center")
    cax = fig.add_axes([0.665, 0.575, 0.29, 0.03])
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    cb.set_ticks([300, 1000, 2500, 5000, 10000])
    cb.set_ticklabels(["300", "1,000", "2,500", "5,000", "10,000+"])
    cb.ax.tick_params(labelsize=10, colors=INK2, length=3)
    cb.outline.set_visible(False)
    pan.plot([0.0, 0.07], [0.47, 0.47], color=OTHER, lw=2.0, solid_capstyle="butt")
    pan.text(0.09, 0.47, f"Sections {name} does not supply", fontsize=10.5, color=INK2, va="center")
    pan.scatter([0.035], [0.395], s=260, c=HATCH, edgecolors=HATCH_EDGE, linewidths=1.4)
    pan.text(0.09, 0.395, f"{name} hatchery", fontsize=10.5, color=INK2, va="center")
    fig.text(0.5, 0.02, "Source: PFBC hatcheries layer, 2026 stocked sections and stocking schedule.", fontsize=9, color=INK2, ha="center")

    out = FIG_DIR / f"{name.lower().replace(' ', '_')}_heat_map.png"
    fig.savefig(out, dpi=300, facecolor=SURFACE)
    plt.close(fig)
    log.info("wrote %s", out)


# %% Draw
for h in HATCHERIES:
    draw(h)
