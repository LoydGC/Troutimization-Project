"""Build the section-level base tables and map layers from the downloaded PFBC layers.

Inputs : data/interim/pfbc_gis/*.parquet (from 01_download_pfbc_layers.py), data/raw/pa_hatcheries.gpkg
Outputs: data/processed/stocking_section_year.{parquet,csv}  long baseline: section x year x species
         data/processed/sections.{parquet,csv}               one row per stocked section, no geometry
         data/processed/pfbc_stocking_rates.csv              Operational Guidelines Table 18, expanded by code
         data/processed/pa_trout.gpkg                        map layers joined on section_id
         logs/02_build_sections.log, logs/02_overlap_check.csv

    .venv/bin/python scripts/02_build_sections.py
"""
from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from common import INTERIM_DIR, LOG_DIR, PROCESSED_DIR, RAW_DIR, setup_logging

YEARS = (2024, 2025, 2026)
SPECIES = {"TotalBrookStocked": "brook", "TotalBrownStocked": "brown", "TotalRainbowStocked": "rainbow",
           "TotalGoldenStocked": "golden", "TotalBroodStocked": "brood"}
METRIC_CRS = "EPSG:26918"  # UTM 18N: lengths and distances
M_PER_MI = 1609.344
MIN_OVERLAP_MI = 100 / M_PER_MI  # CLAUDE.md rule 8: overlap must exceed 100 m to count
CHECK_BUFFER_M = 30  # geometric overlap: section length within 30 m of a same-water wild-trout line
CONTEXT_SIMPLIFY_M = 5  # wild-trout layers in pa_trout.gpkg (overlaps are computed before simplifying)
NAT_REPRO_GEOM_MI = 0.5  # nat. repro: some records' river miles cover less than their line and Limits text
LENGTH_CHECK_TOL = 0.25  # length_check_flag: PFBC Length_MI_ vs river-mile length
STOCKING_BAND = (0.1, 0.9)  # length check: normal range of fish per (rate x mile) among unflagged sections

USE = {"H": "High", "G": "Good", "L": "Low"}
POP = {"M": "Metro", "U": "Urban", "S": "Suburban", "R": "Rural"}
CODE_RE = r"^(?P<biomass_class>[A-E])(?P<use_code>[HGL])(?P<pop_code>[MUSR])(?P<width_class>1S|1L|2|3|4)$"
GUIDELINES = ("PFBC Operational Guidelines for the Management of Trout Fisheries in Pennsylvania Waters, "
              "5th ed., Table 18")

log = logging.getLogger(__name__)
PFBC_GIS = INTERIM_DIR / "pfbc_gis"


def counts(step: str, before: int, after: int, what: str = "rows") -> None:
    log.info("%-55s %6d -> %6d %s", step, before, after, what)


# ---------------------------------------------------------------- stocked sections
def load_year(year: int) -> gpd.GeoDataFrame:
    g = gpd.read_parquet(PFBC_GIS / f"stocked_{year}.parquet")
    assert (g.StockingYear == year).all(), f"StockingYear mismatch in stocked_{year}"
    g["year"] = year
    g["section_id"] = g.RFP_WaterID.astype(str) + "_" + g.SecNum.astype(str)
    g["County"] = g.County.str.strip().str.title()
    n_null = g[list(SPECIES)].isna().sum()
    if n_null.any():
        # Null brook/brown counts are zeros: PFBC's own TotalAdultStocked_minusBrood equals the sum with them as 0.
        log.info("%d: null species counts filled with 0: %s", year, n_null[n_null > 0].to_dict())
    g[list(SPECIES)] = g[list(SPECIES)].fillna(0).astype(int)
    adult = g[["TotalBrookStocked", "TotalBrownStocked", "TotalRainbowStocked"]].sum(axis=1)
    bad = int((adult != g.TotalAdultStocked_minusBrood).sum())
    log.info("%d: rows where brook+brown+rainbow != PFBC TotalAdultStocked_minusBrood: %d "
             "(golden and brood are extra to PFBC's total)", year, bad)
    return g


def join_unique(s: pd.Series) -> str | None:
    vals = [v for v in dict.fromkeys(s.dropna().astype(str).str.strip()) if v]
    return "; ".join(vals) or None


def collapse_duplicates(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Some sections appear as 2 rows, each carrying the full section total: one "Stocked Trout Water" row and
    one "Commonwealth Inland Waters" row.

    Counts are identical, so they're taken once. The "Stocked Trout Water" row's limits, Length_MI_ and line
    are kept (decision 2026-09-27): the two lines don't describe the same stretch, so a union overstated
    length. County and regulation text are joined (some sections cross a county line).
    """
    year = int(g.year.iloc[0])
    dup = g.section_id.duplicated(keep=False)
    if not dup.any():
        return g
    diff = g[dup].groupby("section_id")[list(SPECIES)].nunique().gt(1).any(axis=1)
    if diff.any():
        raise ValueError(f"{year}: duplicate sections with different counts: {list(diff[diff].index)}")
    merged = []
    for sid, grp in g[dup].groupby("section_id", sort=False):
        stw = grp[grp.Reg_Name.str.strip().eq("Stocked Trout Water")]
        if len(stw) != 1:
            log.warning("%d %s: %d 'Stocked Trout Water' rows; keeping the first row", year, sid, len(stw))
            stw = grp
        row = stw.iloc[0].copy()
        for c in ("County", "Reg_Name", "Reg_Link"):
            row[c] = join_unique(grp[c])
        row["SpecReg"] = "Y" if (grp.SpecReg == "Y").any() else row["SpecReg"]
        row["n_pieces"] = len(grp)
        merged.append(row)
    out = pd.concat([g[~dup].assign(n_pieces=1), gpd.GeoDataFrame(merged, crs=g.crs)], ignore_index=True)
    counts(f"{year}: collapse duplicate section_id rows ({dup.sum()} rows, {len(merged)} sections)", len(g), len(out))
    return gpd.GeoDataFrame(out, geometry="geometry", crs=g.crs)


def build_stocking_long(years: dict[int, gpd.GeoDataFrame]) -> pd.DataFrame:
    frames = []
    for year, g in years.items():
        long = g[["section_id", "year", *SPECIES]].melt(["section_id", "year"], var_name="field", value_name="count")
        long["species"] = long.field.map(SPECIES)
        long["source_layer"] = f"stocked_{year}"
        frames.append(long.drop(columns="field"))
    out = pd.concat(frames, ignore_index=True)[["section_id", "year", "species", "count", "source_layer"]]
    out["species"] = pd.Categorical(out.species, categories=list(SPECIES.values()))
    return out.sort_values(["section_id", "year", "species"]).reset_index(drop=True)


# ---------------------------------------------------------------- PFBC allocation categories (Table 18)
def table18() -> pd.DataFrame:
    """Maximum stocking rate (trout/acre/yr) for every allocation-code combination, per Table 18."""
    good = {"M": 323, "U": 285, "S": 190, "R": 95}
    river = {("1S", "H"): {"U": 137, "S": 122, "R": 110}, ("1S", "G"): {"U": 84, "S": 65, "R": 57},
             ("1L", "H"): {"U": 91, "S": 72, "R": 61}, ("1L", "G"): {"U": 53, "S": 50, "R": 38}}
    rows = []
    for b in "BCDE":
        for p in "MUSR":
            for w in ("2", "3"):
                if b == "B":
                    rows.append((b, "H", p, w, 147, "Optimum Yield"))
                else:
                    rows.append((b, "H", p, w, 361 if p == "M" else 323, "High Yield"))
                rows.append((b, "G", p, w, good[p], "Optimum Yield"))
            rows += [(b, "H", p, "4", 57, "Optimum Yield"), (b, "G", p, "4", 57, "Optimum Yield")]
            rows += [(b, "L", p, w, 57, "Low Yield") for w in ("2", "3", "4")]
    for w in ("1S", "1L"):  # river rows don't depend on biomass; Metro isn't listed
        for b in "ABCDE":
            for p in "USR":
                rows += [(b, "H", p, w, river[(w, "H")][p], "River"), (b, "G", p, w, river[(w, "G")][p], "River"),
                         (b, "L", p, w, 34 if w == "1S" else 30, "River")]
    t = pd.DataFrame(rows, columns=["biomass_class", "use_code", "pop_code", "width_class", "max_trout_per_acre",
                                    "membership"])
    t.insert(0, "allocation_code", t.biomass_class + t.use_code + t.pop_code + t.width_class)
    t["source"] = GUIDELINES
    assert t.allocation_code.is_unique
    return t


def parse_allocation(sections: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    parts = sections.allocation_code.str.extract(CODE_RE)
    bad = parts.biomass_class.isna() & sections.allocation_code.notna()
    if bad.any():
        log.warning("allocation codes not matching %s: %s", CODE_RE, sections.loc[bad, "allocation_code"].tolist())
    sections = sections.join(parts)
    sections["use_potential"] = sections.use_code.map(USE)
    sections["pop_density"] = sections.pop_code.map(POP)
    sections = sections.merge(rates[["allocation_code", "max_trout_per_acre"]], on="allocation_code", how="left")
    sections["max_trout_per_acre_missing_reason"] = np.select(
        [sections.max_trout_per_acre.notna(), sections.biomass_class.eq("A"), sections.pop_code.eq("M")],
        [None, "biomass class A (Class A wild trout) not in Table 18", "Metro river not in Table 18"],
        "code not in Table 18")
    sections["max_trout_per_acre"] = sections.max_trout_per_acre.astype("Int64")
    log.info("Table 18 rate found for %d of %d sections; missing reasons: %s", sections.max_trout_per_acre.notna().sum(),
             len(sections), sections.max_trout_per_acre_missing_reason.value_counts().to_dict())
    return sections.drop(columns=["use_code", "pop_code"])


# ---------------------------------------------------------------- wild-trout overlap
def choose_length(s: pd.DataFrame) -> pd.DataFrame:
    """length_mi = PFBC's Length_MI_, except flagged sections whose stocking fits the river-mile length instead.

    PFBC allocates fish as rate x acres, so fish / (Table 18 rate x length) is similar within a width class.
    Its normal range (STOCKING_BAND quantiles among unflagged sections) turns a flagged section's fish into an
    expected length range. Where exactly one of PFBC's two lengths falls in it, that one is kept; otherwise
    Length_MI_ stays (decision 2026-09-27). Only a length choice: stocking counts are never changed.
    """
    fish = s[[f"total_{y}" for y in YEARS]].astype(float).mean(axis=1)  # mean per year stocked
    k = fish / (s.max_trout_per_acre * s.pfbc_length_mi)
    ref = k[~s.length_check_flag & (fish > 0)].groupby(s.width_class)
    q_lo, q_hi = STOCKING_BAND
    exp_mi = fish / (s.max_trout_per_acre * s.width_class.map(ref.median()))
    exp_lo = fish / (s.max_trout_per_acre * s.width_class.map(ref.quantile(q_hi)))
    exp_hi = fish / (s.max_trout_per_acre * s.width_class.map(ref.quantile(q_lo)))
    fits_p = s.pfbc_length_mi.between(exp_lo, exp_hi).fillna(False).to_numpy(bool)
    fits_r = s.rm_length_mi.between(exp_lo, exp_hi).fillna(False).to_numpy(bool)
    no_ref = (exp_mi.isna() | (fish <= 0)).to_numpy(bool)
    result = pd.Series(np.select([no_ref, fits_p & ~fits_r, fits_r & ~fits_p, fits_p & fits_r],
                                 ["no_rate_or_fish", "fits_pfbc_length", "fits_river_miles", "both_plausible"],
                                 "neither"), index=s.index)
    s["length_check_result"] = result.where(s.length_check_flag, None)
    use_rm = s.length_check_result.eq("fits_river_miles")
    s["length_mi"] = s.pfbc_length_mi.where(~use_rm, s.rm_length_mi)
    s["length_source"] = np.where(use_rm, "river_miles", "pfbc_length")

    flagged = s[s.length_check_flag].assign(
        pfbc_to_rm_ratio=(s.pfbc_length_mi / s.rm_length_mi.where(s.rm_length_mi > 0)).round(2),
        mean_fish_per_year=fish.round(0), stocking_expected_mi=exp_mi.round(2),
        stocking_range_lo_mi=exp_lo.round(2), stocking_range_hi_mi=exp_hi.round(2))
    flagged[["section_id", "water_name", "county", "n_pieces", "width_class", "max_trout_per_acre",
             "mean_fish_per_year", "pfbc_length_mi", "rm_length_mi", "pfbc_to_rm_ratio", "stocking_expected_mi",
             "stocking_range_lo_mi", "stocking_range_hi_mi", "length_check_result", "length_source", "length_mi",
             "upper_limit", "lower_limit"]].sort_values(["length_check_result", "section_id"]).to_csv(
        LOG_DIR / "02_length_check.csv", index=False)
    log.info("length_check_flag: %d sections where PFBC Length_MI_ and river-mile length differ by > %d%%; "
             "stocking check: %s (logs/02_length_check.csv)", len(flagged), LENGTH_CHECK_TOL * 100,
             flagged.length_check_result.value_counts().to_dict())
    log.info("length_source: %s", s.length_source.value_counts().to_dict())
    return s


def merge_intervals(df: pd.DataFrame) -> dict[int, list[tuple[float, float]]]:
    """River-mile intervals per RFP water id, overlapping intervals merged."""
    out: dict[int, list[tuple[float, float]]] = {}
    for rfp, grp in df.groupby("rfp"):
        ivs = sorted(zip(grp.lo, grp.hi))
        merged = [list(ivs[0])]
        for lo, hi in ivs[1:]:
            if lo <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        out[rfp] = [tuple(m) for m in merged]
    return out


def river_mile_overlap(sections: pd.DataFrame, wild: gpd.GeoDataFrame) -> pd.Series:
    """Shared river miles between each stocked section and a wild-trout layer on the same RFP water id."""
    w = pd.DataFrame({"rfp": wild.RFP_WaterI, "lo": wild[["SecUpperLi", "SecLowerLi"]].min(axis=1),
                      "hi": wild[["SecUpperLi", "SecLowerLi"]].max(axis=1)})
    ivs = merge_intervals(w)
    out = []
    for rfp, lo, hi in zip(sections.rfp_water_id, sections.lower_rm, sections.upper_rm):
        lo, hi = min(lo, hi), max(lo, hi)
        out.append(sum(max(0.0, min(hi, whi) - max(lo, wlo)) for wlo, whi in ivs.get(rfp, [])))
    return pd.Series(out, index=sections.index).round(3)


def geometric_overlap(geoms: gpd.GeoSeries, rfp: pd.Series, wild: gpd.GeoDataFrame) -> pd.Series:
    """Miles of each section within CHECK_BUFFER_M of wild-layer lines on the same RFP water id.

    Restricting to the same water id keeps tributary mouths from counting as overlap.
    """
    buf = gpd.GeoDataFrame({"rfp": wild.RFP_WaterI.values}, geometry=wild.to_crs(METRIC_CRS).buffer(CHECK_BUFFER_M).values,
                           crs=METRIC_CRS)
    sec = gpd.GeoDataFrame({"rfp": rfp.values}, geometry=geoms.to_crs(METRIC_CRS).values, crs=METRIC_CRS,
                           index=geoms.index)
    pairs = gpd.sjoin(sec, buf, predicate="intersects")
    pairs = pairs[pairs.rfp_left == pairs.rfp_right]
    out = pd.Series(0.0, index=geoms.index)
    for idx, grp in pairs.groupby(level=0):
        zone = shapely.union_all(buf.geometry.loc[grp.index_right].values)
        out[idx] = sec.geometry.loc[idx].intersection(zone).length / M_PER_MI
    return out.round(3)


def class_a_attributes(sections: pd.DataFrame, class_a: gpd.GeoDataFrame) -> pd.DataFrame:
    """Species (Fishery text) and biomass class of the Class A sections each stocked section overlaps."""
    ca = class_a.assign(rfp=class_a.RFP_WaterI, lo=class_a[["SecUpperLi", "SecLowerLi"]].min(axis=1),
                        hi=class_a[["SecUpperLi", "SecLowerLi"]].max(axis=1),
                        fishery=class_a.Fishery.str.strip().replace("", np.nan))
    rows = []
    for sid, rfp, lo, hi in zip(sections.section_id, sections.rfp_water_id, sections.lower_rm, sections.upper_rm):
        lo, hi = min(lo, hi), max(lo, hi)
        hit = ca[(ca.rfp == rfp) & ((np.minimum(hi, ca.hi) - np.maximum(lo, ca.lo)) > MIN_OVERLAP_MI)]
        text = join_unique(hit.fishery)
        low = (text or "").lower()
        rows.append({"section_id": sid, "class_a_gis_keys": join_unique(hit.GIS_Key),
                     "class_a_fishery": text, "class_a_biomass": join_unique(hit.TroutBioma),
                     "class_a_wild_brook": ("brook" in low) if text else pd.NA,
                     "class_a_wild_brown": ("brown" in low) if text else pd.NA,
                     "class_a_wild_rainbow": ("rainbow" in low) if text else pd.NA})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- sections table
def midpoint(geom) -> shapely.Point:
    line = shapely.line_merge(geom) if geom.geom_type == "MultiLineString" else geom
    if line.geom_type == "LineString":
        return line.interpolate(0.5, normalized=True)
    return line.representative_point()


def build_sections(years: dict[int, gpd.GeoDataFrame], long: pd.DataFrame, rates: pd.DataFrame,
                   wild: dict[str, gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    stacked = pd.concat(years.values(), ignore_index=True)
    latest = stacked.sort_values("year").drop_duplicates("section_id", keep="last")
    counts("union of sections across years (latest year's attributes)", len(stacked), len(latest))
    latest = gpd.GeoDataFrame(latest, geometry="geometry", crs="EPSG:4326").set_index("section_id", drop=False)

    metric = latest.geometry.to_crs(METRIC_CRS)
    mids = gpd.GeoSeries([midpoint(g) for g in metric], index=latest.index, crs=METRIC_CRS).to_crs("EPSG:4326")
    s = pd.DataFrame({
        "section_id": latest.section_id,
        "rfp_water_id": latest.RFP_WaterID.astype(int),
        "sec_num": latest.SecNum.astype(int),
        "gis_key": latest.GIS_Key,
        "water_name": latest.WtrName.str.strip(),
        "county": latest.County,
        "water_type": "stream",
        "latest_year": latest.year,
        "upper_limit": latest.SecUpper_1,
        "lower_limit": latest.SecLower_1,
        "upper_rm": latest.SecUpperLi.round(3),
        "lower_rm": latest.SecLowerLi.round(3),
        "pfbc_length_mi": latest.Length_MI_.round(3),
        "rm_length_mi": (latest.SecUpperLi - latest.SecLowerLi).abs().round(3),
        "rm_limits_reversed": latest.SecUpperLi < latest.SecLowerLi,
        "mid_lat": mids.y.round(6),
        "mid_lon": mids.x.round(6),
        "n_pieces": latest.n_pieces.fillna(1).astype(int),
        "allocation_code": latest.AllocationCode,
        "pfbc_category": latest.Description.str.strip(),
        "reg_name": latest.Reg_Name,
        "special_reg": latest.SpecReg.eq("Y"),
        "best_fishing_water": latest.Best_Fishing_Wtr.notna() & latest.Best_Fishing_Wtr.astype(str).str.strip().ne(""),
        "mentored_youth_water": latest.Mentored_Youth_Wtr.notna() & latest.Mentored_Youth_Wtr.astype(str).str.strip().ne(""),
        # "<Null>" is PFBC's own placeholder for an empty value
        "program_name": latest.Wtr_Prog_Name.where(~latest.Wtr_Prog_Name.astype(str).str.strip().isin(["", "<Null>"]),
                                                   None),
    }).reset_index(drop=True)
    # Flag sections where PFBC's Length_MI_ disagrees with PFBC's own river miles (resolved in choose_length).
    ratio = s.pfbc_length_mi / s.rm_length_mi.where(s.rm_length_mi > 0)
    s["length_check_flag"] = ~ratio.between(1 / (1 + LENGTH_CHECK_TOL), 1 + LENGTH_CHECK_TOL)
    s.loc[ratio.isna(), "length_check_flag"] = True
    for c in ("best_fishing_water", "mentored_youth_water"):
        log.info("%s: %d sections flagged (raw values: %s)", c, s[c].sum(),
                 latest[{"best_fishing_water": "Best_Fishing_Wtr", "mentored_youth_water": "Mentored_Youth_Wtr"}[c]]
                 .value_counts(dropna=False).head(5).to_dict())

    # stocking history, wide
    wide = long.pivot_table(index="section_id", columns=["species", "year"], values="count", aggfunc="sum",
                            observed=True)
    wide.columns = [f"{sp}_{yr}" for sp, yr in wide.columns]
    for y in YEARS:
        wide[f"total_{y}"] = wide[[f"{sp}_{y}" for sp in SPECIES.values()]].sum(axis=1, min_count=1)
    stocked_years = long.groupby("section_id").year.unique().map(lambda ys: ",".join(map(str, sorted(ys))))
    s = s.merge(wide.astype("Int64").reset_index(), on="section_id", how="left")
    s["years_stocked"] = s.section_id.map(stocked_years)
    s["n_years_stocked"] = s.years_stocked.str.count(",") + 1

    s = parse_allocation(s, rates)
    s = choose_length(s)

    # Wild-trout overlap: river miles on the same RFP water id (CLAUDE.md rule 8), cross-checked against
    # geometry on the same water id. Class A / Wilderness (exclusions) use river miles only. Natural
    # reproduction (a soft penalty) also counts a >= 0.5 mi geometric overlap, because some of its records'
    # river miles are shorter than their own line and Limits text (e.g. "Headwaters to Mouth").
    geoms = latest.geometry.reset_index(drop=True)
    check = s[["section_id", "water_name", "county", "lower_rm", "upper_rm"]].copy()
    for name, layer in wild.items():
        rm = river_mile_overlap(s, layer)
        geo = geometric_overlap(geoms, s.rfp_water_id, layer)
        s[f"{name}_overlap_mi"] = rm
        s[f"{name}_flag"] = rm > MIN_OVERLAP_MI
        check[f"{name}_rm_mi"], check[f"{name}_geom_mi"] = rm, geo
        disagree = (rm > MIN_OVERLAP_MI) != (geo > MIN_OVERLAP_MI)
        check[f"{name}_disagree"] = disagree
        log.info("%s: %d sections overlap > 100 m by river miles; %d by geometry; %d disagree", name,
                 (rm > MIN_OVERLAP_MI).sum(), (geo > MIN_OVERLAP_MI).sum(), disagree.sum())
        if name == "nat_repro":
            s["nat_repro_geom_overlap_mi"] = geo
            extra = ~s.nat_repro_flag & (geo >= NAT_REPRO_GEOM_MI)
            s["nat_repro_flag"] = s.nat_repro_flag | extra
            s["nat_repro_flag_source"] = np.select([rm > MIN_OVERLAP_MI, extra], ["river_miles", "geometry"], None)
            log.info("nat_repro: %d more sections flagged by >= %.1f mi same-water geometric overlap (%d total)",
                     extra.sum(), NAT_REPRO_GEOM_MI, s.nat_repro_flag.sum())
    flagged = check.filter(like="_disagree").any(axis=1)
    check[flagged].to_csv(LOG_DIR / "02_overlap_check.csv", index=False)
    log.info("wrote %d sections where the methods disagree to logs/02_overlap_check.csv", flagged.sum())

    s = s.merge(class_a_attributes(s, wild["class_a"]), on="section_id", how="left")
    return gpd.GeoDataFrame(s, geometry=geoms, crs="EPSG:4326")


# ---------------------------------------------------------------- validation and outputs
def validate(s: pd.DataFrame, long: pd.DataFrame) -> None:
    bear = long[(long.year == 2026) & long.section_id.isin(["3197_2", "3197_3"])]
    got = bear.pivot_table(index="section_id", columns="species", values="count", observed=True)
    assert got.loc["3197_2", "brown"] == 150 and got.loc["3197_2", "rainbow"] == 850, got
    assert got.loc["3197_3", "rainbow"] == 900 and got.loc["3197_3", "brown"] == 0, got
    b = s.set_index("section_id").loc[["3197_2", "3197_3"]]
    assert not b.class_a_flag.any(), "Bear Creek stocked sections must not be flagged Class A"
    assert b.nat_repro_flag.all(), "Bear Creek stocked sections must be flagged natural reproduction"
    log.info("Bear Creek (3197) checks passed: 2026 brown 150 + rainbow 1,750; not Class A; natural reproduction")
    lc = s.set_index("section_id")
    assert lc.at["322_3", "length_check_result"] == "fits_pfbc_length" and lc.at["322_3", "length_mi"] < 4, \
        "Shenango River 322_3 should keep PFBC's 3.5 mi (its river miles say 33.8)"
    assert lc.at["3117_2", "length_source"] == "river_miles" and lc.at["3117_2", "length_mi"] == 5.6, \
        "Locust Creek 3117_2 should use its 5.6 river miles (PFBC length 7.8)"
    assert lc.length_mi.notna().all() and (lc.length_mi > 0).all()
    assert s.section_id.is_unique and long.duplicated(["section_id", "year", "species"]).sum() == 0
    assert (long["count"] >= 0).all()


def write_outputs(sections: gpd.GeoDataFrame, long: pd.DataFrame, rates: pd.DataFrame,
                  wild: dict[str, gpd.GeoDataFrame]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    flat = pd.DataFrame(sections.drop(columns="geometry"))
    flat.to_parquet(PROCESSED_DIR / "sections.parquet", index=False)
    flat.to_csv(PROCESSED_DIR / "sections.csv", index=False)
    long.to_parquet(PROCESSED_DIR / "stocking_section_year.parquet", index=False)
    long.to_csv(PROCESSED_DIR / "stocking_section_year.csv", index=False)
    rates.to_csv(PROCESSED_DIR / "pfbc_stocking_rates.csv", index=False)

    gpkg = PROCESSED_DIR / "pa_trout.gpkg"
    gpkg.unlink(missing_ok=True)
    map_cols = ["section_id", "water_name", "county", "latest_year", "years_stocked", "allocation_code",
                "pfbc_category", "reg_name", "length_mi", "length_source", "total_2024", "total_2025", "total_2026",
                "class_a_flag", "nat_repro_flag", "wilderness_flag", "geometry"]
    sections[map_cols].to_file(gpkg, layer="sections", driver="GPKG")
    hatch = gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg")
    hatch = hatch[hatch.TROUT.str.lower().eq("y")]
    hatch[["NAME", "FULL_NAME", "COUNTY", "REGION", "TROUT", "WARM_COOL", "STEEL_SALM", "geometry"]].to_crs(
        "EPSG:4326").to_file(gpkg, layer="hatcheries", driver="GPKG")
    for name, layer in wild.items():  # context for maps only: simplified to 5 m to keep the file small
        simple = layer.to_crs(METRIC_CRS).simplify(CONTEXT_SIMPLIFY_M).to_crs("EPSG:4326")
        layer.assign(geometry=simple).to_file(gpkg, layer=name, driver="GPKG")
    log.info("pa_trout.gpkg: sections %d, hatcheries %d, %s; %.1f MB", len(sections), len(hatch),
             {k: len(v) for k, v in wild.items()}, gpkg.stat().st_size / 1e6)
    for p in sorted(PROCESSED_DIR.glob("*.*")):
        if p.stat().st_size > 50e6:
            log.warning("%s is %.0f MB, over the 50 MB limit for committed files", p.name, p.stat().st_size / 1e6)


def main() -> None:
    setup_logging("02_build_sections")
    years = {}
    for y in YEARS:
        g = load_year(y)
        years[y] = collapse_duplicates(g)
    long = build_stocking_long(years)
    for y in YEARS:
        raw = gpd.read_parquet(PFBC_GIS / f"stocked_{y}.parquet")[list(SPECIES)].fillna(0).sum()
        after = long[long.year == y].groupby("species", observed=True)["count"].sum()
        log.info("%d fish by species, layer sum -> after duplicate collapse: %s", y,
                 {SPECIES[k]: f"{int(v):,} -> {int(after[SPECIES[k]]):,}" for k, v in raw.items()})

    wild = {"class_a": gpd.read_parquet(PFBC_GIS / "class_a.parquet"),
            "nat_repro": gpd.read_parquet(PFBC_GIS / "nat_repro.parquet"),
            "wilderness": gpd.read_parquet(PFBC_GIS / "wilderness.parquet")}
    rates = table18()
    sections = build_sections(years, long, rates, wild)
    validate(sections, long)
    write_outputs(sections, long, rates, wild)


if __name__ == "__main__":
    main()
