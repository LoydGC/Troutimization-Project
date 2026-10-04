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
    by_region = ["p88_primary_water_type", "p93_travel_distance_typical_trip", "p94_travel_distance_farthest", "p95_importance_near_home",
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


def test_county_anglers():
    ca = pd.read_csv(PROCESSED / "county_anglers.csv")
    regions = pd.read_csv(PROCESSED / "county_region.csv")
    assert len(ca) == 67 and set(ca["county"]) == set(regions["county"]), "spelled as in sections.county"
    assert abs(ca["anglers"].sum() - 421_615) < 5, "data_methods.md County anglers: 421,615 resident anglers"
    assert abs(ca["online_permits"].sum() - 117_500) < 5, "data_dictionary.md county_anglers: 117,500 online"
    parts = ca["annual_trout_combo"] + ca["multi_trout_combo"] - ca["nonres_licenses"]
    assert (ca["resident_permits"] == parts).all() and (parts >= 0).all()
    assert abs(ca["anglers_by_sales"].sum() - ca["anglers"].sum()) < 5, "the sensitivity moves anglers, same total"
    assert ca["pop_2020"].sum() == 13_002_700, "data_methods.md County anglers: PA's 2020 Census population"


def test_subdivision_anglers():
    sub = pd.read_parquet(PROCESSED / "subdivision_anglers.parquet")
    cs = pd.read_parquet(PROCESSED / "county_subdivisions.parquet")
    ca = pd.read_csv(PROCESSED / "county_anglers.csv", dtype={"county_fips": str}).set_index("county_fips")
    assert len(sub) == 2567 and sub["subdivision_id"].is_unique, "data_dictionary.md subdivision_anglers: 2,567 rows"
    assert set(sub["subdivision_id"]) == set(cs["subdivision_id"]), "one row per county_subdivisions origin"
    assert sub[["pop_2020", "region", "angler_rate", "anglers"]].notna().all().all()
    assert sub["pop_2020"].sum() == 13_002_700, "data_methods.md County anglers: PA's 2020 Census population"
    by_county = sub.groupby("county_fips")[["pop_2020", "anglers"]].sum()
    # Falls Creek borough's Clearfield part (42 people in 2020) is in Jefferson County by 2026 (known_gaps.md)
    moved = {"42033": -42, "42065": 42}
    pop_diff = by_county["pop_2020"] - ca.loc[by_county.index, "pop_2020"]
    assert pop_diff[pop_diff != 0].to_dict() == moved, "data_methods.md County anglers: only Falls Creek moved"
    assert ((by_county["anglers"] - ca.loc[by_county.index, "anglers"]).abs() < 5).all(), "anglers sum to the county"
    assert abs(sub["anglers"].sum() - ca["anglers"].sum()) < 1, "data_methods.md: 421,615 anglers statewide"
    rate = sub["county_fips"].map(ca["angler_rate"])
    assert ((sub["angler_rate"] - rate).abs() < 1e-6).all(), "each subdivision takes its county's angler rate"


def test_demand(sections, stocked_2026):
    d = pd.read_parquet(PROCESSED / "demand.parquet").set_index("section_id")
    assert set(d.index) == set(sections.index[stocked_2026]), "one row per 2026-stocked section"
    total = d["prox_days"].sum()
    assert abs(total - 7_121_847) < 10, \
        "CLAUDE.md Known facts / data_dictionary.md demand: 7,121,847 stream angler-days (lake days removed)"
    for col in ["prox_days_pooled", "prox_days_pop", "pref_days"]:
        assert abs(d[col].sum() - total) < 1, f"data_dictionary.md demand: {col} sums to the statewide total"
    assert (d["prox_days"] > 0).all() and (d["pref_days"] >= d["pref_days_named"]).all()
    named = d["pref_days_named"].sum() / total
    assert abs(named - 0.695) < 0.001, "data_methods.md Preference demand: 69.5% of stream mentions placed"
    assert sorted(d.index[d["pref_per_mi_flag"]]) == ["1327_1", "2027_1"], \
        "model_design.md Per-mile flag: the Youghiogheny and White Clay Creek"
    flags = d[["dhalo", "catch_release", "keystone_select", "open_year_round"]].sum().to_dict()
    assert flags == {"dhalo": 56, "catch_release": 30, "keystone_select": 24, "open_year_round": 16}, \
        "data_methods.md Regulation flags"
    assert (d["dhalo"] == (sections.loc[d.index, "program"] == "DHALO")).all(), "same 56 as the density cap"


def test_survey_crosswalk():
    cw = pd.read_csv(PROCESSED / "survey_water_crosswalk.csv", dtype={"river_id": "Int64"})
    waters = pd.read_csv(PROCESSED / "angler_survey" / "p76-77_preferred_waters_overall.csv")
    assert set(cw["waterbody"]) == set(waters["waterbody"]), "every survey water has a row"
    shares = cw.dropna(subset=["river_id"]).groupby("waterbody")["match_share"].sum()
    assert ((shares - 1).abs() < 1e-6).all(), "match_share sums to 1 per matched water"
    assert (cw.loc[cw["match_method"] == "review", "river_id"].isna()).all(), "undecided names get no river"
    split = cw[cw["waterbody"] == "French Creek"].set_index("river_id")["match_share"].round(2).to_dict()
    assert split == {413: 0.75, 1882: 0.25}, "data_methods.md Survey water crosswalk: French Creek"


def test_stocking_events(sections, stocked_2026):
    ev = pd.read_parquet(PROCESSED / "stocking_events.parquet")
    assert len(ev) == 2474, "data_dictionary.md stocking_events: 2,474 rows (section x date)"
    assert ev["water_type"].value_counts().to_dict() == {"stream": 2102, "lake": 372}, \
        "data_methods.md Stocking schedule: 2,102 stream and 372 lake events"
    assert ev["match_method"].value_counts().to_dict() == {
        "limits": 1766, "lake": 372, "name_county": 321, "coords": 9, "unmatched": 6}, \
        "data_methods.md Stocking schedule: match methods"
    assert not ev.duplicated(["section_id", "date", "week_of"]).loc[ev["section_id"].notna()].any()
    assert ev["week_of_only"].sum() == 74 and (ev["week_of_only"] == ev["date"].isna()).all(), \
        "data_methods.md Stocking schedule: 74 week-of-only events"
    assert (ev["run_id"].isna() == ev["week_of_only"]).all(), "every dated event has a run"
    assert ev.loc[ev["water_type"] == "lake", "section_id"].isna().all()
    scheduled = set(ev["section_id"].dropna())
    assert set(sections.index[stocked_2026]) <= scheduled, "data_methods.md: all 1,022 candidates are scheduled"
    assert len(scheduled - set(sections.index[stocked_2026])) == 8, \
        "known_gaps.md Stocking schedule: 8 scheduled sections not stocked in the 2026 layer"
    assert abs(ev["alloc_fish"].sum() - sections["total_2026"].sum()) < 5, "every 2026 stream fish is placed once"
    bear = ev[ev["section_id"].isin(["3197_2", "3197_3"])]
    assert set(bear["hatchery"]) == {"Tylersville"} and len(bear) == 4, "Bear Creek: 2 Tylersville visits each"


def test_hatchery_schedule_supply(sections):
    h = pd.read_csv(PROCESSED / "hatchery_schedule_supply.csv").set_index("hatchery")
    active = h.index[h["n_stream_events"] > 0]
    assert set(active) == {"Bellefonte", "Benner Spring", "Corry", "Huntsdale", "Oswayo", "Pleasant Gap",
                           "Reynoldsdale", "Tionesta", "Tylersville"}, "data_methods.md: 9 hatcheries on the schedule"
    assert not h.loc[["Linesville", "Pleasant Mount"], "n_stream_events"].any(), \
        "known_gaps.md: Linesville and Pleasant Mount stock no scheduled stream sections"
    assert not h.loc["Tionesta", "in_production_csv"], "known_gaps.md: Tionesta has no production figure"
    assert abs(h["stream_fish_2026"].sum() - sections["total_2026"].sum()) < 10, "shares cover every 2026 fish"
    assert abs(h["share"].sum() - 1) < 1e-3 and abs(h["lbs_share"].sum() - 1) < 1e-3
    assert h["n_lake_events"].sum() == 372


def test_section_schedule_and_clusters(stocked_2026):
    ss = pd.read_parquet(PROCESSED / "section_schedule.parquet").set_index("section_id")
    assert set(ss.index) == set(stocked_2026.index[stocked_2026]), "one row per 2026-stocked section"
    assert (ss["n_events"] > 0).all() and (ss["cluster_source"] == "schedule").all()
    assert ss["multi_hatchery"].sum() == 49, "data_dictionary.md section_schedule: 49 multi-hatchery sections"
    assert ss["cluster_id"].nunique() == 351 and ss["detour_singleton"].sum() == 103, \
        "data_methods.md Runs and clusters: 351 clusters, 103 singletons"
    assert ss["cluster_id_strict"].nunique() == 528, "data_methods.md Runs and clusters: 528 under the strict rule"
    assert (ss.loc[ss["detour_singleton"], "detour_mi"] == 0).all()
    assert (ss.loc[~ss["detour_singleton"], "detour_mi"] >= ss.loc[~ss["detour_singleton"], "detour_nn_mi"]).all()
    assert ss.loc["3197_2", "cluster_id"] == ss.loc["3197_3", "cluster_id"], "Bear Creek 02-03 share both runs"
    c = pd.read_csv(PROCESSED / "clusters.csv").set_index("cluster_id")
    assert len(c) == 351 and c["n_sections"].sum() == 1022
    assert (c["n_sections"] == ss["cluster_id"].value_counts().reindex(c.index)).all()
    assert not c["span_flag"].any(), "data_methods.md Runs and clusters: no cluster spans > 60 road-mi"


def test_transport_inputs(sections, stocked_2026):
    h = pd.read_parquet(PROCESSED / "hatcheries.parquet")
    assert len(h) == 13, "CLAUDE.md Supply node: 13 hatcheries in PFBC's layer"
    assert h.in_2026_schedule.sum() == 9, "CLAUDE.md Supply node: 9 on the 2026 schedule"
    assert h.supply.sum() == 2_606_465, "model_design.md Constraints (Total fish): T = sum of supply"
    cm = pd.read_parquet(PROCESSED / "cost_matrix.parquet")
    assert len(cm) == 13 * 1022 and not cm[["road_mi", "cluster_road_mi", "cost_per_fish"]].isna().any().any()
    assert cm.groupby(["cluster_id", "hatchery_id"]).cluster_road_mi.nunique().eq(1).all()
    assert cm.cluster_id.nunique() == 310, "model_design.md Transport cost: k-medoids clusters (310) set the haul"
    bf = pd.read_parquet(PROCESSED / "baseline_flows.parquet")
    per_section = bf.groupby("section_id").fish.sum()
    total = sections.loc[stocked_2026, "total_2026"].astype(float)
    assert (per_section.reindex(total.index) - total).abs().max() < 1, "baseline flows = 2026 counts"
    load = bf.groupby("hatchery").fish.sum()
    assert (load - h.set_index("hatchery").supply.reindex(load.index)).abs().max() < 2, "loads = supply (rounding)"
    assert round(bf.cost.sum()) == 351_524, "model_design.md Transport cost: baseline $351.5k/yr"


def test_model_input():
    m = pd.read_parquet(PROCESSED / "model_input.parquet")
    assert len(m) == 1022 and m.section_id.is_unique and m.complete.all()
    assert m.x0.sum() == 2_606_468
    assert m.impact_simple.sum() == 624, "model_design.md Wild-trout impact: simple score on 624 sections"
    assert m.loc[m.impact_simple == 1, "x0"].sum() == 1_445_045
    # main impact version (decision 2026-10-04): biomass weight x share on wild-trout water, class D = 1
    assert m.impact_weighted.gt(0).sum() == 624
    assert round((m.impact_weighted * m.x0).sum()) == 2_274_440, "model_design.md Wild-trout impact: weighted 2026 total"
