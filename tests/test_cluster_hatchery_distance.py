"""cluster_hatchery_distance is the plain unweighted average of its members' road miles from each hatchery (scripts/18_cluster_hatchery_distance.py)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

P = Path(__file__).resolve().parents[1] / "data" / "processed"
LABELS = {
    "nate_schedule": ("section_schedule", "cluster_id"),
    "kmedoids_best_silhouette": ("section_medoid_clusters", "silhouette_best_cluster_id"),
    "kmedoids_limits": ("section_medoid_clusters", "medoid_cluster_id"),
    "hierarchical_best_silhouette": ("section_hierarchical_clusters", "silhouette_best_cluster_id"),
    "hierarchical_limits": ("section_hierarchical_clusters", "limits_cluster_id"),
}


@pytest.fixture(scope="module")
def table():
    return pd.read_parquet(P / "cluster_hatchery_distance.parquet")


@pytest.fixture(scope="module")
def ids():
    return pd.read_parquet(P / "section_schedule.parquet")["section_id"].tolist()


@pytest.fixture(scope="module")
def road(ids):
    d = pd.read_parquet(P / "hatchery_to_section_road_distance.parquet")
    return d[d.section_id.isin(ids)].pivot_table(index="section_id", columns="hatchery", values="road_mi")


def labelling(method):
    name, col = LABELS[method]
    return pd.read_parquet(P / f"{name}.parquet").set_index("section_id")[col]


def test_one_row_per_method_cluster_and_hatchery(table):
    expected = {"nate_schedule": 351, "kmedoids_best_silhouette": 310, "kmedoids_limits": 407, "hierarchical_best_silhouette": 309, "hierarchical_limits": 375}
    for method, k in expected.items():
        t = table[table.method == method]
        assert t.cluster_id.nunique() == k and len(t) == k * 13, f"{method}: {k} clusters x 13 hatcheries (docs/clustering_options.md)"
        assert not t.duplicated(["cluster_id", "hatchery"]).any()


def test_average_equals_the_plain_mean_of_the_members(table, road):
    rng = np.random.default_rng(0)
    for method in LABELS:
        lab = labelling(method)
        t = table[table.method == method]
        for _ in range(40):
            row = t.iloc[int(rng.integers(len(t)))]
            members = lab[lab == row.cluster_id].index
            assert len(members) == row.n_sections
            assert row.avg_road_mi == pytest.approx(road.loc[members, row.hatchery].mean(), abs=6e-4)
            assert row.min_road_mi == pytest.approx(road.loc[members, row.hatchery].min(), abs=6e-4)
            assert row.max_road_mi == pytest.approx(road.loc[members, row.hatchery].max(), abs=6e-4)


def test_size_weighted_average_of_clusters_equals_the_all_section_mean(table, road, ids):
    for method in LABELS:
        t = table[table.method == method]
        agg = (t.avg_road_mi * t.n_sections).groupby(t.hatchery).sum() / len(ids)
        assert np.allclose(agg.reindex(road.columns), road.mean(axis=0), atol=2e-3), method


def test_a_section_alone_has_its_own_distance(table, road):
    lab = labelling("nate_schedule")
    alone = lab[lab.map(lab.value_counts()) == 1].index[:25]
    t = table[table.method == "nate_schedule"].set_index(["cluster_id", "hatchery"])
    for sid in alone:
        for h in ("Bellefonte", "Corry", "Tylersville"):
            assert t.loc[(lab[sid], h), "avg_road_mi"] == pytest.approx(road.loc[sid, h], abs=6e-4)
