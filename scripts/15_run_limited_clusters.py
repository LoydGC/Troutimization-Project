"""Width-limited clusters: a cluster is what one truck can cover on a run, measured as how far apart its sections are.

Idea (Gavin, 2026-10-01): a tank of gas (or a day of driving) doesn't care whether it is spent hopping from stream to stream
or on one long leg; what matters is the total reach of the run, which the distance between the cluster's two farthest sections
represents. So the only rule is WIDTH. There is no hop limit and no cap on the number of sections. The limit doesn't depend on
the hatchery, so it can be measured on the real schedule and applied to geography alone, leaving the model free to choose
which hatchery serves which stream.

Rule (road miles, from section-to-section OSRM distances): a cluster is valid when its two farthest sections are at most W miles
apart. Method: complete-linkage hierarchical clustering cut at W. Complete linkage merges groups by their FARTHEST pair, so the cut
distance is exactly the largest distance between two sections in a cluster and the width limit is guaranteed. (A k-medoids
start with splitting of too-wide clusters was tried first: more clusters, 270 vs 234 at 19.9 mi, and silhouette 0.34 vs 0.42.)

Downstream use: a cluster supplies an AVERAGE hatchery-to-section cost, applied to depositing fish in a stream, so no cap on
sections is needed for the cost to be right; width is what keeps a cluster's sections about equally far from any hatchery.

Settings (parameters.csv: run_width_max_mi; value = tight, high = loose), the width of the 632 real multi-section runs on this matrix:
  tight  W 19.9  (90th percentile of run width)
  loose  W 47.5  (the widest real run). Both width-only versions (no section cap) were set aside 2026-10-01 in favour of the
         two options below; they stay in the saved table and comparison.csv as reference rows, but are not drawn.

Added (2026-10-01): hierarchical with the SAME limits as script 13 (cluster_max_width_mi 20, cluster_max_sections 4), so k-medoids and
hierarchical are compared like for like. The tree is walked from the top and split at the first merge that breaks either limit.
Saved as limits_cluster_id and drawn first.

Added: the same complete-linkage dendrogram cut at the number of clusters with the best silhouette, with no limits at all
(deterministic: no random starts). It is saved as silhouette_best_cluster_id and drawn in place of the 47.5 mi version.

Graded with: silhouette; hatchery-distance error (cluster-average distance from each of the 9 scheduled hatcheries vs. each member's
own; the clustering never sees hatcheries); agreement with real runs (share of multi-section runs kept whole in one cluster, and
share of same-cluster pairs that really shared a run). Compared with script 13 (k-medoids, which also caps sections at 4) and
Nate's schedule clusters.

Inputs : data/processed/section_to_section_road_distance.parquet (12), hatchery_to_section_road_distance.parquet (11),
         section_schedule.parquet and stocking_events.parquet (Nate), section_medoid_clusters.parquet (13),
         parameters.csv, pa_trout.gpkg (sections layer), data/raw/pa_boundary.gpkg
Outputs: data/processed/section_run_limited_clusters.{parquet,csv}   section_id, tight_cluster_id, loose_cluster_id,
                                                                    silhouette_best_cluster_id, limits_cluster_id
         outputs/tables/run_limited_clusters/comparison.csv, real_run_yardstick.csv
         outputs/figures/run_limited_clusters/maps.png, metrics.png
         logs/15_run_limited_clusters.log

    python scripts/15_run_limited_clusters.py
"""
# %% Setup
from __future__ import annotations

import itertools
import logging

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Polygon as Poly
from scipy.cluster.hierarchy import fcluster, linkage, to_tree
from scipy.spatial.distance import squareform
from shapely.ops import unary_union
from sklearn.metrics import silhouette_samples

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "run_limited_clusters"
TABLE_DIR = ROOT / "outputs" / "tables" / "run_limited_clusters"
CRS, MARGIN_M = 26918, 2500
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SCHEDULED = ["Bellefonte", "Benner Spring", "Corry", "Huntsdale", "Oswayo", "Pleasant Gap", "Reynoldsdale", "Tionesta", "Tylersville"]




setup_logging("15_run_limited_clusters")
log = logging.getLogger("15_run_limited_clusters")
FIG_DIR.mkdir(parents=True, exist_ok=True); TABLE_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK,
                     "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False})

par = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter")
SETTINGS = {"tight": float(par.loc["run_width_max_mi", "value"]), "loose": float(par.loc["run_width_max_mi", "high"])}
LIM_W, LIM_M = float(par.loc["cluster_max_width_mi", "value"]), int(par.loc["cluster_max_sections", "value"])   # the limits script 13 uses


# %% Load: road-mile matrix (symmetrized), hatchery distances, real runs, other clusters
ss = pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet")
ids = ss["section_id"].tolist(); ix = {s: i for i, s in enumerate(ids)}; n = len(ids)
r = pd.read_parquet(PROCESSED_DIR / "section_to_section_road_distance.parquet")
D = np.zeros((n, n))
D[r.from_section_id.map(ix).to_numpy(), r.to_section_id.map(ix).to_numpy()] = r.road_mi.to_numpy()
D = (D + D.T) / 2
np.fill_diagonal(D, 0)
nate = ss["cluster_id"].astype("category").cat.codes.to_numpy()
kmed = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet").set_index("section_id").loc[ids, "medoid_cluster_id"].astype("category").cat.codes.to_numpy()
hm = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet").pivot_table(index="section_id", columns="hatchery", values="road_mi").reindex(ids)
H9 = hm[[c for c in hm.columns if any(s.lower() in c.lower() for s in SCHEDULED)]].to_numpy()

ev = pd.read_parquet(PROCESSED_DIR / "stocking_events.parquet")
ev = ev[ev.section_id.isin(ix) & ev.run_id.notna()]
runs = [[ix[s] for s in sorted(set(g))] for g in ev.groupby("run_id").section_id.agg(list)]
multi = [x for x in runs if len(x) > 1]
widths = pd.Series([D[np.ix_(x, x)].max() for x in multi])
yardstick = pd.DataFrame({"width_mi": [widths.median(), widths.quantile(.9), widths.quantile(.99), widths.max()]}, index=["p50", "p90", "p99", "max"]).round(1)
yardstick.to_csv(TABLE_DIR / "real_run_yardstick.csv")
print(f"{len(multi)} real multi-section runs\n{yardstick.to_string()}")
assert abs(SETTINGS["tight"] - widths.quantile(.9)) < 0.1 and abs(SETTINGS["loose"] - widths.max()) < 0.1, "settings are not the real-run width p90 / max"


# %% Width-limited clustering: complete linkage cut at W, so no two sections in a cluster are farther apart than W
Z = linkage(squareform(D, checks=False), method="complete")
labels = {}
for name, W in SETTINGS.items():
    labels[name] = fcluster(Z, W, criterion="distance") - 1
    widest = max(D[np.ix_(g, g)].max() for g in (np.flatnonzero(labels[name] == c) for c in np.unique(labels[name])) if len(g) > 1)
    assert widest <= W + 1e-6, "width limit broken"
    log.info("%s (W %.1f mi): %d clusters, widest %.1f mi", name, W, len(set(labels[name])), widest)


# %% Hierarchical with the same limits as script 13 (apples to apples with k-medoids): at most LIM_W mi wide, LIM_M sections
def limited_cut(Z, W, M):
    """Walk the complete-linkage tree from the top; split any node that is wider than W or has more than M sections.
    For complete linkage a node's merge height is the largest distance inside it, so node.dist is its width."""
    out, stack = [], [to_tree(Z)]
    while stack:
        nd = stack.pop()
        if nd.get_count() <= M and nd.dist <= W:
            out.append(nd.pre_order())
        else:
            stack += [nd.get_left(), nd.get_right()]
    lab = np.zeros(n, int)
    for c, members in enumerate(out):
        lab[members] = c
    return lab


hier_lim = limited_cut(Z, LIM_W, LIM_M)
assert pd.Series(hier_lim).value_counts().max() <= LIM_M
assert max(D[np.ix_(g, g)].max() for g in (np.flatnonzero(hier_lim == c) for c in np.unique(hier_lim)) if len(g) > 1) <= LIM_W + 1e-6
log.info("hierarchical + limits (<= %.0f mi, <= %d sections): %d clusters", LIM_W, LIM_M, len(set(hier_lim)))


# %% Hierarchical with no limits: cut the same dendrogram at the k with the best silhouette
sil_by_k = {k: silhouette_samples(D, fcluster(Z, k, criterion="maxclust"), metric="precomputed").mean() for k in range(20, 701)}
K_H = max(sil_by_k, key=sil_by_k.get)
hier_best = fcluster(Z, K_H, criterion="maxclust") - 1
near = [k for k, v in sil_by_k.items() if v >= sil_by_k[K_H] - 0.01]
pd.Series(sil_by_k, name="silhouette").rename_axis("k").round(3).to_csv(TABLE_DIR / "hierarchical_silhouette_by_k.csv")
log.info("hierarchical (complete linkage), no limits: best silhouette %.3f at k = %d (%d clusters); every k from %d to %d is within 0.01 of it",
         sil_by_k[K_H], K_H, len(set(hier_best)), min(near), max(near))


# %% Grade: tightness, hatchery-distance error, and agreement with real runs
co_pairs = {(min(a, b), max(a, b)) for x in multi for a, b in itertools.combinations(x, 2)}
ci = np.array([p[0] for p in co_pairs]); cj = np.array([p[1] for p in co_pairs])


def describe(lab, name):
    lab = np.asarray(lab); sizes = pd.Series(lab).value_counts()
    w = [D[np.ix_(g, g)].max() for g in (np.flatnonzero(lab == c) for c in sizes.index) if len(g) > 1]
    sil = silhouette_samples(D, lab, metric="precomputed")
    err = np.zeros_like(H9)
    for c in sizes.index:
        g = np.flatnonzero(lab == c); err[g] = H9[g].mean(0) - H9[g]
    same = (sizes * (sizes - 1) // 2).sum()
    return {"method": name, "clusters": len(sizes), "singletons": int((sizes == 1).sum()), "biggest (sections)": int(sizes.max()),
            "median width (mi)": round(float(np.median(w)), 1), "widest (mi)": round(float(np.max(w)), 1),
            "mean silhouette": round(float(sil.mean()), 3),
            "hatchery-distance error (% of distance)": round(100 * float(np.abs(err).sum() / H9.sum()), 2),
            "hatchery-distance error (mean mi)": round(float(np.abs(err).mean()), 2),
            "real runs kept whole (%)": round(100 * float(np.mean([len(set(lab[x])) == 1 for x in multi])), 1),
            "real co-run pairs kept together (%)": round(100 * float((lab[ci] == lab[cj]).mean()), 1),
            "same-cluster pairs that shared a run (%)": round(100 * float((lab[ci] == lab[cj]).sum() / same), 1)}


rows = [describe(hier_lim, f"Hierarchical + limits ({LIM_M} sections, {LIM_W:g} mi)"),
        describe(hier_best, f"Hierarchical, best silhouette, no limits ({len(set(hier_best))} clusters)"),
        describe(kmed, f"Script 13: k-medoids + limits ({LIM_M} sections, {LIM_W:g} mi)"),
        describe(nate, "Nate's schedule clusters"),
        describe(labels["tight"], f"Reference only: hierarchical, width limit {SETTINGS['tight']:g} mi, no size cap (not drawn)"),
        describe(labels["loose"], f"Reference only: hierarchical, width limit {SETTINGS['loose']:g} mi, no size cap (not drawn)")]
comparison = pd.DataFrame(rows).set_index("method")
comparison.to_csv(TABLE_DIR / "comparison.csv")
print(comparison.T.to_string())

out = pd.DataFrame({"section_id": ids,
                    "tight_cluster_id": [f"T{c + 1:03d}" for c in labels["tight"]],
                    "loose_cluster_id": [f"L{c + 1:03d}" for c in labels["loose"]],
                    "silhouette_best_cluster_id": [f"H{c + 1:03d}" for c in hier_best],
                    "limits_cluster_id": [f"HL{c + 1:03d}" for c in hier_lim]})
out.to_parquet(PROCESSED_DIR / "section_run_limited_clusters.parquet", index=False)
out.to_csv(PROCESSED_DIR / "section_run_limited_clusters.csv", index=False)
assert out.section_id.is_unique and len(out) == n
log.info("wrote %d rows to section_run_limited_clusters", len(out))


# %% Maps
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]].to_crs(CRS).set_index("section_id")
geom = sec.geometry.reindex(ids)
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg").to_crs(CRS) if (RAW_DIR / "pa_boundary.gpkg").exists() else None
cmap = LinearSegmentedColormap.from_list("size", ["#dbe7f8", "#2a78d6", "#0b3a7a"]); norm = Normalize(2, 12)


def poly(ax, g, **kw):
    ax.add_patch(Poly(np.array(g.exterior.coords), closed=True, joinstyle="round", **kw))


def state_map(ax, lab, name, c):
    sizes = pd.Series(lab).value_counts()
    if pa is not None:
        pa.boundary.plot(ax=ax, color=INK2, lw=1.0)
    gpd.GeoSeries(geom).plot(ax=ax, color="#cfcec8", lw=0.4, zorder=1)
    hulls = {k: unary_union(list(geom.iloc[np.flatnonzero(lab == k)])).convex_hull.buffer(MARGIN_M) for k in sizes.index if sizes[k] > 1}
    for k, h in sorted(hulls.items(), key=lambda kv: -sizes[kv[0]]):
        poly(ax, h, facecolor=cmap(norm(min(sizes[k], 12))), alpha=0.6, edgecolor="none", zorder=2)
    for k, h in hulls.items():
        poly(ax, h, fill=False, edgecolor=INK, lw=0.5, zorder=3)
    one = [i for i in range(n) if sizes[lab[i]] == 1]
    pts = gpd.GeoSeries([geom.iloc[i].representative_point() for i in one])
    ax.scatter(pts.x, pts.y, s=11, color=ORANGE, zorder=4, linewidth=0)
    ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_title(name, loc="left", fontsize=12, fontweight="bold", pad=44)
    ax.text(0, 1.01, f"{int(c['clusters'])} clusters · {int(c['singletons'])} single-section trips · biggest {int(c['biggest (sections)'])} sections · widest {c['widest (mi)']:.0f} mi\n"
            f"silhouette {c['mean silhouette']:.2f} · real runs kept whole {c['real runs kept whole (%)']:.0f}% · hatchery-distance error {c['hatchery-distance error (% of distance)']:.1f}%",
            transform=ax.transAxes, fontsize=9.4, color=INK, va="bottom")


shown = [(comparison.index[0], hier_lim), (comparison.index[1], hier_best), (comparison.index[2], kmed)]
fig, axs = plt.subplots(1, 3, figsize=(20, 6.2), gridspec_kw={"wspace": 0.03})
fig.suptitle("Hierarchical clusters (complete linkage) with the same limits as k-medoids, or cut at the best silhouette", x=0.01, ha="left", fontsize=14.5, fontweight="bold")
fig.text(0.01, 0.9, "Road miles only; no schedule or hatchery information enters the clustering. Left and right share the same limits (4 sections, 20 mi); the middle has none. Orange dots = single-section trips. Shading = sections per cluster.", fontsize=10.5, color=INK2)
for ax, (name, lab) in zip(axs, shown):
    state_map(ax, lab, name, comparison.loc[name])
fig.subplots_adjust(top=0.72)
fig.savefig(FIG_DIR / "maps.png", dpi=115, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)


# %% Metrics figure
panels = [("mean silhouette", "Silhouette\n(higher = tighter)", 0.0, 0.5), ("hatchery-distance error (% of distance)", "Hatchery-distance error, % of distance\n(lower = cost estimate more accurate)", 0, 3.5),
          ("real runs kept whole (%)", "Real truck runs kept whole in one cluster, %\n(higher = more faithful to PFBC)", 0, 100),
          ("same-cluster pairs that shared a run (%)", "Same-cluster pairs that really shared a run, %\n(higher = fewer clusters no truck would make)", 0, 100)]
colors = [AQUA, AQUA, BLUE, ORANGE]
short = ["Hierarchical\n+ limits", "Hierarchical\nbest silhouette", "k-medoids\n+ limits", "Nate's"]
fig, axs = plt.subplots(1, 4, figsize=(21, 5.0))
fig.suptitle("How the hierarchical clusters score", x=0.01, ha="left", fontsize=14, fontweight="bold")
for ax, (col, title, lo, hi) in zip(axs, panels):
    vals = comparison[col].iloc[:4]
    ax.bar(short, vals, color=colors, width=0.62)
    for x, v in enumerate(vals):
        ax.text(x, v + (hi - lo) * 0.015, f"{v:.2f}" if hi < 10 else f"{v:.0f}", ha="center", fontsize=10, color=INK)
    ax.set_ylim(lo, hi); ax.set_title(title, loc="left", fontsize=10.8); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
fig.text(0.01, 0.01, "Both limit-based options use 4 sections and 20 mi (parameters.csv); best silhouette has no limits. The width-only 19.9 mi and 47.5 mi versions are kept in comparison.csv as reference rows. Nate's clusters are built from the runs, so the two run-agreement panels favour them by construction.",
         fontsize=9.5, color=INK2)
fig.tight_layout(rect=(0, 0.05, 1, 0.9))
fig.savefig(FIG_DIR / "metrics.png", dpi=115)
log.info("saved figures to %s", FIG_DIR.relative_to(ROOT))
