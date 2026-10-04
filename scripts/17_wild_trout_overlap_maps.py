"""Maps of where PFBC's stocked sections overlap wild-trout waters: Class A streams, and Natural Reproduction waters.

Overlap is the repo's definition (CLAUDE.md rule 8): shared river miles on the same RFP_WaterID, from `sections.class_a_overlap_mi` and
`sections.nat_repro_overlap_mi`, not a plain geometric intersect. The maps draw the wild-trout layer for context, all stocked sections
in grey, and the overlapping sections in colour.

Inputs : data/processed/sections.parquet (overlap miles, length_mi, total_2026), data/processed/pa_trout.gpkg (sections, class_a, nat_repro
         layers; gitignored, rebuilt by scripts 01-02), data/raw/pa_boundary.gpkg (state outline, optional)
Outputs: outputs/figures/wild_trout_overlap/class_a_overlap_map.png        18 sections, bars per section
         outputs/figures/wild_trout_overlap/nat_repro_overlap_map.png      531 sections, coloured by overlap miles, top 15 and a share histogram
         logs/17_wild_trout_overlap_maps.log

    python scripts/17_wild_trout_overlap_maps.py
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
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "wild_trout_overlap"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"      # reference palette slots 1-3: wild-trout water = aqua, overlap = orange
setup_logging("17_wild_trout_overlap_maps")
log = logging.getLogger("17_wild_trout_overlap_maps")
FIG_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})

tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "water_name", "county", "length_mi", "rm_length_mi", "class_a_overlap_mi",
                                                                    "nat_repro_overlap_mi", "total_2026", "latest_year"])
tab["stocked_2026"] = tab.total_2026.fillna(0) > 0
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg") if (RAW_DIR / "pa_boundary.gpkg").exists() else None


def base_map(ax, layer):
    if pa is not None:
        pa.boundary.plot(ax=ax, color=INK2, lw=0.9)
    layer.plot(ax=ax, color=AQUA, lw=0.7, alpha=0.5, zorder=1)
    sec.plot(ax=ax, color="#bdbcb5", lw=0.6, zorder=2)
    ax.set_aspect(1 / np.cos(np.radians(41)))
    ax.set_axis_off()


# %% Figure 1: Class A (18 sections, one bar each)
over = tab[tab.class_a_overlap_mi > 0].sort_values("class_a_overlap_mi", ascending=False).reset_index(drop=True)
assert len(over) == 18, "docs say 18 sections overlap Class A by river mile (CLAUDE.md Known facts)"
log.info("Class A: %d sections, %.2f river miles; %d stocked in 2026", len(over), over.class_a_overlap_mi.sum(), over.stocked_2026.sum())
class_a = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="class_a")
hit = sec.merge(over[["section_id", "class_a_overlap_mi", "stocked_2026"]], on="section_id")

fig = plt.figure(figsize=(18, 8.6))
gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 1], wspace=0.42)
fig.suptitle("Where stocked sections overlap Class A wild trout streams", x=0.012, ha="left", fontsize=15, fontweight="bold")
fig.text(0.012, 0.915, f"{len(over)} stocked sections share {over.class_a_overlap_mi.sum():.1f} river miles with Class A water ({int(over.stocked_2026.sum())} of them stocked in 2026). "
         "Overlap is measured in shared river miles on the same water, not by where the lines touch.", fontsize=10.5, color=INK2)
ax = fig.add_subplot(gs[0, 0])
base_map(ax, class_a)
hit.plot(ax=ax, color=ORANGE, lw=3.2, zorder=4)
cent = hit.geometry.apply(lambda g: g.interpolate(0.5, normalized=True))
rank = {sid: i + 1 for i, sid in enumerate(over.section_id)}
for k, ((_, r), pt) in enumerate(zip(hit.iterrows(), cent)):
    dx, dy = ((7, 7), (-7, 7), (7, -8), (-7, -8))[k % 4]
    ax.annotate(str(rank[r.section_id]), (pt.x, pt.y), xytext=(dx, dy), textcoords="offset points", fontsize=8.5, color=INK, ha="center", va="center",
                bbox=dict(facecolor=SURFACE, edgecolor=ORANGE, lw=1.0, boxstyle="circle,pad=0.18"), zorder=6,
                arrowprops=dict(arrowstyle="-", color=ORANGE, lw=0.7, shrinkA=0, shrinkB=0))
ax.legend(handles=[plt.Line2D([], [], color=AQUA, lw=2, alpha=0.7, label="Class A wild trout streams (1,361 reaches)"),
                   plt.Line2D([], [], color="#bdbcb5", lw=2, label="PFBC stocked sections (1,045)"),
                   plt.Line2D([], [], color=ORANGE, lw=3.2, label="Stocked sections that overlap Class A (18)")],
          loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=1, frameon=False, fontsize=10)
bx = fig.add_subplot(gs[0, 1])
y = np.arange(len(over))[::-1]
bx.barh(y, over.rm_length_mi, color="#e3e2dc", height=0.7, label="section's river-mile span")
bx.barh(y, over.class_a_overlap_mi, color=np.where(over.stocked_2026, ORANGE, "none"), edgecolor=ORANGE, height=0.42, label="river miles overlapping Class A")
for yi, (_, r) in zip(y, over.iterrows()):
    bx.text(r.rm_length_mi + 0.12, yi, f"{r.class_a_overlap_mi:.1f}", va="center", fontsize=9.5, color=INK)
bx.set_yticks(y)
bx.set_yticklabels([f"{i + 1}. {r.water_name} ({r.section_id})" + ("" if r.stocked_2026 else " (not stocked 2026)") for i, (_, r) in enumerate(over.iterrows())], fontsize=9.5)
bx.set_xlabel("river miles")
bx.set_title("Overlap miles by section", loc="left", fontsize=11.5)
bx.grid(axis="x", color=GRID, lw=0.8)
bx.set_axisbelow(True)
bx.legend(frameon=False, fontsize=9.5, loc="lower right")
fig.text(0.012, 0.012, "Grey bars are each section's river-mile span, the measure the overlap is taken from, so overlap never exceeds them. PFBC's own Length_MI_ is shorter for some sections "
         "(Martins Creek 3.4 mi vs 4.7 mi of river miles; docs/known_gaps.md). Buffalo Creek 3190_2 became Class A in 2026 and was dropped from the 2026 schedule (hollow bar).", fontsize=9.5, color=INK2)
fig.savefig(FIG_DIR / "class_a_overlap_map.png", dpi=115, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)

# %% Figure 2: Natural Reproduction waters (531 sections, so colour by overlap miles)
nr = tab[tab.nat_repro_overlap_mi > 0].copy()
nr["share"] = nr.nat_repro_overlap_mi / nr.rm_length_mi          # same measure as the overlap, so never above 100%
fish = nr.loc[nr.stocked_2026, "total_2026"].sum()
log.info("Natural Reproduction: %d sections, %.0f river miles; %d stocked in 2026 carrying %d of %d fish", len(nr), nr.nat_repro_overlap_mi.sum(),
         nr.stocked_2026.sum(), fish, tab.total_2026.fillna(0).sum())
nat = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="nat_repro")
hit = sec.merge(nr[["section_id", "nat_repro_overlap_mi"]], on="section_id")
cmap = LinearSegmentedColormap.from_list("ov", ["#f8d9c9", "#eb6834", "#8f2f0e"])
norm = Normalize(0, 15)

fig = plt.figure(figsize=(18, 9.2))
gs = fig.add_gridspec(2, 2, width_ratios=[1.55, 1], height_ratios=[1.35, 1], wspace=0.34, hspace=0.42)
fig.suptitle("Where stocked sections overlap Natural Reproduction (wild trout) waters", x=0.012, ha="left", fontsize=15, fontweight="bold")
fig.text(0.012, 0.925, f"{len(nr)} of PFBC's 1,045 stocked sections overlap them: {nr.nat_repro_overlap_mi.sum():,.0f} river miles, carrying "
         f"{fish / 1e6:.2f}M of the {tab.total_2026.fillna(0).sum() / 1e6:.2f}M fish stocked in 2026 ({100 * fish / tab.total_2026.fillna(0).sum():.0f}%).",
         fontsize=10.5, color=INK2)
fig.text(0.012, 0.9, "Overlap is shared river miles on the same water, not where the lines touch.", fontsize=10.5, color=INK2)
ax = fig.add_subplot(gs[:, 0])
base_map(ax, nat)
hit.sort_values("nat_repro_overlap_mi").plot(ax=ax, column="nat_repro_overlap_mi", cmap=cmap, norm=norm, lw=2.2, zorder=4)
cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=0.55, pad=0.03, aspect=22, location="bottom")
cb.set_label("river miles of overlap in the section (15 and up shown darkest)", color=INK2)
cb.outline.set_visible(False)
ax.legend(handles=[plt.Line2D([], [], color=AQUA, lw=2, alpha=0.7, label="Natural Reproduction waters (6,224 reaches)"),
                   plt.Line2D([], [], color="#bdbcb5", lw=2, label="PFBC stocked sections (1,045), not overlapping"),
                   plt.Line2D([], [], color=ORANGE, lw=2.5, label=f"Stocked sections that overlap ({len(nr)}), by overlap miles")],
          loc="upper left", bbox_to_anchor=(0.0, 1.07), ncol=1, frameon=False, fontsize=10)

top = nr.sort_values("nat_repro_overlap_mi", ascending=False).head(15).reset_index(drop=True)
bx = fig.add_subplot(gs[0, 1])
y = np.arange(len(top))[::-1]
bx.barh(y, top.rm_length_mi, color="#e3e2dc", height=0.72, label="section's river-mile span")
bx.barh(y, top.nat_repro_overlap_mi, color=ORANGE, height=0.44, label="river miles overlapping")
for yi, (_, r) in zip(y, top.iterrows()):
    bx.text(r.rm_length_mi + 0.2, yi, f"{r.nat_repro_overlap_mi:.1f}", va="center", fontsize=9, color=INK)
bx.set_yticks(y)
bx.set_yticklabels([f"{r.water_name} ({r.section_id})" for _, r in top.iterrows()], fontsize=9)
bx.set_xlabel("river miles")
bx.set_title("The 15 sections with the most overlap", loc="left", fontsize=11.5, pad=22)
bx.grid(axis="x", color=GRID, lw=0.8)
bx.set_axisbelow(True)
bx.legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2)

hx = fig.add_subplot(gs[1, 1])
hx.hist(nr.share, bins=np.linspace(0, 1.0, 21), color=ORANGE, edgecolor=SURFACE)
full = int((nr.share >= 0.9).sum())
hx.axvline(0.9, color=INK2, lw=1, ls="--")
hx.text(0.88, hx.get_ylim()[1] * 0.92, f"{full} of {len(nr)} sections ({100 * full / len(nr):.0f}%)\nare at least 90% overlapped", ha="right", va="top", fontsize=9.5, color=INK)
hx.set_xlabel("overlap miles as a share of the section's river-mile span")
hx.set_ylabel("sections")
hx.set_title("How fully each section is covered", loc="left", fontsize=11.5)
hx.grid(axis="y", color=GRID, lw=0.8)
hx.set_axisbelow(True)
fig.text(0.012, 0.012, f"Shares use river miles, the measure the overlap comes from. Against PFBC's Length_MI_ instead, {int((nr.nat_repro_overlap_mi > nr.length_mi * 1.02).sum())} sections would exceed 100%, because Length_MI_ is shorter than the river-mile span "
         "for them (docs/known_gaps.md). The 18 sections with a flagged line but no shared river miles are not counted.", fontsize=9.5, color=INK2)
fig.savefig(FIG_DIR / "nat_repro_overlap_map.png", dpi=115, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)
log.info("saved figures to %s", FIG_DIR.relative_to(ROOT))
