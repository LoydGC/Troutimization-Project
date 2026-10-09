"""3 x 2 comparison grid (the format of scripts/16's approach_comparison_no_limits): how 2026 truck trips actually grouped sections, versus the two clusterings.

Columns : 1. historical truck runs (2026 pre-season: every section has at most one, so runs partition the sections; 991 of 1,022 are in one),
          2. Nate's schedule clusters (built from the runs: sections that share at least half their runs),
          3. k-medoids on road miles, best silhouette, 310 clusters (the model's base clustering).
Top row : statewide (shading = sections per group, dark dots = sections on their own). Bottom row: the same patch of the state around the biggest real
          truck run (orange lines); outlines = every group of that column that touches it.
Width   = the longest road distance between any two sections of a group (road miles, section_to_section_road_distance).

Inputs : data/processed/section_schedule.parquet, stocking_events.parquet, section_medoid_clusters.parquet, section_to_section_road_distance.parquet,
         pa_trout.gpkg (sections), data/raw/pa_boundary.gpkg
Outputs: outputs/figures/method_comparison/trips_vs_clusters.png   logs/30_trips_vs_clusters_grid.log

    python scripts/figures/30_trips_vs_clusters_grid.py
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
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Polygon as Poly
from shapely.ops import unary_union

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/, where common.py lives
from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "method_comparison"
CRS = 26918
SURFACE, INK, INK2, GRID, ORANGE = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e0", "#eb6834"
setup_logging("30_trips_vs_clusters_grid")
log = logging.getLogger("30_trips_vs_clusters_grid")
FIG_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})

# %% Groupings
ss = pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet")
ids = ss["section_id"].tolist()
ix = {s: i for i, s in enumerate(ids)}
n = len(ids)
ev = pd.read_parquet(PROCESSED_DIR / "stocking_events.parquet")
pre = ev[(ev.water_type == "stream") & ev.section_id.isin(ids) & (ev.season == "P")]
assert pre.groupby("section_id").run_id.nunique().max() == 1
run_of = pre.drop_duplicates("section_id").set_index("section_id").run_id.reindex(ids)
runs = np.where(run_of.notna(), run_of.fillna("").to_numpy(), [f"none{i}" for i in range(n)])             # no pre-season run = on its own
nate = ss["cluster_id"].to_numpy()
km = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet").set_index("section_id").loc[ids, "silhouette_best_cluster_id"].to_numpy()
assert len(set(km)) == 310
cols = {"1. Historical truck runs (2026 pre-season)": runs, "2. Nate's schedule clusters (built from the runs)": nate, "3. k-medoids, 310 clusters (the model)": km}

r = pd.read_parquet(PROCESSED_DIR / "section_to_section_road_distance.parquet")
D = np.zeros((n, n))
D[r.from_section_id.map(ix).to_numpy(), r.to_section_id.map(ix).to_numpy()] = r.road_mi.to_numpy()
D = (D + D.T) / 2
np.fill_diagonal(D, 0)

multi_runs = [np.flatnonzero(runs == c) for c, k in pd.Series(runs).value_counts().items() if k >= 2]


def stats(lab):
    lab = np.asarray(lab)
    sizes = pd.Series(lab).value_counts()
    groups = [np.flatnonzero(lab == c) for c in sizes.index if sizes[c] > 1]
    w = [D[np.ix_(g, g)].max() for g in groups]
    whole = np.mean([len(set(lab[g])) == 1 for g in multi_runs])
    pairs = same = 0
    for g in groups:
        for a, b in itertools.combinations(g, 2):
            pairs += 1
            same += int(runs[a] == runs[b] and not str(runs[a]).startswith("none"))
    return dict(groups=len(sizes), alone=int((sizes == 1).sum()), biggest=int(sizes.max()), typical=float(np.median([len(g) for g in groups])), widest=max(w),
                med_w=float(np.median(w)), whole=100 * whole, same=100 * same / pairs)


S = {name: stats(lab) for name, lab in cols.items()}
for name, s_ in S.items():
    log.info("%s: %s", name, {k: round(v, 1) for k, v in s_.items()})

# %% Geometry
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]].to_crs(CRS).set_index("section_id")
geom = sec.geometry.reindex(ids)
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg").to_crs(CRS)
pts = gpd.GeoSeries([g.representative_point() for g in geom])
px, py = pts.x.to_numpy(), pts.y.to_numpy()
cmap_s = LinearSegmentedColormap.from_list("size", ["#dbe7f8", "#2a78d6", "#0b3a7a"])
norm_s = Normalize(2, 12)


def base(ax):
    pa.boundary.plot(ax=ax, color=INK2, lw=0.8)
    gpd.GeoSeries(geom).plot(ax=ax, color="#d9d8d2", lw=0.4, zorder=1)
    ax.set_aspect("equal")
    ax.set_axis_off()


def poly(ax, g, **kw):
    ax.add_patch(Poly(np.array(g.exterior.coords), closed=True, joinstyle="round", **kw))


big_i = max(multi_runs, key=lambda g: (len(set(km[g])), len(g)))     # the real truck run that k-medoids splits into the most clusters (ties: the bigger run)
big_hull = unary_union(list(geom.iloc[big_i])).convex_hull.buffer(2500)
minx, miny, maxx, maxy = big_hull.bounds
log.info("focus run: %d sections in %d k-medoids clusters, %d Nate clusters; %s", len(big_i), len(set(km[big_i])), len(set(nate[big_i])), run_of.iloc[big_i[0]])

# %% Draw
fig = plt.figure(figsize=(19, 10.8))
gs = fig.add_gridspec(2, 3, height_ratios=[0.8, 1], hspace=0.16, wspace=0.04, left=0.02, right=0.93, top=0.84, bottom=0.04)
fig.suptitle("What truck trips actually looked like, versus how the model groups sections", x=0.012, y=0.985, ha="left", fontsize=16, fontweight="bold")
fig.text(0.012, 0.935, "Top: statewide (shading = sections per group, dark dots = sections on their own). "
         "Bottom: the same patch of the state, around one real truck run that k-medoids splits apart (orange lines).", fontsize=11, color=INK2, va="bottom")
for j, (name, lab) in enumerate(cols.items()):
    s_ = S[name]
    sizes = pd.Series(lab).value_counts()
    hulls = {c: unary_union(list(geom.iloc[np.flatnonzero(lab == c)])).convex_hull.buffer(2500) for c in sizes.index}
    ax = fig.add_subplot(gs[0, j])
    base(ax)
    for c, h in sorted(hulls.items(), key=lambda kv: -sizes[kv[0]]):
        if sizes[c] > 1:
            poly(ax, h, facecolor=cmap_s(norm_s(min(sizes[c], 12))), alpha=0.6, edgecolor="none", zorder=2)
    for c, h in hulls.items():
        if sizes[c] > 1:
            poly(ax, h, fill=False, edgecolor=INK, lw=0.5, zorder=3)
    one = np.flatnonzero(pd.Series(lab).map(sizes).to_numpy() == 1)
    ax.scatter(px[one], py[one], s=9, color=INK2, linewidth=0, zorder=4)
    ax.set_title(name, loc="left", fontsize=12.5, fontweight="bold", pad=70)
    unit = "runs" if j == 0 else "clusters"
    n_groups = s_["groups"] - (int(sum(str(c).startswith("none") for c in sizes.index)) if j == 0 else 0)          # the 31 sections without a pre-season run are not runs
    ax.text(0, 1.01, f"{n_groups} {unit} · {s_['alone']} sections on their own · biggest {s_['biggest']} sections\n"
            f"typical {s_['typical']:.0f} sections, {s_['med_w']:.0f} mi across · widest {s_['widest']:.0f} mi\n"
            f"keeps {s_['whole']:.0f}% of real multi-section runs whole · {s_['same']:.0f}% of group-mates rode one truck",
            transform=ax.transAxes, fontsize=9.8, color=INK, va="bottom")
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
    z.set_title(f"Same {len(big_i)} sections: {k_in} {'run' if j == 0 else 'cluster'}{'s' if k_in > 1 else ''}", loc="left", fontsize=11)
fig.colorbar(ScalarMappable(norm=norm_s, cmap=cmap_s), cax=fig.add_axes([0.945, 0.56, 0.008, 0.22])).set_label("sections in group", color=INK2)
fig.text(0.012, 0.008, "A run = one truck meeting (date, hatchery, meeting place, time) in PFBC's 2026 pre-season schedule; 31 sections have no pre-season run and count as on their own. "
         "Nate's clusters link sections that share at least half their runs. k-medoids uses only road miles between sections, no size or width limit. "
         "Width = longest road distance between any two sections of a group.", fontsize=9.5, color=INK2, wrap=True)
fig.savefig(FIG_DIR / "trips_vs_clusters.png", dpi=115, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)
log.info("saved %s", (FIG_DIR / "trips_vs_clusters.png").relative_to(ROOT))
