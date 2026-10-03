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


# %% Nate's clusters re-run on road miles
# His grouping rule uses only shared truck runs (scripts/10_runs_clusters.py: pair_shares + components); distance only feeds four derived fields
# (detour_mi, detour_nn_mi, cluster_mi, span_mi), which he computes as straight-line miles x circuity 1.3. Re-run his own functions to confirm the
# groups, then recompute those four fields on real road miles.
import importlib.util

from scipy.sparse.csgraph import minimum_spanning_tree

_spec = importlib.util.spec_from_file_location("nate_script_10", ROOT / "scripts" / "10_runs_clusters.py")
n10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(n10)
_sec10, _ev = n10.load()                      # his own loader: 2026 stream events on the 1,022 sections
_par = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter")
_share_min = float(_par.loc["cluster_share_min", "value"])
_pairs = n10.pair_shares(_ev)
_rerun = n10.components(pd.Index(ids), _pairs, _share_min)
same_groups = (pd.crosstab(_rerun.to_numpy(), ss["cluster_id"].to_numpy()) > 0).sum().max() == 1 and _rerun.nunique() == ss["cluster_id"].nunique()
assert same_groups and (_rerun.to_numpy() == ss["cluster_id"].to_numpy()).all(), "re-run of Nate's grouping differs from the committed clusters"
log.info("Nate's grouping re-run with his own functions: %d clusters, identical to section_schedule.cluster_id (the rule has no distance in it)", _rerun.nunique())


def road_detour(lab):
    """Road miles from each section to its nearest cluster-mate (0 for a section alone)."""
    lab = np.asarray(lab)
    same = lab[:, None] == lab[None, :]
    d = np.where(same, D, np.inf)
    np.fill_diagonal(d, np.inf)
    near = d.min(axis=1)
    return np.where(np.isfinite(near), near, 0.0)


nate_lab = ss["cluster_id"].to_numpy()
det_road = road_detour(nate_lab)
alone_mask = pd.Series(nate_lab).map(pd.Series(nate_lab).value_counts()).to_numpy() == 1
nn = D.copy()
np.fill_diagonal(nn, np.inf)
nn_road = nn.min(axis=1)

rows = []
for cid, g in ss.groupby("cluster_id"):
    i = np.flatnonzero(nate_lab == cid)
    sub = D[np.ix_(i, i)]
    mst = minimum_spanning_tree(sub + 1e-6 * (sub == 0) * (1 - np.eye(len(i)))).sum() if len(i) > 1 else 0.0
    rows.append({"cluster_id": cid, "n_sections": len(i), "span_mi_road": round(float(sub.max()), 2), "cluster_mi_road": round(float(mst), 2)})
cl_road = pd.DataFrame(rows).merge(pd.read_csv(PROCESSED_DIR / "clusters.csv")[["cluster_id", "span_mi", "cluster_mi"]], on="cluster_id") \
    .rename(columns={"span_mi": "span_mi_linear_x1.3", "cluster_mi": "cluster_mi_linear_x1.3"})
(ROOT / "outputs" / "tables" / "method_comparison").mkdir(parents=True, exist_ok=True)
cl_road.to_csv(ROOT / "outputs" / "tables" / "method_comparison" / "nate_clusters_road_vs_linear.csv", index=False)
det_lin = ss["detour_mi"].to_numpy()
nonsingle = ~alone_mask
summary = {
    "detour to nearest cluster-mate, median (non-singleton)": (np.median(det_lin[nonsingle]), np.median(det_road[nonsingle])),
    "detour to nearest cluster-mate, 90th pct": (np.quantile(det_lin[nonsingle], .9), np.quantile(det_road[nonsingle], .9)),
    "nearest stocked section of any cluster, median": (ss["detour_nn_mi"].median(), np.median(nn_road)),
    "cluster span (farthest pair), median (2+ sections)": (cl_road[cl_road.n_sections > 1]["span_mi_linear_x1.3"].median(), cl_road[cl_road.n_sections > 1]["span_mi_road"].median()),
    "cluster span, widest": (cl_road["span_mi_linear_x1.3"].max(), cl_road["span_mi_road"].max()),
    "clusters wider than 60 mi (his QA flag)": (int((cl_road["span_mi_linear_x1.3"] > 60).sum()), int((cl_road["span_mi_road"] > 60).sum())),
    "route length through a cluster (MST), median (2+ sections)": (cl_road[cl_road.n_sections > 1]["cluster_mi_linear_x1.3"].median(), cl_road[cl_road.n_sections > 1]["cluster_mi_road"].median()),
}
for k, (a, b) in summary.items():
    log.info("Nate's %s: straight-line x1.3 = %.2f, road miles = %.2f", k, a, b)
NATE_DETOUR = (float(np.median(det_lin[nonsingle])), float(np.median(det_road[nonsingle])))


# %% No-limits comparison: Nate's vs k-medoids vs hierarchical (both best silhouette), and how each breaks up Nate's biggest cluster
from matplotlib.cm import ScalarMappable
from sklearn.metrics import silhouette_samples

MIX_OUTLINE = "#d81b7c"      # outline of a cluster that mixes scheduled hatcheries (orange is for sections; magenta stands apart from the blue shading)

_supply = pd.read_csv(PROCESSED_DIR / "hatchery_schedule_supply.csv")
_producing = _supply.loc[_supply["stream_fish_2026"] > 0, "hatchery"].tolist()
_hm = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet").pivot_table(index="section_id", columns="hatchery", values="road_mi").reindex(ids)
HP = _hm[_producing].to_numpy()
prim = ss["primary_hatchery"].to_numpy()


def stats(lab):
    lab = np.asarray(lab)
    sizes = pd.Series(lab).value_counts()
    w = [D[np.ix_(g, g)].max() for g in (np.flatnonzero(lab == c) for c in sizes.index) if len(g) > 1]
    err = np.zeros_like(HP)
    for c in sizes.index:
        g = np.flatnonzero(lab == c)
        err[g] = HP[g].mean(0) - HP[g]
    dr = road_detour(lab)
    ns = pd.Series(lab).map(sizes).to_numpy() > 1
    return dict(clusters=len(sizes), alone=int((sizes == 1).sum()), biggest=int(sizes.max()), widest=max(w), detour=float(np.median(dr[ns])),
                sil=silhouette_samples(D, lab, metric="precomputed").mean(), err=100 * np.abs(err).sum() / HP.sum(), err_mi=np.abs(err).mean())


trio = {"1. Nate's schedule clusters": methods["Nate's schedule clusters"],
        f"2. k-medoids, no limits, best silhouette ({K_PLAIN})": methods[f"k-medoids, no limits, best silhouette ({K_PLAIN})"],
        f"3. Hierarchical, no limits, best silhouette ({K_HIER})": methods[f"Hierarchical, no limits, best silhouette ({K_HIER})"]}
big = ss["cluster_id"].value_counts().idxmax()
big_idx = np.flatnonzero((ss["cluster_id"] == big).to_numpy())
big_hull = unary_union(list(geom.iloc[big_idx])).convex_hull.buffer(2500)
minx, miny, maxx, maxy = big_hull.bounds

fig = plt.figure(figsize=(19, 10.8))
gs = fig.add_gridspec(2, 3, height_ratios=[0.8, 1], hspace=0.16, wspace=0.04, left=0.02, right=0.93, top=0.84, bottom=0.04)
fig.suptitle("Three ways to group the 1,022 stocked sections by similar cost, with no limits", x=0.012, y=0.985, ha="left", fontsize=16, fontweight="bold")
fig.text(0.012, 0.935, "Top: statewide (shading = sections per cluster, dark dots = sections left alone, magenta outline = cluster mixes sections whose scheduled hatcheries differ). "
         "Bottom: the same patch of the state, around Nate's biggest cluster (orange lines).", fontsize=11, color=INK2, va="bottom")
for j, (name, lab) in enumerate(trio.items()):
    s = stats(lab)
    sizes = pd.Series(lab).value_counts()
    hulls = {c: unary_union(list(geom.iloc[np.flatnonzero(lab == c)])).convex_hull.buffer(2500) for c in sizes.index}
    ax = fig.add_subplot(gs[0, j])
    base(ax)
    for c, h in sorted(hulls.items(), key=lambda kv: -sizes[kv[0]]):
        if sizes[c] > 1:
            poly(ax, h, facecolor=cmap_s(norm_s(min(sizes[c], 12))), alpha=0.6, edgecolor="none", zorder=2)
    for c, h in hulls.items():
        if sizes[c] > 1:
            mixed = len(set(prim[lab == c])) > 1
            poly(ax, h, fill=False, edgecolor=MIX_OUTLINE if mixed else INK, lw=2.2 if mixed else 0.5, zorder=3)
    one = np.flatnonzero(pd.Series(lab).map(sizes).to_numpy() == 1)
    ax.scatter(px[one], py[one], s=9, color=INK2, linewidth=0, zorder=4)
    ax.set_title(name, loc="left", fontsize=12.5, fontweight="bold", pad=70)
    ax.text(0, 1.01, f"{s['clusters']} clusters · {s['alone']} left alone · biggest {s['biggest']} sections\n"
            f"widest {s['widest']:.0f} mi · silhouette {s['sil']:.2f} · hatchery-distance error {s['err']:.1f}% ({s['err_mi']:.1f} mi)\n"
            f"median detour to nearest cluster-mate: {s['detour']:.1f} road mi" + (f"\nre-run on road miles: same groups. His straight-line x 1.3 gave {NATE_DETOUR[0]:.1f} mi" if j == 0 else ""),
            transform=ax.transAxes, fontsize=9.8, color=INK, va="bottom")
    z = fig.add_subplot(gs[1, j])
    z.set_xlim(minx - 12000, maxx + 12000)
    z.set_ylim(miny - 12000, maxy + 12000)
    gpd.GeoSeries(geom).plot(ax=z, color="#cfcec8", lw=0.8)
    gpd.GeoSeries(geom.iloc[big_idx]).plot(ax=z, color=ORANGE, lw=3.0, zorder=4)
    for c, h in hulls.items():
        if h.intersects(big_hull):
            poly(z, h, facecolor="#00000008", edgecolor=INK, lw=1.2, zorder=2)
    z.set_aspect("equal")
    z.set_xticks([])
    z.set_yticks([])
    for sp in z.spines.values():
        sp.set_color(GRID)
    n_in = len(set(lab[big_idx]))
    z.set_title(f"Same {len(big_idx)} sections: {n_in} cluster{'s' if n_in > 1 else ''}", loc="left", fontsize=11)
fig.colorbar(ScalarMappable(norm=norm_s, cmap=cmap_s), cax=fig.add_axes([0.945, 0.56, 0.008, 0.22])).set_label("sections in cluster", color=INK2)
fig.text(0.012, 0.008, "1 is built from PFBC's truck-run schedule (carries PFBC's hatchery choices). 2 and 3 use only road miles between sections and no width or size limits; "
         "each picks its number of clusters by the best silhouette. Hatchery-distance error: how far a cluster's average distance from each hatchery producing 2026 fish sits from each member's own.",
         fontsize=9.5, color=INK2, wrap=True)
fig.savefig(FIG_DIR / "approach_comparison_no_limits.png", dpi=115, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)
log.info("saved %s", (FIG_DIR / "approach_comparison_no_limits.png").relative_to(ROOT))
