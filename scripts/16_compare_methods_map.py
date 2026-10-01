"""Map every clustering method side by side, with the sections left alone (clusters of one section) highlighted.

Visual comparison only. A section is "left alone" when its cluster has no other section in it.
Last panel: how many of the methods leave each section alone (sections alone under many methods are the robustly
remote ones). The methods use only road miles between sections, except Nate's, which is built from the schedule.

Inputs : data/processed/section_to_section_road_distance.parquet (12), section_schedule.parquet (Nate's clusters),
         section_medoid_clusters.parquet (13), section_hierarchical_clusters.parquet (15), pa_trout.gpkg, data/raw/pa_boundary.gpkg
Outputs: outputs/figures/method_comparison/single_section_trips.png
         logs/16_compare_methods_map.log

    python scripts/16_compare_methods_map.py
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
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.cm import ScalarMappable
from sklearn.cluster import DBSCAN

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "method_comparison"
CRS = 26918
SURFACE, INK, INK2, GRID, ORANGE = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0", "#eb6834"
setup_logging("16_compare_methods_map")
log = logging.getLogger("16_compare_methods_map")
FIG_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})

# %% Load the road-mile matrix and the saved clusterings
ss = pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet")
ids = ss["section_id"].tolist(); ix = {s: i for i, s in enumerate(ids)}; n = len(ids)
r = pd.read_parquet(PROCESSED_DIR / "section_to_section_road_distance.parquet")
D = np.zeros((n, n))
D[r.from_section_id.map(ix).to_numpy(), r.to_section_id.map(ix).to_numpy()] = r.road_mi.to_numpy()
D = (D + D.T) / 2
np.fill_diagonal(D, 0)
kmed = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet").set_index("section_id").loc[ids]
rl = pd.read_parquet(PROCESSED_DIR / "section_hierarchical_clusters.parquet").set_index("section_id").loc[ids]


# %% Option 2 (k-medoids, no limits, k from the best silhouette) is saved by script 13; DBSCAN is cheap to rebuild
plain = kmed["silhouette_best_cluster_id"].to_numpy()
K_PLAIN = len(set(plain))
HIER = rl["silhouette_best_cluster_id"].to_numpy()
K_HIER = len(set(HIER))
db = DBSCAN(eps=6, min_samples=2, metric="precomputed").fit(D).labels_                                       # noise = alone
db = np.where(db == -1, db.max() + 1 + np.cumsum(db == -1), db)

methods = {
    "Nate's schedule clusters": ss["cluster_id"].to_numpy(),
    f"k-medoids, no limits, best silhouette ({K_PLAIN})": plain,
    "Script 13: k-medoids + limits (4 sections, 20 mi)": kmed["medoid_cluster_id"].to_numpy(),
    f"Hierarchical, no limits, best silhouette ({K_HIER})": HIER,
    "Hierarchical + limits (4 sections, 20 mi)": rl["limits_cluster_id"].to_numpy(),
    "DBSCAN, eps 6 mi, min_samples 2": db,
}
alone = {name: (pd.Series(lab).map(pd.Series(lab).value_counts()).to_numpy() == 1) for name, lab in methods.items()}
count = np.sum(list(alone.values()), axis=0)
for name, a in alone.items():
    log.info("%s: %d sections left alone", name, a.sum())
log.info("alone under all %d methods: %d; under 4 or more: %d; under none: %d", len(methods), (count == len(methods)).sum(), (count >= 4).sum(), (count == 0).sum())


# %% Map
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]].to_crs(CRS).set_index("section_id")
geom = sec.geometry.reindex(ids)
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg").to_crs(CRS) if (RAW_DIR / "pa_boundary.gpkg").exists() else None
pts = gpd.GeoSeries([g.representative_point() for g in geom])
px, py = pts.x.to_numpy(), pts.y.to_numpy()


def base(ax):
    if pa is not None:
        pa.boundary.plot(ax=ax, color=INK2, lw=0.8)
    gpd.GeoSeries(geom).plot(ax=ax, color="#d9d8d2", lw=0.4, zorder=1)
    ax.set_aspect("equal"); ax.set_axis_off()


fig, axs = plt.subplots(2, 4, figsize=(22, 10.6), gridspec_kw={"hspace": 0.16, "wspace": 0.02})
fig.suptitle("Which sections are left alone? Single-section clusters under each clustering method", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.925, "Orange dot = the section is a cluster of one (left alone). Grey lines = all 1,022 stocked sections. Every method except Nate's uses only road miles between sections.",
         fontsize=10.5, color=INK2)
for ax, (name, lab) in zip(axs.ravel(), methods.items()):
    base(ax)
    a = alone[name]
    ax.scatter(px[a], py[a], s=22, color=ORANGE, edgecolor=SURFACE, linewidth=0.4, zorder=4)
    ax.set_title(f"{name}\n{len(set(lab))} clusters · {int(a.sum())} sections left alone", loc="left", fontsize=11, fontweight="bold")

for extra in axs.ravel()[len(methods) + 1:]:
    extra.set_axis_off()
ax = axs.ravel()[len(methods)]
base(ax)
levels = np.arange(1, len(methods) + 2)
cmap = ListedColormap(["#c9ddf6", "#9dc0ef", "#6aa0e6", "#2a78d6", "#1d5fb0", "#12447f", "#0b2f5c"][: len(methods)])
norm = BoundaryNorm(levels, cmap.N)
m = count > 0
ax.scatter(px[m], py[m], s=22, c=count[m], cmap=cmap, norm=norm, edgecolor=SURFACE, linewidth=0.4, zorder=4)
ax.set_title(f"How many of the {len(methods)} methods leave a section alone\n{int(m.sum())} sections alone in at least one · {int((count >= 4).sum())} in four or more", loc="left", fontsize=11, fontweight="bold")
cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=0.6, pad=0.01, aspect=22, ticks=levels[:-1] + 0.5)
cb.ax.set_yticklabels([str(i) for i in levels[:-1]]); cb.set_label("methods that leave it alone", color=INK2); cb.outline.set_visible(False)
fig.savefig(FIG_DIR / "single_section_trips.png", dpi=110, bbox_inches="tight", pad_inches=0.25)
log.info("saved %s", (FIG_DIR / "single_section_trips.png").relative_to(ROOT))
plt.close(fig)


# %% Options overview: one card per method, with the algorithm family, status and a plain-language line
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Polygon as Poly
from shapely.ops import unary_union

BLUE, AQUA = "#2a78d6", "#1baf7a"
cmap_s = LinearSegmentedColormap.from_list("size", ["#dbe7f8", "#2a78d6", "#0b3a7a"]); norm_s = Normalize(2, 12)
# name -> (algorithm family, status, status colour, plain-language line)
cards = {
    "Nate's schedule clusters": ("SCHEDULE LINKS (connected groups)", "PHASE 1 (plan of record)", ORANGE,
                                 "Sections that share at least half their truck runs are linked; each linked group is a cluster."),
    f"k-medoids, no limits, best silhouette ({K_PLAIN})": ("K-MEDOIDS (partitioning)", "CANDIDATE: k set by best silhouette", AQUA,
                                   f"Try every k; keep the {K_PLAIN} whose clusters score best on silhouette. Centers are real sections. No size or width limit."),
    "Script 13: k-medoids + limits (4 sections, 20 mi)": ("K-MEDOIDS (partitioning)", "REFERENCE: real-run limits (we considered them)", INK2,
                                                          "Same, then split any cluster wider than 20 mi or with more than 4 sections."),
    "Hierarchical + limits (4 sections, 20 mi)": ("HIERARCHICAL, complete linkage", "REFERENCE: same real-run limits as #3", INK2,
                                           "Merge nearest groups, then split any cluster wider than 20 mi or with more than 4 sections: the same limits as #3."),
    f"Hierarchical, no limits, best silhouette ({K_HIER})": ("HIERARCHICAL, complete linkage", "CANDIDATE: k set by best silhouette", AQUA,
                                           f"The same merging as #5, cut where the silhouette is best ({K_HIER} clusters). No width or size limit."),
    "DBSCAN, eps 6 mi, min_samples 2": ("DBSCAN (density-based)", "SCRAPPED: chains; only flags remote sections", INK2,
                                        "A section within 6 mi of another joins its cluster, chaining along streams; sections with no neighbour are noise."),
}
fam_note = [("SCHEDULE LINKS", "uses what PFBC actually did, so it carries PFBC's hatchery choices"),
            ("K-MEDOIDS", "you give a number of clusters (#2: best silhouette); centers are real sections"),
            ("HIERARCHICAL", "merges nearest groups; cut at a number of clusters (#4) or a maximum width (#5)"),
            ("DBSCAN", "you choose a neighbour reach; clusters chain, loners become noise")]


def poly(ax, g, **kw):
    ax.add_patch(Poly(np.array(g.exterior.coords), closed=True, joinstyle="round", **kw))


fig = plt.figure(figsize=(21, 14.6))
gs = fig.add_gridspec(2, 3, hspace=0.78, wspace=0.04, left=0.02, right=0.99, top=0.76, bottom=0.15)
fig.suptitle("Clustering options so far: six ways to group the 1,022 stocked sections by similar cost", x=0.012, y=0.995, ha="left", fontsize=19, fontweight="bold")
fig.text(0.012, 0.9, "Shading = sections per cluster. Orange dots = sections left alone in their cluster. All but #1 use only road miles between sections.\n"
         "Top line = algorithm family, bold = what we called it, colored = where it stands.", fontsize=12.5, color=INK2, va="bottom")
axes = [fig.add_subplot(g) for g in gs]
for k, (ax, (name, lab)) in enumerate(zip(axes, methods.items()), start=1):
    fam, status, scol, line = cards[name]
    sizes = pd.Series(lab).value_counts(); a = alone[name]
    base(ax)
    hulls = {c: unary_union(list(geom.iloc[np.flatnonzero(lab == c)])).convex_hull.buffer(2500) for c in sizes.index if sizes[c] > 1}
    for c, h in sorted(hulls.items(), key=lambda kv: -sizes[kv[0]]):
        poly(ax, h, facecolor=cmap_s(norm_s(min(sizes[c], 12))), alpha=0.6, edgecolor="none", zorder=2)
    for c, h in hulls.items():
        poly(ax, h, fill=False, edgecolor=INK, lw=0.5, zorder=3)
    ax.scatter(px[a], py[a], s=20, color=ORANGE, edgecolor=SURFACE, linewidth=0.4, zorder=4)
    widest = max(D[np.ix_(g, g)].max() for g in (np.flatnonzero(lab == c) for c in sizes.index) if len(g) > 1)
    ax.text(0, 1.50, fam, transform=ax.transAxes, fontsize=10.5, color=INK2, fontweight="bold", va="bottom")
    ax.text(0, 1.38, f"{k}. {name}" + ("*" if name.startswith(("Script 13", "Hierarchical + limits")) else ""), transform=ax.transAxes, fontsize=12.5, color=INK, fontweight="bold", va="bottom")
    ax.text(0, 1.27, status, transform=ax.transAxes, fontsize=11, color=scol, fontweight="bold", va="bottom")
    ax.text(0, 1.20, "\n".join(__import__("textwrap").wrap(line, 48)), transform=ax.transAxes, fontsize=10.5, color=INK, va="top")
    ax.text(0, -0.02, f"{len(sizes)} clusters  ·  {int(a.sum())} alone  ·  widest {widest:.0f} mi", transform=ax.transAxes, fontsize=12, color=INK, fontweight="bold", va="top")

fig.text(0.012, 0.11, "What the algorithm families mean.  " + "\n" + "\n".join(f"{a}  =  {b}" for a, b in fam_note), fontsize=11.5, color=INK2, va="top", linespacing=1.6)
fig.text(0.50, 0.11, "* #3 and #5 apply realistic truck-run limits (20 mi wide, 4 sections) so we can show we considered them; the objective does not need\n"
         "   them, so they are references, not the candidates. Same limits for both, so k-medoids and hierarchical are compared like for like. Where they come\n"
         "   from: the 2026 schedule has 1,015 truck runs; 90% of the 632 runs with 2 or more sections are no wider than 19.9 mi (rounded to 20), and 99% of\n"
         "   all runs have 4 or fewer sections. Borrowed from PFBC's schedule, not a PFBC rule. Also tested and set aside: hierarchical with a width limit\n"
         "   only (19.9 mi: 234 clusters; 47.5 mi: 74 clusters, averaging error 5.7%). Kept in docs/clustering_options.md and cluster_tracker.md.",
         fontsize=10.5, color=INK2, va="top", linespacing=1.55)
fig.text(0.012, 0.006, "Retired along the way: a hop limit (a cluster is a representative cost, not a trip), and DBSCAN at 19.9 / 47.5 mi (collapses the whole state into one cluster).",
         fontsize=11, color=INK2, va="bottom")
fig.savefig(FIG_DIR / "options_overview.png", dpi=105, bbox_inches="tight", pad_inches=0.2)
log.info("saved %s", (FIG_DIR / "options_overview.png").relative_to(ROOT))
