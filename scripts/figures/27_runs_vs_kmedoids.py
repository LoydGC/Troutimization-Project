"""Slide visual: what 2026 truck trips actually looked like versus what the model's k-medoids clusters treat as shared trucks.

Left  = PFBC's 2026 pre-season truck runs (stocking_events, season P: one run per section; a run = date + hatchery + meeting place + time,
        scripts/09_stocking_schedule.py). These are the groups Nate's clusters are built from.
Right = the model's clusters (k-medoids on road miles, best silhouette, 310): in the model, cluster-mates supplied by the same hatchery in the same
        round share trucks (scripts/20_transport_cost.py, optimization.py).
Same patch of the state in both panels. Colours only separate groups; grey = a section on its own. Statistics are computed on the whole state.
Pre-season is used because every section has at most one pre-season stocking, so runs partition the sections cleanly (991 of 1,022 sections).

Inputs : data/processed/stocking_events.parquet, section_medoid_clusters.parquet, section_to_section_road_distance.parquet, sections.parquet,
         pa_trout.gpkg (sections layer), data/raw/pa_boundary.gpkg
Outputs: outputs/figures/kmedoids/runs_vs_kmedoids.png   logs/27_runs_vs_kmedoids.log
No title on purpose: it is added in the deck.

    python scripts/figures/27_runs_vs_kmedoids.py
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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/, where common.py lives
from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging, register_open_sans

FIG_DIR = ROOT / "outputs" / "figures" / "kmedoids"
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
BLUE, OTHER = "#2a78d6", "#c9c8c1"
PALETTE = ["#2a78d6", "#f5ae00", "#a6192e", "#1baf7a", "#7b4fb0", "#d81b7c", "#56b4e9", "#8c9a1b"]
setup_logging("27_runs_vs_kmedoids")
log = logging.getLogger("27_runs_vs_kmedoids")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Open Sans (the deck's font; SIL Open Font License), local only: see common.register_open_sans. Falls back to DejaVu Sans if absent.
register_open_sans()
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})

# %% Pre-season runs and clusters
tot = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"]).set_index("section_id").total_2026
ids = tot[tot.fillna(0) > 0].index
assert len(ids) == 1022
ev = pd.read_parquet(PROCESSED_DIR / "stocking_events.parquet")
st = ev[(ev.water_type == "stream") & ev.section_id.isin(ids) & (ev.season == "P")]
assert st.groupby("section_id").run_id.nunique().max() == 1, "every section has at most one pre-season run"
run_of = st.drop_duplicates("section_id").set_index("section_id").run_id
runs = run_of.groupby(run_of).apply(lambda s: list(s.index))
n_run = runs.map(len)
km = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet").set_index("section_id").silhouette_best_cluster_id.loc[ids]
assert km.nunique() == 310
n_km = km.value_counts()

# road miles between sections, for widths
d = pd.read_parquet(PROCESSED_DIR / "section_to_section_road_distance.parquet", columns=["from_section_id", "to_section_id", "road_mi"])
pos = {s: i for i, s in enumerate(ids)}
M = np.full((len(ids), len(ids)), np.nan)
M[d.from_section_id.map(pos).to_numpy(), d.to_section_id.map(pos).to_numpy()] = d.road_mi.to_numpy()
M = np.fmax(M, M.T)                                                                      # symmetric, farthest of the two directions


def width(secs):
    ix = [pos[s] for s in secs]
    return float(np.nanmax(M[np.ix_(ix, ix)])) if len(ix) > 1 else 0.0


run_w = runs[n_run >= 2].map(width)
km_w = pd.Series({c: width(list(g.index)) for c, g in km.groupby(km) if len(g) >= 2})

# how the two groupings relate
multi = runs[n_run >= 2]
whole = sum(km.loc[s].nunique() == 1 for s in multi)
pairs = same = 0
for c, g in km.groupby(km):
    for a, b in itertools.combinations(g.index, 2):
        pairs += 1
        same += int(a in run_of.index and b in run_of.index and run_of[a] == run_of[b])
stats = dict(runs=len(runs), multi=len(multi), single=int((n_run == 1).sum()), sec_in_multi=int(n_run[n_run >= 2].sum()), n_run_sections=int(n_run.sum()),
             run_med=float(n_run.median()), run_max=int(n_run.max()), run_width=float(run_w.median()), run_w90=float(run_w.quantile(.9)),
             km_clusters=len(n_km), km_med=float(n_km.median()), km_max=int(n_km.max()), km_width=float(km_w.median()),
             whole=int(whole), whole_pct=100 * whole / len(multi), pairs=pairs, same_pct=100 * same / pairs)
log.info("stats: %s", {k: round(v, 1) if isinstance(v, float) else v for k, v in stats.items()})

# %% Choose a patch: the window holding the most multi-section runs entirely inside it
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
sec = sec[sec.section_id.isin(ids)].set_index("section_id").loc[ids]
pt = sec.geometry.representative_point()
px, py = pt.x.to_numpy(), pt.y.to_numpy()
W, Hh = 0.95, 0.62
best = (-1, None)
for x0 in np.arange(-80.4, -75.2, 0.1):
    for y0 in np.arange(39.8, 41.9, 0.1):
        inside = (px >= x0) & (px <= x0 + W) & (py >= y0) & (py <= y0 + Hh)
        s_in = set(np.asarray(ids)[inside])
        score = sum(all(s in s_in for s in secs) for secs in multi if secs[0] in s_in)
        if score > best[0]:
            best = (score, (x0, y0))
x0, y0 = best[1]
log.info("patch: x %.2f..%.2f, y %.2f..%.2f holds %d multi-section runs", x0, x0 + W, y0, y0 + Hh, best[0])
sel = (px >= x0) & (px <= x0 + W) & (py >= y0) & (py <= y0 + Hh)
local = sec[sel].copy()
local["run"] = run_of.reindex(local.index)
local["km"] = km.reindex(local.index)
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")

# %% Draw
fig = plt.figure(figsize=(13.333, 7.5))
panels = [("What trucks actually did", "2026 pre-season runs: sections that shared one truck run", "run", 0.03),
          ("What the model treats as shared trucks", "k-medoids clusters: sections close by road", "km", 0.515)]
pw, ph = 0.455, 0.56
for head, sub, col, left in panels:
    ax = fig.add_axes([left, 0.20, pw, ph])
    sizes = local[col].map(local[col].value_counts())
    local[col].value_counts()
    grp = local[local[col].notna() & (sizes >= 2)]
    order = {g: i for i, g in enumerate(sorted(grp[col].unique(), key=lambda g: (grp[grp[col] == g].geometry.representative_point().x.mean())))}
    gm = grp.to_crs(26918)
    for g, i in order.items():
        c = PALETTE[i % len(PALETTE)]
        sub_g = grp[grp[col] == g]
        gpd.GeoSeries([gm[gm[col] == g].unary_union.convex_hull], crs=26918).to_crs(4326).plot(ax=ax, facecolor=c, edgecolor=c, alpha=0.16, lw=1.2, zorder=2)
        sub_g.plot(ax=ax, color=c, lw=3.4, zorder=4)
    alone = local[~local.index.isin(grp.index)]
    alone.plot(ax=ax, color=OTHER, lw=2.2, zorder=3)
    ax.set_xlim(x0, x0 + W)
    ax.set_ylim(y0, y0 + Hh)
    ax.set_aspect(1 / np.cos(np.radians(y0 + Hh / 2)))
    ax.set_xticks([])
    ax.set_yticks([])
    for s_ in ax.spines.values():
        s_.set_color("#d9d8d2")
    fig.text(left, 0.835, head, fontsize=17, fontweight="bold", ha="left")
    fig.text(left, 0.795, sub, fontsize=11, color=INK2, ha="left")
S = stats
fig.text(0.03, 0.155, f"{S['runs']} runs statewide. {S['multi']} of them ({100 * S['multi'] / S['runs']:.0f}%) served 2 or more sections;\n"
         f"a typical run served {S['run_med']:.0f}, at most {S['run_max']}, about {S['run_width']:.0f} road miles across.", fontsize=11.5, color=INK, ha="left", va="top", linespacing=1.4)
fig.text(0.515, 0.155, f"{S['km_clusters']} clusters statewide, a typical one with {S['km_med']:.0f} sections and at most {S['km_max']},\n"
         f"about {S['km_width']:.0f} road miles across. Grouped by closeness only, not by what a truck did.", fontsize=11.5, color=INK, ha="left", va="top", linespacing=1.4)
fig.text(0.5, 0.075, f"Only {S['whole_pct']:.0f}% of real multi-section runs stay whole inside one cluster, and only {S['same_pct']:.0f}% of cluster-mates actually rode the same pre-season truck.",
         fontsize=13, fontweight="bold", color="#a6192e", ha="center")
fig.text(0.5, 0.03, "Same patch of the state in both panels; colors only separate groups, grey = a section on its own. Pre-season runs (every section has at most one). "
         "Source: PFBC 2026 stocking schedule; k-medoids on OSRM road miles.", fontsize=8.5, color=INK2, ha="center")
out = FIG_DIR / "runs_vs_kmedoids.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
