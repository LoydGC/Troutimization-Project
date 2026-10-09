"""Slide visuals for the model's clusters: k-medoids on road miles, no limits, k chosen by best silhouette (310 clusters).

This is the clustering the model uses for haul cost (scripts/20_transport_cost.py, BASE_CLUSTERING = "kmedoids"; labels in
section_medoid_clusters.silhouette_best_cluster_id; averages in cluster_hatchery_distance, method kmedoids_best_silhouette).
Three images, deck style (Open Sans, 16:9, no titles; they are added in the deck):
  kmedoids_map.png      the 310 clusters on the state: hull shaded by sections per cluster, dots = sections alone, key numbers
  kmedoids_example.png  one 4-section cluster zoomed in, and each member's road miles from Bellefonte next to the average the model uses
  kmedoids_choosing_k.png  mean silhouette for every k tried (20 to 700), with k = 310 marked

Inputs : data/processed/section_medoid_clusters.parquet, cluster_hatchery_distance.parquet, hatchery_to_section_road_distance.parquet,
         sections.parquet, pa_trout.gpkg (sections layer), data/raw/pa_boundary.gpkg, outputs/tables/medoid_clusters/{comparison,silhouette_by_k}.csv
Outputs: outputs/figures/kmedoids/*.png   logs/26_kmedoids_visuals.log

    python scripts/26_kmedoids_visuals.py
"""
# %% Setup
from __future__ import annotations

import logging

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "kmedoids"
TAB_DIR = ROOT / "outputs" / "tables" / "medoid_clusters"
SURFACE, INK, INK2, GRID = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, AMBER, AMBER_TEXT, OTHER = "#2a78d6", "#f5ae00", "#8a5d00", "#cdccc5"
setup_logging("26_kmedoids_visuals")
log = logging.getLogger("26_kmedoids_visuals")
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
lab = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet", columns=["section_id", "silhouette_best_cluster_id"]) \
    .rename(columns={"silhouette_best_cluster_id": "cluster"})
tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "water_name", "total_2026"])
stocked = tab[tab.total_2026.fillna(0) > 0]
lab = lab[lab.section_id.isin(stocked.section_id)]
assert len(lab) == 1022 and lab.cluster.nunique() == 310, "docs: 310 clusters over the 1,022 stocked sections"
size = lab.cluster.value_counts()
lab["size"] = lab.cluster.map(size)
cmp_ = pd.read_csv(TAB_DIR / "comparison.csv", index_col=0)
col = [c for c in cmp_.columns if "310" in c][0]
widest, err_txt = float(cmp_.loc["widest (mi)", col]), cmp_.loc["hatchery_distance_error", col]
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]].merge(lab, on="section_id")
assert len(sec) == 1022
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")
sec_m = sec.to_crs(26918)
hull = sec_m.dissolve("cluster", aggfunc={"size": "first"}).convex_hull.rename("geometry").to_frame()
hull["size"] = sec_m.groupby("cluster")["size"].first()
hull = gpd.GeoDataFrame(hull, geometry="geometry", crs=26918)
alone = sec_m[sec_m["size"] == 1].copy()
alone["geometry"] = alone.geometry.representative_point()
log.info("%d clusters; sizes: alone %d, pairs %d, 3-5 %d, 6+ %d, biggest %d, mean %.2f; widest %.0f mi; hatchery-distance error: %s",
         len(size), (size == 1).sum(), (size == 2).sum(), size.between(3, 5).sum(), (size >= 6).sum(), size.max(), size.mean(), widest, err_txt)
cmap = LinearSegmentedColormap.from_list("sz", ["#cfe3fa", BLUE, "#0a2a5e"])
norm = Normalize(2, 9)

# %% Figure 1: the 310 clusters on the state
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.02, 0.06, 0.61, 0.82])
pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
h2 = hull[hull["size"] >= 2].to_crs(4326)
h2.plot(ax=ax, color=[cmap(norm(s)) for s in h2["size"]], edgecolor="#0b2a5e", lw=0.6, alpha=0.9, zorder=2)
alone.to_crs(4326).plot(ax=ax, color=AMBER, edgecolor="#2b2100", linewidth=0.5, markersize=22, zorder=4)
ax.set_xlim(-80.85, -74.45)
ax.set_ylim(39.6, 42.45)
ax.set_aspect(1 / np.cos(np.radians(41)))
ax.set_axis_off()
# Legend and key numbers sit under the map; the right-hand side is left clear for the method explanation added in the deck.
ov = fig.add_axes([0, 0, 1, 1])
ov.set_axis_off()
ov.set_xlim(0, 1)
ov.set_ylim(0, 1)
ov.text(0.04, 0.136, "Sections per cluster", fontsize=11.5, fontweight="bold", va="center")
cax = fig.add_axes([0.04, 0.083, 0.20, 0.022])
cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
cb.set_ticks([2, 4, 6, 8, 9])
cb.set_ticklabels(["2", "4", "6", "8", "9"])
cb.ax.tick_params(labelsize=9.5, colors=INK2, length=3)
cb.outline.set_visible(False)
ov.scatter([0.285], [0.094], s=90, c=AMBER, edgecolors="#2b2100", linewidths=0.8)
ov.text(0.30, 0.094, f"{(size == 1).sum()} sections stand alone", fontsize=11, color=INK, va="center")
ov.text(0.04, 0.032, f"{len(size)} clusters  ·  {size.mean():.1f} sections per cluster on average  ·  widest cluster {widest:.0f} mi "
        "(the longest road distance between any two of its sections)", fontsize=10.5, color=INK2, va="center")     # width = max pairwise road miles (script 13)
fig.savefig(FIG_DIR / "kmedoids_map.png", dpi=300, facecolor=SURFACE)
plt.close(fig)
log.info("wrote kmedoids_map.png")

# %% Figure 2: one cluster up close, and the average the model uses
cdh = pd.read_parquet(PROCESSED_DIR / "cluster_hatchery_distance.parquet")
cdh = cdh[(cdh.method == "kmedoids_best_silhouette") & (cdh.hatchery == "Bellefonte") & (cdh.n_sections == 4)]
cdh = cdh.assign(spread=cdh.max_road_mi - cdh.min_road_mi)
diag = hull.geometry.apply(lambda g: np.hypot(g.bounds[2] - g.bounds[0], g.bounds[3] - g.bounds[1]) / 1609.344)       # miles across the cluster
cdh = cdh.assign(diag_mi=cdh.cluster_id.map(diag))
cand = cdh[cdh.diag_mi.between(8, 20)]
pick = cand.iloc[(cand.spread - 15).abs().argsort()].iloc[0]       # a 4-section cluster with a visible spread in distances (about 15 mi)
cid = pick.cluster_id
mem = sec[sec.cluster == cid].merge(stocked[["section_id", "water_name"]], on="section_id", suffixes=("", "_t"))
rd = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet", columns=["hatchery", "section_id", "road_mi"])
rd = rd[(rd.hatchery == "Bellefonte") & rd.section_id.isin(mem.section_id)].set_index("section_id").road_mi
mem["road_mi"] = mem.section_id.map(rd)
mem = mem.sort_values("road_mi").reset_index(drop=True)
avg = float(mem.road_mi.mean())
assert abs(avg - pick.avg_road_mi) < 0.01, "the cluster average must match cluster_hatchery_distance"
log.info("example cluster %s: %s road miles from Bellefonte %s, average %.1f", cid, list(mem.water_name), mem.road_mi.round(1).tolist(), avg)

fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.02, 0.06, 0.52, 0.82])
hc = hull[hull.index == cid].to_crs(4326).geometry.iloc[0]
cx, cy = hc.centroid.x, hc.centroid.y
half = max(0.12, (hull.loc[cid].geometry.bounds[3] - hull.loc[cid].geometry.bounds[1]) / 111000 * 1.8)
ax.set_xlim(cx - half * 1.25, cx + half * 1.25)
ax.set_ylim(cy - half, cy + half)
ax.set_aspect(1 / np.cos(np.radians(cy)))
sec.plot(ax=ax, color=OTHER, lw=1.0, zorder=1)
hull.to_crs(4326).plot(ax=ax, facecolor="none", edgecolor="#9fb9d9", lw=0.8, zorder=2)
gpd.GeoSeries([hc], crs=4326).plot(ax=ax, facecolor="#e3eefb", edgecolor=BLUE, lw=2.0, alpha=0.7, zorder=3)
mem.plot(ax=ax, color=BLUE, lw=3.6, zorder=5)
for i, r in mem.iterrows():
    p = r.geometry.representative_point()
    ax.annotate(str(i + 1), (p.x, p.y), xytext=(14, 14), textcoords="offset points", ha="center", va="center", fontsize=11, fontweight="bold", color="white", zorder=7,
                bbox=dict(boxstyle="circle,pad=0.3", fc=INK, ec="white", lw=1.2))
ax.set_axis_off()
bx = fig.add_axes([0.70, 0.16, 0.26, 0.54])
y = np.arange(len(mem))[::-1]
lo, hi = mem.road_mi.min() - 8, mem.road_mi.max() + 8
bx.hlines(y, lo, mem.road_mi, color="#b9d3f2", lw=3, zorder=2)
bx.scatter(mem.road_mi, y, s=260, c=BLUE, edgecolors="white", linewidths=1.5, zorder=4)
for yi, v in zip(y, mem.road_mi):
    bx.text(v, yi + 0.33, f"{v:.0f}", va="bottom", ha="center", color=INK, fontsize=12, fontweight="bold")
bx.axvline(avg, color=AMBER, lw=3, zorder=3)
bx.text(avg, len(mem) - 0.25, f"average {avg:.0f}", color=AMBER_TEXT, fontsize=12, fontweight="bold", ha="center", va="bottom")
bx.set_xlim(lo, hi)
bx.set_ylim(-0.6, len(mem) - 0.1)
bx.set_yticks(y)
bx.set_yticklabels([f"{i + 1}" for i in range(len(mem))], fontsize=12)
bx.tick_params(axis="x", labelsize=10, colors=INK2, length=0)
bx.tick_params(axis="y", length=0)
for s_ in ("top", "right", "left"):
    bx.spines[s_].set_visible(False)
bx.spines["bottom"].set_color(INK2)
bx.grid(axis="x", color=GRID, zorder=0)
bx.set_xlabel("one-way road miles from Bellefonte", fontsize=11, color=INK2)
fig.text(0.58, 0.84, "One cluster, four sections", fontsize=15, fontweight="bold", ha="left")
fig.text(0.58, 0.795, f"Each section is a different distance from the hatchery.\nThe model costs all four at the cluster average, {avg:.0f} miles.", fontsize=11, color=INK2, ha="left", va="top", linespacing=1.3)
fig.text(0.5, 0.02, "Example: one typical 4-section cluster. Distances are OSRM road miles; the average is the cluster's mean, as in cluster_hatchery_distance.",
         fontsize=9, color=INK2, ha="center")
fig.savefig(FIG_DIR / "kmedoids_example.png", dpi=300, facecolor=SURFACE)
plt.close(fig)
log.info("wrote kmedoids_example.png")

# %% Figure 3: choosing k
sk = pd.read_csv(TAB_DIR / "silhouette_by_k.csv")
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0.09, 0.10, 0.86, 0.80])
ax.plot(sk.clusters, sk.silhouette, color=BLUE, lw=2.4, marker="o", ms=5, zorder=3)
best = sk.loc[sk.clusters == 310].iloc[0]
ax.scatter([310], [best.silhouette], s=170, c=AMBER, edgecolors="#2b2100", linewidths=1.6, zorder=5)
ax.annotate("310 clusters\nsilhouette 0.39", (310, best.silhouette), xytext=(60, 28), textcoords="offset points", fontsize=14, fontweight="bold", ha="left",
            arrowprops=dict(arrowstyle="-", color=INK, lw=1))
ax.set_xlim(0, 720)
ax.set_ylim(0.2, 0.45)
ax.set_xlabel("number of clusters tried", fontsize=13, color=INK2, labelpad=10)
ax.set_ylabel("mean silhouette score  (higher = tighter, better separated)", fontsize=12.5, color=INK2, labelpad=10)
ax.tick_params(labelsize=12, colors=INK2, length=0)
ax.grid(axis="y", color=GRID, zorder=0)
for s_ in ("top", "right", "left"):
    ax.spines[s_].set_visible(False)
ax.spines["bottom"].set_color(INK2)
fig.savefig(FIG_DIR / "kmedoids_choosing_k.png", dpi=300, facecolor=SURFACE)
plt.close(fig)
log.info("wrote kmedoids_choosing_k.png")
