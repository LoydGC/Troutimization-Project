"""SCRAPPED 2026-10-01 (kept for the record; see docs/clustering_options.md and cluster_tracker.md entry 6): DBSCAN on road miles,
tested with the width of PFBC's real truck runs, next to a width-limited alternative. DBSCAN chains the whole state into one
cluster at those widths and only behaves at eps near 6 mi. Script 15 now covers the width-limited (hierarchical) versions.

Question: how far does PFBC make a truck travel on one run, and what do clusters look like if that is the distance
rule? Real multi-section runs are 19.9 road mi wide at the 90th percentile and 47.5 mi at the maximum (script 13's
yardstick; set as constants in this script). Like script 13 it uses only road miles between
sections, never the schedule or hatcheries, so it carries none of PFBC's hatchery choices.

How DBSCAN works here, and the traps:
  - Units: the input is the road-MILE matrix (metric="precomputed"), so `eps` is in miles. A check compares sklearn's
    neighbour count with a hand count at the start of the run.
  - `eps` is a NEIGHBOUR reach, not a cluster width. A section joins a cluster if it is within `eps` of any member,
    so clusters chain along streams: a cluster can be many times wider than `eps`. At 19.9 and 47.5 mi everything
    in the state chains into one cluster (every section has a neighbour within 19.9 mi).
  - `min_samples` (counts the section itself): a section is a core point if at least that many sections, itself
    included, lie within `eps`. Non-core sections within `eps` of a core point join its cluster; the rest are NOISE
    (label -1). Noise is the useful part: remote sections that no nearby section supports, i.e. the ones that need
    their own trip. 1 means no noise, 2 means "needs one neighbour", larger values demand a denser neighbourhood.
  - Silhouette needs 2+ clusters (undefined for one). Noise sections count as one-section clusters (silhouette 0).

What the script runs:
  A. DBSCAN at the two real-run widths (the test asked for).
  B. A DBSCAN `eps` sweep, to show where chaining starts and which `eps` DBSCAN actually works at.
  C. Complete linkage cut at the same two widths. Here the cut IS the maximum distance between any two sections in
     a cluster, so the width is guaranteed. This is the method that matches "a truck covers at most X miles".
  Compared with script 13's 407 limited k-medoids and Nate's 351 schedule clusters on silhouette and width.

Inputs : data/processed/section_to_section_road_distance.parquet   (12)
         data/processed/section_schedule.parquet                    Nate's clusters, for the comparison only (10)
         data/processed/section_medoid_clusters.parquet             script 13's clusters, for the comparison (13)
         data/processed/pa_trout.gpkg (sections layer), data/raw/pa_boundary.gpkg   for the maps
         data/processed/parameters.csv                              (none: the test values are constants below)
Outputs: outputs/tables/dbscan_clusters/{comparison.csv, eps_sweep.csv, min_samples_check.csv}
         outputs/figures/dbscan_clusters/{maps.png, eps_sweep.png}
         logs/14_dbscan_clusters.log

    python scripts/14_dbscan_clusters.py
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
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Polygon as Poly
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from shapely.ops import unary_union
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_samples
from sklearn.neighbors import NearestNeighbors

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "dbscan_clusters"
TABLE_DIR = ROOT / "outputs" / "tables" / "dbscan_clusters"
CRS, MARGIN_M = 26918, 2500
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"      # reference palette slots 1-3
EPS_GRID = [3, 4, 5, 6, 7, 8, 10, 12, 15, 19.9, 30, 47.5]

setup_logging("14_dbscan_clusters")
log = logging.getLogger("14_dbscan_clusters")
FIG_DIR.mkdir(parents=True, exist_ok=True); TABLE_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK,
                     "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False})

par = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter")["value"]
# Scrapped exploration (2026-10-01), so these test values live here, not in parameters.csv: the real-run width p90 and max
# (the same numbers as run_width_max_mi, script 15) and min_samples (counts the section itself; 2 = needs one neighbour).
EPS_P90, EPS_MAX, MIN_SAMPLES = 19.9, 47.5, 2


# %% Load the road-mile matrix (symmetrized) and the clusters to compare with
ss = pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet")
ids = ss["section_id"].tolist(); ix = {s: i for i, s in enumerate(ids)}; n = len(ids)
r = pd.read_parquet(PROCESSED_DIR / "section_to_section_road_distance.parquet")
D = np.zeros((n, n))
D[r.from_section_id.map(ix).to_numpy(), r.to_section_id.map(ix).to_numpy()] = r.road_mi.to_numpy()
D = (D + D.T) / 2
np.fill_diagonal(D, 0)
nate = ss["cluster_id"].astype("category").cat.codes.to_numpy()
kmed = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet").set_index("section_id").loc[ids, "medoid_cluster_id"].astype("category").cat.codes.to_numpy()
log.info("%d sections; road-mile matrix median %.0f mi, max %.0f mi", n, np.median(D[D > 0]), D.max())

# Units check: sklearn's neighbour count within eps must equal a hand count on the mile matrix.
rng = np.random.default_rng(0)
for eps in (EPS_P90, EPS_MAX):
    by_hand = (D <= eps).sum(axis=1)
    sk = np.array([len(x) for x in NearestNeighbors(radius=eps, metric="precomputed").fit(D).radius_neighbors(D, return_distance=False)])
    assert (sk == by_hand).all(), "eps is not being applied in the matrix's units"
    log.info("units check, eps = %.1f mi: sklearn and a hand count agree for all %d sections (median %d neighbours incl. itself)", eps, n, np.median(by_hand))


# %% Helpers
def with_noise_as_trips(lab):
    """DBSCAN noise (-1) becomes one-section clusters, so every section is in exactly one cluster."""
    lab = np.asarray(lab); out = lab.copy(); k = (lab == -1).sum()
    out[lab == -1] = lab.max() + 1 + np.arange(k)
    return out


def describe(lab, name, noise=0):
    lab = np.asarray(lab); sizes = pd.Series(lab).value_counts()
    widths = [D[np.ix_(g, g)].max() for g in (np.flatnonzero(lab == c) for c in sizes.index) if len(g) > 1]
    sil = silhouette_samples(D, lab, metric="precomputed") if 1 < len(sizes) < n else None
    return {"method": name, "clusters": len(sizes), "noise (remote) sections": noise, "singletons": int((sizes == 1).sum()),
            "biggest (sections)": int(sizes.max()), "median width (mi)": round(float(np.median(widths)), 1) if widths else 0.0,
            "widest (mi)": round(float(np.max(widths)), 1) if widths else 0.0,
            "mean silhouette": round(float(sil.mean()), 3) if sil is not None else np.nan,
            "sections with negative silhouette (%)": round(100 * float((sil < 0).mean()), 1) if sil is not None else np.nan}


def dbscan(eps, min_samples):
    lab = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed").fit(D).labels_
    return lab, int((lab == -1).sum())


# %% A. DBSCAN at the two real-run widths
runs = {}
for eps, tag in ((EPS_P90, "p90"), (EPS_MAX, "max")):
    lab, noise = dbscan(eps, MIN_SAMPLES)
    runs[f"DBSCAN eps {eps:g} mi ({tag} real run)"] = (with_noise_as_trips(lab), noise)
    log.info("DBSCAN eps %.1f, min_samples %d: %d clusters (excluding noise), %d noise", eps, MIN_SAMPLES, lab.max() + 1, noise)

# %% B. eps sweep (min_samples as set) and the effect of min_samples at the best eps
sweep = []
for eps in EPS_GRID:
    lab, noise = dbscan(eps, MIN_SAMPLES)
    sweep.append({"eps_mi": eps, **{k: v for k, v in describe(with_noise_as_trips(lab), "", noise).items() if k != "method"}})
sweep = pd.DataFrame(sweep)
sweep.to_csv(TABLE_DIR / "eps_sweep.csv", index=False)
BEST_EPS = float(sweep.loc[sweep["mean silhouette"].idxmax(), "eps_mi"])
log.info("DBSCAN eps with the highest silhouette: %g mi", BEST_EPS)
ms_rows = []
for ms in (1, 2, 3, 5, 10):
    lab, noise = dbscan(BEST_EPS, ms)
    ms_rows.append({"eps_mi": BEST_EPS, "min_samples": ms, **{k: v for k, v in describe(with_noise_as_trips(lab), "", noise).items() if k != "method"}})
pd.DataFrame(ms_rows).to_csv(TABLE_DIR / "min_samples_check.csv", index=False)
print(pd.DataFrame(ms_rows).to_string(index=False))
lab, noise = dbscan(BEST_EPS, MIN_SAMPLES)
runs[f"DBSCAN eps {BEST_EPS:g} mi (best silhouette)"] = (with_noise_as_trips(lab), noise)

# %% C. Complete linkage cut at the same widths (cluster width guaranteed <= cut)
Z = linkage(squareform(D, checks=False), method="complete")
for cut, tag in ((EPS_P90, "p90"), (EPS_MAX, "max")):
    lab = fcluster(Z, cut, criterion="distance") - 1
    runs[f"Width limit {cut:g} mi ({tag} real run)"] = (lab, 0)
    assert max(D[np.ix_(g, g)].max() for g in (np.flatnonzero(lab == c) for c in np.unique(lab)) if len(g) > 1) <= cut + 1e-6
runs["Script 13: k-medoids with limits"] = (kmed, 0)
runs["Nate's schedule clusters"] = (nate, 0)

rows = [describe(lab, name, noise) for name, (lab, noise) in runs.items()]
comparison = pd.DataFrame(rows).set_index("method")
comparison.to_csv(TABLE_DIR / "comparison.csv")
print(comparison.T.to_string())


# %% Maps
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]].to_crs(CRS).set_index("section_id")
geom = sec.geometry.reindex(ids)
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg").to_crs(CRS) if (RAW_DIR / "pa_boundary.gpkg").exists() else None
cmap = LinearSegmentedColormap.from_list("size", ["#dbe7f8", "#2a78d6", "#0b3a7a"]); norm = Normalize(2, 18)


def poly(ax, g, **kw):
    ax.add_patch(Poly(np.array(g.exterior.coords), closed=True, joinstyle="round", **kw))


def state_map(ax, lab, title, stat):
    sizes = pd.Series(lab).value_counts()
    if pa is not None:
        pa.boundary.plot(ax=ax, color=INK2, lw=1.0)
    gpd.GeoSeries(geom).plot(ax=ax, color="#cfcec8", lw=0.4, zorder=1)
    hulls = {c: unary_union(list(geom.iloc[np.flatnonzero(lab == c)])).convex_hull.buffer(MARGIN_M) for c in sizes.index if sizes[c] > 1}
    for c, h in sorted(hulls.items(), key=lambda kv: -sizes[kv[0]]):
        poly(ax, h, facecolor=cmap(norm(min(sizes[c], 18))), alpha=0.55, edgecolor="none", zorder=2)
    for c, h in hulls.items():
        poly(ax, h, fill=False, edgecolor=INK, lw=0.5, zorder=3)
    one = [i for i in range(n) if sizes[lab[i]] == 1]
    pts = gpd.GeoSeries([geom.iloc[i].representative_point() for i in one])
    ax.scatter(pts.x, pts.y, s=11, color=ORANGE, zorder=4, linewidth=0)
    ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=40)
    ax.text(0, 1.01, stat, transform=ax.transAxes, fontsize=9.6, color=INK, va="bottom")


names = list(runs)
fig, axs = plt.subplots(2, 3, figsize=(19, 10.4), gridspec_kw={"hspace": 0.28, "wspace": 0.03})
fig.suptitle("DBSCAN and width-limited clusters at the width of PFBC's real truck runs", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.935, "Same 1,022 sections, road miles only. Shading = sections per cluster; orange dots = sections left alone "
         "(DBSCAN noise, i.e. remote sections, or singletons). Silhouette is undefined for a single cluster.", fontsize=10.5, color=INK2)
order = [names[0], names[1], names[2], names[3], names[4], names[5]]
for ax, name in zip(axs.ravel(), order):
    lab, noise = runs[name]; c = comparison.loc[name]
    sil = "n/a (one cluster)" if np.isnan(c["mean silhouette"]) else f"{c['mean silhouette']:.2f}"
    state_map(ax, lab, name, f"{int(c['clusters'])} clusters · {int(c['singletons'])} sections left alone · biggest {int(c['biggest (sections)'])} sections\n"
                              f"widest {c['widest (mi)']:.0f} mi · silhouette {sil}")
fig.text(0.01, 0.012, "Top row: DBSCAN, where eps is how far one section may sit from its nearest cluster-mate, so clusters chain and can far exceed eps. "
         "Bottom row: complete linkage, where the cut is the largest distance between any two sections in a cluster, then script 13's clusters.", fontsize=9.5, color=INK2)
fig.savefig(FIG_DIR / "maps.png", dpi=115, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)


# %% eps sweep figure and silhouette comparison
fig, axs = plt.subplots(1, 3, figsize=(19, 5.6), gridspec_kw={"width_ratios": [1, 1, 1.25]})
fig.suptitle("DBSCAN chains: widest cluster explodes well below the real-run widths, and the silhouette peaks near 6 mi", x=0.01, ha="left", fontsize=13.5, fontweight="bold")
a, b, c = axs
a.plot(sweep.eps_mi, sweep["widest (mi)"], color=BLUE, lw=2, marker="o", ms=5, markeredgecolor=SURFACE, label="widest cluster")
a.plot(sweep.eps_mi, sweep["eps_mi"], color=INK2, lw=1, ls="--", label="eps (the width you might expect)")
a.set_yscale("log"); a.set_xlabel("DBSCAN eps (road miles)"); a.set_ylabel("road miles (log)")
a.set_title("Widest cluster vs eps", loc="left", fontsize=11.5); a.legend(frameon=False, fontsize=9.5)
b.plot(sweep.eps_mi, sweep["noise (remote) sections"], color=ORANGE, lw=2, marker="o", ms=5, markeredgecolor=SURFACE, label=f"noise sections (min_samples {MIN_SAMPLES})")
b.plot(sweep.eps_mi, sweep["biggest (sections)"], color=BLUE, lw=2, marker="o", ms=5, markeredgecolor=SURFACE, label="biggest cluster (sections)")
b.set_yscale("log"); b.set_xlabel("DBSCAN eps (road miles)"); b.set_title("Remote sections vs the chained blob", loc="left", fontsize=11.5); b.legend(frameon=False, fontsize=9.5)
for ax_ in (a, b):
    for x, t in ((EPS_P90, "19.9"), (EPS_MAX, "47.5")):
        ax_.axvline(x, color=INK2, lw=0.8, ls=":")
    ax_.grid(color=GRID, lw=0.8); ax_.set_axisbelow(True)
sil = comparison["mean silhouette"]; lbl = list(sil.index)
colors = [AQUA if "Width limit" in m else (ORANGE if "Nate" in m else BLUE) for m in lbl]
ypos = np.arange(len(lbl))[::-1]
c.barh(ypos, sil.fillna(0), color=colors, height=0.62)
for y, v in zip(ypos, sil):
    c.text((0 if np.isnan(v) else max(v, 0)) + 0.01, y, "undefined (1 cluster)" if np.isnan(v) else f"{v:.2f}", va="center", fontsize=10, color=INK)
c.set_yticks(ypos); c.set_yticklabels(lbl, fontsize=9.5); c.axvline(0, color=INK2, lw=0.8)
c.set_xlim(-0.05, 0.6); c.set_xlabel("mean silhouette (higher = tighter, better separated)")
c.set_title("Silhouette by approach (noise counted as one-section trips)", loc="left", fontsize=11.5); c.grid(axis="x", color=GRID, lw=0.8); c.set_axisbelow(True)
fig.text(0.01, 0.01, f"Dotted lines: 19.9 mi (90% of real runs are narrower) and 47.5 mi (the widest). DBSCAN min_samples = {MIN_SAMPLES}. Colors: blue = DBSCAN / script 13, green = width-limited, orange = Nate's.",
         fontsize=9.5, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 0.92))
fig.savefig(FIG_DIR / "eps_sweep.png", dpi=115)
log.info("saved figures to %s", FIG_DIR.relative_to(ROOT))
