"""Add the river key, PFBC region, area and river cap (the per-section density bound) to sections.

River cap (docs/model_design.md "Density bound"): max(river_rate x area_acres, 300), where river_rate is the
highest Table 18 rate over use potential and population for the section's biomass + width, and area uses the
top of the PFBC width class. The 17 Class A overlaps stocked in 2026 and the sections PFBC stocks above their
river cap are capped at their 2026 stocking instead. Exclusions are set in 05_environment.py, not here.

Inputs : data/processed/sections.parquet (02, 03), data/processed/pfbc_stocking_rates.csv (Table 18),
         data/processed/parameters.csv (widths, minimum fish, biomass-A rate),
         data/raw/pfbc_docs/<date>/summarybook.pdf (county lists by region; downloaded if missing)
Outputs: data/processed/sections.{parquet,csv}  + river_id, region, width_top_m, width_mid_m, area_acres,
                                                  area_acres_mid, river_rate, cap_source, cap_fish, cap_fish_mid,
                                                  cap_fish_class_a_river
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
COLS = ["river_id", "region", "width_top_m", "width_mid_m", "area_acres", "area_acres_mid", "river_rate",
        "cap_source", "cap_fish", "cap_fish_mid", "cap_fish_class_a_river"]

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


def add_cap(s: pd.DataFrame, params: pd.DataFrame) -> pd.DataFrame:
    rates = pd.read_csv(PROCESSED_DIR / "pfbc_stocking_rates.csv", dtype={"width_class": str})
    river = rates.groupby(["biomass_class", "width_class"]).max_trout_per_acre.max()
    s["river_rate"] = [river.get((b, w), np.nan) for b, w in zip(s.biomass_class, s.width_class)]
    a_rate = params.loc[params.parameter == "river_rate_per_acre", "value"].item()
    no_rate = s.river_rate.isna() & s.biomass_class.eq("A") & s.width_class.isin(["2", "3"])
    s.loc[no_rate, "river_rate"] = a_rate
    log.info("river_rate: Table 18 max over use and population for %d sections; biomass A at widths 2-3 "
             "(no Table 18 rate) use %d for %d sections (assumption, parameters.csv)", (~no_rate).sum(), a_rate,
             no_rate.sum())
    assert s.river_rate.notna().all(), s.loc[s.river_rate.isna(), ["section_id", "allocation_code"]]

    min_fish = params.loc[params.parameter == "min_fish_per_section", "value"].item()
    river_cap = np.maximum(s.river_rate * s.area_acres, min_fish).round()
    river_cap_mid = np.maximum(s.river_rate * s.area_acres_mid, min_fish).round()
    fish = s.total_2026.fillna(0).astype(float)
    class_a = s.class_a_flag & (fish > 0)
    over = ~class_a & (fish > river_cap)
    s["cap_source"] = np.select([class_a, over], ["class_a", "baseline"], "river_rate")
    at_2026 = s.cap_source.ne("river_rate")
    s["cap_fish"] = river_cap.where(~at_2026, fish).astype(int)
    s["cap_fish_mid"] = river_cap_mid.where(~at_2026, fish).astype(int)
    # Scenario "Class A allowed to grow": Class A sections get the river cap, but never less than today.
    s["cap_fish_class_a_river"] = s.cap_fish.where(~class_a, np.maximum(river_cap, fish)).astype(int)

    log.info("cap_source: %s", s.cap_source.value_counts().to_dict())
    for i, row in s[s.cap_source.eq("baseline")].iterrows():
        log.info("  above river cap, capped at 2026 stocking: %s %s (%s, %.2f mi): %d fish vs river cap %d",
                 row.section_id, row.water_name, row.allocation_code, row.length_mi, row.total_2026, river_cap[i])
    ca_below = class_a & (fish > river_cap)
    log.info("Class A sections whose 2026 stocking exceeds their river cap: %d %s", ca_below.sum(),
             s.loc[ca_below, "section_id"].tolist())
    stocked = fish > 0
    over_mid = stocked & ~at_2026 & (fish > river_cap_mid)
    log.info("2026-stocked sections above cap_fish: %d; above cap_fish_mid (midpoint widths; the model would "
             "have to cut them): %d", (stocked & (fish > s.cap_fish)).sum(), over_mid.sum())
    total = fish.sum()
    log.info("statewide cap vs 2026 stocking (%d fish): cap_fish %.2fx, cap_fish_mid %.2fx, "
             "cap_fish_class_a_river %.2fx", total, s.cap_fish.sum() / total, s.cap_fish_mid.sum() / total,
             s.cap_fish_class_a_river.sum() / total)

    check = s[["section_id", "water_name", "county", "allocation_code", "length_mi", "width_top_m", "width_mid_m",
               "area_acres", "area_acres_mid", "river_rate", "total_2026", "cap_source", "cap_fish",
               "cap_fish_mid", "cap_fish_class_a_river"]].assign(
        river_cap=river_cap.astype(int), river_cap_mid=river_cap_mid.astype(int),
        fish_to_river_cap=(fish / river_cap).round(3), fish_to_river_cap_mid=(fish / river_cap_mid).round(3))
    check.round({"area_acres": 2, "area_acres_mid": 2}).sort_values("fish_to_river_cap", ascending=False).to_csv(
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
    assert s.section_id.is_unique and s[COLS].drop(columns="river_id").notna().all().all()


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
