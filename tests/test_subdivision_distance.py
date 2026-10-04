"""Facts about the county-subdivision tables (docs/data_dictionary.md, docs/data_methods.md § County subdivisions).

A failing assert names the doc to fix when a count changes on purpose. These read the committed tables; the Census
and OSRM downloads are not re-run here.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
KM_PER_MI = 1.609344


@pytest.fixture(scope="module")
def subs():
    return pd.read_parquet(PROCESSED / "county_subdivisions.parquet")


@pytest.fixture(scope="module")
def road():
    return pd.read_parquet(PROCESSED / "subdivision_to_section_road_distance.parquet")


@pytest.fixture(scope="module")
def section_ids():
    return pd.read_parquet(PROCESSED / "sections.parquet")["section_id"]


def test_lookup_is_the_2026_vintage_pa_set(subs):
    assert len(subs) == 2567 and subs.subdivision_id.is_unique, \
        "data_methods.md: 2,568 Census rows minus the Lake Erie 'County subdivisions not defined' row = 2,567 subdivisions"
    assert subs.subdivision_id.str.fullmatch(r"42\d{8}").all()
    assert "4204900000" not in set(subs.subdivision_id), "the Lake Erie water row is left out"
    assert subs.county_fips.nunique() == 67 and subs.county.notna().all()
    assert subs.type.value_counts().to_dict() == {"township": 1544, "borough": 960, "city": 56, "municipality": 6, "town": 1}
    assert (subs.area_land_km2 > 0).all()


def test_centroids_are_in_pennsylvania_and_near_a_road(subs):
    assert subs.centroid_lat.between(39.7, 42.3).all() and subs.centroid_lon.between(-80.6, -74.6).all()
    assert subs[["centroid_lat", "centroid_lon", "intpt_lat", "intpt_lon", "origin_lat", "origin_lon", "road_snap_m"]].notna().all().all()
    assert (~subs.centroid_in_polygon).sum() == 44, "data_methods.md: 44 centroids fall outside their own subdivision (kept, flagged)"
    assert subs.road_snap_m.max() < 5000, "data_methods.md: every centroid snaps to a road within 5 km"


def test_only_pine_township_is_routed_from_a_moved_origin(subs):
    moved = subs[subs.origin_point != "centroid"]
    assert moved.subdivision_id.tolist() == ["4200560280"] and moved.origin_point.iloc[0] == "nearest_routable_grid_point", \
        "known_gaps.md: Pine township (Armstrong)'s centroid snaps to a disconnected road, so its origin is the nearest routable grid point"
    assert 0 < moved.origin_shift_m.iloc[0] < 1000
    same = subs[subs.origin_point == "centroid"]
    assert (same.origin_lat == same.centroid_lat).all() and (same.origin_lon == same.centroid_lon).all() and (same.origin_shift_m == 0).all()


def test_road_table_is_every_subdivision_by_every_section(subs, road, section_ids):
    assert len(road) == len(subs) * len(section_ids) == 2_682_515, \
        "data_dictionary.md: subdivision_to_section_road_distance = 2,567 subdivisions x 1,045 sections"
    assert set(road.subdivision_id) == set(subs.subdivision_id) and set(road.section_id) == set(section_ids)
    assert not road.duplicated(["subdivision_id", "section_id"]).any()
    assert road[["road_km", "road_mi", "road_min"]].notna().all().all() and (road.road_mi >= 0).all()
    assert np.allclose(road.road_mi * KM_PER_MI, road.road_km, atol=0.01)
    assert (PROCESSED / "subdivision_to_section_road_distance.parquet").stat().st_size < 50e6, "CLAUDE.md: files under 50 MB"


def test_road_is_never_shorter_than_straight_line(subs, road, section_ids):
    """A route can't beat the straight line between its points; the slack is the snap to the road at each end."""
    sec = pd.read_parquet(PROCESSED / "sections.parquet").set_index("section_id")
    snap_sec = pd.read_parquet(PROCESSED / "hatchery_to_section_road_distance.parquet").drop_duplicates("section_id").set_index("section_id").snap_m
    s = road.sample(5000, random_state=0)
    a, b = subs.set_index("subdivision_id").loc[s.subdivision_id], sec.loc[s.section_id]
    to_m = Transformer.from_crs("EPSG:4326", "EPSG:26918", always_xy=True)
    ax, ay = to_m.transform(a.origin_lon.to_numpy(), a.origin_lat.to_numpy())
    bx, by = to_m.transform(b.mid_lon.to_numpy(), b.mid_lat.to_numpy())
    straight_m = np.hypot(ax - bx, ay - by)
    slack_m = a.road_snap_m.to_numpy() + snap_sec.loc[s.section_id].to_numpy() + 1
    assert (s.road_km.to_numpy() * 1000 >= straight_m - slack_m).all()
