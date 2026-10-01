"""Geography-only clusters of the 1,022 stocked sections (k-medoids on road miles, with size limits), compared with Nate's.

Why: the model chooses x[h, s], which hatchery stocks which stream. A cluster stands in for one trip, with cost = the
average road distance from a hatchery to the sections in the cluster. So clusters must not carry PFBC's own hatchery
choices. These ignore the stocking schedule and the hatcheries entirely (Nate's scripts 09-10 build clusters from the
schedule, so they freeze PFBC's routes). k-medoids is like k-means, but the centers are real sections and it works
on a distance table (here road miles) instead of coordinates.

Method (decided 2026-09-30, after a sweep of k): k-medoids with `cluster_start_k` clusters, then any cluster wider
than `cluster_max_width_mi` or bigger than `cluster_max_sections` is split (k-medoids inside it) until none is.
The final count (407 with the default seed; 407-417 across seeds) follows from the limits. Limits and start k are in data/processed/parameters.csv.
Check: for each of the 9 scheduled hatcheries, a cluster's average distance is within ~2% of a member's own distance
(Nate's: 3%); `hatchery_distance_error` in comparison.csv. The clustering never sees the hatcheries; the check does.
Not used (an idea to revisit, docs/scenarios_and_extensions.md): fish counts and truckload size.

Inputs : data/processed/section_to_section_road_distance.parquet   road miles between sections   (12_section_road_distances.py)
         data/processed/section_schedule.parquet                    Nate's run clusters and main hatchery, only for the comparison (10)
         data/processed/hatchery_to_section_road_distance.parquet   for the hatchery-distance check only (11)
         data/processed/parameters.csv                              cluster_max_width_mi, cluster_max_sections, cluster_start_k
         data/processed/pa_trout.gpkg (sections layer)              section lines, for the maps (gitignored; rebuilt by 01-02)
         data/raw/pa_boundary.gpkg                                   state outline for the maps (optional)
Outputs: data/processed/section_medoid_clusters.{parquet,csv}       one row per section: its k-medoids cluster (with limits) and medoid,
                                                                    plus silhouette_best_cluster_id (no limits, k set by the best silhouette)
         outputs/tables/medoid_clusters/comparison.csv              the three approaches side by side (Nate, k-medoids, k-medoids with limits)
         outputs/tables/medoid_clusters/silhouette_by_k.csv         silhouette and total distance for a range of k
         outputs/figures/medoid_clusters/maps.png, silhouette.png, approach_comparison.png (all three approaches, statewide and zoomed)
         logs/13_medoid_clusters.log

    python scripts/13_medoid_clusters.py [--restarts 30]
      --restarts   random starts per k; the best (lowest total distance) is kept
"""
# %% Setup
from __future__ import annotations

import argparse
import logging

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as Poly
from shapely.ops import unary_union
from sklearn.metrics import adjusted_rand_score, silhouette_samples

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "medoid_clusters"
TABLE_DIR = ROOT / "outputs" / "tables" / "medoid_clusters"
CRS, MARGIN_M = 26918, 2500
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"          # reference palette slots 1-2: k-medoids = blue, Nate's = orange
K_GRID = list(range(20, 100, 10)) + list(range(100, 701, 10))   # silhouette curve, unlimited k-medoids; its peak sets the plain version's k
SCHEDULED = ["Bellefonte", "Benner Spring", "Corry", "Huntsdale", "Oswayo", "Pleasant Gap", "Reynoldsdale", "Tionesta", "Tylersville"]

ap = argparse.ArgumentParser()
ap.add_argument("--restarts", type=int, default=30)
args = ap.parse_args()
setup_logging("13_medoid_clusters")
log = logging.getLogger("13_medoid_clusters")
FIG_DIR.mkdir(parents=True, exist_ok=True); TABLE_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK,
                     "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False})


# %% Load: road-mile matrix (symmetrized) and Nate's clusters
ss = pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet")
ids = ss["section_id"].tolist(); ix = {s: i for i, s in enumerate(ids)}; n = len(ids)
r = pd.read_parquet(PROCESSED_DIR / "section_to_section_road_distance.parquet")
D = np.zeros((n, n))
D[r.from_section_id.map(ix).to_numpy(), r.to_section_id.map(ix).to_numpy()] = r.road_mi.to_numpy()
D = (D + D.T) / 2                      # road distance is almost symmetric (0.3% median gap); use the mean of both directions
np.fill_diagonal(D, 0)
nate = ss["cluster_id"].astype("category").cat.codes.to_numpy()
hatch = ss["primary_hatchery"].to_numpy()
par = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter")["value"]
MAX_W, MAX_N, START_K = float(par["cluster_max_width_mi"]), int(par["cluster_max_sections"]), int(par["cluster_start_k"])
log.info("%d sections; start k = %d, limits: width <= %.0f mi, <= %d sections (Nate's clusters: %d)", n, START_K, MAX_W, MAX_N, ss["cluster_id"].nunique())


# %% k-medoids (alternating assign / recenter, k-medoids++ starts)
def kmedoids(D, k, rng, max_iter=100):
    n = len(D)
    med = [int(rng.integers(n))]
    d = D[med[0]].copy()
    for _ in range(1, k):                                   # k-medoids++: next center far from the current ones
        p = d ** 2
        p[med] = 0
        nxt = int(rng.choice(n, p=p / p.sum())) if p.sum() > 0 else int(rng.choice(np.setdiff1d(np.arange(n), med)))
        med.append(nxt); d = np.minimum(d, D[nxt])
    med = np.array(med)
    for _ in range(max_iter):
        lab = D[:, med].argmin(axis=1)
        new = med.copy()
        for c in range(k):
            members = np.flatnonzero(lab == c)
            if len(members):                                # the member with the smallest total distance to the others
                new[c] = members[D[np.ix_(members, members)].sum(axis=1).argmin()]
        if np.array_equal(new, med):
            break
        med = new
    lab = D[:, med].argmin(axis=1)
    return med, lab, float(D[np.arange(len(D)), med[lab]].sum())


def best_of(k, restarts, seed=0, Dm=None):
    Dm = D if Dm is None else Dm
    rng = np.random.default_rng(seed + k)
    best = None
    for _ in range(restarts):
        res = kmedoids(Dm, k, rng)
        if best is None or res[2] < best[2]:
            best = res
    med, lab, cost = best
    present, lab = np.unique(lab, return_inverse=True)     # compact labels (drops any empty cluster), keep medoids aligned
    return med[present], lab, cost


# %% Limits: split any cluster that is too wide or has too many sections
def within_limits(idx):
    return len(idx) <= MAX_N and (len(idx) == 1 or D[np.ix_(idx, idx)].max() <= MAX_W)


def limited_clusters(start_k, restarts):
    _, lab, _ = best_of(start_k, restarts)
    todo = [np.flatnonzero(lab == c) for c in np.unique(lab)]; done = []; n_split = 0
    while todo:
        g = todo.pop()
        if within_limits(g):
            done.append(g); continue
        n_split += 1; kk = 2
        while True:                                          # fewest pieces that all meet the limits
            _, sub, _ = best_of(kk, 5, seed=start_k, Dm=D[np.ix_(g, g)])
            parts = [g[sub == c] for c in np.unique(sub)]
            if all(within_limits(p) for p in parts) or kk >= len(g):
                break
            kk += 1
        done.extend(parts)
    out = np.zeros(n, int)
    for c, g in enumerate(done):
        out[g] = c
    return out, n_split


# %% Silhouette and total distance across k (unlimited k-medoids, for context)
rows = []
for k in K_GRID:
    sils = []
    for seed in (0, 1000):                  # two independent best-of runs per k; the score is their mean (k-medoids silhouette is noisy)
        med, lab, cost = best_of(k, max(5, args.restarts // 3), seed=seed)
        sils.append(silhouette_samples(D, lab, metric="precomputed").mean() if 1 < len(set(lab)) < n else np.nan)
    rows.append({"k": k, "clusters": len(set(lab)), "total_distance_to_medoid_mi": round(cost, 1),
                 "silhouette": round(float(np.mean(sils)), 3), "silhouette_run_gap": round(abs(sils[0] - sils[1]), 3)})
    log.info("k=%d: silhouette %.3f (two runs %.3f / %.3f), total distance to medoids %.0f mi", k, np.mean(sils), *sils, cost)
curve = pd.DataFrame(rows)
curve.to_csv(TABLE_DIR / "silhouette_by_k.csv", index=False)
K_SIL = int(curve.loc[curve["silhouette"].idxmax(), "k"])          # plain k-medoids: the k with the best silhouette
near = curve[curve["silhouette"] >= curve["silhouette"].max() - 0.01]["k"]
log.info("best silhouette %.3f at k = %d; every k from %d to %d scores within 0.01 of it (the peak is a plateau, "
         "and two runs at the same k differ by about %.3f)", curve["silhouette"].max(), K_SIL, near.min(), near.max(), curve["silhouette_run_gap"].median())

kmed, n_split = limited_clusters(START_K, args.restarts)
K = len(set(kmed))
log.info("start k = %d -> %d clusters after splitting %d that broke the limits", START_K, K, n_split)
medoid_of = np.zeros(n, int); med = np.zeros(K, int)
for c in range(K):                                        # medoid = the member with the smallest total distance to the others
    g = np.flatnonzero(kmed == c); med[c] = g[D[np.ix_(g, g)].sum(axis=1).argmin()]; medoid_of[g] = med[c]
widest = max(D[np.ix_(g, g)].max() for g in (np.flatnonzero(kmed == c) for c in range(K)) if len(g) > 1)
assert pd.Series(kmed).value_counts().max() <= MAX_N and widest <= MAX_W, "limits not met"


# %% Compare with Nate's clusters on the same measures
def describe(lab, name):
    lab = np.asarray(lab); sizes = pd.Series(lab).value_counts()
    sil = silhouette_samples(D, lab, metric="precomputed")
    width, to_center, mate, mixed, multi = [], [], [], 0, 0
    for c, g in pd.Series(np.arange(n)).groupby(lab):
        idx = g.to_numpy()
        sub = D[np.ix_(idx, idx)]
        to_center.extend(sub[:, sub.sum(axis=1).argmin()])   # distance to the most central member
        if len(idx) > 1:
            multi += 1; width.append(sub.max()); mixed += len(set(hatch[idx])) > 1
            mate.extend((sub + np.diag([np.inf] * len(idx))).min(axis=1))
    return {"method": name, "clusters": len(sizes), "singletons": int((sizes == 1).sum()), "pairs": int((sizes == 2).sum()),
            "size 3-5": int(sizes.between(3, 5).sum()), "size 6+": int((sizes >= 6).sum()), "biggest": int(sizes.max()),
            "median width (mi)": round(float(np.median(width)), 1), "widest (mi)": round(float(np.max(width)), 1),
            "mean silhouette": round(float(sil.mean()), 3), "sections with negative silhouette (%)": round(100 * float((sil < 0).mean()), 1),
            "clusters mixing main hatcheries": f"{mixed} of {multi}",
            "median distance to nearest cluster-mate (mi)": round(float(np.median(mate)), 1),
            "median distance to cluster center (mi)": round(float(np.median(to_center)), 1),
            "total distance to cluster center (mi)": round(float(np.sum(to_center)), 0)}, sil


_, plain, _ = best_of(K_SIL, args.restarts)               # approach 2: plain k-medoids, no limits, k from the best silhouette
tab_n, sil_n = describe(nate, "1. Nate's schedule clusters")
tab_p, sil_p = describe(plain, f"2. k-medoids, no limits, best silhouette ({len(set(plain))} clusters)")
tab_k, sil_k = describe(kmed, f"3. k-medoids with limits ({K} clusters)")

_hm = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet").pivot_table(index="section_id", columns="hatchery", values="road_mi").reindex(ids)
H = _hm[[c for c in _hm.columns if any(s.lower() in c.lower() for s in SCHEDULED)]].to_numpy()   # sections x 9 scheduled hatcheries


def hatchery_error(lab):
    """Cluster-average road distance from each scheduled hatchery vs. each member's own: (mean mi, p90 mi, share of total distance)."""
    err = np.zeros_like(H)
    for c in np.unique(lab):
        g = np.flatnonzero(lab == c); err[g] = H[g].mean(0) - H[g]
    return np.abs(err).mean(), np.quantile(np.abs(err), .9), 100 * np.abs(err).sum() / H.sum()


herr = {}
for t, lab in ((tab_n, nate), (tab_p, plain), (tab_k, kmed)):
    herr[t["method"]] = e = hatchery_error(lab)
    t["hatchery_distance_error"] = f"{e[0]:.1f} mi mean, {e[1]:.1f} mi p90 ({e[2]:.1f}% of distance)"
comparison = pd.DataFrame([tab_n, tab_p, tab_k]).set_index("method").T
comparison.loc["agreement with approach 3 (adjusted Rand, 0 to 1)"] = [round(adjusted_rand_score(kmed, x), 2) for x in (nate, plain, kmed)]
comparison.to_csv(TABLE_DIR / "comparison.csv")
print(comparison.to_string())

out = pd.DataFrame({"section_id": ids, "medoid_cluster_id": [f"M{c + 1:03d}" for c in kmed],
                    "medoid_section_id": [ids[i] for i in medoid_of], "cluster_size": pd.Series(kmed).map(pd.Series(kmed).value_counts()).to_numpy(),
                    "dist_to_medoid_mi": D[np.arange(n), medoid_of].round(2), "silhouette": sil_k.round(3),
                    "silhouette_best_cluster_id": [f"B{c + 1:03d}" for c in plain]})   # option 2: plain k-medoids at the best-silhouette k
out.to_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet", index=False)
out.to_csv(PROCESSED_DIR / "section_medoid_clusters.csv", index=False)
assert out.section_id.is_unique and len(out) == n and (out.dist_to_medoid_mi >= 0).all()
assert all(out.set_index("section_id").loc[m, "medoid_cluster_id"] == c for m, c in zip(out.medoid_section_id, out.medoid_cluster_id))
log.info("wrote %d rows to section_medoid_clusters (each medoid sits in its own cluster)", len(out))


# %% Figure 1: maps
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]].to_crs(CRS)
sec = sec.set_index("section_id")
geom = sec.geometry.reindex(ids)
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg").to_crs(CRS) if (RAW_DIR / "pa_boundary.gpkg").exists() else None
cmap = LinearSegmentedColormap.from_list("size", ["#dbe7f8", "#2a78d6", "#0b3a7a"])
norm = Normalize(2, 18)


def hulls_of(lab):
    return {c: unary_union(list(geom.iloc[np.flatnonzero(lab == c)])).convex_hull.buffer(MARGIN_M) for c in np.unique(lab)}


def poly(ax, g, **kw):
    ax.add_patch(Poly(np.array(g.exterior.coords), closed=True, joinstyle="round", **kw))


def state_map(ax, lab, title):
    hulls = hulls_of(lab); sizes = pd.Series(lab).value_counts()
    if pa is not None:
        pa.boundary.plot(ax=ax, color=INK2, lw=1.0)
    gpd.GeoSeries(geom).plot(ax=ax, color="#cfcec8", lw=0.4, zorder=1)
    mixed = {c: len(set(hatch[lab == c])) > 1 for c in hulls}
    for c, h in sorted(hulls.items(), key=lambda kv: -sizes[kv[0]]):
        if sizes[c] > 1:
            poly(ax, h, facecolor=cmap(norm(min(sizes[c], 18))), alpha=0.55, edgecolor="none", zorder=2)
    for c, h in hulls.items():
        if sizes[c] > 1:
            poly(ax, h, fill=False, edgecolor=ORANGE if mixed[c] else INK, lw=1.6 if mixed[c] else 0.5, zorder=3)
    one = [i for i in range(n) if sizes[lab[i]] == 1]
    pts = gpd.GeoSeries([geom.iloc[i].representative_point() for i in one])
    ax.scatter(pts.x, pts.y, s=9, color=INK2, zorder=4, linewidth=0)
    ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_title(title, loc="left", fontsize=11.5)
    return sum(mixed[c] for c in hulls if sizes[c] > 1)


fig = plt.figure(figsize=(17, 10.6))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.10, wspace=0.04)
fig.suptitle("Nate's schedule clusters vs k-medoids on road miles: the same 1,022 sections in a similar number of clusters",
             x=0.01, ha="left", fontsize=14, fontweight="bold")
fig.text(0.01, 0.948, f"Left: sections PFBC stocks on the same truck runs. Right: sections grouped only by driving distance, ignoring the schedule and hatcheries. "
         f"Outlines in orange mix sections whose main hatcheries differ.", fontsize=10.5, color=INK2)
ax1, ax2 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
m1 = state_map(ax1, nate, f"Nate's schedule clusters: {len(set(nate))} clusters, silhouette {tab_n['mean silhouette']:.2f}")
m2 = state_map(ax2, kmed, f"k-medoids with limits: {len(set(kmed))} clusters, silhouette {tab_k['mean silhouette']:.2f}")
ax1.text(0.0, 0.0, f"{m1} clusters mix main hatcheries", transform=ax1.transAxes, fontsize=10, color=ORANGE)
ax2.text(0.0, 0.0, f"{m2} clusters mix main hatcheries", transform=ax2.transAxes, fontsize=10, color=ORANGE)
cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=[ax1, ax2], shrink=0.5, pad=0.012, aspect=22, location="right")
cb.set_label("sections in the cluster (shading)", color=INK2); cb.outline.set_visible(False)

# zoom: where Nate's biggest cluster sits, and how k-medoids cuts those sections up
big = ss["cluster_id"].value_counts().idxmax()
big_idx = np.flatnonzero((ss["cluster_id"] == big).to_numpy())
big_hull = unary_union(list(geom.iloc[big_idx])).convex_hull.buffer(MARGIN_M)
minx, miny, maxx, maxy = big_hull.bounds
kh = hulls_of(kmed)
touch = sorted({kmed[i] for i in big_idx})
za, zb = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])
for ax in (za, zb):
    ax.set_xlim(minx - 12000, maxx + 12000); ax.set_ylim(miny - 12000, maxy + 12000)
    gpd.GeoSeries(geom).plot(ax=ax, color="#cfcec8", lw=0.8, zorder=1)
    gpd.GeoSeries(geom.iloc[big_idx]).plot(ax=ax, color=ORANGE, lw=3.0, zorder=4)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)
poly(za, big_hull, facecolor="#00000010", edgecolor=INK, lw=1.5, zorder=2)
za.set_title(f"Nate's {big}, his biggest cluster: {len(big_idx)} sections in one cluster", loc="left", fontsize=11.5)
for c in touch:
    poly(zb, kh[c], facecolor="#00000008", edgecolor=INK, lw=1.3, zorder=2)
    mi = med[c]
    p = geom.iloc[mi].representative_point()
    zb.scatter(p.x, p.y, marker="*", s=230, color=INK, edgecolor=SURFACE, linewidth=0.9, zorder=6)
poly(zb, big_hull, fill=False, edgecolor=ORANGE, lw=1.4, linestyle="--", zorder=3)
zb.set_title(f"The same {len(big_idx)} sections under k-medoids: they fall into {len(touch)} clusters", loc="left", fontsize=11.5)
zb.legend(handles=[Line2D([], [], color=ORANGE, lw=3, label=f"sections in Nate's {big}"),
                   Line2D([], [], color=ORANGE, lw=1.4, ls="--", label=f"Nate's {big} outline"),
                   Line2D([], [], color=INK, lw=1.3, label="a k-medoids cluster"),
                   Line2D([], [], marker="*", ls="", color=INK, markersize=13, label="its medoid (most central section)")],
          loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, frameon=False, fontsize=9.5)
fig.text(0.01, 0.008, "Outlines are each cluster's convex hull plus a 2.5 km margin, so they overlap where clusters sit close together. "
         "Distances are real road miles from OSRM.", fontsize=9.5, color=INK2)
fig.savefig(FIG_DIR / "maps.png", dpi=120, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)


# %% Figure 2: silhouette graphs
fig, (a, b) = plt.subplots(1, 2, figsize=(15, 5.6), gridspec_kw={"width_ratios": [1.1, 1]})
fig.suptitle("How tight and well separated are the clusters? Silhouette score (higher is better, 1 is perfect, below 0 is misplaced)",
             x=0.01, ha="left", fontsize=13, fontweight="bold")
a.plot(curve.k, curve.silhouette, color=BLUE, lw=2, marker="o", markersize=6, markeredgecolor=SURFACE)
a.scatter([len(set(nate))], [tab_n["mean silhouette"]], s=110, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=5)
a.annotate(f"Nate's schedule clusters: {tab_n['mean silhouette']:.2f}", (len(set(nate)), tab_n["mean silhouette"]), xytext=(14, -4),
           textcoords="offset points", fontsize=10.5, color=INK)
a.scatter([K], [tab_k["mean silhouette"]], s=110, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=5)
a.annotate(f"with limits, {K} clusters: {tab_k['mean silhouette']:.2f}", (K, tab_k["mean silhouette"]), xytext=(16, 16), textcoords="offset points", fontsize=10.5, color=INK, ha="left")
ks = curve[curve.k == K_SIL].iloc[0]
a.scatter([K_SIL], [ks.silhouette], s=110, color=AQUA, edgecolor=SURFACE, linewidth=1.5, zorder=5)
a.annotate(f"no limits, best silhouette (k = {K_SIL}): {ks.silhouette:.2f}", (K_SIL, ks.silhouette), xytext=(0, 14), textcoords="offset points", fontsize=10.5, color=INK, ha="center")
a.set_ylim(0, 0.46)
a.set_xlabel("number of clusters (k)"); a.set_ylabel("mean silhouette score")
a.set_title("k-medoids silhouette across k (no limits)", loc="left", fontsize=11.5); a.grid(color=GRID, lw=0.8); a.set_axisbelow(True)
bins = np.linspace(-0.6, 1, 41)
for sil, col, lab in ((sil_k, BLUE, "k-medoids"), (sil_n, ORANGE, "Nate's schedule clusters")):
    b.hist(sil, bins=bins, histtype="step", lw=2, color=col, label=f"{lab} (mean {sil.mean():.2f})")
b.axvline(0, color=INK2, lw=0.8, ls=":")
b.set_xlabel("silhouette score of each section"); b.set_ylabel("number of sections")
b.set_title(f"Every section's score ({K} clusters with limits)", loc="left", fontsize=11.5); b.legend(frameon=False, loc="upper right", fontsize=10.5)
b.grid(color=GRID, lw=0.8); b.set_axisbelow(True)
fig.text(0.01, 0.005, "Silhouette compares a section's average road distance to its own cluster with its distance to the nearest other cluster. Singletons score 0 (the spike at 0).\n"
         "k-medoids optimizes distance, so it wins this measure by design; it says nothing about which sections share a truck.", fontsize=9.5, color=INK2)
fig.tight_layout(rect=(0, 0.07, 1, 0.92))
fig.savefig(FIG_DIR / "silhouette.png", dpi=120)
log.info("saved figures to %s", FIG_DIR.relative_to(ROOT))


# %% Figure 3: all three approaches, statewide and zoomed on Nate's biggest cluster
approaches = [(tab_n["method"], nate, tab_n, sil_n), (tab_p["method"], plain, tab_p, sil_p), (tab_k["method"], kmed, tab_k, sil_k)]
fig = plt.figure(figsize=(19, 10.6))
gs = fig.add_gridspec(2, 3, height_ratios=[0.8, 1], hspace=0.12, wspace=0.03)
fig.suptitle("Three ways to group the 1,022 stocked sections by similar cost", x=0.01, ha="left", fontsize=15, fontweight="bold")
fig.text(0.01, 0.935, "Top: statewide (shading = sections per cluster, grey dots = singletons, orange outline = cluster mixes sections whose scheduled hatcheries differ). "
         "Bottom: the same patch of the state, around Nate's biggest cluster (orange lines).", fontsize=10.5, color=INK2)
for j, (name, lab, tab, _) in enumerate(approaches):
    ax = fig.add_subplot(gs[0, j])
    state_map(ax, lab, name)
    ax.set_title(name.split(" (")[0].replace("k-medoids, no limits, best silhouette", "k-medoids, best silhouette"), loc="left", fontsize=12.5, fontweight="bold", pad=46)
    e = herr[name]
    ax.text(0, 1.01, f"{tab['clusters']} clusters · {tab['singletons']} singletons · biggest {tab['biggest']} sections\n"
            f"widest {tab['widest (mi)']:.0f} mi · silhouette {tab['mean silhouette']:.2f} · hatchery-distance error {e[2]:.1f}% ({e[0]:.1f} mi)",
            transform=ax.transAxes, fontsize=9.8, color=INK, va="bottom")
    z = fig.add_subplot(gs[1, j])
    z.set_xlim(minx - 12000, maxx + 12000); z.set_ylim(miny - 12000, maxy + 12000)
    gpd.GeoSeries(geom).plot(ax=z, color="#cfcec8", lw=0.8)
    gpd.GeoSeries(geom.iloc[big_idx]).plot(ax=z, color=ORANGE, lw=3.0, zorder=4)
    hh = hulls_of(lab)
    for c in {lab[i] for i in range(n) if hh[lab[i]].intersects(big_hull)}:          # every cluster that reaches the patch
        poly(z, hh[c], facecolor="#00000008", edgecolor=INK, lw=1.2, zorder=2)
    z.set_aspect("equal"); z.set_xticks([]); z.set_yticks([])
    for s_ in z.spines.values():
        s_.set_color(GRID)
    n_in = len(set(lab[big_idx]))
    z.set_title(f"Same {len(big_idx)} sections: {n_in} cluster{'s' if n_in > 1 else ''}", loc="left", fontsize=11)
fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=fig.add_axes([0.915, 0.60, 0.008, 0.2])).set_label("sections in cluster", color=INK2)
fig.text(0.01, 0.01, "1: built from PFBC's truck-run schedule (carries PFBC's hatchery choices). 2 and 3: built only from road miles between sections; 3 splits any cluster "
         f"over {MAX_W:.0f} mi wide or {MAX_N} sections. Hatchery-distance error: how far a cluster's average distance from each of the 9 scheduled hatcheries sits from each member's own.",
         fontsize=9.5, color=INK2, wrap=True)
fig.savefig(FIG_DIR / "approach_comparison.png", dpi=115, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)
log.info("saved approach_comparison.png")
