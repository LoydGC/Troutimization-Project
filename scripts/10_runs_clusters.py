"""Group the 2026-stocked sections into stocking-run clusters and compute each section's detour miles.

A run is one truck meeting as PFBC lists it: date + hatchery + meeting place + time (stocking_events.run_id).
Two sections are linked when they share a run in at least cluster_share_min of the visits of the less-visited one:

    share(a, b) = runs holding both a and b / min(runs of a, runs of b)

counting dated events only (week-of-only events have no run). Clusters are the connected components of the links.
Sensitivity: a strict majority (share > 0.5, stored as the parameter's high value 0.51, which is the same thing for
fewer than 50 visits). Sections with no schedule record are singletons.

Detour (road miles = straight-line miles between PFBC's section midpoints x circuity_factor):
  detour_mi     to the nearest section in the same cluster; 0 for a singleton (detour_singleton flags it)
  detour_nn_mi  to the nearest 2026-stocked section of any cluster (geographic-only fallback, for comparison)

Inputs : data/processed/stocking_events.parquet (09), sections.parquet, parameters.csv
Outputs: data/processed/section_schedule.{parquet,csv}  one row per 2026-stocked section (1,022)
         data/processed/clusters.csv                    one row per cluster (default rule)
         logs/10_runs_clusters.log

    .venv/bin/python scripts/10_runs_clusters.py      (run after 09)
"""
from __future__ import annotations

import itertools
import logging

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, minimum_spanning_tree
from scipy.spatial.distance import cdist

from common import PROCESSED_DIR, setup_logging

M_PER_MI = 1609.344
BEAR = ["3197_2", "3197_3"]

log = logging.getLogger(__name__)


def param(name: str, col: str = "value") -> float:
    p = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter")
    return float(p.loc[name, col])


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    sections = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    sec = sections[sections.total_2026.fillna(0) > 0].set_index("section_id").sort_index()
    ev = pd.read_parquet(PROCESSED_DIR / "stocking_events.parquet")
    stream = ev[ev.section_id.notna()]
    ev = stream[stream.section_id.isin(sec.index)]
    log.info("stream events on 2026-stocked sections: %d of %d matched stream events (%d on sections not stocked "
             "in 2026)", len(ev), len(stream), len(stream) - len(ev))
    return sec, ev


def hatcheries(sec: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    """Scheduled hatchery per section: primary = most events (ties go alphabetically, and are logged)."""
    counts = ev.groupby(["section_id", "hatchery"]).size().rename("n").reset_index()
    counts = counts.sort_values(["section_id", "n", "hatchery"], ascending=[True, False, True])
    top = counts.groupby("section_id").head(2)
    ties = top.groupby("section_id").n.agg(lambda n: len(n) == 2 and n.iloc[0] == n.iloc[1])
    log.info("sections whose top two hatcheries tie on events (primary = alphabetical): %d %s", ties.sum(),
             ties.index[ties].tolist())
    first = counts.drop_duplicates("section_id").set_index("section_id")
    out = pd.DataFrame(index=sec.index)
    out["n_events"] = ev.groupby("section_id").size().reindex(out.index).fillna(0).astype(int)
    out["n_runs"] = ev.groupby("section_id").run_id.nunique().reindex(out.index).fillna(0).astype(int)
    out["primary_hatchery"] = first.hatchery
    out["primary_hatchery_share"] = (first.n / out.n_events.where(out.n_events > 0)).round(3)
    n_hatch = counts.groupby("section_id").size().reindex(out.index).fillna(0)
    out["multi_hatchery"] = n_hatch > 1
    out["hatcheries"] = counts.groupby("section_id").hatchery.agg(", ".join)
    log.info("sections with events: %d; more than one hatchery: %d; primary hatchery counts: %s",
             (out.n_events > 0).sum(), out.multi_hatchery.sum(), out.primary_hatchery.value_counts().to_dict())
    return out


def pair_shares(ev: pd.DataFrame) -> pd.DataFrame:
    """Every pair of sections sharing at least one run, with share = shared runs / min(runs of each)."""
    runs = ev.dropna(subset=["run_id"]).groupby("run_id").section_id.agg(lambda s: sorted(set(s)))
    visits = ev.dropna(subset=["run_id"]).groupby("section_id").run_id.nunique()
    n = {}
    for members in runs:
        for a, b in itertools.combinations(members, 2):
            n[(a, b)] = n.get((a, b), 0) + 1
    p = pd.DataFrame([(a, b, k) for (a, b), k in n.items()], columns=["a", "b", "n_shared"])
    p["share"] = p.n_shared / np.minimum(p.a.map(visits), p.b.map(visits))
    log.info("runs: %d (sections per run: %s); co-run pairs: %d; share distribution: %s", len(runs),
             runs.str.len().value_counts().sort_index().to_dict(), len(p),
             p.share.round(2).value_counts().sort_index().to_dict())
    return p


def components(ids: pd.Index, pairs: pd.DataFrame, share_min: float) -> pd.Series:
    """cluster_id per section: connected components of the pairs with share >= share_min, largest first."""
    pos = pd.Series(np.arange(len(ids)), index=ids)
    e = pairs[pairs.share >= share_min]
    adj = coo_matrix((np.ones(len(e)), (pos[e.a].values, pos[e.b].values)), shape=(len(ids), len(ids)))
    _, comp = connected_components(adj, directed=False)
    comp = pd.Series(comp, index=ids)
    size = comp.map(comp.value_counts())
    order = (pd.DataFrame({"comp": comp, "size": size, "sid": ids}).groupby("comp").agg(size=("size", "first"),
             first=("sid", "min")).sort_values(["size", "first"], ascending=[False, True]))
    label = pd.Series([f"C{i + 1:04d}" for i in range(len(order))], index=order.index)
    return comp.map(label)


def detours(cluster: pd.Series, dist_mi: np.ndarray) -> pd.Series:
    c = cluster.to_numpy(dtype=object)
    same = c[:, None] == c[None, :]
    d = np.where(same, dist_mi, np.inf)
    np.fill_diagonal(d, np.inf)
    near = d.min(axis=1)
    return pd.Series(np.where(np.isfinite(near), near, 0.0), index=cluster.index).round(2)


def cluster_table(out: pd.DataFrame, ev: pd.DataFrame, xy: np.ndarray, circ: float, span_check: float) -> pd.DataFrame:
    rows = []
    pos = pd.Series(np.arange(len(out)), index=out.index)
    to_ll = Transformer.from_crs("EPSG:26918", "EPSG:4326", always_xy=True)
    for cid, g in out.groupby("cluster_id"):
        i = pos[g.index].values
        d = cdist(xy[i], xy[i])
        mst = minimum_spanning_tree(d + 1e-6 * (d == 0) * (1 - np.eye(len(i)))).sum() if len(i) > 1 else 0.0
        lon, lat = to_ll.transform(*xy[i].mean(axis=0))
        e = ev[ev.section_id.isin(g.index)]
        rows.append({"cluster_id": cid, "cluster_source": g.cluster_source.iloc[0], "n_sections": len(g),
                     "section_ids": ", ".join(g.index), "centroid_lat": round(lat, 5), "centroid_lon": round(lon, 5),
                     "cluster_mi": round(mst * circ / M_PER_MI, 2), "span_mi": round(d.max() * circ / M_PER_MI, 2),
                     "hatcheries": ", ".join(e.hatchery.value_counts().index), "n_runs": e.run_id.nunique(),
                     "n_events": len(e)})
    t = pd.DataFrame(rows)
    t["span_flag"] = t.span_mi > span_check
    return t


def main() -> None:
    setup_logging("10_runs_clusters")
    circ = param("circuity_factor")
    share_min, share_strict = param("cluster_share_min"), param("cluster_share_min", "high")
    span_check = param("cluster_span_check_mi")
    sec, ev = load()
    out = hatcheries(sec, ev)
    pairs = pair_shares(ev)
    log.info("pairs at exactly 0.5: %d; at >= %.2f: %d; at >= %.2f (strict): %d", (pairs.share == 0.5).sum(),
             share_min, (pairs.share >= share_min).sum(), share_strict, (pairs.share >= share_strict).sum())

    to_xy = Transformer.from_crs("EPSG:4326", "EPSG:26918", always_xy=True)
    xy = np.column_stack(to_xy.transform(sec.mid_lon.values, sec.mid_lat.values))
    dist_mi = cdist(xy, xy) / M_PER_MI * circ
    for suffix, threshold in (("", share_min), ("_strict", share_strict)):
        out[f"cluster_id{suffix}"] = components(out.index, pairs, threshold)
        out[f"cluster_size{suffix}"] = out[f"cluster_id{suffix}"].map(out[f"cluster_id{suffix}"].value_counts())
        out[f"detour_mi{suffix}"] = detours(out[f"cluster_id{suffix}"], dist_mi)
        sizes = out.drop_duplicates(f"cluster_id{suffix}")[f"cluster_size{suffix}"].value_counts().sort_index()
        log.info("clusters (share >= %.2f): %d; size distribution %s; singletons %d", threshold,
                 out[f"cluster_id{suffix}"].nunique(), sizes.to_dict(), sizes.get(1, 0))
    out["cluster_source"] = np.where(out.n_events > 0, "schedule", "no_schedule_singleton")
    out["detour_singleton"] = out.cluster_size == 1
    nn = dist_mi.copy()
    np.fill_diagonal(nn, np.inf)
    out["detour_nn_mi"] = nn.min(axis=1).round(2)
    log.info("singletons: %s", out[out.detour_singleton].cluster_source.value_counts().to_dict())
    log.info("detour_mi (non-singletons) median %.1f, 90%% %.1f, max %.1f; detour_nn_mi median %.1f, 90%% %.1f, "
             "max %.1f", *out.detour_mi[~out.detour_singleton].quantile([0.5, 0.9, 1]),
             *out.detour_nn_mi.quantile([0.5, 0.9, 1]))

    cols = ["n_events", "n_runs", "primary_hatchery", "primary_hatchery_share", "multi_hatchery", "hatcheries",
            "cluster_id", "cluster_source", "cluster_size", "detour_mi", "detour_singleton", "detour_nn_mi",
            "cluster_id_strict", "cluster_size_strict", "detour_mi_strict"]
    res = out[cols].reset_index()
    assert len(res) == 1022 and res.section_id.is_unique
    res.to_parquet(PROCESSED_DIR / "section_schedule.parquet", index=False)
    res.to_csv(PROCESSED_DIR / "section_schedule.csv", index=False)

    t = cluster_table(out, ev, xy, circ, span_check)
    assert t.n_sections.sum() == len(res)
    t.to_csv(PROCESSED_DIR / "clusters.csv", index=False)
    wide = t[t.span_flag]
    log.info("clusters spanning > %.0f road-mi: %d %s", span_check, len(wide),
             wide[["cluster_id", "n_sections", "span_mi", "hatcheries", "section_ids"]].values.tolist())
    log.info("largest span: %s", t.nlargest(3, "span_mi")[["cluster_id", "n_sections", "span_mi", "cluster_mi",
                                                             "hatcheries"]].values.tolist())
    log.info("cluster_mi (multi-section clusters): median %.1f, max %.1f",
             t.cluster_mi[t.n_sections > 1].median(), t.cluster_mi.max())

    # hand check: Bear Creek (CLAUDE.md Known facts) and its nearest stocked neighbours
    pos = pd.Series(np.arange(len(out)), index=out.index)
    for sid in BEAR:
        near = pd.Series(nn[pos[sid]], index=out.index).nsmallest(5)
        log.info("%s: cluster %s (members %s), detour_mi %.2f, detour_nn_mi %.2f, runs %s; nearest: %s", sid,
                 out.at[sid, "cluster_id"], out.index[out.cluster_id == out.at[sid, "cluster_id"]].tolist(),
                 out.at[sid, "detour_mi"],
                 out.at[sid, "detour_nn_mi"], sorted(ev.loc[ev.section_id == sid, "run_id"].dropna()),
                 [(n, round(d, 1), out.at[n, "cluster_id"]) for n, d in near.items()])
    assert out.at[BEAR[0], "cluster_id"] == out.at[BEAR[1], "cluster_id"], "Bear Creek 02-03 share every run"


if __name__ == "__main__":
    main()
