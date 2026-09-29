"""Add the river key, PFBC region, area and density cap (the per-section density bound) to sections.

Density cap (docs/model_design.md "Density bound"; revised 2026-09-27): cap_fish = max(cap_rate x area_acres,
300), with area at the top of the PFBC width class. cap_rate is the higher of
  access_rate   the highest Table 18 rate for the section's biomass + width at its own recreational use potential
                (access) or any worse one, over all population classes, and
  program_rate  the Guidelines' own rate for a special program (Delayed Harvest Artificial Lures Only, Table 46;
                tailwaters, Table 45), NA otherwise.
The 17 Class A overlaps stocked in 2026 and the sections PFBC stocks above their cap are capped at their 2026
stocking instead. The river cap (cap_rate_river: Table 18 at any access, or the program rate) is kept as the
looser sensitivity. Exclusions are set in 05_environment.py, not here.

Inputs : data/processed/sections.parquet (02, 03), data/processed/pfbc_stocking_rates.csv (Table 18),
         data/processed/parameters.csv (widths, minimum fish, biomass-A rate),
         data/raw/pfbc_docs/<date>/summarybook.pdf (county lists by region; downloaded if missing)
Outputs: data/processed/sections.{parquet,csv}  + river_id, region, width_top_m, width_mid_m, area_acres,
                                                  area_acres_mid, program, program_rate, access_rate,
                                                  cap_rate, cap_rate_river, cap_source, cap_fish,
                                                  cap_fish_mid, cap_fish_river, cap_fish_class_a_grow
         data/processed/county_region.csv       the 67 counties and their PFBC region
         logs/04_river_cap.log, logs/04_cap_check.csv (2026 stocking vs cap for every section)

    .venv/bin/python scripts/04_river_cap.py      (run after 03_coop_stockings.py)
"""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pdfplumber

from common import LOG_DIR, PROCESSED_DIR, RAW_DIR, PoliteSession, save_raw, setup_logging

SUMMARY_BOOK_URL = ("https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/fishing/regulations/"
                    "summarybook.pdf")
N_COUNTIES = 67
NOT_COUNTIES = {"DAY"}  # "OPENING DAY:" is the only other all-caps label in the region lists
M_PER_MI = 1609.344
M2_PER_ACRE = 4046.8564224
ACRES_PER_MI_M = M_PER_MI / M2_PER_ACRE  # a section 1 mi long and 1 m wide covers 0.398 acres
USE_RANK = {"L": 0, "G": 1, "H": 2}  # Table 18 recreational use potential (access), worst to best
# Special-program rates (trout/acre/yr) that PFBC uses instead of Table 18 for their sections (Operational
# Guidelines 5th ed.): Table 46, Delayed Harvest Artificial Lures Only Areas (pdf p. 85), by width class, and
# Table 45, tailwater trout fisheries (pdf p. 80; sections <= 2 mi), by recreational use potential.
DHALO_RATE = {"2": 190, "3": 190, "1S": 133, "1L": 133}
TAILWATER_RATE = {"H": 266, "G": 247}
# No PFBC layer flags tailwaters. Table 45 needs a section <= 2 mi directly below a major reservoir's cold-water
# outflow: the Youghiogheny below the Youghiogheny River Lake dam, and Conneauttee Creek below the Edinboro Lake
# dam (team knowledge, 2026-09-28). Other dam sections checked: docs/known_gaps.md "Tailwater sections".
TAILWATERS = {"1327_1", "2649_1"}
COLS = ["river_id", "region", "width_top_m", "width_mid_m", "area_acres", "area_acres_mid", "program",
        "program_rate", "access_rate", "cap_rate", "cap_rate_river", "cap_source", "cap_fish", "cap_fish_mid", "cap_fish_river",
        "cap_fish_class_a_grow"]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- region
def summary_book() -> Path:
    found = sorted(RAW_DIR.glob("pfbc_docs/*/summarybook.pdf"))
    if found:
        return found[-1]
    r = PoliteSession().get(SUMMARY_BOOK_URL)
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        n_pages = len(pdf.pages)
    return save_raw("pfbc_docs", "summarybook.pdf", r.content, SUMMARY_BOOK_URL, records=n_pages)


def county_regions(path: Path) -> pd.DataFrame:
    """County -> PFBC region from the summary book's regulated trout waters lists.

    Each page is headed "TROUT FISHING <REGION> REGION"; where one region's list ends mid-page the header names
    both, and the "<Region> Region Regulated Trout Waters" subheading splits the page. Waters are listed under
    county labels like "BERKS:". Two-county labels ("MIFFLIN/UNION:") are boundary waters listed in both
    regions, so only single-county labels count.
    """
    rows = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            regions = re.findall(r"TROUT FISHING (\w+) REGION", (page.extract_text() or "").split("\n")[0])
            if not regions:
                continue
            words = page.extract_words()
            split = [w["top"] for w, nxt in zip(words, words[1:]) if w["text"] == "Region" and nxt["text"] == "Regulated"]
            for w in words:
                label = re.fullmatch(r"([A-Z]{2}[A-Za-z]*):", w["text"])
                if not label or label.group(1) in NOT_COUNTIES:
                    continue
                second = len(regions) > 1 and bool(split) and w["top"] >= split[-1] - 2
                rows.append({"county": label.group(1).title(), "region": regions[-1 if second else 0].title(),
                             "pdf_page": page_no})
    d = pd.DataFrame(rows)
    per = d.groupby("county").region.unique()
    conflicts = per[per.map(len) > 1]
    assert conflicts.empty, f"counties listed under more than one region: {conflicts.to_dict()}"
    assert len(per) == N_COUNTIES, f"found {len(per)} counties, expected {N_COUNTIES}: {sorted(per.index)}"
    out = per.map(lambda r: r[0]).rename("region").reset_index()
    out["source"] = f"PFBC 2026 Pennsylvania Fishing Summary, regulated trout waters by region ({path.name})"
    log.info("county -> region from %s: %d labels, %d counties; counties per region %s", path.name, len(d),
             len(out), out.region.value_counts().sort_index().to_dict())
    return out


def add_region(s: pd.DataFrame, cr: pd.DataFrame) -> pd.DataFrame:
    lookup = cr.set_index("county").region
    regions = s.county.str.split("; ").map(lambda cs: sorted({lookup[c] for c in cs}))
    two = regions.map(len) > 1
    assert not two.any(), f"sections spanning two regions: {s.loc[two, 'section_id'].tolist()}"
    s["region"] = regions.str[0]
    log.info("sections per region: %s", s.region.value_counts().sort_index().to_dict())
    return s


# ---------------------------------------------------------------- river key
def add_river_id(s: pd.DataFrame) -> pd.DataFrame:
    s["river_id"] = s.rfp_water_id
    names = s.groupby("river_id").water_name.unique()
    multi = names[names.map(len) > 1]
    log.info("river_id with more than one water_name: %d %s", len(multi), multi.map(list).to_dict())
    by_county = s.assign(c=s.county.str.split("; ")).explode("c").groupby(["water_name", "c"]).river_id.unique()
    shared = by_county[by_county.map(len) > 1]
    log.info("water_name + county with more than one river_id: %d %s", len(shared), shared.map(list).to_dict())
    log.info("river_id: %d rivers for %d sections", s.river_id.nunique(), len(s))
    return s


# ---------------------------------------------------------------- area and cap
def parameters() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "parameters.csv", dtype={"applies_to": str})


def add_area(s: pd.DataFrame, params: pd.DataFrame) -> pd.DataFrame:
    width = params[params.parameter == "width_m"].set_index("applies_to")
    s["width_top_m"] = s.width_class.map(width.value)
    s["width_mid_m"] = s.width_class.map(width.low)
    assert s[["width_top_m", "width_mid_m"]].notna().all().all()
    s["area_acres"] = s.length_mi * s.width_top_m * ACRES_PER_MI_M
    s["area_acres_mid"] = s.length_mi * s.width_mid_m * ACRES_PER_MI_M
    return s


def table18_caps(s: pd.DataFrame, params: pd.DataFrame) -> pd.DataFrame:
    """Two cap rates from Table 18 for each section's biomass + width, both ignoring population:
    access_rate = highest rate at the section's own access rating or any worse one (the default cap), and
    cap_rate_river = highest rate at any access (the looser sensitivity; add_cap folds in program rates)."""
    rates = pd.read_csv(PROCESSED_DIR / "pfbc_stocking_rates.csv", dtype={"width_class": str})
    rates["use_rank"] = rates.use_code.map(USE_RANK)
    s["use_rank"] = s.allocation_code.str[1].map(USE_RANK)
    assert rates.use_rank.notna().all() and s.use_rank.notna().all()
    river = rates.groupby(["biomass_class", "width_class"]).max_trout_per_acre.max()
    # Highest rate at each access level, then carried up so better access never lowers it (Table 18 gives
    # biomass B + High at widths 2-3 a flat 147 but B + Good up to 323; model_design.md "Density bound")
    by_use = (rates.groupby(["biomass_class", "width_class", "use_rank"]).max_trout_per_acre.max()
              .groupby(level=[0, 1]).cummax())
    s["cap_rate_river"] = [river.get((b, w), np.nan) for b, w in zip(s.biomass_class, s.width_class)]
    s["access_rate"] = [by_use.get((b, w, u), np.nan) for b, w, u in zip(s.biomass_class, s.width_class,
                                                                      s.use_rank)]
    own = rates.groupby(["biomass_class", "width_class", "use_rank"]).max_trout_per_acre.max()
    lifted = [(b, w, u) for b, w, u in zip(s.biomass_class, s.width_class, s.use_rank)
              if (b, w, u) in own.index and own[(b, w, u)] < by_use[(b, w, u)]]
    log.info("access_rate above the section's own access row (better access never lowers the cap): %d "
             "sections %s", len(lifted), pd.Series(lifted).value_counts().to_dict())

    a_rate = params.loc[params.parameter == "biomass_a_rate_per_acre", "value"].item()
    no_rate = s.cap_rate_river.isna() & s.biomass_class.eq("A") & s.width_class.isin(["2", "3"])
    assert not (no_rate & s.use_rank.eq(USE_RANK["L"])).any(), "biomass-A Low access at widths 2-3: no rule"
    s.loc[no_rate, ["cap_rate_river", "access_rate"]] = a_rate
    log.info("cap_rate_river / access_rate: Table 18 for %d sections; biomass A at widths 2-3 (no Table 18 rate, "
             "all Good or High access) use %d for %d sections (assumption, parameters.csv)", (~no_rate).sum(),
             a_rate, no_rate.sum())
    assert s[["cap_rate_river", "access_rate"]].notna().all().all(), \
        s.loc[s.access_rate.isna(), ["section_id", "allocation_code"]]
    assert (s.access_rate <= s.cap_rate_river).all()
    log.info("access_rate below cap_rate_river: %s", s[s.access_rate < s.cap_rate_river].use_potential.value_counts()
             .to_dict())
    return s.drop(columns="use_rank")


def program_rates(s: pd.DataFrame) -> pd.DataFrame:
    """PFBC's own rate for sections in a special program (Tables 45-46), NA for the rest."""
    dhalo = s.reg_name.fillna("").str.contains("Delayed Harvest")
    tail = s.section_id.isin(TAILWATERS)
    assert not (dhalo & tail).any() and tail.sum() == len(TAILWATERS)
    s["program"] = pd.Series(np.select([tail, dhalo], ["tailwater", "DHALO"], ""), index=s.index).replace("", pd.NA)
    s["program_rate"] = pd.array(np.select([tail, dhalo], [s.allocation_code.str[1].map(TAILWATER_RATE),
                                                          s.width_class.map(DHALO_RATE)], np.nan), dtype="Float64")
    assert s.program_rate.notna().eq(s.program.notna()).all(), s.loc[s.program.notna() & s.program_rate.isna()]
    log.info("program rates (Guidelines Tables 45-46): %s; above the Table 18 access rate for %d sections",
             s.program.value_counts().to_dict(), (s.program_rate > s.access_rate).fillna(False).sum())
    return s


def add_cap(s: pd.DataFrame, params: pd.DataFrame) -> pd.DataFrame:
    s = program_rates(table18_caps(s, params))
    min_fish = params.loc[params.parameter == "min_fish_per_section", "value"].item()
    # A special program's rate counts as a rate PFBC's rules allow, so the cap uses whichever is higher
    s["cap_rate"] = np.fmax(s.access_rate, s.program_rate.astype(float))
    s["cap_rate_river"] = np.fmax(s.cap_rate_river, s.program_rate.astype(float))
    rate_cap = np.maximum(s.cap_rate * s.area_acres, min_fish).round()
    rate_cap_mid = np.maximum(s.cap_rate * s.area_acres_mid, min_fish).round()
    river_cap = np.maximum(s.cap_rate_river * s.area_acres, min_fish).round()
    fish = s.total_2026.fillna(0).astype(float)
    class_a = s.class_a_flag & (fish > 0)
    over = ~class_a & (fish > rate_cap)
    by_program = s.program_rate.astype(float).gt(s.access_rate).to_numpy()
    s["cap_source"] = np.select([class_a, over, by_program], ["class_a", "baseline", "program_rate"], "access_rate")
    at_2026 = s.cap_source.isin(["class_a", "baseline"])
    s["cap_fish"] = rate_cap.where(~at_2026, fish).astype(int)
    s["cap_fish_mid"] = rate_cap_mid.where(~at_2026, fish).astype(int)
    # Sensitivity "river cap": ignore access too. Class A stays at today; sections above it keep today's count.
    s["cap_fish_river"] = np.maximum(river_cap, fish).where(~class_a, fish).astype(int)
    # Scenario "Class A allowed to grow": Class A sections get the normal cap, but never less than today.
    s["cap_fish_class_a_grow"] = s.cap_fish.where(~class_a, np.maximum(rate_cap, fish)).astype(int)

    log.info("cap_source: %s", s.cap_source.value_counts().to_dict())
    for i, row in s[s.cap_source.eq("baseline")].iterrows():
        log.info("  above the cap, capped at 2026 stocking: %s %s (%s, %.2f mi): %d fish vs cap %d, "
                 "river cap %d", row.section_id, row.water_name, row.allocation_code, row.length_mi,
                 row.total_2026, rate_cap[i], river_cap[i])
    ca_below = class_a & (fish > rate_cap)
    log.info("Class A sections whose 2026 stocking exceeds their cap: %d %s", ca_below.sum(),
             s.loc[ca_below, "section_id"].tolist())
    stocked = fish > 0
    over_mid = stocked & ~at_2026 & (fish > rate_cap_mid)
    log.info("2026-stocked sections above cap_fish: %d; above cap_fish_mid (midpoint widths; the model would "
             "have to cut them): %d", (stocked & (fish > s.cap_fish)).sum(), over_mid.sum())
    total = fish.sum()
    log.info("statewide cap vs 2026 stocking (%d fish): cap_fish %.2fx, cap_fish_mid %.2fx, cap_fish_river "
             "%.2fx, cap_fish_class_a_grow %.2fx", total, s.cap_fish.sum() / total, s.cap_fish_mid.sum() / total,
             s.cap_fish_river.sum() / total, s.cap_fish_class_a_grow.sum() / total)

    check = s[["section_id", "water_name", "county", "allocation_code", "length_mi", "width_top_m", "width_mid_m",
               "area_acres", "area_acres_mid", "program", "program_rate", "access_rate", "cap_rate", "cap_rate_river",
               "total_2026", "cap_source", "cap_fish", "cap_fish_mid", "cap_fish_river",
               "cap_fish_class_a_grow"]].assign(
        rate_cap=rate_cap.astype(int), rate_cap_mid=rate_cap_mid.astype(int),
        fish_to_cap=(fish / rate_cap).round(3), fish_to_cap_mid=(fish / rate_cap_mid).round(3))
    check.round({"area_acres": 2, "area_acres_mid": 2}).sort_values("fish_to_cap", ascending=False).to_csv(
        LOG_DIR / "04_cap_check.csv", index=False)
    log.info("wrote logs/04_cap_check.csv (%d sections)", len(check))
    s["area_acres"], s["area_acres_mid"] = s.area_acres.round(3), s.area_acres_mid.round(3)
    return s


# ---------------------------------------------------------------- main
def validate(s: pd.DataFrame) -> None:
    bear = s.set_index("section_id").loc[["3197_2", "3197_3"]]
    assert (bear.river_id == 3197).all(), "Bear Creek (Schuylkill) sections must share river_id 3197"
    assert bear.region.eq("Southeast").all(), bear.region  # Schuylkill County
    log.info("Bear Creek (3197) checks passed: river_id 3197, Southeast")
    assert s.section_id.is_unique and s[COLS].drop(columns=["river_id", "program", "program_rate"]).notna().all().all()


def main() -> None:
    setup_logging("04_river_cap")
    s = pd.read_parquet(PROCESSED_DIR / "sections.parquet").drop(columns=COLS, errors="ignore")
    n = len(s)
    cr = county_regions(summary_book())
    cr.to_csv(PROCESSED_DIR / "county_region.csv", index=False)
    s = add_river_id(s)
    s = add_region(s, cr)
    params = parameters()
    s = add_area(s, params)
    s = add_cap(s, params)
    assert len(s) == n
    validate(s)
    s.to_parquet(PROCESSED_DIR / "sections.parquet", index=False)
    s.to_csv(PROCESSED_DIR / "sections.csv", index=False)
    log.info("sections: %d rows, %d columns", len(s), s.shape[1])


if __name__ == "__main__":
    main()
