"""Transport cost inputs (Prompt 7): supply nodes, the hatchery x section cost matrix, and PFBC's 2026 baseline flows.

Follows docs/model_design.md § Transport cost. Distances are Gavin's (scripts 11, 13, 15, 18); this script only joins them.
- Supply nodes (decision 2026-09-29): PFBC's State Fish Hatcheries layer (13). The base model uses the 9 with 2026 stream
  fish in the schedule (in_2026_schedule); supply = each one's 2026 stream fish from the schedule, which names the
  hatchery for every event (decision 2026-09-28). Production pounds are not used (decision 2026-10-04).
- Haul miles (decision 2026-10-04): each section is costed at its cluster's mean road miles from the hatchery, using
  Gavin's k-medoids clusters (best silhouette, 310). Nate's schedule clusters, Gavin's hierarchical clusters and each
  section's own road miles are kept as sensitivity columns. A cluster is a cost, not a trip; no detour charge.
- cost_per_fish = 2 x cluster_road_mi x cost_per_truck_mile / fish_per_load (parameters.csv): the per-fish cost, kept for the linear
  baseline and as a sensitivity. The model counts truck trips from cluster_road_mi instead (scripts/optimization.py).
- Baseline flows: PFBC's 2026 schedule names the hatchery for every event; each section's 2026 fish are split over its
  events by species (stocking_events.alloc_fish, script 09). The nearest-hatchery assignment is the sensitivity.

Inputs : data/interim/pfbc_gis/hatcheries.parquet (01), sections.parquet (02-04), hatchery_schedule_supply.csv and
         stocking_events.parquet (09), hatchery_to_section_road_distance.parquet (11), section_medoid_clusters (13),
         section_hierarchical_clusters (15), section_schedule (10), cluster_hatchery_distance.parquet (18), parameters.csv
Outputs: data/processed/hatcheries.{parquet,csv}       one row per state fish hatchery (13)
         data/processed/cost_matrix.{parquet,csv}      one row per hatchery x 2026-stocked section (13 x 1,022)
         data/processed/baseline_flows.{parquet,csv}   PFBC's 2026 fish by section x scheduled hatchery
         logs/20_transport_cost.log                    baseline cost, loads vs supply, fleet-miles check

    .venv/bin/python scripts/20_transport_cost.py      (run after 09, 10 and Gavin's 11-18)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from common import INTERIM_DIR, PROCESSED_DIR, setup_logging

# cluster labelling -> (cluster_hatchery_distance.method, table with the section's label, its column)
CLUSTERINGS = {
    "kmedoids": ("kmedoids_best_silhouette", "section_medoid_clusters.parquet", "silhouette_best_cluster_id"),
    "schedule": ("nate_schedule", "section_schedule.parquet", "cluster_id"),
    "hierarchical": ("hierarchical_best_silhouette", "section_hierarchical_clusters.parquet", "silhouette_best_cluster_id"),
}
BASE_CLUSTERING = "kmedoids"  # decision 2026-10-04

log = logging.getLogger(__name__)


def param(name: str) -> float:
    p = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter")
    return float(p.loc[name, "value"])


def candidates() -> pd.DataFrame:
    s = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    s = s[s.total_2026.fillna(0).gt(0)].reset_index(drop=True)
    assert len(s) == 1022
    return s


# ---------------------------------------------------------------- supply nodes
def hatcheries() -> pd.DataFrame:
    layer = pd.read_parquet(INTERIM_DIR / "pfbc_gis" / "hatcheries.parquet")
    h = pd.DataFrame({
        "hatchery_id": layer.ID.astype(int), "hatchery": layer.NAME.str.strip(),
        "full_name": layer.FULL_NAME.str.strip(), "county": layer.COUNTY.str.strip(),
        "region": layer.REGION.str.strip(), "lat": layer.Lat, "lon": layer.Long_,
        "trout_flag": layer.TROUT.str.strip().str.lower().eq("y"),
    })
    sup = pd.read_csv(PROCESSED_DIR / "hatchery_schedule_supply.csv")
    unknown = set(sup.hatchery) - set(h.hatchery)
    assert not unknown, f"schedule hatcheries not in the layer: {unknown}"
    h = h.merge(sup[["hatchery", "stream_fish_2026"]], on="hatchery", how="left")
    log.info("hatcheries: %d in PFBC's layer; %d in the schedule's supply table; not in it (no 2026 events): %s",
             len(h), len(sup), sorted(set(h.hatchery) - set(sup.hatchery)))
    # hatcheries the 2026 schedule lists no stream events for supply 0 stream fish in 2026
    h["supply"] = h.stream_fish_2026.fillna(0).astype(int)
    h["in_2026_schedule"] = h.supply.gt(0)
    h = h.drop(columns=["stream_fish_2026"]).sort_values("hatchery_id").reset_index(drop=True)
    log.info("supply: %d hatcheries with 2026 stream fish, %s fish (the model's total T); by hatchery %s",
             h.in_2026_schedule.sum(), f"{h.supply.sum():,}", h.set_index("hatchery").supply[h.in_2026_schedule.to_numpy()].to_dict())
    return h


# ---------------------------------------------------------------- cost matrix
def cluster_miles(road: pd.DataFrame, s: pd.DataFrame, key: str) -> pd.Series:
    """Each (hatchery, section)'s cluster-average road miles under one labelling (Gavin's table), checked against a
    recomputation from the section road miles."""
    method, table, col = CLUSTERINGS[key]
    lab = pd.read_parquet(PROCESSED_DIR / table)[["section_id", col]].rename(columns={col: "cluster_id"})
    lab = lab[lab.section_id.isin(s.section_id)]
    assert set(lab.section_id) == set(s.section_id) and lab.cluster_id.notna().all(), f"{key}: a section has no cluster"
    c = pd.read_parquet(PROCESSED_DIR / "cluster_hatchery_distance.parquet")
    c = c.loc[c.method == method, ["cluster_id", "hatchery_id", "avg_road_mi"]]
    m = road.merge(lab, on="section_id").merge(c, on=["cluster_id", "hatchery_id"], how="left")
    assert m.avg_road_mi.notna().all(), f"{key}: missing cluster distances"
    check = m.groupby(["cluster_id", "hatchery_id"]).road_mi.transform("mean")
    assert np.allclose(check, m.avg_road_mi, atol=0.01), f"{key}: cluster averages don't reproduce"
    err = (m.avg_road_mi - m.road_mi).abs()
    log.info("%s clusters (%s): %d clusters; cluster average vs own road miles: mean |gap| %.1f mi, p90 %.1f, max %.1f",
             key, method, lab.cluster_id.nunique(), err.mean(), err.quantile(0.9), err.max())
    return m.set_index(["hatchery_id", "section_id"]).avg_road_mi.rename(f"cluster_road_mi_{key}"), lab


def cost_matrix(h: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    road = pd.read_parquet(PROCESSED_DIR / "hatchery_to_section_road_distance.parquet",
                           columns=["hatchery_id", "section_id", "road_mi"])
    n = len(road)
    road = road[road.section_id.isin(s.section_id)]
    assert len(road) == len(h) * len(s) and road.road_mi.notna().all(), "every hatchery x section needs a road distance"
    log.info("road distances: %d hatchery x section pairs; kept %d to the %d sections stocked in 2026", n, len(road), len(s))
    cm = road.set_index(["hatchery_id", "section_id"])
    for key in CLUSTERINGS:
        miles, lab = cluster_miles(road, s, key)
        cm = cm.join(miles)
        if key == BASE_CLUSTERING:
            cm = cm.join(lab.set_index("section_id").cluster_id, on="section_id")
    cm = cm.reset_index()
    cm["cluster_road_mi"] = cm[f"cluster_road_mi_{BASE_CLUSTERING}"]
    per_fish_mi = 2 * param("cost_per_truck_mile") / param("fish_per_load")
    cm["cost_per_fish"] = cm.cluster_road_mi * per_fish_mi
    log.info("cost per fish = 2 x cluster_road_mi x $%.2f / %d fish = $%.5f per fish per one-way mile",
             param("cost_per_truck_mile"), param("fish_per_load"), per_fish_mi)
    cm = cm.merge(h[["hatchery_id", "hatchery", "in_2026_schedule"]], on="hatchery_id")
    cols = ["hatchery_id", "hatchery", "in_2026_schedule", "section_id", "cluster_id", "road_mi", "cluster_road_mi",
            "cost_per_fish", "cluster_road_mi_kmedoids", "cluster_road_mi_schedule", "cluster_road_mi_hierarchical"]
    cm = cm[cols].sort_values(["hatchery_id", "section_id"]).reset_index(drop=True)
    cm = cm.drop(columns="cluster_road_mi_kmedoids")  # same as cluster_road_mi
    return cm


# ---------------------------------------------------------------- baseline
def baseline_flows(h: pd.DataFrame, s: pd.DataFrame, cm: pd.DataFrame) -> pd.DataFrame:
    e = pd.read_parquet(PROCESSED_DIR / "stocking_events.parquet")
    st = e[e.water_type.eq("stream")]
    out_of_set = st[~st.section_id.isin(s.section_id)]
    log.info("schedule stream events: %d; %d are on sections with no 2026 count or unmatched (%s fish), left out",
             len(st), len(out_of_set), out_of_set.alloc_fish.fillna(0).sum())
    st = st[st.section_id.isin(s.section_id)]
    x0 = st.groupby(["section_id", "hatchery"], as_index=False).alloc_fish.sum().rename(columns={"alloc_fish": "fish"})
    x0 = x0.merge(h[["hatchery", "hatchery_id"]], on="hatchery", how="left")
    assert x0.hatchery_id.notna().all()
    per_section = x0.groupby("section_id").fish.sum().reindex(s.section_id)
    gap = per_section.to_numpy(dtype=float) - s.total_2026.to_numpy(dtype=float)
    assert np.abs(gap).max() < 1, "flows != 2026 counts"  # species splits over events leave fractions of a fish
    log.info("baseline flows vs 2026 counts: largest gap %.2f fish, total %.2f", np.abs(gap).max(), gap.sum())
    x0 = x0.merge(cm[["hatchery_id", "section_id", "road_mi", "cluster_road_mi", "cost_per_fish"]],
                  on=["hatchery_id", "section_id"], how="left")
    x0["cost"] = x0.fish * x0.cost_per_fish
    log.info("baseline flows: %d section x hatchery pairs on %d sections (%d get fish from 2 hatcheries), %s fish",
             len(x0), x0.section_id.nunique(), x0.section_id.duplicated().sum(), f"{x0.fish.sum():,.1f}")
    return x0[["section_id", "hatchery_id", "hatchery", "fish", "road_mi", "cluster_road_mi", "cost_per_fish", "cost"]]


def baseline_report(h: pd.DataFrame, s: pd.DataFrame, cm: pd.DataFrame, x0: pd.DataFrame) -> None:
    F, g = param("fish_per_load"), param("cost_per_truck_mile")
    load = x0.groupby("hatchery").fish.sum()
    sup = h.set_index("hatchery").supply
    cmp = pd.DataFrame({"baseline_load": load.round(1), "supply": sup[load.index]})
    cmp["load_minus_supply"] = (cmp.baseline_load - cmp.supply).round(1)
    log.info("scheduled baseline: each hatchery's load vs supply (differences are rounding in the supply table):\n%s",
             cmp.to_string())

    def score(flows: pd.DataFrame, miles: str) -> tuple[float, float]:
        truck_mi = (2 * flows[miles] * flows.fish / F).sum()
        return truck_mi * g, truck_mi

    rows = {}
    for miles in ["cluster_road_mi", "road_mi"]:
        rows[f"scheduled, {miles}"] = score(x0, miles)
    # nearest of the 9 producing hatcheries, by the same miles, ignoring supply
    live = cm[cm.in_2026_schedule]
    fish = s.set_index("section_id").total_2026.astype(float)
    for miles in ["cluster_road_mi", "road_mi"]:
        near = live.loc[live.groupby("section_id")[miles].idxmin()].copy()
        near["fish"] = near.section_id.map(fish)
        rows[f"nearest, {miles}"] = score(near, miles)
        if miles == "cluster_road_mi":
            nl = near.groupby("hatchery").fish.sum().reindex(sup[h.in_2026_schedule.to_numpy()].index).fillna(0)
            log.info("nearest-hatchery baseline (cluster miles): load / supply by hatchery %s (not supply-feasible)",
                     (nl / sup[nl.index]).round(2).to_dict())
            same = x0.merge(near[["section_id", "hatchery"]], on="section_id", suffixes=("", "_nearest"))
            log.info("sections whose scheduled hatchery is their nearest (cluster miles): %d of %d (fish-weighted %.0f%%)",
                     same.loc[same.hatchery == same.hatchery_nearest, "section_id"].nunique(), len(s),
                     100 * same.loc[same.hatchery == same.hatchery_nearest, "fish"].sum() / same.fish.sum())
    t = pd.DataFrame(rows, index=["cost_usd", "truck_miles"]).T
    t["mean_haul_mi"] = t.truck_miles * F / 2 / fish.sum()
    log.info("baseline transport cost per year (2 x miles x $%.2f / %d fish per load):\n%s", g, F,
             t.round(0).to_string())
    tm = t.loc["scheduled, cluster_road_mi", "truck_miles"]
    fleet = param("fleet_miles_per_year")
    log.info("fleet-miles check: the scheduled baseline implies %s stream truck-miles at %d fish per load vs ~%s "
             "reported (all trips); matching it would take %.0f fish per load", f"{tm:,.0f}", F, f"{fleet:,.0f}",
             F * tm / fleet)


def main() -> None:
    setup_logging("20_transport_cost")
    s = candidates()
    h = hatcheries()
    cm = cost_matrix(h, s)
    x0 = baseline_flows(h, s, cm)
    baseline_report(h, s, cm, x0)
    for name, df in [("hatcheries", h), ("cost_matrix", cm), ("baseline_flows", x0)]:
        df.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
        df.round(5).to_csv(PROCESSED_DIR / f"{name}.csv", index=False)
        log.info("%s: %d rows, columns %s", name, len(df), list(df.columns))


if __name__ == "__main__":
    main()
