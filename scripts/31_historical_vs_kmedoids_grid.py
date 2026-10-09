"""2 x 2 grid in the Sep 30 comparison format: Historical clusters (defined by a simple rule on real truck runs) versus the model's k-medoids clusters.

Left  = "Historical": Nate's schedule clusters. The rule: two sections are linked when, of the 2026 truck runs that visited either one, at least half
        visited both (runs holding both / the smaller section's runs >= 0.5; scripts/10_runs_clusters.py, parameters.csv cluster_share_min); each linked
        group is a cluster. A run = date + hatchery + meeting place + time. Uses all seasons' runs. Distance plays no part in the rule.
Right = k-medoids on road miles between sections, no limits, number of clusters (310) chosen by best silhouette; the model's base clustering.
Top row: statewide (shading = sections per cluster, dark dots = sections on their own, orange outline = cluster mixes sections whose scheduled hatcheries
differ). Bottom row: the same patch of the state, around Nate's biggest cluster (orange lines).

Inputs : data/processed/section_schedule.parquet, section_medoid_clusters.parquet, section_to_section_road_distance.parquet,
         hatchery_to_section_road_distance.parquet, hatchery_schedule_supply.csv, pa_trout.gpkg (sections), data/raw/pa_boundary.gpkg
Outputs: outputs/figures/method_comparison/historical_vs_kmedoids.png   logs/31_historical_vs_kmedoids_grid.log

    python scripts/31_historical_vs_kmedoids_grid.py
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
from matplotlib.patches import Polygon as Poly
from shapely.ops import unary_union
from sklearn.metrics import silhouette_samples

from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "method_comparison"
CRS = 26918
SURFACE, INK, INK2, GRID, ORANGE = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e0", "#eb6834"
setup_logging("31_historical_vs_kmedoids_grid")
log = logging.getLogger("31_historical_vs_kmedoids_grid")
FIG_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})

# %% Data
ss = pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet")
ids = ss["section_id"].tolist()
ix = {s: i for i, s in enumerate(ids)}
n = len(ids)
share_min = float(pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter").loc["cluster_share_min", "value"])
assert share_min == 0.5, "the rule on the slide says at least half"
hist = ss["cluster_id"].to_numpy()
km = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet").set_index("section_id").loc[ids, "silhouette_best_cluster_id"].to_numpy()
assert len(set(hist)) == 351 and len(set(km)) == 310
cols = {"1  Historical: sections that shared truck runs": hist, "2  k-medoids on road miles, no limits (the model)": km}

r = pd.read_parquet(PROCESSED_DIR / "section_to_section_road_distance.parquet")
D = np.zeros((n, n))
D[r.from_section_id.map(ix).to_numpy(), r.to_section_id.map(ix).to_numpy()] = r.road_mi.to_numpy()
D = (D + D.T) / 2
np.fill_diagonal(D, 0)
supply = pd.read_csv(PROCESSED_DIR / "hatchery_schedule_supply.csv")
producing = supply.loc[supply["stream_fish_2026"] > 0, "hatchery"].tolist()
HP = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet").pivot_table(index="section_id", columns="hatchery", values="road_mi").reindex(ids)[producing].to_numpy()
prim = ss["primary_hatchery"].to_numpy()


def stats(lab):
    lab = np.asarray(lab)
    sizes = pd.Series(lab).value_counts()
    groups = [np.flatnonzero(lab == c) for c in sizes.index]
    w = [D[np.ix_(g, g)].max() for g in groups if len(g) > 1]
    err = np.zeros_like(HP)
    for g in groups:
        err[g] = HP[g].mean(0) - HP[g]
    return dict(clusters=len(sizes), alone=int((sizes == 1).sum()), biggest=int(sizes.max()), widest=max(w),
                sil=silhouette_samples(D, lab, metric="precomputed").mean(), err=100 * np.abs(err).sum() / HP.sum(), err_mi=np.abs(err).mean())


S = {name: stats(lab) for name, lab in cols.items()}
for name, s_ in S.items():
    log.info("%s: %s", name, {k: round(float(v), 2) for k, v in s_.items()})
assert S[list(cols)[0]]["clusters"] == 351 and S[list(cols)[0]]["alone"] == 103 and S[list(cols)[1]]["alone"] == 54      # docs/clustering_options.md

# %% Geometry
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]].to_crs(CRS).set_index("section_id")
geom = sec.geometry.reindex(ids)
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg").to_crs(CRS)
pts = gpd.GeoSeries([g.representative_point() for g in geom])
px, py = pts.x.to_numpy(), pts.y.to_numpy()
cmap_s = LinearSegmentedColormap.from_list("size", ["#dbe7f8", "#2a78d6", "#0b3a7a"])
norm_s = Normalize(2, 18)


def base(ax):
    pa.boundary.plot(ax=ax, color=INK2, lw=0.8)
    gpd.GeoSeries(geom).plot(ax=ax, color="#d9d8d2", lw=0.4, zorder=1)
    ax.set_aspect("equal")
    ax.set_axis_off()


def poly(ax, g, **kw):
    ax.add_patch(Poly(np.array(g.exterior.coords), closed=True, joinstyle="round", **kw))


big = pd.Series(hist).value_counts().idxmax()
big_i = np.flatnonzero(hist == big)
big_hull = unary_union(list(geom.iloc[big_i])).convex_hull.buffer(2500)
minx, miny, maxx, maxy = big_hull.bounds

# %% Draw
fig = plt.figure(figsize=(14.2, 10.8))
gs = fig.add_gridspec(2, 2, height_ratios=[0.8, 1], hspace=0.22, wspace=0.05, left=0.03, right=0.92, top=0.80, bottom=0.04)
fig.suptitle("What historical truck trips grouped together, versus how the model groups sections", x=0.012, y=0.985, ha="left", fontsize=16, fontweight="bold")
fig.text(0.012, 0.915, "Historical rule: link two sections when at least half of the truck runs that visited either one visited both.", fontsize=11.5, color=INK2, va="bottom")
for j, (name, lab) in enumerate(cols.items()):
    s_ = S[name]
    sizes = pd.Series(lab).value_counts()
    hulls = {c: unary_union(list(geom.iloc[np.flatnonzero(lab == c)])).convex_hull.buffer(2500) for c in sizes.index}
    ax = fig.add_subplot(gs[0, j])
    base(ax)
    for c, h in sorted(hulls.items(), key=lambda kv: -sizes[kv[0]]):
        if sizes[c] > 1:
            poly(ax, h, facecolor=cmap_s(norm_s(min(sizes[c], 18))), alpha=0.6, edgecolor="none", zorder=2)
    n_mixed = 0
    for c, h in hulls.items():
        if sizes[c] > 1:
            mixed = len(set(prim[lab == c])) > 1
            n_mixed += mixed
            poly(ax, h, fill=False, edgecolor=ORANGE if mixed else INK, lw=1.8 if mixed else 0.5, zorder=3)
    one = np.flatnonzero(pd.Series(lab).map(sizes).to_numpy() == 1)
    ax.scatter(px[one], py[one], s=9, color=INK2, linewidth=0, zorder=4)
    ax.set_title(name, loc="left", fontsize=13, fontweight="bold", pad=44)
    ax.text(0, 1.01, f"{s_['clusters']} clusters · {s_['alone']} on their own · biggest {s_['biggest']} sections\n"
            f"widest {s_['widest']:.0f} mi · {n_mixed} mix hatcheries (orange outline)", transform=ax.transAxes, fontsize=10.5, color=INK, va="bottom", linespacing=1.4)
    z = fig.add_subplot(gs[1, j])
    z.set_xlim(minx - 12000, maxx + 12000)
    z.set_ylim(miny - 12000, maxy + 12000)
    gpd.GeoSeries(geom).plot(ax=z, color="#cfcec8", lw=0.8)
    gpd.GeoSeries(geom.iloc[big_i]).plot(ax=z, color=ORANGE, lw=3.0, zorder=4)
    for c, h in hulls.items():
        if h.intersects(big_hull):
            poly(z, h, facecolor="#00000008", edgecolor=INK, lw=1.2, zorder=2)
    z.set_aspect("equal")
    z.set_xticks([])
    z.set_yticks([])
    for sp in z.spines.values():
        sp.set_color(GRID)
    k_in = len(set(lab[big_i]))
    z.set_title(f"Same {len(big_i)} sections: {k_in} cluster{'s' if k_in > 1 else ''}", loc="left", fontsize=11)
fig.colorbar(ScalarMappable(norm=norm_s, cmap=cmap_s), cax=fig.add_axes([0.935, 0.50, 0.010, 0.22])).set_label("sections in cluster", color=INK2)
fig.savefig(FIG_DIR / "historical_vs_kmedoids.png", dpi=115, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)
log.info("saved %s", (FIG_DIR / "historical_vs_kmedoids.png").relative_to(ROOT))
