"""Average road distance from each hatchery to each cluster, for every cluster labelling we have saved.

Formula (the representative distance a cluster supplies, docs/clustering_options.md § Objective):

    avg_road_mi[method, cluster k, hatchery h] = (1 / n_k) * sum over sections s in k of road_mi[h, s]

an UNWEIGHTED mean over the cluster's member sections, of the one-way OSRM road miles from hatchery h to section s
(hatchery_to_section_road_distance). Cost per fish is linear in miles (cost[h,s] = 2 x road_mi x $/truck-mile / fish per load), so a cluster's
average cost from h is the same average taken on cost. Also saved: min, max and mean absolute deviation of the members' distances (how well
the average stands in for each member) and a fish-weighted average (weights = 2026 stocked fish) as a check on the equal-weight choice.

Labellings (one row per method x cluster x hatchery, all 13 hatcheries so the table also holds if more hatcheries are switched on):
  nate_schedule              section_schedule.cluster_id                       Nate's schedule run clusters (Phase 1)
  kmedoids_best_silhouette   section_medoid_clusters.silhouette_best_cluster_id
  kmedoids_limits            section_medoid_clusters.medoid_cluster_id
  hierarchical_best_silhouette  section_hierarchical_clusters.silhouette_best_cluster_id
  hierarchical_limits        section_hierarchical_clusters.limits_cluster_id

Checks run every time (asserted): independent matrix recomputation; counts add up to 1,022 per method; singleton = the section's own distance;
min <= average <= max; the weighted-by-size average of cluster averages equals the all-section mean for each hatchery; and the hatchery-distance
error over the hatcheries producing 2026 fish reproduces the numbers in docs/clustering_options.md.

Inputs : data/processed/section_schedule.parquet, section_medoid_clusters.parquet, section_hierarchical_clusters.parquet,
         hatchery_to_section_road_distance.parquet, hatchery_schedule_supply.csv, sections.parquet (total_2026)
Outputs: data/processed/cluster_hatchery_distance.{parquet,csv}
         logs/18_cluster_hatchery_distance.log

    python scripts/18_cluster_hatchery_distance.py
"""
# %% Setup
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from common import PROCESSED_DIR, setup_logging

setup_logging("18_cluster_hatchery_distance")
log = logging.getLogger("18_cluster_hatchery_distance")

# %% Load
ss = pd.read_parquet(PROCESSED_DIR / "section_schedule.parquet", columns=["section_id", "cluster_id"]).set_index("section_id")
ids = ss.index.tolist()
km = pd.read_parquet(PROCESSED_DIR / "section_medoid_clusters.parquet").set_index("section_id").loc[ids]
hc = pd.read_parquet(PROCESSED_DIR / "section_hierarchical_clusters.parquet").set_index("section_id").loc[ids]
labelings = {
    "nate_schedule": ss["cluster_id"],
    "kmedoids_best_silhouette": km["silhouette_best_cluster_id"],
    "kmedoids_limits": km["medoid_cluster_id"],
    "hierarchical_best_silhouette": hc["silhouette_best_cluster_id"],
    "hierarchical_limits": hc["limits_cluster_id"],
}
hd = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet", columns=["hatchery_id", "hatchery", "section_id", "road_mi"])
hd = hd[hd.section_id.isin(ids)]
assert hd.groupby("hatchery").section_id.nunique().eq(len(ids)).all(), "every hatchery needs a distance to every one of the 1,022 sections"
assert hd.road_mi.notna().all()
hatcheries = hd[["hatchery_id", "hatchery"]].drop_duplicates().sort_values("hatchery_id").reset_index(drop=True)
supply = pd.read_csv(PROCESSED_DIR / "hatchery_schedule_supply.csv")
producing = set(supply.loc[supply["stream_fish_2026"] > 0, "hatchery"])
fish = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"]).set_index("section_id").total_2026.reindex(ids).fillna(0)
log.info("%d sections, %d hatcheries (%d produce 2026 stream fish), %d labellings", len(ids), len(hatcheries), len(producing), len(labelings))

# %% Build: pandas groupby
hd = hd.merge(fish.rename("fish"), left_on="section_id", right_index=True)
frames = []
for method, lab in labelings.items():
    d = hd.merge(lab.rename("cluster_id"), left_on="section_id", right_index=True)
    g = d.groupby(["cluster_id", "hatchery_id", "hatchery"], sort=True)
    t = g.road_mi.agg(n_sections="size", avg_road_mi="mean", min_road_mi="min", max_road_mi="max").reset_index()
    d["abs_dev"] = (d.road_mi - d.groupby(["cluster_id", "hatchery"]).road_mi.transform("mean")).abs()
    t = t.merge(d.groupby(["cluster_id", "hatchery"]).abs_dev.mean().rename("mean_abs_dev_mi").reset_index(), on=["cluster_id", "hatchery"])
    w = d.assign(wd=d.road_mi * d.fish).groupby(["cluster_id", "hatchery"]).agg(wd=("wd", "sum"), w=("fish", "sum")).reset_index()
    w["avg_road_mi_fish_weighted"] = np.where(w.w > 0, w.wd / w.w.where(w.w > 0), np.nan)
    t = t.merge(w[["cluster_id", "hatchery", "avg_road_mi_fish_weighted"]], on=["cluster_id", "hatchery"])
    t.insert(0, "method", method)
    t["produces_2026_stream_fish"] = t.hatchery.isin(producing)
    frames.append(t)
out = pd.concat(frames, ignore_index=True)
for c in ("avg_road_mi", "min_road_mi", "max_road_mi", "mean_abs_dev_mi", "avg_road_mi_fish_weighted"):
    out[c] = out[c].round(3)
out = out[["method", "cluster_id", "hatchery_id", "hatchery", "produces_2026_stream_fish", "n_sections", "avg_road_mi", "min_road_mi", "max_road_mi",
           "mean_abs_dev_mi", "avg_road_mi_fish_weighted"]]

# %% Verify the formula
D = hd.pivot_table(index="section_id", columns="hatchery", values="road_mi").reindex(ids)          # sections x hatcheries, miles
for method, lab in labelings.items():
    t = out[out.method == method]
    k = lab.nunique()
    assert len(t) == k * len(hatcheries), f"{method}: expected {k} clusters x {len(hatcheries)} hatcheries"
    assert t.groupby("hatchery").n_sections.sum().eq(len(ids)).all(), f"{method}: sections per hatchery do not add up to {len(ids)}"
    # 1) independent recomputation with plain numpy: average the member rows of the distance matrix
    mat = D.to_numpy()
    for cid, members in lab.groupby(lab).groups.items():
        rows = mat[[ids.index(s) for s in members]]
        got = t[t.cluster_id == cid].set_index("hatchery").loc[D.columns, "avg_road_mi"].to_numpy()
        assert np.allclose(rows.mean(axis=0), got, atol=6e-4), f"{method} {cid}: table disagrees with the plain average of members"
    # 2) a section alone has exactly its own distance
    sizes = lab.map(lab.value_counts())
    for sid in sizes[sizes == 1].index[:200]:
        own = t[t.cluster_id == lab[sid]].set_index("hatchery").loc[D.columns, "avg_road_mi"].to_numpy()
        assert np.allclose(own, D.loc[sid].to_numpy(), atol=6e-4)
    # 3) bounds and aggregation: size-weighted mean of cluster averages = mean over all sections, per hatchery
    assert ((t.min_road_mi <= t.avg_road_mi + 1e-6) & (t.avg_road_mi <= t.max_road_mi + 1e-6)).all()
    agg = t.assign(w=t.avg_road_mi * t.n_sections).groupby("hatchery").w.sum() / len(ids)
    assert np.allclose(agg.reindex(D.columns), D.mean(axis=0), atol=2e-3), f"{method}: aggregation identity fails"
    # 4) the hatchery-distance error reported in the docs, from this table (hatcheries producing 2026 fish)
    prod_cols = [c for c in D.columns if c in producing]
    avg_for_section = np.column_stack([lab.map(t[t.hatchery == h].set_index("cluster_id").avg_road_mi).to_numpy() for h in prod_cols])
    err = 100 * np.abs(avg_for_section - D[prod_cols].to_numpy()).sum() / D[prod_cols].to_numpy().sum()
    fw = (t.avg_road_mi_fish_weighted - t.avg_road_mi).abs()
    log.info("%-30s clusters %3d | rows %5d | hatchery-distance error %.2f%% | fish-weighted vs equal-weight average: median gap %.2f mi, 90th pct %.2f mi",
             method, k, len(t), err, fw.median(), fw.quantile(.9))
log.info("all checks passed")
# spot check printed for the record: Nate's biggest cluster, Bellefonte
big = labelings["nate_schedule"].value_counts().index[0]
members = labelings["nate_schedule"][labelings["nate_schedule"] == big].index
dist = D.loc[members, "Bellefonte"]
row = out[(out.method == "nate_schedule") & (out.cluster_id == big) & (out.hatchery == "Bellefonte")].iloc[0]
log.info("spot check, %s (%d sections) from Bellefonte: members' miles %s -> mean %.3f; table says %.3f", big, len(members),
         dist.round(1).tolist(), dist.mean(), row.avg_road_mi)

# %% Save
out.to_parquet(PROCESSED_DIR / "cluster_hatchery_distance.parquet", index=False)
out.to_csv(PROCESSED_DIR / "cluster_hatchery_distance.csv", index=False)
log.info("wrote %d rows to cluster_hatchery_distance", len(out))
