"""County anglers: resident trout-permit holders per county, from PFBC's 2024 license sales by agent county.

Follows docs/model_design.md § Angler benefit (Proximity demand, step 1). Limits of the source (store county,
not home county; online sales have no county): docs/known_gaps.md § Angler numbers by county.

    anglers = trout + combo permits sold by the county's agents (annual + multi-year sold in 2024)
              - non-resident and tourist licenses sold there (annual + multi-year)
              + online resident permits x the county's share of PA population

Every input is kept as a column, so a PFBC table of permit holders by home county can replace it later.

Inputs : data/raw/pfbc_docs/*/fishinglicensesalesbycounty2024.pdf (pages 1-2 annual, 3-4 multi-year)
         data/raw/census/*/CenPop2020_Mean_BG42.txt (2020 block-group population, summed to counties)
         data/processed/county_region.csv (04)
Outputs: data/processed/county_anglers.csv   one row per county (67)
         logs/06_county_anglers.log

    .venv/bin/python scripts/06_county_anglers.py
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import pdfplumber

from common import PROCESSED_DIR, RAW_DIR, setup_logging

log = logging.getLogger(__name__)

# Numbers are right-aligned under their headers and blank cells print nothing, so each number is assigned to
# the column whose right edge (x1, points) is nearest. Edges read off the PDF's header layout and data rows.
ANNUAL_COLS = {126: "resident", 157: "senior_resident", 187: "senior_lifetime", 217: "oneday_resident",
               247: "guard_reserve", 278: "disabled_veteran", 308: "nonresident", 338: "nonres_pa_student",
               368: "tourist_7day", 399: "tourist_3day", 429: "tourist_1day", 459: "voluntary_youth",
               490: "pow_annual", 516: "pow_lifetime", 550: "license_total", 580: "trout_permit",
               610: "erie_permit", 640: "combo_permit", 671: "permit_total"}
MULTI_COLS = {126: "res_3yr", 157: "senior_3yr", 187: "nonres_3yr", 217: "res_5yr", 247: "senior_5yr",
              278: "nonres_5yr", 308: "res_10yr", 338: "nonres_10yr", 368: "multi_license_total",
              399: "trout_3yr", 429: "erie_3yr", 459: "combo_3yr", 489: "trout_5yr", 520: "erie_5yr",
              550: "combo_5yr", 580: "trout_10yr", 610: "erie_10yr", 641: "combo_10yr",
              671: "multi_permit_total", 691: "rank", 731: "license_grand_total"}
ANNUAL_LICENSES = [c for c in list(ANNUAL_COLS.values())[:14]]
MULTI_LICENSES = list(MULTI_COLS.values())[:8]
NONRES_ANNUAL = ["nonresident", "nonres_pa_student", "tourist_7day", "tourist_3day", "tourist_1day"]
NONRES_MULTI = ["nonres_3yr", "nonres_5yr", "nonres_10yr"]
TROUT_MULTI = ["trout_3yr", "combo_3yr", "trout_5yr", "combo_5yr", "trout_10yr", "combo_10yr"]
NOT_COUNTIES = ["Out of State", "Total", "Internet", "Grand Total"]


def license_pdf() -> Path:
    found = sorted(RAW_DIR.glob("pfbc_docs/*/fishinglicensesalesbycounty2024.pdf"))
    assert found, "license sales PDF missing: see data/raw/manifest.csv for its URL"
    return found[-1]


def parse_page(page, cols: dict[int, str]) -> list[dict]:
    lines: dict[int, list] = {}
    for w in page.extract_words():
        if w["top"] >= 110:  # below the header block
            lines.setdefault(round(w["top"]), []).append(w)
    rows = []
    for words in lines.values():
        words.sort(key=lambda w: w["x0"])
        label = " ".join(w["text"] for w in words if not re.fullmatch(r"[\d,]+|--", w["text"]))
        rec: dict = {"county": label}
        for w in words:
            if re.fullmatch(r"[\d,]+", w["text"]):
                edge = min(cols, key=lambda c: abs(c - w["x1"]))
                assert abs(edge - w["x1"]) < 8, f"unplaced number {w['text']} at x1={w['x1']:.0f} ({label})"
                assert cols[edge] not in rec, f"two numbers in column {cols[edge]} ({label})"
                rec[cols[edge]] = int(w["text"].replace(",", ""))
        rows.append(rec)
    return rows


def read_sales(path: Path) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        annual = pd.DataFrame(parse_page(pdf.pages[0], ANNUAL_COLS) + parse_page(pdf.pages[1], ANNUAL_COLS))
        multi = pd.DataFrame(parse_page(pdf.pages[2], MULTI_COLS) + parse_page(pdf.pages[3], MULTI_COLS))
    tables = []
    for df, cols in ((annual, ANNUAL_COLS), (multi, MULTI_COLS)):
        df = df.set_index("county").reindex(columns=list(cols.values())).fillna(0).astype(int)  # blank cell = 0
        assert df.index.is_unique and len(df) == 67 + len(NOT_COUNTIES), (len(df), df.index.tolist())
        tables.append(df)
    annual, multi = tables
    assert annual.index.equals(multi.index)

    # every row against the PDF's own totals
    checks = {
        "annual licenses": (annual[ANNUAL_LICENSES].sum(axis=1), annual.license_total),
        "annual permits": (annual[["trout_permit", "erie_permit", "combo_permit"]].sum(axis=1), annual.permit_total),
        "multi-year licenses": (multi[MULTI_LICENSES].sum(axis=1), multi.multi_license_total),
        "multi-year permits": (multi[list(MULTI_COLS.values())[9:18]].sum(axis=1), multi.multi_permit_total),
        "license grand total": (annual.license_total + multi.multi_license_total, multi.license_grand_total),
    }
    for name, (got, want) in checks.items():
        bad = got.ne(want)
        assert not bad.any(), f"{name}: rows don't add to the PDF's total: {got[bad].index.tolist()}"
    counties = annual.index.difference(NOT_COUNTIES)
    for df in (annual, multi):
        body = df.drop(columns="rank", errors="ignore")
        assert body.loc[counties].sum().add(body.loc["Out of State"]).equals(body.loc["Total"]), "county sum != Total"
        assert body.loc["Total"].add(body.loc["Internet"]).equals(body.loc["Grand Total"]), "Total + Internet != Grand"
    log.info("license PDF parsed: 67 counties + %s; every row matches the PDF's row totals, column totals and "
             "grand totals", ", ".join(NOT_COUNTIES))
    return annual.join(multi.drop(columns="rank"))


def census_population() -> pd.DataFrame:
    path = sorted(RAW_DIR.glob("census/*/CenPop2020_Mean_BG42.txt"))[-1]
    bg = pd.read_csv(path, dtype={"STATEFP": str, "COUNTYFP": str}, encoding="utf-8-sig")
    log.info("Census 2020 block groups: %d, population %s", len(bg), f"{bg.POPULATION.sum():,}")
    return bg.groupby("COUNTYFP", as_index=False).POPULATION.sum().rename(columns={"POPULATION": "pop_2020"})


def county_names() -> pd.DataFrame:
    """County FIPS -> name, from the 2020 Census gazetteer (already downloaded with the block groups)."""
    import zipfile
    path = sorted(RAW_DIR.glob("census/*/2020_Gaz_counties_national.zip"))[-1]
    with zipfile.ZipFile(path) as z:
        gz = pd.read_csv(z.open(z.namelist()[0]), sep="\t", dtype={"GEOID": str})
    gz.columns = gz.columns.str.strip()
    gz = gz[gz.USPS.eq("PA")]
    return pd.DataFrame({"COUNTYFP": gz.GEOID.str[2:], "county": gz.NAME.str.removesuffix(" County")})


def build(sales: pd.DataFrame) -> pd.DataFrame:
    def permits_less_nonres(r: pd.Series) -> dict:
        return {
            "annual_trout_combo": r.trout_permit + r.combo_permit,
            "multi_trout_combo": r[TROUT_MULTI].sum(),
            "nonres_licenses": r[NONRES_ANNUAL].sum() + r[NONRES_MULTI].sum(),
        }

    parts = pd.DataFrame({k: permits_less_nonres(r) for k, r in sales.iterrows()}).T.astype(int)
    parts["resident_permits"] = parts.annual_trout_combo + parts.multi_trout_combo - parts.nonres_licenses

    online = parts.loc["Internet"]
    log.info("online: %s trout + combo permits (annual + multi-year) - %s non-resident and tourist licenses = %s "
             "resident permits with no county", f"{online.annual_trout_combo + online.multi_trout_combo:,}",
             f"{online.nonres_licenses:,}", f"{online.resident_permits:,}")
    oos = parts.loc["Out of State"]
    log.info("dropped: Out of State agents, %s permits - %s non-resident licenses = %s (not PA residents)",
             f"{oos.annual_trout_combo + oos.multi_trout_combo:,}", f"{oos.nonres_licenses:,}",
             f"{oos.resident_permits:,}")

    pop = census_population().merge(county_names(), on="COUNTYFP", how="outer", validate="1:1")
    assert pop.notna().all().all() and len(pop) == 67
    # the PDF prints "Mckean", the Census "McKean": match case-insensitively
    counties = parts.drop(index=NOT_COUNTIES).rename(index=str.lower)
    df = pop.assign(key=pop.county.str.lower()).merge(counties, left_on="key", right_index=True, how="outer",
                                                      validate="1:1", indicator=True)
    assert df._merge.eq("both").all(), df[df._merge.ne("both")]
    df = df.drop(columns=["_merge", "key"])
    neg = df.resident_permits.lt(0)
    assert not neg.any(), f"more non-resident licenses than permits: {df.loc[neg, 'county'].tolist()}"

    df["pop_share"] = df.pop_2020 / df.pop_2020.sum()
    df["online_permits"] = online.resident_permits * df.pop_share
    df["anglers"] = df.resident_permits + df.online_permits
    df["angler_rate"] = df.anglers / df.pop_2020
    # sensitivity (known_gaps.md): online permits split like the county's store sales instead of by population
    df["online_permits_by_sales"] = online.resident_permits * df.resident_permits / df.resident_permits.sum()
    df["anglers_by_sales"] = df.resident_permits + df.online_permits_by_sales
    df["angler_rate_by_sales"] = df.anglers_by_sales / df.pop_2020

    # county names as the rest of the project spells them (title case from PFBC: "Mckean")
    regions = pd.read_csv(PROCESSED_DIR / "county_region.csv")[["county", "region"]]
    regions["key"] = regions.county.str.lower()
    df = df.assign(key=df.county.str.lower()).drop(columns="county").merge(regions, on="key", how="left",
                                                                           validate="1:1").drop(columns="key")
    assert df.region.notna().all()
    df["county_fips"] = "42" + df.COUNTYFP
    cols = ["county", "county_fips", "region", "pop_2020", "annual_trout_combo", "multi_trout_combo",
            "nonres_licenses", "resident_permits", "pop_share", "online_permits", "anglers", "angler_rate",
            "online_permits_by_sales", "anglers_by_sales", "angler_rate_by_sales"]
    df = df[cols].sort_values("county").reset_index(drop=True)
    total = parts.drop(index=NOT_COUNTIES).resident_permits.sum() + online.resident_permits
    assert abs(df.anglers.sum() - total) < 1e-6 and abs(df.anglers_by_sales.sum() - total) < 1e-6
    return df


def main() -> None:
    setup_logging("06_county_anglers")
    df = build(read_sales(license_pdf()))
    state_rate = df.anglers.sum() / df.pop_2020.sum()
    log.info("resident anglers: %s (population %s, %.1f per 100 residents)", f"{df.anglers.sum():,.0f}",
             f"{df.pop_2020.sum():,}", 100 * state_rate)
    q = (df.angler_rate / state_rate).quantile([0, 0.1, 0.5, 0.9, 1]).round(2).tolist()
    log.info("county angler rate / state rate, min-p10-median-p90-max: %s", q)
    log.info("lowest: %s", df.nsmallest(3, "angler_rate")[["county", "angler_rate"]].round(3).values.tolist())
    log.info("highest: %s", df.nlargest(3, "angler_rate")[["county", "angler_rate"]].round(3).values.tolist())
    by_region = df.groupby("region").agg(pop=("pop_2020", "sum"), anglers=("anglers", "sum"))
    log.info("by region:\n%s", by_region.assign(share=by_region.anglers / by_region.anglers.sum(),
                                                 rate=by_region.anglers / by_region["pop"]).round(3).to_string())
    rates = ["pop_share", "angler_rate", "angler_rate_by_sales"]
    df.round(1).assign(**df[rates].round(6)).to_csv(PROCESSED_DIR / "county_anglers.csv", index=False)
    log.info("wrote county_anglers.csv: %d rows", len(df))


if __name__ == "__main__":
    main()
