"""Angler demand per 2026-stocked section: proximity and preference angler-days, kept as separate columns.

Follows docs/model_design.md § Angler benefit (decision 2026-09-27); the model blends the two with weight w.
Values no source gives ("over 50 days", "<0.5%", the lake share of "both") come from data/processed/parameters.csv.

Stream angler-days (decision 2026-10-03): the survey's days fished include lake days, and lakes aren't in the
section set, so each home region's lake share of days (p88: % primarily lakes + lake_days_both_share x % both)
is removed first. All demand columns are stream angler-days.

Proximity ("band version"; origins and distances decided 2026-10-04): each county subdivision's stream angler-days
(2020 population x county angler rate x its home region's mean days fished, p115, x (1 - its lake share)) go out
by its home region's trip-distance bands (p93), measured in Gavin's road miles from the subdivision's centroid to
the section midpoint (no circuity factor). Within a band they're split among the stocked sections in that band by
length; a band with no section passes its share to the next band out that has one (decision 2026-10-04), or, if
none farther out does, to the nearest band in. Every angler-day is placed once.

Preference: each survey stream water's share of mentions (p76-77; lake mentions leave the denominator with the
lake days) x statewide stream angler-days, split over its stocked sections by length (crosswalk from 07). The
share we can't place is spread like prox_days.

Inputs : data/processed/sections.parquet (02-04), subdivision_anglers.parquet (06), survey_water_crosswalk.csv (07),
         subdivision_to_section_road_distance.parquet (19, Gavin), angler_survey/p88, p93, p115, p76-77, p85 (00),
         parameters.csv
Outputs: data/processed/demand.{parquet,csv}  one row per 2026-stocked section
         logs/08_demand.log, logs/08_demand_waters.csv (per survey water: preference, proximity, flags)

    .venv/bin/python scripts/08_demand.py      (run after 06 and 07)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from common import LOG_DIR, PROCESSED_DIR, setup_logging

SURVEY = PROCESSED_DIR / "angler_survey"
REGIONS = ["northwest", "northcentral", "northeast", "southwest", "southcentral", "southeast"]
# p93 bands in driving miles, upper edges; 0 road mi is in the first band, and the last (> 150 mi) is open, so every
# section is in some band
BAND_EDGES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 150, np.inf]
BANDS = ["0-10 miles", "11-20 miles", "21-30 miles", "31-40 miles", "41-50 miles", "51-60 miles", "61-70 miles",
         "71-80 miles", "81-90 miles", "91-100 miles", "101-150 miles", "More than 150 miles"]
# p115 bands: midpoints, and the open top band from parameters.csv
DAYS_MID = {"41 to 50 days": 45.5, "31 to 40 days": 35.5, "21 to 30 days": 25.5, "11 to 20 days": 15.5,
            "6 to 10 days": 8, "5 days": 5, "4 days": 4, "3 days": 3, "2 days": 2, "1 day": 1}
CATCH_RELEASE = r"catch[- ]and[- ]release"  # 5 spellings in reg_name

log = logging.getLogger(__name__)


def param(name: str) -> float:
    p = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter")
    return float(p.loc[name, "value"])


def survey_table(name: str) -> pd.DataFrame:
    return pd.read_csv(SURVEY / name).set_index("response")


# ---------------------------------------------------------------- survey curves
def days_by_region() -> pd.Series:
    """Mean days fished for stocked trout by home region (p115), "Don't know" dropped."""
    t = survey_table("p115_days_fished_stocked_2022_by_region.csv")
    mids = pd.Series({**DAYS_MID, "Over 50 days": param("days_fished_over_50")})
    pct = t.loc[mids.index, REGIONS + ["statewide_all"]].astype(float)
    mean = pct.mul(mids, axis=0).sum() / pct.sum()
    published = float(t.loc["Mean", "statewide_all"])
    assert abs(mean["statewide_all"] - published) < 0.1, "p115 mean not reproduced"
    log.info("days fished (p115 midpoints, over 50 = %g): %s; statewide %.2f vs published %.1f",
             mids["Over 50 days"], mean[REGIONS].round(1).to_dict(), mean["statewide_all"], published)
    return mean[REGIONS]


def lake_shares() -> pd.Series:
    """Share of stocked-trout days spent on lakes, by home region (p88): % primarily lakes + b x % both."""
    t = survey_table("p88_primary_water_type_by_region.csv")
    both = param("lake_days_both_share")
    pct = t.loc[["Lakes", "Streams and rivers", "Both about equally"], REGIONS].astype(float)
    share = (pct.loc["Lakes"] + both * pct.loc["Both about equally"]) / pct.sum()  # "Do not know" (0%) dropped
    log.info("lake share of days (p88: primarily lakes + %g x both): %s", both, share.round(3).to_dict())
    return share


def band_shares() -> pd.DataFrame:
    """Share of trips in each p93 distance band, by home region (columns), "Don't know" dropped."""
    t = survey_table("p93_travel_distance_typical_trip_by_region.csv").loc[BANDS, REGIONS].astype(float)
    return t / t.sum()


# ---------------------------------------------------------------- inputs
def subdivisions(days: pd.Series, lake: pd.Series) -> pd.DataFrame:
    o = pd.read_parquet(PROCESSED_DIR / "subdivision_anglers.parquet")
    assert o.subdivision_id.is_unique and o.region.notna().all()
    log.info("origins: %d county subdivisions, %d with no population (they get no angler-days)", len(o),
             o.pop_2020.eq(0).sum())
    state_rate = o.anglers.sum() / o.pop_2020.sum()
    o["home"] = o.region.str.lower()
    all_days = o.anglers * o.home.map(days)
    o["days_per_angler"] = o.home.map(days * (1 - lake))  # stream days only
    o["angler_days"] = o.anglers * o.days_per_angler
    o["angler_days_pop"] = o.pop_2020 * state_rate * o.days_per_angler
    log.info("statewide stream angler-days: %s (%s anglers x days by home region x (1 - lake share); "
             "%s with lake days, %.1f%% removed)", f"{o.angler_days.sum():,.0f}", f"{o.anglers.sum():,.0f}",
             f"{all_days.sum():,.0f}", 100 * (1 - o.angler_days.sum() / all_days.sum()))
    return o


def candidates() -> pd.DataFrame:
    s = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    s = s[s.total_2026.fillna(0).gt(0)].reset_index(drop=True)
    assert len(s) == 1022 and s.length_mi.gt(0).all()
    return s


def road_miles(o: pd.DataFrame, s: pd.DataFrame) -> np.ndarray:
    """Road miles (OSRM, Gavin's script 19) from each subdivision's centroid to each 2026 section's midpoint."""
    d = pd.read_parquet(PROCESSED_DIR / "subdivision_to_section_road_distance.parquet",
                        columns=["subdivision_id", "section_id", "road_mi"])
    n, n_sec = len(d), d.section_id.nunique()
    d = d[d.section_id.isin(s.section_id)]
    assert set(d.section_id) == set(s.section_id), "a 2026 section has no road distances"
    log.info("road distances: %d pairs (%d sections); kept %d to the %d sections stocked in 2026, left out %d to "
             "the other %d", n, n_sec, len(d), len(s), n - len(d), n_sec - len(s))
    road = d.pivot(index="subdivision_id", columns="section_id", values="road_mi")
    road = road.reindex(index=o.subdivision_id, columns=s.section_id).to_numpy(dtype=float)
    assert len(d) == road.size and not np.isnan(road).any(), "every subdivision x section pair needs a road distance"
    log.info("road mi: %d pairs at 0 (first band), median nearest section %.1f, farthest pair %.1f (the last "
             "band's end)", (road == 0).sum(), np.median(road.min(axis=1)), road.max())
    return road


# ---------------------------------------------------------------- proximity
def band_targets(has: np.ndarray) -> np.ndarray:
    """Band each (origin, band) cell's share lands in: itself if it holds a stocked section, else the next band out
    that does (decision 2026-10-04: an angler whose usual trip length has no stocked water drives a little farther),
    else, past the last such band, the nearest band in."""
    n_o, n_b = has.shape
    out_, in_ = np.full((n_o, n_b), -1), np.full((n_o, n_b), -1)
    nxt, prv = np.full(n_o, -1), np.full(n_o, -1)
    for b in range(n_b - 1, -1, -1):
        nxt = np.where(has[:, b], b, nxt)
        out_[:, b] = nxt
    for b in range(n_b):
        prv = np.where(has[:, b], b, prv)
        in_[:, b] = prv
    target = np.where(out_ >= 0, out_, in_)
    assert (target >= 0).all(), "an origin has no stocked section in any band"
    return target


def per_mile_rates(band: np.ndarray, length: np.ndarray, shares: np.ndarray) -> np.ndarray:
    """Angler-day share per stocked mile for each (origin, section) pair.

    band: (n_o, n_s) band index of each pair; shares: (n_o, n_bands) each origin's band shares.
    Returns rate with sum over s of rate[i, s] * length[s] = 1 for every origin.
    """
    n_o, n_bands = shares.shape
    miles = np.stack([(band == b) @ length for b in range(n_bands)], axis=1)  # stocked miles per band
    live = np.zeros_like(shares)  # empty bands pass their share to the next band out (band_targets)
    np.add.at(live, (np.repeat(np.arange(n_o), n_bands), band_targets(miles > 0).ravel()), shares.ravel())
    assert np.allclose(live.sum(axis=1), 1) and not (live[miles == 0] > 0).any()
    per_mile = np.divide(live, miles, out=np.zeros_like(live), where=miles > 0)
    rate = np.take_along_axis(per_mile, band, axis=1)
    assert np.allclose(rate @ length, 1)
    return rate


def proximity(o: pd.DataFrame, s: pd.DataFrame, road: np.ndarray, shares: pd.DataFrame) -> tuple:
    band = np.searchsorted(BAND_EDGES, road, side="left").astype(np.int8)  # (0,10] -> 0, (10,20] -> 1, ...
    length = s.length_mi.to_numpy()
    home = o.home.to_numpy()

    regional = shares[home].T.to_numpy()  # each subdivision's own region's curve
    miles = np.stack([(band == b) @ length for b in range(len(BANDS))], axis=1)
    empty = (miles == 0) & (regional > 0)
    target = band_targets(miles > 0)
    inward = empty & (target < np.arange(len(BANDS)))
    moved = regional * o.angler_days.to_numpy()[:, None] / o.angler_days.sum()
    log.info("band shares passed on: %d of %d subdivision x band cells have no stocked section (%.1f%% of "
             "angler-days move to the next band out; %d cells, %.2f%%, have none farther out and move in)",
             empty.sum(), empty.size, 100 * moved[empty & ~inward].sum(), inward.sum(), 100 * moved[inward].sum())
    rate = per_mile_rates(band, length, regional)

    region_days = o.groupby("home").angler_days.sum()
    pooled_curve = shares.mul(region_days[REGIONS], axis=1).sum(axis=1) / region_days.sum()
    log.info("pooled in-state curve (regions weighted by angler-days): %s",
             dict(zip(BANDS, pooled_curve.round(3))))
    rate_pooled = per_mile_rates(band, length, np.tile(pooled_curve.to_numpy(), (len(o), 1)))

    out = pd.DataFrame({"section_id": s.section_id})
    out["prox_days"] = (o.angler_days.to_numpy() @ rate) * length
    out["prox_days_pooled"] = (o.angler_days.to_numpy() @ rate_pooled) * length
    pop_raw = (o.angler_days_pop.to_numpy() @ rate) * length
    # a "where" sensitivity: rescaled to the same statewide total, so it only moves demand around
    out["prox_days_pop"] = pop_raw * o.angler_days.sum() / pop_raw.sum()
    log.info("prox_days_pop: every county at the state angler rate; %s angler-days before rescaling to %s",
             f"{pop_raw.sum():,.0f}", f"{o.angler_days.sum():,.0f}")
    for c in ["prox_days", "prox_days_pooled", "prox_days_pop"]:
        assert np.isclose(out[c].sum(), o.angler_days.sum()), c
    log.info("proximity: all three columns sum to the statewide total; prox_days quantiles p10/50/90 %s",
             out.prox_days.quantile([0.1, 0.5, 0.9]).round(0).tolist())
    return out, rate, band


def proximity_checks(o, s, out, rate, road) -> None:
    """Report: angler-days landing in the home region vs the survey's p85, and Bear Creek's catchment."""
    p85 = pd.read_csv(SURVEY / "p85_preferred_water_county_by_region.csv").set_index("county")
    p85 = p85.drop(index="Not sure of county")
    cr = pd.read_csv(PROCESSED_DIR / "county_region.csv").set_index("county").region.str.lower()
    p85.index = p85.index.map(lambda c: c if c in cr.index else c.replace("McK", "Mck"))
    assert p85.index.isin(cr.index).all(), p85.index[~p85.index.isin(cr.index)]
    length = s.length_mi.to_numpy()
    sec_region = s.region.str.lower().to_numpy()
    rows = []
    for r in REGIONS:
        i = o.home.eq(r).to_numpy()
        landed = (o.angler_days.to_numpy()[i] @ rate[i]) * length
        rows.append({"home_region": r, "own_region_share": landed[sec_region == r].sum() / landed.sum(),
                     "p85_own_region_share": p85.loc[cr[p85.index] == r, r].sum() / p85[r].sum()})
    log.info("share of each home region's angler-days landing in its own region vs p85 (favorite water's "
             "county in the home region):\n%s", pd.DataFrame(rows).round(2).to_string(index=False))

    j = s.index[s.section_id.eq("3197_2")][0]
    contrib = pd.Series(o.angler_days.to_numpy() * rate[:, j] * length[j])
    rings = pd.cut(road[:, j], [0, 10, 20, 30, 50, 100, np.inf], include_lowest=True)
    log.info("Bear Creek 3197_2: %.0f prox angler-days; share by road-mile ring %s", contrib.sum(),
             (contrib.groupby(rings, observed=True).sum() / contrib.sum()).round(2).to_dict())


# ---------------------------------------------------------------- preference
def preference(s: pd.DataFrame, out: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cw = pd.read_csv(PROCESSED_DIR / "survey_water_crosswalk.csv", dtype={"river_id": "Int64"})
    waters = pd.read_csv(SURVEY / "p76-77_preferred_waters_overall.csv")
    assert set(waters.waterbody) == set(cw.waterbody), "crosswalk and p76-77 disagree"
    below = param("survey_pct_below_half")
    waters["pct"] = waters.pct_overall.where(~waters.lt_0_5_pct, below)
    assert waters.pct.notna().all()
    # lake mentions leave the denominator, as lake days left the total (subdivisions)
    lakes = waters.waterbody.isin(cw.loc[cw.water_type.eq("lake"), "waterbody"])
    total_pct = waters.pct[~lakes].sum()
    log.info("survey mentions: %.1f%% in all (up to three waters each, incl. Other and Don't know; %d waters "
             "at '<0.5%%' = %g%%); %d lakes (%.2f%%) dropped, leaving %.2f%%", waters.pct.sum(),
             waters.lt_0_5_pct.sum(), below, lakes.sum(), waters.pct[lakes].sum(), total_pct)
    statewide = out.prox_days.sum()

    s = s.assign(prox_days=out.prox_days.to_numpy())
    river_mi = s.groupby("river_id").length_mi.sum()
    placed = cw[cw.river_id.notna() & cw.river_id.isin(river_mi.index)].merge(
        waters[["waterbody", "pct"]], on="waterbody", how="left", validate="m:1")
    placed["pref_days"] = placed.pct / total_pct * placed.match_share * statewide
    by_river = placed.groupby("river_id").pref_days.sum()
    named = s.river_id.map(by_river).fillna(0) * s.length_mi / s.river_id.map(river_mi)

    unplaced = statewide - named.sum()
    out["pref_days_named"] = named.to_numpy()
    out["pref_days"] = out.pref_days_named + unplaced * out.prox_days / statewide
    assert np.isclose(out.pref_days.sum(), statewide)
    share_named = (placed.pct * placed.match_share).sum() / total_pct
    log.info("preference: %.1f%% of mentions land on %d matched rivers (%d sections); %.1f%% unplaced "
             "(Other, Don't know, unmatched, not stocked in 2026) is spread like prox_days",
             100 * named.sum() / statewide, by_river.size, named.gt(0).sum(), 100 * unplaced / statewide)
    assert abs(share_named - named.sum() / statewide) < 1e-9

    # per river: flag, destination index
    rv = s.assign(pref_days_named=named).groupby("river_id").agg(
        water_name=("water_name", "first"), stocked_mi=("length_mi", "sum"), prox_days=("prox_days", "sum"),
        pref_days_named=("pref_days_named", "sum"))
    rv = rv[rv.pref_days_named.gt(0)]
    max_prox_per_mi = (s.prox_days / s.length_mi).max()
    rv["pref_per_mi"] = rv.pref_days_named / rv.stocked_mi
    rv["pref_per_mi_flag"] = rv.pref_per_mi > max_prox_per_mi
    rv["destination_index"] = rv.pref_days_named / rv.prox_days
    names = placed.groupby("river_id").waterbody.agg("; ".join)
    rv["survey_waterbody"] = names
    log.info("flagged (preference per stocked mile > the state's highest prox_days per mile, %.0f): %s",
             max_prox_per_mi, rv[rv.pref_per_mi_flag][["water_name", "stocked_mi", "pref_per_mi"]]
             .round(1).reset_index().values.tolist())
    rv.sort_values("pref_days_named", ascending=False).round(3).to_csv(LOG_DIR / "08_demand_waters.csv")
    out = out.merge(rv[["survey_waterbody", "pref_per_mi_flag", "destination_index"]],
                    left_on=s.river_id.to_numpy(), right_index=True, how="left").drop(columns="key_0")
    out["pref_per_mi_flag"] = out.pref_per_mi_flag.fillna(False).astype(bool)
    return out, rv


# ---------------------------------------------------------------- regulation flags
def regulation_flags(s: pd.DataFrame) -> pd.DataFrame:
    reg = s.reg_name.fillna("")
    flags = pd.DataFrame({
        "dhalo": reg.str.contains("Delayed Harvest"),
        "catch_release": reg.str.contains(CATCH_RELEASE, case=False),
        "keystone_select": s.program_name.eq("KSSTW"),
        "open_year_round": reg.str.contains("Open Year-Round"),
    })
    log.info("regulation flags (2026 sections): %s", flags.sum().to_dict())
    return flags


# ---------------------------------------------------------------- main
def report(s: pd.DataFrame, out: pd.DataFrame) -> None:
    named = out.pref_days_named.gt(0)
    log.info("2026 fish on survey-named waters: %.1f%% (%d of %d sections)",
             100 * s.total_2026[named.to_numpy()].sum() / s.total_2026.sum(), named.sum(), len(s))
    per_acre = s.total_2026 / s.area_acres
    rho = {"total_2026": out.prox_days.corr(s.total_2026, method="spearman"),
           "fish_per_acre": out.prox_days.corr(per_acre, method="spearman"),
           "prox_days_pop": out.prox_days.corr(out.prox_days_pop, method="spearman"),
           "prox_days_pooled": out.prox_days.corr(out.prox_days_pooled, method="spearman"),
           "pref_days": out.prox_days.corr(out.pref_days, method="spearman")}
    log.info("rank correlation of prox_days with: %s", {k: round(float(v), 2) for k, v in rho.items()})


def main() -> None:
    setup_logging("08_demand")
    days = days_by_region()
    shares = band_shares()
    o = subdivisions(days, lake_shares())
    s = candidates()
    road = road_miles(o, s)
    out, rate, _ = proximity(o, s, road, shares)
    proximity_checks(o, s, out, rate, road)
    out, _ = preference(s, out)
    out = pd.concat([out, regulation_flags(s).set_axis(out.index)], axis=1)
    out.insert(1, "river_id", s.river_id.to_numpy())
    report(s, out)
    assert out.section_id.is_unique and len(out) == len(s)
    out.to_parquet(PROCESSED_DIR / "demand.parquet", index=False)
    out.round(3).to_csv(PROCESSED_DIR / "demand.csv", index=False)
    log.info("demand: %d rows, columns %s", len(out), list(out.columns))


if __name__ == "__main__":
    main()
