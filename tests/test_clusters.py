"""Facts about Gavin's cluster and road-distance tables (docs/clustering_options.md, docs/data_dictionary.md).

A failing assert names the doc to fix when a count changes on purpose.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"


@pytest.fixture(scope="module")
def ids():
    return pd.read_parquet(PROCESSED / "section_schedule.parquet")["section_id"].tolist()


@pytest.fixture(scope="module")
def road_mi(ids):
    """Symmetrized section-to-section road miles, in the order of `ids` (as the clustering scripts build it)."""
    ix = {s: i for i, s in enumerate(ids)}
    r = pd.read_parquet(PROCESSED / "section_to_section_road_distance.parquet")
    n = len(ids)
    D = np.zeros((n, n))
    D[r.from_section_id.map(ix).to_numpy(), r.to_section_id.map(ix).to_numpy()] = r.road_mi.to_numpy()
    return (D + D.T) / 2


def widest(D, labels):
    out = 0.0
    for c in np.unique(labels):
        g = np.flatnonzero(labels == c)
        if len(g) > 1:
            out = max(out, D[np.ix_(g, g)].max())
    return out


def test_section_to_section_distance_table(ids):
    r = pd.read_parquet(PROCESSED / "section_to_section_road_distance.parquet")
    n = len(ids)
    assert len(r) == n * n == 1_044_484, "data_dictionary.md: section_to_section_road_distance has sections x sections rows"
    assert set(r.from_section_id) == set(ids) == set(r.to_section_id)
    assert r.road_mi.notna().all() and (r.road_mi >= 0).all()


def test_hatchery_to_section_distance_table():
    h = pd.read_parquet(PROCESSED / "hatchery_to_section_road_distance.parquet")
    assert h.hatchery.nunique() == 13 and h.section_id.nunique() == 1045 and len(h) == 13 * 1045, \
        "data_dictionary.md: hatchery_to_section_road_distance is 13 hatcheries x 1,045 sections"
    assert h.road_mi.notna().all()


def test_hatcheries_producing_2026_fish_are_nine():
    s = pd.read_csv(PROCESSED / "hatchery_schedule_supply.csv")
    producing = s.loc[s["stream_fish_2026"] > 0, "hatchery"]
    assert len(producing) == 9, "clustering_options.md: 9 of 13 hatcheries produce stream fish in the 2026 schedule"
    h = pd.read_parquet(PROCESSED / "hatchery_to_section_road_distance.parquet")
    assert set(producing) <= set(h.hatchery), "every producing hatchery needs road distances"


def test_k_medoid_clusters(ids, road_mi):
    k = pd.read_parquet(PROCESSED / "section_medoid_clusters.parquet")
    assert len(k) == len(ids) and k.section_id.is_unique and set(k.section_id) == set(ids)
    lab = k.set_index("section_id").loc[ids]
    assert lab["medoid_cluster_id"].nunique() == 407, "clustering_options.md option 3: 407 clusters"
    assert lab["silhouette_best_cluster_id"].nunique() == 310, "clustering_options.md option 2: 310 clusters (best silhouette)"
    sizes = lab["medoid_cluster_id"].value_counts()
    assert sizes.max() <= 4, "option 3 caps clusters at 4 sections (parameters.csv cluster_max_sections)"
    codes = lab["medoid_cluster_id"].astype("category").cat.codes.to_numpy()
    assert widest(road_mi, codes) <= 20 + 1e-6, "option 3 caps clusters at 20 mi (parameters.csv cluster_max_width_mi)"


def test_hierarchical_clusters(ids, road_mi):
    t = pd.read_parquet(PROCESSED / "section_hierarchical_clusters.parquet")
    assert list(t.columns) == ["section_id", "width_only_19_9_cluster_id", "width_only_47_5_cluster_id",
                               "silhouette_best_cluster_id", "limits_cluster_id"], "data_dictionary.md: section_hierarchical_clusters columns"
    assert len(t) == len(ids) and t.section_id.is_unique and set(t.section_id) == set(ids)
    t = t.set_index("section_id").loc[ids]
    expected = {"silhouette_best_cluster_id": 309, "limits_cluster_id": 375, "width_only_19_9_cluster_id": 234, "width_only_47_5_cluster_id": 74}
    for col, n_clusters in expected.items():
        assert t[col].nunique() == n_clusters, f"clustering_options.md: {col} has {n_clusters} clusters"
    assert t["limits_cluster_id"].value_counts().max() <= 4
    for col, w in (("limits_cluster_id", 20), ("width_only_19_9_cluster_id", 19.9), ("width_only_47_5_cluster_id", 47.5)):
        codes = t[col].astype("category").cat.codes.to_numpy()
        assert widest(road_mi, codes) <= w + 1e-6, f"{col} must be no wider than {w} mi"
