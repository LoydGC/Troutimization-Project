"""Checks that data/processed still matches the numbers the docs cite.

A failure means a rebuild changed a documented fact. If the change is intended, update the expected value
here and the doc named in the assert message.
"""
from pathlib import Path

import pandas as pd
import pytest

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"


@pytest.fixture(scope="module")
def sections():
    return pd.read_parquet(PROCESSED / "sections.parquet").set_index("section_id")


@pytest.fixture(scope="module")
def stocked_2026(sections):
    return sections["total_2026"].fillna(0).gt(0).astype(bool)


def test_section_counts(sections, stocked_2026):
    assert sections.index.is_unique
    assert len(sections) == 1045, "CLAUDE.md Known facts: 1,045 sections stocked 2024-26"
    assert (sections["n_years_stocked"] == 3).sum() == 1007, "CLAUDE.md Known facts: 1,007 in all three years"
    assert stocked_2026.sum() == 1022, "CLAUDE.md Candidate sections: 1,022 stocked in 2026"


def test_dropped_sections(sections, stocked_2026):
    dropped = sections[~stocked_2026]
    assert len(dropped) == 23, "CLAUDE.md Candidate sections: 23 dropped by 2026"
    assert {"3656_2", "3190_2"} <= set(dropped.index), "Blue Hole Creek and Buffalo Creek are among them"
    # 18 by river miles + West Branch Briar Creek 209_2 by geometry, including Blue Hole and Buffalo Creek
    assert dropped["nat_repro_flag"].sum() == 19, "CLAUDE.md Candidate sections: 19 natural-reproduction waters"


def test_class_a(sections, stocked_2026):
    class_a = sections["class_a_flag"]
    assert class_a.sum() == 18, "CLAUDE.md Known facts: 18 Class A overlaps"
    assert (class_a & stocked_2026).sum() == 17, "model_design.md Density bound: 17 capped at today's stocking"
    assert list(sections.index[class_a & ~stocked_2026]) == ["3190_2"], "model_design.md Exclusions: Buffalo Creek"
    biomass_a = sections["biomass_class"] == "A"
    assert biomass_a.sum() == 13, "known_gaps.md Class A exemptions: 13 biomass-A sections"
    assert (biomass_a & class_a).sum() == 13, "known_gaps.md Class A exemptions: all 13 overlap Class A"
    assert sections["wilderness_flag"].sum() == 0, "CLAUDE.md Known facts: none overlap Wilderness"


def test_flags_and_rates(sections):
    assert sections["nat_repro_flag"].sum() == 549, "data_methods.md: 549 natural-reproduction sections"
    assert sections["length_check_flag"].sum() == 57, "known_gaps.md: 57 length_check_flag sections"
    assert (sections["length_source"] == "river_miles").sum() == 9, "known_gaps.md: 9 use river miles"
    assert sections["max_trout_per_acre"].isna().sum() == 11, "data_methods.md: 11 with no Table 18 rate"
    assert sections["coop_stocked"].sum() == 292, "CLAUDE.md Co-op nurseries: 292 coop_stocked sections"
    assert list(sections.index[sections["rm_limits_reversed"]]) == ["3306_2"], "CLAUDE.md Known facts: Sherman Creek"


def test_bear_creek(sections):
    """CLAUDE.md Known facts: the Bear Creek (Schuylkill) test case."""
    bear = sections.loc[["3197_2", "3197_3"]]
    assert (bear["rfp_water_id"] == 3197).all()
    assert bear["brown_2026"].tolist() == [150, 0]
    assert bear["rainbow_2026"].tolist() == [850, 900]
    assert not bear["class_a_flag"].any()
    assert bear["nat_repro_flag"].all()


def test_baseline(sections):
    y = pd.read_parquet(PROCESSED / "stocking_section_year.parquet")
    assert len(y) == 15450, "data_dictionary.md: 15,450 rows"
    assert (y["count"] >= 0).all()
    assert set(y["section_id"]) == set(sections.index)
    totals = y.groupby("year")["count"].sum().to_dict()
    assert totals == {2024: 2_599_733, 2025: 2_615_828, 2026: 2_606_468}, "known_gaps.md: stream fish per year"
