"""Match the PFBC co-op nursery stocking list to our sections and flag co-op-stocked sections.

Co-op fish are fixed background in the model (not PFBC's decision, not in its allocation; co-op policy §III.12).
The list has no fish counts or years: it says which waters each nursery stocks and with which species.

Inputs : data/raw/pfbc_coop/<date>/cnu-stockings-website.xlsx (latest), data/raw/Coop_nurseries.geojson (Gavin),
         data/processed/pa_trout.gpkg (sections), data/interim/pfbc_gis/{nat_repro,class_a}.parquet
Outputs: data/processed/coop_stockings.{parquet,csv}   one row per co-op listing, with match method
         data/processed/sections.{parquet,csv}         + coop_stocked, coop_species, coop_n_nurseries
         logs/03_coop_stockings.log, logs/03_coop_review.csv (rows for manual review, with a blank review_note)

    .venv/bin/python scripts/03_coop_stockings.py      (run after 02_build_sections.py)
"""
from __future__ import annotations

import difflib
import logging
import re

import geopandas as gpd
import pandas as pd
import shapely

from common import INTERIM_DIR, LOG_DIR, PROCESSED_DIR, RAW_DIR, setup_logging

METRIC_CRS = "EPSG:26918"
M_PER_MI = 1609.344
SPECIES = ["brook", "brown", "rainbow", "golden"]
LAKE_RE = r"\b(?:lake|pond|dam|reservoir|impoundment)\b"
COOP_COLS = ["coop_stocked", "coop_species", "coop_n_nurseries"]

log = logging.getLogger(__name__)


def norm(s) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", str(s).lower())).strip()


def load_list() -> pd.DataFrame:
    path = sorted((RAW_DIR / "pfbc_coop").glob("*/cnu-stockings-website.xlsx"))[-1]
    d = pd.read_excel(path, header=3)
    d.columns = ["sponsor", "nursery", "county", "stream", "section", *SPECIES]
    n_raw = len(d)
    d = d.dropna(subset=["stream"]).reset_index(drop=True)
    log.info("%s: %d rows -> %d with a water name", path.relative_to(RAW_DIR), n_raw, len(d))
    for c in ("sponsor", "nursery", "county", "stream"):
        d[c] = d[c].astype(str).str.strip()
    d["section"] = pd.to_numeric(d.section, errors="coerce").astype("Int64")
    for sp in SPECIES:
        d[sp] = d[sp].astype(str).str.strip().str.upper().eq("X")
    dup = d.duplicated(["nursery", "county", "stream", "section"])
    log.info("duplicate nursery/water rows: %d (kept)", dup.sum())
    return d


def match_waters(d: pd.DataFrame) -> pd.DataFrame:
    """section_id when the listing names a PFBC-stocked section; otherwise a stream-level geometry if we have one."""
    sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections").to_crs(METRIC_CRS)
    sec["sec_num"] = sec.section_id.str.split("_").str[1].astype(int)
    sec = sec.assign(county_one=sec.county.str.split("; ")).explode("county_one")
    sec["key_stream"], sec["key_county"] = sec.water_name.map(norm), sec.county_one.map(norm)
    by_section = sec.drop_duplicates(["key_stream", "key_county", "sec_num"]).set_index(
        ["key_stream", "key_county", "sec_num"])
    by_stream = sec.groupby(["key_stream", "key_county"]).geometry.apply(lambda g: shapely.union_all(g.values))

    wild = []
    for name, county_field in (("nat_repro", "County"), ("class_a", "COUNTY_NAM")):
        w = gpd.read_parquet(INTERIM_DIR / "pfbc_gis" / f"{name}.parquet").to_crs(METRIC_CRS)
        wild.append(pd.DataFrame({"key_stream": w.WtrName.map(norm), "key_county": w[county_field].map(norm),
                                  "geometry": w.geometry}))
    by_wild = pd.concat(wild).groupby(["key_stream", "key_county"]).geometry.apply(
        lambda g: shapely.union_all(g.values))

    ids, methods, geoms = [], [], []
    for stream, county, section in zip(d.stream.map(norm), d.county.map(norm), d.section):
        k3 = (stream, county, int(section)) if pd.notna(section) else None
        if k3 is not None and k3 in by_section.index:
            ids.append(by_section.at[k3, "section_id"]); methods.append("pfbc_section")
            geoms.append(by_section.at[k3, "geometry"])
        elif (stream, county) in by_stream.index:  # PFBC stream, but a section PFBC doesn't stock (or none given)
            ids.append(None); methods.append("pfbc_stream_other_section"); geoms.append(by_stream[(stream, county)])
        elif (stream, county) in by_wild.index:
            ids.append(None); methods.append("wild_layer_stream"); geoms.append(by_wild[(stream, county)])
        else:
            ids.append(None); geoms.append(None)
            methods.append("unmatched_lake_pond" if re.search(LAKE_RE, stream) else "unmatched")
    d["section_id"], d["match_method"] = ids, methods
    d["water_type"] = d.stream.str.contains(LAKE_RE, case=False, regex=True).map({True: "lake_pond", False: "stream"})
    log.info("water matches: %s", d.match_method.value_counts().to_dict())
    return d, gpd.GeoSeries(geoms, index=d.index, crs=METRIC_CRS)


def contains(name: str, index) -> list[str]:
    """Layer names that contain, or are contained in, this name (spaces ignored), e.g. "Kenny Stewart"."""
    a = name.replace(" ", "")
    return [k for k in index if len(k) >= 5 and (k.replace(" ", "") in a or a in k.replace(" ", ""))]


def add_nursery_distance(d: pd.DataFrame, water_geoms: gpd.GeoSeries) -> pd.DataFrame:
    """Straight-line miles from the nursery (Gavin's co-op layer, matched by nursery then sponsor name)."""
    c = gpd.read_file(RAW_DIR / "Coop_nurseries.geojson").to_crs(METRIC_CRS)
    by_nursery = c.assign(k=c.NURSERY_NA.map(norm)).drop_duplicates("k").set_index("k")
    by_sponsor = c.assign(k=c.SPONSOR_NA.map(norm)).drop_duplicates("k").set_index("k")
    pts, how = [], []
    for nursery, sponsor in zip(d.nursery.map(norm), d.sponsor.map(norm)):
        if nursery in by_nursery.index:
            pts.append(by_nursery.at[nursery, "geometry"]); how.append("nursery_name")
        elif sponsor in by_sponsor.index:
            pts.append(by_sponsor.at[sponsor, "geometry"]); how.append("sponsor_name")
        elif len(hit := contains(nursery, by_nursery.index)) == 1:
            pts.append(by_nursery.at[hit[0], "geometry"]); how.append("name_contains")
        elif len(hit := contains(sponsor, by_sponsor.index)) == 1:
            pts.append(by_sponsor.at[hit[0], "geometry"]); how.append("name_contains")
        else:
            pts.append(None); how.append(None)
    pts = gpd.GeoSeries(pts, index=d.index, crs=METRIC_CRS)
    d["nursery_located_by"] = how
    ll = pts.to_crs("EPSG:4326")
    d["nursery_lat"], d["nursery_lon"] = ll.y.round(4), ll.x.round(4)
    ok = pts.notna() & water_geoms.notna()
    d["nursery_to_water_mi"] = pd.Series([w.distance(p) / M_PER_MI if o else None
                                          for w, p, o in zip(water_geoms, pts, ok)], index=d.index).round(2)
    missing = d.loc[pts.isna(), "nursery"].unique()
    log.info("nursery location found for %d of %d nurseries; missing: %s", d.nursery.nunique() - len(missing),
             d.nursery.nunique(), sorted(missing))
    q = d.nursery_to_water_mi.dropna()
    log.info("nursery -> water straight-line miles (n=%d): median %.1f, 90%% %.1f, max %.1f; within 10 mi %.0f%%",
             len(q), q.median(), q.quantile(0.9), q.max(), 100 * (q <= 10).mean())
    return d


def flag_sections(d: pd.DataFrame) -> pd.DataFrame:
    sections = pd.read_parquet(PROCESSED_DIR / "sections.parquet").drop(columns=COOP_COLS, errors="ignore")
    hits = d[d.match_method == "pfbc_section"]
    flags = hits.groupby("section_id").agg(
        coop_species=("section_id", lambda idx: ",".join(sp for sp in SPECIES if hits.loc[idx.index, sp].any())),
        coop_n_nurseries=("nursery", "nunique")).reset_index()
    before = len(sections)
    sections = sections.merge(flags, on="section_id", how="left")
    assert len(sections) == before
    sections["coop_stocked"] = sections.coop_n_nurseries.notna()
    sections["coop_n_nurseries"] = sections.coop_n_nurseries.fillna(0).astype(int)
    unknown = set(flags.section_id) - set(sections.section_id)
    assert not unknown, unknown
    sections.to_parquet(PROCESSED_DIR / "sections.parquet", index=False)
    sections.to_csv(PROCESSED_DIR / "sections.csv", index=False)
    log.info("sections flagged coop_stocked: %d of %d", sections.coop_stocked.sum(), len(sections))
    return sections


def suggest_names(d: pd.DataFrame) -> pd.Series:
    """Closest water name in the same county (stocked sections + wild-trout layers), to speed up manual review."""
    names = [pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["water_name", "county"])
             .assign(county=lambda x: x.county.str.split("; ")).explode("county")]
    for name, county_field in (("nat_repro", "County"), ("class_a", "COUNTY_NAM")):
        w = pd.read_parquet(INTERIM_DIR / "pfbc_gis" / f"{name}.parquet", columns=["WtrName", county_field])
        names.append(w.rename(columns={"WtrName": "water_name", county_field: "county"}))
    names = pd.concat(names).dropna()
    by_county = names.assign(k=names.county.map(norm)).groupby("k").water_name.unique()
    out = []
    for stream, county in zip(d.stream, d.county):
        cands = {norm(n): n for n in by_county.get(norm(county), [])}
        best = difflib.get_close_matches(norm(stream), list(cands), n=1, cutoff=0.85)
        out.append(cands[best[0]] if best else None)
    return pd.Series(out, index=d.index)


def write_review(d: pd.DataFrame, sections: pd.DataFrame) -> None:
    """One file of everything worth a human look; fill review_note by hand."""
    sec = sections.set_index("section_id")
    ctx = ["years_stocked", "biomass_class", "class_a_flag", "nat_repro_flag"]
    parts = []
    unmatched = d[d.match_method.str.startswith("unmatched")].copy()
    unmatched["review_reason"] = unmatched.match_method.map(
        {"unmatched": "water not found (stream)", "unmatched_lake_pond": "water not found (lake/pond)"})
    unmatched["suggested_name"] = suggest_names(unmatched)
    parts.append(unmatched)
    lost = d[d.nursery_located_by.isna()].drop_duplicates("nursery").copy()
    lost["review_reason"] = "nursery not in Gavin's co-op layer"
    parts.append(lost[["sponsor", "nursery", "county", "review_reason"]])
    on = d[d.match_method == "pfbc_section"].join(sec[ctx + ["total_2026"]], on="section_id")
    dropped = on[on.total_2026.isna()].assign(review_reason="co-op lists a section PFBC no longer stocks (2026)")
    class_a = on[on.class_a_flag].assign(review_reason="co-op lists a section overlapping Class A")
    parts += [dropped, class_a]
    cols = ["review_reason", "sponsor", "nursery", "county", "stream", "section", "section_id", "suggested_name",
            *ctx, "review_note"]
    review = pd.concat(parts, ignore_index=True).reindex(columns=cols)
    review.to_csv(LOG_DIR / "03_coop_review.csv", index=False)
    log.info("wrote logs/03_coop_review.csv: %s", review.review_reason.value_counts().to_dict())


def main() -> None:
    setup_logging("03_coop_stockings")
    d = load_list()
    d, water_geoms = match_waters(d)
    d = add_nursery_distance(d, water_geoms)
    cols = ["sponsor", "nursery", "county", "stream", "section", *SPECIES, "water_type", "match_method",
            "section_id", "nursery_located_by", "nursery_lat", "nursery_lon", "nursery_to_water_mi"]
    d[cols].to_parquet(PROCESSED_DIR / "coop_stockings.parquet", index=False)
    d[cols].to_csv(PROCESSED_DIR / "coop_stockings.csv", index=False)
    sections = flag_sections(d)
    write_review(d, sections)

    # validation: a listing we know is on PFBC-stocked sections
    yb = d[(d.stream == "Yellow Breeches Creek") & (d.county == "Cumberland")]
    assert (yb.match_method == "pfbc_section").all(), yb[["section", "match_method"]]
    log.info("Yellow Breeches Creek (Cumberland) co-op listings matched to PFBC sections: %s",
             yb.section_id.tolist())


if __name__ == "__main__":
    main()
