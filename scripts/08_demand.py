"""Angler demand per 2026-stocked section: proximity and preference angler-days, kept as separate columns.

Follows docs/model_design.md § Angler benefit (decision 2026-09-27); the model blends the two with weight w.
Values no source gives (circuity, "over 50 days", "<0.5%") come from data/processed/parameters.csv.

Proximity ("band version"): each Census block group's angler-days (population x county angler rate x its home
region's mean days fished, p115) go out by its home region's trip-distance bands (p93). Within a band they're
split among the stocked sections in that band by length; a band with no section passes its share to the
block group's other bands in proportion. Every angler-day is placed once.

Preference: each survey water's share of mentions (p76-77) x statewide angler-days, split over its stocked
sections by length (crosswalk from 07). The share we can't place is spread like prox_days.

Inputs : data/processed/sections.parquet (02-04), county_anglers.csv (06), survey_water_crosswalk.csv (07),
         angler_survey/p93, p115, p76-77, p85 (00), parameters.csv
         data/raw/census/*/CenPop2020_Mean_BG42.txt (2020 block-group population and center of population)
Outputs: data/processed/demand.{parquet,csv}  one row per 2026-stocked section
         logs/08_demand.log, logs/08_demand_waters.csv (per survey water: preference, proximity, flags)

    .venv/bin/python scripts/08_demand.py      (run after 06 and 07)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from pyproj import Transformer

from common import LOG_DIR, PROCESSED_DIR, RAW_DIR, setup_logging

SURVEY = PROCESSED_DIR / "angler_survey"
REGIONS = ["northwest", "northcentral", "northeast", "southwest", "southcentral", "southeast"]
M_PER_MI = 1609.344
# p93 bands in driving miles, upper edges; the last (> 150 mi) is open, so every section is in some band
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


def band_shares() -> pd.DataFrame:
    """Share of trips in each p93 distance band, by home region (columns), "Don't know" dropped."""
    t = survey_table("p93_travel_distance_typical_trip_by_region.csv").loc[BANDS, REGIONS].astype(float)
    return t / t.sum()


# ---------------------------------------------------------------- inputs
def block_groups(days: pd.Series) -> pd.DataFrame:
    path = sorted(RAW_DIR.glob("census/*/CenPop2020_Mean_BG42.txt"))[-1]
    bg = pd.read_csv(path, dtype={"STATEFP": str, "COUNTYFP": str, "TRACTCE": str, "BLKGRPCE": str},
                     encoding="utf-8-sig")
    ca = pd.read_csv(PROCESSED_DIR / "county_anglers.csv", dtype={"county_fips": str})
    n = len(bg)
    bg = bg.assign(county_fips=bg.STATEFP + bg.COUNTYFP).merge(
        ca[["county_fips", "county", "region", "angler_rate"]], on="county_fips", how="left", validate="m:1")
    assert len(bg) == n and bg.region.notna().all()
    empty = bg.POPULATION.eq(0)
    log.info("block groups: %d, %d with no population (they get no angler-days)", n, empty.sum())
    state_rate = (bg.POPULATION * bg.angler_rate).sum() / bg.POPULATION.sum()
    bg["home"] = bg.region.str.lower()
    bg["days_per_angler"] = bg.home.map(days)
    bg["angler_days"] = bg.POPULATION * bg.angler_rate * bg.days_per_angler
    bg["angler_days_pop"] = bg.POPULATION * state_rate * bg.days_per_angler
    log.info("statewide angler-days: %s (%s anglers x days by home region)", f"{bg.angler_days.sum():,.0f}",
             f"{(bg.POPULATION * bg.angler_rate).sum():,.0f}")
    return bg


def candidates() -> pd.DataFrame:
    s = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    s = s[s.total_2026.fillna(0).gt(0)].reset_index(drop=True)
    assert len(s) == 1022 and s.length_mi.gt(0).all()
    return s


def road_miles(bg: pd.DataFrame, s: pd.DataFrame) -> np.ndarray:
    """Straight-line miles (EPSG:26918) from block-group center of population to section midpoint x circuity."""
    to_utm = Transformer.from_crs(4326, 26918, always_xy=True)
    bx, by = to_utm.transform(bg.LONGITUDE.values, bg.LATITUDE.values)
    sx, sy = to_utm.transform(s.mid_lon.values, s.mid_lat.values)
    straight = np.hypot(bx[:, None] - sx[None, :], by[:, None] - sy[None, :]) / M_PER_MI
    c = param("circuity_factor")
    log.info("distances: %d block groups x %d sections; road mi = straight x %g, farthest pair %.0f road mi",
             len(bg), len(s), c, straight.max() * c)
    return straight * c


# ---------------------------------------------------------------- proximity
def per_mile_rates(band: np.ndarray, length: np.ndarray, shares: np.ndarray) -> np.ndarray:
    """Angler-day share per stocked mile for each (block group, section) pair.

    band: (n_bg, n_s) band index of each pair; shares: (n_bg, n_bands) each block group's band shares.
    Returns rate with sum over s of rate[i, s] * length[s] = 1 for every block group.
    """
    n_bands = shares.shape[1]
    miles = np.stack([(band == b) @ length for b in range(n_bands)], axis=1)  # stocked miles per band
    live = np.where(miles > 0, shares, 0.0)
    live = live / live.sum(axis=1, keepdims=True)  # empty bands pass their share on in proportion
    per_mile = np.divide(live, miles, out=np.zeros_like(live), where=miles > 0)
    rate = np.take_along_axis(per_mile, band, axis=1)
    assert np.allclose(rate @ length, 1)
    return rate


def proximity(bg: pd.DataFrame, s: pd.DataFrame, road: np.ndarray, shares: pd.DataFrame) -> tuple:
    band = np.searchsorted(BAND_EDGES, road, side="left").astype(np.int8)  # (0,10] -> 0, (10,20] -> 1, ...
    length = s.length_mi.to_numpy()
    home = bg.home.to_numpy()

    regional = shares[home].T.to_numpy()  # each block group's own region's curve
    miles = np.stack([(band == b) @ length for b in range(len(BANDS))], axis=1)
    empty = (miles == 0) & (regional > 0)
    log.info("band shares passed on: %d of %d block group x band cells have no stocked section (%.1f%% of "
             "angler-days re-spread)", empty.sum(), empty.size,
             100 * (regional * empty * bg.angler_days.to_numpy()[:, None]).sum() / bg.angler_days.sum())
    rate = per_mile_rates(band, length, regional)

    region_days = bg.groupby("home").angler_days.sum()
    pooled_curve = shares.mul(region_days[REGIONS], axis=1).sum(axis=1) / region_days.sum()
    log.info("pooled in-state curve (regions weighted by angler-days): %s",
             dict(zip(BANDS, pooled_curve.round(3))))
    rate_pooled = per_mile_rates(band, length, np.tile(pooled_curve.to_numpy(), (len(bg), 1)))

    out = pd.DataFrame({"section_id": s.section_id})
    out["prox_days"] = (bg.angler_days.to_numpy() @ rate) * length
    out["prox_days_pooled"] = (bg.angler_days.to_numpy() @ rate_pooled) * length
    pop_raw = (bg.angler_days_pop.to_numpy() @ rate) * length
    # a "where" sensitivity: rescaled to the same statewide total, so it only moves demand around
    out["prox_days_pop"] = pop_raw * bg.angler_days.sum() / pop_raw.sum()
    log.info("prox_days_pop: every county at the state angler rate; %s angler-days before rescaling to %s",
             f"{pop_raw.sum():,.0f}", f"{bg.angler_days.sum():,.0f}")
    for c in ["prox_days", "prox_days_pooled", "prox_days_pop"]:
        assert np.isclose(out[c].sum(), bg.angler_days.sum()), c
    log.info("proximity: all three columns sum to the statewide total; prox_days quantiles p10/50/90 %s",
             out.prox_days.quantile([0.1, 0.5, 0.9]).round(0).tolist())
    return out, rate, band


def proximity_checks(bg, s, out, rate, road) -> None:
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
        i = bg.home.eq(r).to_numpy()
        landed = (bg.angler_days.to_numpy()[i] @ rate[i]) * length
        rows.append({"home_region": r, "own_region_share": landed[sec_region == r].sum() / landed.sum(),
                     "p85_own_region_share": p85.loc[cr[p85.index] == r, r].sum() / p85[r].sum()})
    log.info("share of each home region's angler-days landing in its own region vs p85 (favorite water's "
             "county in the home region):\n%s", pd.DataFrame(rows).round(2).to_string(index=False))

    j = s.index[s.section_id.eq("3197_2")][0]
    contrib = pd.Series(bg.angler_days.to_numpy() * rate[:, j] * length[j])
    rings = pd.cut(road[:, j], [0, 10, 20, 30, 50, 100, np.inf])
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
    total_pct = waters.pct.sum()
    log.info("survey mentions: %.1f%% in all (up to three waters each, incl. Other and Don't know; %d waters "
             "at '<0.5%%' = %g%%)", total_pct, waters.lt_0_5_pct.sum(), below)
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
             "(Other, Don't know, lakes, unmatched, not stocked in 2026) is spread like prox_days",
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
    bg = block_groups(days)
    s = candidates()
    road = road_miles(bg, s)
    out, rate, _ = proximity(bg, s, road, shares)
    proximity_checks(bg, s, out, rate, road)
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
