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
    # including Blue Hole and Buffalo Creek
    assert dropped["nat_repro_flag"].sum() == 18, "CLAUDE.md Candidate sections: 18 natural-reproduction waters"


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
    assert sections["nat_repro_flag"].sum() == 531, "data_methods.md: 531 natural-reproduction sections"
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


def test_river_region_area(sections):
    assert (sections["river_id"] == sections["rfp_water_id"]).all()
    assert sections["river_id"].nunique() == 695, "data_dictionary.md: 695 rivers"
    assert (sections.loc[["3197_2", "3197_3"], "region"] == "Southeast").all(), "CLAUDE.md Known facts: Bear Creek"
    regions = pd.read_csv(PROCESSED / "county_region.csv")
    assert len(regions) == 67 and regions["county"].is_unique, "CLAUDE.md Known facts: all 67 counties"
    assert regions["region"].nunique() == 6
    assert sections[["width_top_m", "width_mid_m", "area_acres", "area_acres_mid"]].notna().all().all()


def test_density_cap(sections, stocked_2026):
    assert sections["cap_source"].value_counts().to_dict() == {
        "access_rate": 1012, "class_a": 17, "program_rate": 9, "baseline": 7}, \
        "CLAUDE.md Density bound / data_dictionary.md cap_source"
    assert set(sections.index[sections["cap_source"] == "baseline"]) == {
        "1327_1", "2649_1", "2254_2", "1767_5", "2892_3", "183_9", "4029_7"}, \
        "model_design.md Density bound: the 7 sections above the cap"
    assert sections["program"].value_counts().to_dict() == {"DHALO": 56, "tailwater": 2}, \
        "model_design.md Density bound: Guidelines Tables 45-46"
    assert sections.loc["1327_1", "program_rate"] == 266, "Table 45: tailwater, High access"
    assert sections.loc["2649_1", "program_rate"] == 247, "Table 45: tailwater, Good access"
    fish_2026 = sections["total_2026"].fillna(0)
    assert (sections["cap_fish"] >= fish_2026).all(), "cap_fish never forces a cut in the base model"
    assert (sections["cap_fish"] >= 300).all() and (sections["cap_fish_mid"] <= sections["cap_fish"]).all()
    assert (sections["access_rate"] <= sections["cap_rate"]).all()
    assert (sections["cap_rate"] <= sections["cap_rate_river"]).all()
    has_program = sections["program_rate"].notna()
    assert (sections.loc[~has_program, "cap_rate"] == sections.loc[~has_program, "access_rate"]).all()
    assert (sections["cap_fish_river"] >= sections["cap_fish"]).all()
    assert (sections["cap_fish_class_a_grow"] >= sections["cap_fish"]).all()
    capped = sections["cap_source"].isin(["class_a", "baseline"])
    assert (sections.loc[capped, "cap_fish"] == fish_2026[capped]).all(), "CLAUDE.md: capped at 2026 stocking"
    rate_x_acres = (sections["cap_rate"] * sections["area_acres"]).round().clip(lower=300)
    assert (sections.loc[~capped, "cap_fish"] - rate_x_acres[~capped]).abs().max() <= 1, \
        "data_dictionary.md: cap_fish = cap_rate x area_acres, at least 300"
    over_mid = stocked_2026 & ~capped & (fish_2026 > sections["cap_fish_mid"])
    assert over_mid.sum() == 49, "model_design.md Density bound: 49 above the midpoint cap"
    # Better access never lowers the cap: biomass B + High at widths 2-3 gets 323, not Table 18's 147
    b_high = (sections["biomass_class"] == "B") & (sections["use_potential"] == "High") & \
        sections["width_class"].isin(["2", "3"])
    assert b_high.sum() == 17 and (sections.loc[b_high, "access_rate"] == 323).all(), \
        "model_design.md Density bound: 17 biomass-B High sections"
    assert sections.loc["3197_2", "cap_rate"] == 323 and sections.loc["3197_2", "cap_rate_river"] == 361


def test_environment(sections, stocked_2026):
    env = pd.read_parquet(PROCESSED / "environment.parquet").set_index("section_id")
    assert env.index.equals(sections.index)
    assert (env["exclude"] == ~stocked_2026).all(), "model_design.md Candidate sections: excluded = not stocked 2026"
    assert env["exclude_reason"].value_counts().to_dict() == {
        "not_stocked_2026": 21, "not_stocked_2026; health": 1, "class_a_not_stocked": 1}, \
        "data_dictionary.md environment.exclude_reason"
    assert env["wild_brook_present"].value_counts(dropna=False).to_dict() == {pd.NA: 1028, False: 17}, \
        "known_gaps.md Wild trout species outside Class A"
    share = env["nat_repro_share"]
    assert share.between(0, 1).all() and ((share > 0) == env["nat_repro_flag"]).all()
    assert (share >= 0.9).sum() == 496, "model_design.md Wild-trout impact: 496 of 531 at >= 90%"


def test_baseline(sections):
    y = pd.read_parquet(PROCESSED / "stocking_section_year.parquet")
    assert len(y) == 15450, "data_dictionary.md: 15,450 rows"
    assert (y["count"] >= 0).all()
    assert set(y["section_id"]) == set(sections.index)
    totals = y.groupby("year")["count"].sum().to_dict()
    assert totals == {2024: 2_599_733, 2025: 2_615_828, 2026: 2_606_468}, "known_gaps.md: stream fish per year"


def test_angler_survey():
    survey = PROCESSED / "angler_survey"
    by_region = ["p93_travel_distance_typical_trip", "p94_travel_distance_farthest", "p95_importance_near_home",
                 "p115_days_fished_stocked_2022", "p127_stocked_trout_harvest_per_year",
                 "p140_importance_catching_trout", "p174_support_removing_low_use_waters",
                 "p175_support_more_stocking_high_use_waters", "p178_support_moving_stocking_off_wild_trout_waters"]
    expected = {f"{name}_by_region.csv" for name in by_region} | {
        "p76-77_preferred_waters_overall.csv", "p78-83_preferred_waters_by_region.csv",
        "p84_preferred_water_county_overall.csv", "p85_preferred_water_county_by_region.csv"}
    assert {p.name for p in survey.glob("*.csv")} == expected, "angler_survey/README.md file list"
    waters = pd.read_csv(survey / "p76-77_preferred_waters_overall.csv")
    assert len(waters) == waters["waterbody"].nunique() == 223, "CLAUDE.md Known facts: ~223 named waters"
    tables = {}
    for name in by_region:
        t = pd.read_csv(survey / f"{name}_by_region.csv")
        pct = t[t["row_type"] == "percent"].set_index("response")
        cols = ["northwest", "northcentral", "northeast", "southwest", "southcentral", "southeast", "nonresident",
                "statewide_all"]
        assert pct[cols].sum().between(99, 102).all(), f"{name}: percent columns should sum to ~100"
        tables[name.split("_")[0]] = pct["statewide_all"]
    assert tables["p140"][["Very important", "Somewhat important"]].sum() == 81, "model_design.md: p140 81%"
    assert tables["p175"][["Strongly support", "Moderately support"]].sum() == 80, "model_design.md: p175 80%"
    p178 = tables["p178"]
    assert p178[["Strongly support", "Moderately support"]].sum() == 58, "model_design.md: p178 58% support"
    assert p178[["Moderately oppose", "Strongly oppose"]].sum() == 16, "model_design.md: p178 16% oppose"
