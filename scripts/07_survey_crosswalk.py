"""Match the 2023 angler survey's favorite waters (p76-77) to PFBC rivers stocked in 2026 (Prompt 6 step 3).

Follows docs/model_design.md § Angler benefit (Preference demand). A water matches a river_id by name, restricted
to the named county when the survey gives one. Several candidates are resolved with the by-home-region table
(p78-83): each home region's mentions go to the candidate in that region when there is exactly one. Unmatched
waters are safe (their share goes to the unplaced pool, spread like proximity demand); a wrong match is not, so
anything unclear goes to the review file with river_id NA.

Downstream: a row with a river_id and n_sections_2026 > 0 places pct x match_share on that river's 2026 sections
by length; everything else (lakes, unplaced, review, not_stocked_2026, no_pfbc_section) goes to the unplaced pool.

Inputs : data/processed/angler_survey/p76-77_preferred_waters_overall.csv, p78-83_preferred_waters_by_region.csv
         data/processed/sections.parquet (02, 04), data/processed/county_anglers.csv (06, region weights)
         data/processed/parameters.csv (survey_pct_below_half)
Outputs: data/processed/survey_water_crosswalk.csv   one row per (waterbody, river_id)
         logs/07_survey_crosswalk.log, logs/07_survey_crosswalk_review.csv

    .venv/bin/python scripts/07_survey_crosswalk.py      (run after 06_county_anglers.py)
"""
from __future__ import annotations

import logging
import re

import pandas as pd

from common import LOG_DIR, PROCESSED_DIR, setup_logging

SURVEY_DIR = PROCESSED_DIR / "angler_survey"
REGIONS = {"northwest": "Northwest", "northcentral": "Northcentral", "northeast": "Northeast",
           "southwest": "Southwest", "southcentral": "Southcentral", "southeast": "Southeast"}
ABBREVIATIONS = {"br": "branch", "w": "west", "e": "east", "n": "north", "s": "south", "cr": "creek", "ck": "creek",
                 "crk": "creek", "rn": "run", "fk": "fork"}
LAKE_WORDS = re.compile(r"\b(lakes?|reservoir|pond|dam)\b", re.I)
BRANCH_PREFIXES = {f"{a}{b}" for a in ("east", "west", "north", "south", "middle") for b in ("branch", "fork")}
SURVEY_COUNTY_FIXES = {"Schuykill": "Schuylkill"}  # report spelling
NO_RIVER = {"Other", "Do not know"}
# Matching thresholds (method choices, not model parameters). Own-region share = share of the water's resident
# mentions that come from the river's own region(s); p85 says 67-88% of each region's mentions are at home.
OWN_HIGH, OWN_LOW = 0.5, 0.25
SPLIT_RESOLVED_MIN = 0.8   # of mentions from regions holding any candidate, share where exactly one does
SPLIT_ATTRIBUTED_MIN = 0.5  # and at least half of all the water's mentions get a candidate
SPLIT_DROP_BELOW = 0.10    # a candidate attributed < 10% of the water's mentions is dropped

# Decisions by clear evidence: waterbody -> (river_id, confidence, reason).
MANUAL = {
    "Raystown Branch": (2968, "high", "survey shortens PFBC's 'Raystown Branch Juniata River', the only Raystown "
                                      "Branch; mentions come from Southwest + Southcentral, its two regions"),
    "Big Swickley Creek": (1707, "medium", "survey misspelling of Big Sewickley Creek (Allegheny), the only Big "
                                           "Sewickley; all mentions from the Southwest, its region"),
}
# Name matches judged doubtful, sent to review instead: waterbody -> (other PFBC river_ids to show, why, hint).
SEND_TO_REVIEW = {
    "Bush Kill": ([653], "PFBC also stocks Bushkill Creek 653 (Northampton, SE); 89% of mentions are from SE "
                         "anglers, and 'Bush Kill' may stand for either",
                  "regional split: 2436 (NE mentions) 11% / 653 (SE mentions) 89%"),
    "Little Bush Kill": ([1355], "PFBC also stocks Little Bushkill Creek 1355 (Northampton, SE); 87% of mentions "
                                 "are from SE anglers", "regional split: 2435 (NE) 13% / 1355 (SE) 87%"),
    "Little Beaver Creek": ([300], "72% of mentions are from NW/SW anglers, where the Little Beaver Creek system "
                                  "is (PFBC stocks North Fork Little Beaver Creek 300, Beaver)",
                            "282 for the SE share only, rest unplaced; or split 282/300"),
    "Raccoon Creek": ([], "all mentions from the Southwest; PFBC's only Raccoon Creek is Perry's (SC)",
                      "leave unplaced (a SW Raccoon Creek with no PFBC section)"),
    "Big Sandy Creek": ([2368], "all mentions from the Northwest; PFBC's Big Sandy Creek is Fayette's (SW)",
                        "leave unplaced (maybe Sandy Creek 2368, Venango)"),
    "Little Mahoney Creek": ([78, 3818], "no PFBC water of this name; reads as Little Mahoning Creek 78 (Indiana, "
                                         "SW) or Little Mahanoy Creek 3818 (Schuylkill, SE)",
                             "78: all resident mentions are from the Southwest"),
}

log = logging.getLogger(__name__)


def name_key(name) -> str:
    """Lowercase, drop PFBC suffixes ("Mill Creek (Warrensville)", "- hillsgrove", "@Bowmansville"), expand
    abbreviations and drop spaces, so "Twenty Mile" = "Twentymile" and "Blue Jay" = "Bluejay"."""
    n = re.sub(r"\(.*?\)|\s+-\s+.*$|@.*$", " ", str(name).lower())
    return "".join(ABBREVIATIONS.get(w, w) for w in re.findall(r"[a-z0-9]+", n))


def load_rivers() -> pd.DataFrame:
    s = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    s["stocked26"] = s.total_2026.fillna(0).gt(0)
    s["mi26"] = s.length_mi.where(s.stocked26, 0.0)
    s["counties"] = s.county.str.split("; ")
    r = s.groupby("river_id").agg(
        water_name=("water_name", "first"), counties=("counties", lambda c: sorted({x for l in c for x in l})),
        regions=("region", lambda x: sorted(set(x))), stocked_mi_2026=("mi26", "sum"),
        n_sections_2026=("stocked26", "sum"), lake_erie=("reg_name", lambda x: x.str.contains("Lake Erie").any()))
    r["key"] = r.water_name.map(name_key)
    r["stocked_mi_2026"] = r.stocked_mi_2026.round(3)
    log.info("rivers: %d in sections.parquet, %d with a 2026-stocked section (%d sections)", len(r),
             r.n_sections_2026.gt(0).sum(), s.stocked26.sum())
    return r


def load_survey() -> tuple[pd.DataFrame, pd.DataFrame]:
    p = pd.read_csv(SURVEY_DIR / "p76-77_preferred_waters_overall.csv")
    reg = pd.read_csv(SURVEY_DIR / "p78-83_preferred_waters_by_region.csv").set_index("waterbody")
    assert p.waterbody.is_unique and set(p.waterbody) <= set(reg.index)
    log.info("survey waters: %d rows in p76-77; regional table rows not in p76-77 (ignored): %s", len(p),
             sorted(set(reg.index) - set(p.waterbody)))
    par = pd.read_csv(PROCESSED_DIR / "parameters.csv").set_index("parameter")
    p["pct"] = p.pct_overall.where(~p.lt_0_5_pct, float(par.at["survey_pct_below_half", "value"]))
    a = pd.read_csv(PROCESSED_DIR / "county_anglers.csv")
    w = a.groupby("region").anglers.sum() / a.anglers.sum()
    log.info("region weights (share of resident anglers): %s", w.round(3).to_dict())
    mentions = reg[list(REGIONS)].rename(columns=REGIONS).mul(w)  # pct_R x w_R; nonresidents left out
    return p, mentions


def own_share(regions: list[str], m: pd.Series) -> float | None:
    return None if m.sum() == 0 else float(m[regions].sum() / m.sum())


def attribute(cands: pd.DataFrame, m: pd.Series) -> tuple[dict, float, float]:
    """Each home region's mentions go to the candidate lying there when exactly one does."""
    got, resolved, ambiguous = {rid: 0.0 for rid in cands.index}, 0.0, 0.0
    for region, v in m.items():
        ids = [rid for rid, regs in cands.regions.items() if region in regs]
        if len(ids) == 1:
            got[ids[0]] += v
            resolved += v
        elif len(ids) > 1:
            ambiguous += v
    total = m.sum()
    return {k: v / total for k, v in got.items()}, resolved / total, ambiguous / total


def match_water(w, rivers: pd.DataFrame, m: pd.Series, survey_keys: set) -> list[dict]:
    """Rows for one survey water: dicts with river_id, match_share, match_method, confidence, note (+ review info)."""
    one = lambda **k: [{"river_id": pd.NA, "match_share": pd.NA, **k}]
    if w.waterbody in NO_RIVER:
        return one(water_type="unplaced", match_method="unplaced", confidence="high", note="not a named water")
    if w.county_qualifier == "Lake" or LAKE_WORDS.search(w.waterbody):
        return one(water_type="lake", match_method="lake", confidence="high", note="lake: not in the section set")
    if w.county_qualifier == "other/unsure":
        return one(water_type="stream", match_method="unplaced", confidence="high", note="county not given")
    if w.waterbody in MANUAL:
        rid, conf, why = MANUAL[w.waterbody]
        return [{"river_id": rid, "match_share": 1.0, "water_type": "stream", "match_method": "manual",
                 "confidence": conf, "note": why}]
    review = lambda why, hint, ids: one(water_type="stream", match_method="review", confidence=pd.NA, note=why,
                                        _hint=hint, _cands=ids)
    cands = rivers[rivers.key == name_key(w.name_base)]
    if w.waterbody in SEND_TO_REVIEW:
        extra, why, hint = SEND_TO_REVIEW[w.waterbody]
        return review(why, hint, list(cands.index) + extra)
    if isinstance(w.county_qualifier, str):
        counties = {SURVEY_COUNTY_FIXES.get(c, c) for c in re.split(r"\s+or\s+|,\s*|\s+and\s+", w.county_qualifier)}
        named = cands[cands.counties.map(lambda cs: bool(counties & set(cs)))]
        if named.empty and len(cands):
            return review(f"no PFBC {w.name_base} in {' / '.join(sorted(counties))} County",
                          "leave unplaced", list(cands.index))
        if len(named) == 1:
            return [river_row(named.iloc[0], named.index[0], 1.0, "name_county", "high",
                              "county qualifier pins one river")]
        cands = named
    if cands.empty:
        branches = [rid for rid, k in rivers.key.items() if k.endswith(name_key(w.name_base))
                    and k[: -len(name_key(w.name_base))] in BRANCH_PREFIXES and k not in survey_keys]
        if branches:
            return review("no PFBC section on the main stem; its branches are stocked and not listed in the survey",
                          "split over the branches by stocked miles, or leave unplaced", branches)
        return one(water_type="stream", match_method="no_pfbc_section", confidence="high",
                   note="no PFBC stocked section of this name in 2024-26")
    if len(cands) == 1:
        rid, c = cands.index[0], cands.iloc[0]
        share = own_share(c.regions, m)
        if share is None:
            return [river_row(c, rid, 1.0, "unique_name", "medium", "unique name; no regional mentions to check")]
        conf = "high" if share >= OWN_HIGH else "medium" if share >= OWN_LOW else "low"
        note = "unique name" + ("" if conf == "high" else f"; its region supplies {share:.0%} of resident mentions")
        return [river_row(c, rid, 1.0, "unique_name", conf, note)]
    if m.sum() == 0:
        return review(f"{len(cands)} rivers of this name and no regional mentions", "leave unplaced", list(cands.index))
    got, resolved, ambiguous = attribute(cands, m)
    if resolved / max(resolved + ambiguous, 1e-9) >= SPLIT_RESOLVED_MIN and resolved >= SPLIT_ATTRIBUTED_MIN:
        keep = {k: v for k, v in got.items() if v >= SPLIT_DROP_BELOW}
        dropped = [f"{k} ({v:.0%})" for k, v in got.items() if 0 < v < SPLIT_DROP_BELOW]
        tot = sum(keep.values())
        conf = "high" if len(keep) == 1 and tot >= SPLIT_RESOLVED_MIN else "medium"
        note = (f"home regions attribute {resolved:.0%} of mentions" + (f"; dropped {', '.join(dropped)}" if dropped
                else ""))
        return [river_row(cands.loc[k], k, v / tot, "regional_split", conf, note) for k, v in keep.items()]
    same_region = len({r for regs in cands.regions for r in regs}) == 1
    hint = ("split by stocked miles (all candidates in one region)" if same_region else
            "leave unplaced" if resolved < 0.3 else
            "; ".join(f"{k} gets {v:.0%}" for k, v in got.items() if v > 0) + "; rest unplaced")
    return review(f"{len(cands)} rivers of this name; home regions resolve only {resolved:.0%} of mentions "
                  f"({ambiguous:.0%} from regions with 2+ candidates)", hint, list(cands.index))


def river_row(c, rid, share, method, conf, note) -> dict:
    if c.n_sections_2026 == 0:
        method, note = "not_stocked_2026", f"{note}; river not stocked in 2026 -> unplaced ({method})"
    if c.lake_erie:
        note += "; Lake Erie tributary"
    return {"river_id": rid, "match_share": share, "water_type": "stream", "match_method": method,
            "confidence": conf, "note": note}


def build(p: pd.DataFrame, mentions: pd.DataFrame, rivers: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    survey_keys = set(p.name_base.map(name_key))
    rows, review = [], []
    for w in p.itertuples():
        m = mentions.loc[w.waterbody]
        for r in match_water(w, rivers, m, survey_keys):
            ids, hint = r.pop("_cands", None), r.pop("_hint", "")
            rows.append({"waterbody": w.waterbody, "name_base": w.name_base, "county_qualifier": w.county_qualifier,
                         "pct_overall": w.pct_overall, "lt_0_5_pct": w.lt_0_5_pct, **r})
            if r["match_method"] == "review" or r["confidence"] == "low":
                ids = ids if ids is not None else [r["river_id"]]
                cand = " | ".join(f"{i}: {rivers.at[i, 'water_name']}, {'/'.join(rivers.at[i, 'counties'])}, "
                                  f"{'/'.join(rivers.at[i, 'regions'])}, {rivers.at[i, 'stocked_mi_2026']:.1f} mi 2026"
                                  for i in ids)
                review.append({"waterbody": w.waterbody, "pct": w.pct,
                               "status": "unresolved" if r["match_method"] == "review" else "low-confidence match",
                               "candidates": cand, "regional_pct_by_home_region": regional_text(w.waterbody), "why": r["note"],
                               "hint": hint or "keep if the name is unique in PA, else leave unplaced"})
    cw = pd.DataFrame(rows)
    cw = cw.merge(rivers[["water_name", "stocked_mi_2026", "n_sections_2026"]].assign(
        river_region=rivers.regions.map("; ".join)), left_on="river_id", right_index=True, how="left")
    cw["river_id"] = cw.river_id.astype("Int64")
    cw["n_sections_2026"] = cw.n_sections_2026.astype("Int64")
    cols = ["waterbody", "name_base", "county_qualifier", "pct_overall", "lt_0_5_pct", "water_type", "river_id",
            "water_name", "river_region", "match_share", "stocked_mi_2026", "n_sections_2026", "match_method",
            "confidence", "note"]
    rv = pd.DataFrame(review).sort_values("pct", ascending=False).rename(columns={"pct": "pct_overall"})
    return cw[cols], rv


REGIONAL_RAW: pd.DataFrame | None = None


def regional_text(waterbody: str) -> str:
    r = REGIONAL_RAW.loc[waterbody]
    return ", ".join(f"{ab} {int(r[col])}" for col, ab in zip(REGIONS, ["NW", "NC", "NE", "SW", "SC", "SE"]))


def validate(cw: pd.DataFrame, p: pd.DataFrame) -> None:
    assert set(cw.waterbody) == set(p.waterbody), "every p76-77 water must appear"
    assert not cw.duplicated(["waterbody", "river_id"]).any()
    matched = cw[cw.river_id.notna()]
    assert matched.groupby("waterbody").match_share.sum().sub(1).abs().lt(1e-9).all()
    assert cw.loc[cw.river_id.isna(), "match_share"].isna().all()
    assert cw.loc[cw.match_method.eq("review"), "river_id"].isna().all()
    assert cw.match_method.isin({"unique_name", "name_county", "regional_split", "manual", "lake", "unplaced",
                                 "not_stocked_2026", "no_pfbc_section", "review"}).all()
    assert cw.confidence.dropna().isin({"high", "medium", "low"}).all()
    assert cw.confidence.isna().eq(cw.match_method.eq("review")).all()
    e = cw.set_index("waterbody")
    assert e.at["Pine Creek (Lycoming or Tioga County)", "river_id"] == 1339
    assert e.at["Elk Creek", "river_id"] == 3160, "Elk Creek should be Erie's"


def summarize(cw: pd.DataFrame, p: pd.DataFrame, mentions: pd.DataFrame) -> None:
    pct = p.set_index("waterbody").pct
    res = mentions.sum(axis=1)
    cw = cw.assign(pct=cw.waterbody.map(pct) * cw.match_share.fillna(1),
                   res=cw.waterbody.map(res) * cw.match_share.fillna(1))
    placed = cw.river_id.notna() & cw.n_sections_2026.fillna(0).gt(0)
    cw["outcome"] = cw.match_method.where(~placed, "placed on 2026 river")
    log.info("waters by match_method (a water can have several rows): %s",
             cw.groupby("match_method").waterbody.nunique().to_dict())
    log.info("rows by match_method x confidence:\n%s", pd.crosstab(cw.match_method, cw.confidence.fillna("NA")))
    t, tr = pct.sum(), res.sum()
    log.info("mentions by method (pct_overall with * = %.2f, total %.1f%%; resident-weighted in brackets):",
             p.pct[p.lt_0_5_pct].iloc[0], t)
    for k, g in cw.groupby("match_method"):
        log.info("  %-17s %5.1f%% of mentions [%5.1f%%]", k, 100 * g.pct.sum() / t, 100 * g.res.sum() / tr)
    log.info("mentions landing on 2026-stocked rivers: %.1f%% of all (incl. Other/Don't know) [%.1f%% resident]; "
             "unplaced pool %.1f%%", 100 * cw.pct[placed].sum() / t, 100 * cw.res[placed].sum() / tr,
             100 * cw.pct[~placed].sum() / t)
    for k in ["not_stocked_2026", "no_pfbc_section"]:
        log.info("%s: %s", k, cw.loc[cw.match_method.eq(k), ["waterbody", "river_id"]].values.tolist())
    log.info("lakes (%d): %s", cw.match_method.eq("lake").sum(), cw.loc[cw.match_method.eq("lake"), "waterbody"].tolist())
    log.info("no survey water names Lake Erie or its tributaries as a group; Lake Erie tributaries matched "
             "one by one: %s", cw.loc[cw.note.str.contains("Lake Erie", na=False), "waterbody"].tolist())


def main() -> None:
    global REGIONAL_RAW
    setup_logging("07_survey_crosswalk")
    rivers = load_rivers()
    p, mentions = load_survey()
    REGIONAL_RAW = pd.read_csv(SURVEY_DIR / "p78-83_preferred_waters_by_region.csv").set_index("waterbody")
    cw, rv = build(p, mentions, rivers)
    validate(cw, p)
    summarize(cw, p, mentions)
    cw.to_csv(PROCESSED_DIR / "survey_water_crosswalk.csv", index=False)
    rv.to_csv(LOG_DIR / "07_survey_crosswalk_review.csv", index=False)
    log.info("survey_water_crosswalk: %d rows for %d waters; review file: %d rows (%d unresolved, %d low-confidence)",
             len(cw), cw.waterbody.nunique(), len(rv), rv.status.eq("unresolved").sum(),
             rv.status.eq("low-confidence match").sum())


if __name__ == "__main__":
    main()
