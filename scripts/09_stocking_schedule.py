"""Download PFBC's 2026 adult trout stocking schedule, match events to sections, and credit fish to hatcheries.

The schedule (fbweb.pa.gov/TroutStocking) lists every planned stocking event: water, section number, limits,
date, species stocked (X marks, no counts), meeting place and time, and the hatchery. It is PFBC's planned
schedule ("subject to change without notice") and only 2026 is served. One POST per county returns that county's
whole year; a section on a county line is listed under each of its counties.

Matching a stream record to section_id, first rule that gives exactly one section:
  1. limits      section number + upper and lower limit text (normalized) equal to sections.parquet's
  2. name_county water name (before any ", Trib To ...") + county + section number
  3. coords      the record's upper-limit point lies within COORD_TOL_M of that section's line, same name + number
  4. same_listing the identical listing (water, number, both limits) matched under another county
Anything else is logged to logs/09_schedule_unmatched.csv, never guessed. Lakes (section 0) have no section_id.
Repeats of a section x date are merged: across counties, and within a county where one event is listed once per
regulation piece (like the GIS layer's two-row sections). A species mark on any of the listings counts.
Each dated event gets run_id = date | hatchery | meeting place | time (one truck meeting); spellings of one meeting
place on the same date, hatchery and time (similarity >= MEETING_SIMILAR) count as one place.

Hatchery supply (assumption, labeled): each section's 2026 count of a species (GIS layer) is split equally over
its events marked with that species; brood fish, and a species with no marked event, are split over all of the
section's events. Each event's fish go to its hatchery.

Inputs : fbweb.pa.gov/TroutStocking (GetCountyBySeason, Secondpage), data/processed/sections.parquet,
         data/processed/pa_trout.gpkg (sections), data/raw/pa_hatchery_production.csv, data/raw/pa_hatcheries.gpkg
Outputs: data/raw/pfbc_schedule/<date>/ (raw responses + manifest rows)
         data/processed/stocking_events.{parquet,csv}   one row per section x date (lakes and unmatched included)
         data/processed/hatchery_schedule_supply.csv    one row per hatchery
         logs/09_stocking_schedule.log, logs/09_schedule_unmatched.csv

    .venv/bin/python scripts/09_stocking_schedule.py      (run after 02-04; re-runs read the HTTP cache)
"""
from __future__ import annotations

import difflib
import json
import logging
import re
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
from bs4 import BeautifulSoup

from common import (LOG_DIR, PROCESSED_DIR, RAW_DIR, PoliteSession, ServerRefused, full_url, save_raw,
                    setup_logging)

BASE = "https://fbweb.pa.gov/TroutStocking/Home"
COUNTY_URL = f"{BASE}/GetCountyBySeason"
SCHEDULE_URL = f"{BASE}/Secondpage"
SOURCE = "pfbc_schedule"
METRIC_CRS = "EPSG:26918"
# the 17 pipe-separated fields of each record's data-mapatt, named as in the site's own CSV export (StockedWaters.js)
FIELDS = ["water", "county", "sec", "upper_limit", "lower_limit", "date", "week_of", "brook", "brown", "rainbow",
          "golden", "meeting_place", "meeting_time", "hatchery", "regulation", "reg_link", "season"]
SPECIES = ["brook", "brown", "rainbow", "golden"]
# method thresholds, not model parameters: a coords match must be this close; a match whose upper-limit point is
# farther than QA_DIST_M from its line is logged for a look
COORD_TOL_M = 100
QA_DIST_M = 500
# meeting places on the same date, hatchery and time that are at least this similar are one place spelled two ways
# (e.g. "Mrytle"/"Myrtle Gospel Church"); in 2026 the variants score >= 0.89 and different places <= 0.53
MEETING_SIMILAR = 0.85
N_COUNTIES = 67

log = logging.getLogger(__name__)


def norm(s) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(s or "").upper()).strip()


def local_date(r) -> str:
    """Retrieval date of a response (a cached one keeps its original date, so re-runs reuse the same folder)."""
    when = getattr(r, "created_at", None) or datetime.now(timezone.utc)
    return when.astimezone().strftime("%Y-%m-%d")


def download(session: PoliteSession) -> dict[str, str]:
    """All 67 counties' 2026 schedules (all seasons, no date filter), each raw response saved untouched."""
    params = {"intputSelectedSeasons": ""}  # sic: the site's parameter name
    r = session.get(COUNTY_URL, params)
    counties = r.json()
    save_raw(SOURCE, "counties.json", r.content, full_url(COUNTY_URL, params), records=len(counties),
             date=local_date(r))
    if not counties:
        # The county list came back empty on 2026-09-29 (all 67 on 2026-09-28) while each county's schedule still
        # loaded: fall back to our 67 counties, spelled as the schedule spells them
        log.warning("county list is empty: using the 67 counties in county_region.csv")
        names = pd.read_csv(PROCESSED_DIR / "county_region.csv").county.replace({"Mckean": "McKean"})
        counties = [{"County": c, "IsEnable": True} for c in names]
    assert len(counties) == N_COUNTIES and all(c["IsEnable"] for c in counties), counties
    pages, n_cached = {}, 0
    for c in (c["County"] for c in counties):
        body = {"County": c, "StartDate": "", "EndDate": "", "PageNumber": "", "Water": "", "Season": ""}
        r = session.post(SCHEDULE_URL, body)
        n_cached += bool(getattr(r, "from_cache", False))
        n = r.text.count('data-mapatt="')
        if n == 0 and "No Stockings" not in r.text:
            raise RuntimeError(f"{c}: response has no records and no 'No Stockings' message")
        save_raw(SOURCE, f"schedule_{c.lower().replace(' ', '_')}.html", r.content,
                 f"POST {SCHEDULE_URL} {json.dumps(body)}", records=n, date=local_date(r))
        pages[c] = r.text
    log.info("schedules: %d counties (%d from the HTTP cache), %d records", len(pages), n_cached,
             sum(t.count('data-mapatt="') for t in pages.values()))
    return pages


def coords(link: str | None) -> tuple[float, float]:
    m = re.search(r"q=\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)", link or "")
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def parse(pages: dict[str, str]) -> pd.DataFrame:
    rows = []
    for query_county, text in pages.items():
        for div in BeautifulSoup(text, "lxml").select(".stocksDiv"):
            parts = div["data-mapatt"].split("|")
            assert len(parts) == len(FIELDS), (query_county, parts)
            rec = dict(zip(FIELDS, (p.strip() for p in parts)), query_county=query_county)
            # upper then lower limit, as the page labels them; the first must equal the record's data-ul_* point
            links = [a["href"] for a in div.find_all("a", href=True) if "maps.google.com" in a["href"]]
            rec["ul_lat"], rec["ul_lon"] = coords(links[0] if links else None)
            rec["ll_lat"], rec["ll_lon"] = coords(links[1] if len(links) > 1 else None)
            well = div.select_one(".well")
            if well is not None and rec["ul_lat"] is not None:
                assert abs(float(well["data-ul_lat_gis"]) - rec["ul_lat"]) < 1e-6, rec
            rows.append(rec)
    ev = pd.DataFrame(rows)
    ev[["ul_lat", "ul_lon", "ll_lat", "ll_lon"]] = ev[["ul_lat", "ul_lon", "ll_lat", "ll_lon"]].astype(float)
    ev["sec_num"] = ev.sec.astype(int)
    ev["date"] = pd.to_datetime(ev.date.replace("", None), format="%Y-%m-%d")
    ev["week_of"] = pd.to_datetime(ev.week_of.replace("", None), format="%m-%d-%Y")
    ev["week_of_only"] = ev.date.isna()
    assert (ev.date.notna() | ev.week_of.notna()).all(), "every record has a date or a week"
    for sp in SPECIES:
        ev[sp] = ev[sp].str.upper().eq("X")
    ev["meeting_time"] = ev.meeting_time.str[:5]
    ev["water_type"] = ev.sec_num.eq(0).map({True: "lake", False: "stream"})
    log.info("parsed %d records: %s; seasons %s; week-of only %d", len(ev), ev.water_type.value_counts().to_dict(),
             ev.season.value_counts().to_dict(), ev.week_of_only.sum())
    return ev.drop(columns=["sec"])


def match(ev: pd.DataFrame) -> pd.DataFrame:
    """section_id for stream records (limits, then name_county, then coords); lakes and the rest stay NA."""
    sections = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    lines = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
    lines = lines.to_crs(METRIC_CRS).set_index("section_id").geometry
    s = sections[["section_id", "sec_num", "water_name", "county", "upper_limit", "lower_limit"]].copy()
    s["k_ul"], s["k_ll"], s["k_name"] = s.upper_limit.map(norm), s.lower_limit.map(norm), s.water_name.map(norm)
    by_limits = s.groupby(["sec_num", "k_ul", "k_ll"]).section_id.agg(list)
    s_county = s.assign(county=s.county.str.split("; ")).explode("county")
    s_county["k_county"] = s_county.county.map(norm)  # the layer spells McKean "Mckean"
    by_county = s_county.groupby(["k_name", "k_county", "sec_num"]).section_id.agg(list)
    by_name = s.groupby(["k_name", "sec_num"]).section_id.agg(list)
    name_of = s.set_index("section_id").k_name

    ev["k_name"] = ev.water.str.split(",").str[0].map(norm)
    ul = gpd.GeoSeries(gpd.points_from_xy(ev.ul_lon, ev.ul_lat), crs="EPSG:4326", index=ev.index).to_crs(METRIC_CRS)
    ids, methods = [], []
    for i, r in ev.iterrows():
        if r.water_type == "lake":
            ids.append(None); methods.append("lake"); continue
        hit = by_limits.get((r.sec_num, norm(r.upper_limit), norm(r.lower_limit)), [])
        if len(hit) > 1:
            hit = [h for h in hit if name_of[h] == r.k_name]
        if len(hit) == 1:
            ids.append(hit[0]); methods.append("limits"); continue
        hit = by_county.get((r.k_name, norm(r.county), r.sec_num), [])
        if len(hit) == 1:
            ids.append(hit[0]); methods.append("name_county"); continue
        near = [h for h in by_name.get((r.k_name, r.sec_num), []) if pd.notna(r.ul_lat)
                and lines[h].distance(ul[i]) <= COORD_TOL_M]
        if len(near) == 1:
            ids.append(near[0]); methods.append("coords"); continue
        ids.append(None); methods.append("unmatched")
    ev["section_id"], ev["match_method"] = ids, methods
    listing = ["water", "sec_num", "upper_limit", "lower_limit"]
    known = ev.dropna(subset=["section_id"]).groupby(listing).section_id.agg(lambda x: sorted(set(x)))
    known = known[known.str.len() == 1].str[0]
    fill = (ev.match_method == "unmatched") & ev.set_index(listing).index.isin(known.index)
    ev.loc[fill, "section_id"] = [known[k] for k in ev.loc[fill].set_index(listing).index]
    ev.loc[fill, "match_method"] = "same_listing"
    dist = pd.Series([lines[sid].distance(p) if pd.notna(sid) and not pd.isna(lat) else None
                      for sid, p, lat in zip(ev.section_id, ul, ev.ul_lat)],
                     index=ev.index, dtype=float)
    ev["ul_dist_m"] = dist.round().astype("Int64")
    log.info("stream records matched (before dedupe): %s", ev.match_method.value_counts().to_dict())
    names_differ = ev[(ev.match_method == "limits") & (ev.k_name != ev.section_id.map(name_of))]
    log.info("limits matches whose base name differs from the layer's: %d (%s)", len(names_differ),
             sorted(set(zip(names_differ.water, names_differ.section_id)))[:10])
    far = ev[ev.ul_dist_m > QA_DIST_M].drop_duplicates("section_id")
    log.info("matches whose upper-limit point is > %d m from the section line: %d %s", QA_DIST_M, len(far),
             far[["section_id", "water", "match_method", "ul_dist_m"]].values.tolist())
    return ev


def dedupe(ev: pd.DataFrame) -> pd.DataFrame:
    """One row per section x date. Repeats are merged: listing counties and regulations joined, species marks OR-ed."""
    ev["day"] = ev.date.fillna(ev.week_of)
    point = ev.ul_lat.round(4).astype(str) + "," + ev.ul_lon.round(4).astype(str)
    ev["lake_key"] = (ev.water + " @ " + point).where(ev.water_type == "lake")  # the schedule gives lakes no id
    ev["water_key"] = ev.section_id.fillna(ev.lake_key).fillna(
        "unmatched|" + ev.water + "|" + ev.sec_num.astype(str) + "|" + point)
    key = ["water_key", "day"]
    g = ev.groupby(key)
    n, n_counties = g.size(), g.query_county.nunique()
    log.info("repeats of a section x date: %d cross-county (listed under each county it touches), %d within one "
             "county (listed once per regulation piece)", (n_counties - 1).sum(), (n - n_counties).sum())
    conflicts = g[["hatchery", "meeting_place", "meeting_time", "season"]].nunique().gt(1).any(axis=1)
    log.info("repeats that disagree on hatchery/meeting place/time/season: %d %s (best-matched listing kept)",
             conflicts.sum(), conflicts[conflicts].index.tolist())
    marks = g[SPECIES].nunique().gt(1).any(axis=1)
    log.info("repeats whose species marks differ (combined: a mark on any listing counts): %d %s", marks.sum(),
             marks[marks].index.tolist())
    merged = g.agg(listed_counties=("query_county", lambda c: "; ".join(sorted(set(c)))),
                   regulation=("regulation", lambda r: "; ".join(dict.fromkeys(r))),
                   **{sp: (sp, "any") for sp in SPECIES})
    before = len(ev)
    rank = ev.match_method.map({"limits": 0, "name_county": 1, "coords": 2, "same_listing": 3}).fillna(4)
    ev = (ev.assign(rank=rank).sort_values([*key, "rank", "query_county"]).drop_duplicates(key)  # best match kept
          .drop(columns=["regulation", "rank", *SPECIES]))
    ev = ev.join(merged, on=key)
    ev[SPECIES] = ev[SPECIES].astype(bool)
    log.info("dedupe section x date: %d -> %d records", before, len(ev))
    return run_ids(ev)


def run_ids(ev: pd.DataFrame) -> pd.DataFrame:
    """run_id = date | hatchery | meeting place | time: one truck meeting. NA for week-of-only events."""
    ev["mp_key"] = ev.meeting_place.str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    slot = ev.date.dt.strftime("%Y-%m-%d") + "|" + ev.hatchery + "|" + ev.meeting_time
    merged = []
    for _, keys in ev.groupby(slot).mp_key:
        canon = []
        for k in keys.value_counts().index:  # most-listed spelling first
            same = [c for c in canon if difflib.SequenceMatcher(None, k, c).ratio() >= MEETING_SIMILAR]
            if same:
                ev.loc[keys.index[keys == k], "mp_key"] = same[0]
                merged.append(k)
            else:
                canon.append(k)
    log.info("meeting-place spellings merged into another on the same date/hatchery/time: %d", len(merged))
    ev["run_id"] = (slot.str.rsplit("|", n=1).str[0] + "|" + ev.mp_key + "|" + ev.meeting_time)
    return ev.drop(columns=["mp_key"])


def allocate(ev: pd.DataFrame, sections: pd.DataFrame) -> pd.DataFrame:
    """Split each section's 2026 count by species over its events (assumption; see module docstring)."""
    counts = sections.set_index("section_id")[[f"{sp}_2026" for sp in [*SPECIES, "brood"]]].fillna(0)
    alloc_cols = [f"alloc_{sp}" for sp in [*SPECIES, "brood"]]
    for c in alloc_cols:
        ev[c] = pd.NA
    unmarked, marked_no_fish = [], []
    stream = ev[ev.section_id.notna() & ev.section_id.isin(counts.index[counts.sum(axis=1) > 0])]
    for sid, g in stream.groupby("section_id"):
        for sp in [*SPECIES, "brood"]:
            n = counts.at[sid, f"{sp}_2026"]
            marks = g[sp] if sp in SPECIES else pd.Series(False, index=g.index)
            if sp in SPECIES and marks.any() and n == 0:
                marked_no_fish.append((sid, sp))
            if n == 0:
                ev.loc[g.index, f"alloc_{sp}"] = 0.0
                continue
            if not marks.any():
                marks = pd.Series(True, index=g.index)
                if sp in SPECIES:
                    unmarked.append((sid, sp, int(n)))
            ev.loc[g.index, f"alloc_{sp}"] = marks.astype(float) * n / marks.sum()
    ev[alloc_cols] = ev[alloc_cols].astype("Float64").round(2)
    ev["alloc_fish"] = ev[alloc_cols].sum(axis=1, min_count=1)
    log.info("species with 2026 fish but no event marked (split over all events): %d, %d fish %s", len(unmarked),
             sum(u[2] for u in unmarked), unmarked[:10])
    log.info("species marked on an event but with 0 fish in the 2026 layer: %d section-species %s",
             len(marked_no_fish), marked_no_fish[:10])
    return ev


def hatchery_names() -> tuple[pd.DataFrame, set[str]]:
    prod = pd.read_csv(RAW_DIR / "pa_hatchery_production.csv")
    gpkg = set(gpd.read_file(RAW_DIR / "pa_hatcheries.gpkg").NAME.str.strip())
    return prod, gpkg


def hatchery_table(ev: pd.DataFrame) -> pd.DataFrame:
    prod, gpkg_names = hatchery_names()
    names = set(ev.hatchery)
    log.info("schedule hatchery names: %s; not in pa_hatchery_production.csv: %s; not in pa_hatcheries.gpkg: %s",
             sorted(names), sorted(names - set(prod.hatchery)) or "none", sorted(names - gpkg_names) or "none")
    counted = ev.alloc_fish.notna()  # 2026-stocked sections; the rest have no 2026 count
    stream = ev[counted]
    fish = stream.groupby("hatchery")[[f"alloc_{sp}" for sp in [*SPECIES, "brood"]]].sum()
    fish.columns = [c.replace("alloc_", "") for c in fish.columns]
    t = pd.DataFrame({
        "n_sections": stream.groupby("hatchery").section_id.nunique(),
        "n_stream_events": stream.groupby("hatchery").size(),
        "n_stream_events_uncounted": ev[(ev.water_type == "stream") & ~counted].groupby("hatchery").size(),
        "n_lake_events": ev[ev.water_type == "lake"].groupby("hatchery").size(),
    }).join(fish, how="outer")
    t = t.reindex(sorted(set(t.index) | set(prod.hatchery))).rename_axis("hatchery")
    n_cols = ["n_sections", "n_stream_events", "n_stream_events_uncounted", "n_lake_events"]
    t[n_cols] = t[n_cols].fillna(0).astype(int)
    species = [*SPECIES, "brood"]
    t[species] = t[species].astype(float).fillna(0).round().astype(int)
    t["stream_fish_2026"] = t[species].sum(axis=1)
    t["share"] = (t.stream_fish_2026 / t.stream_fish_2026.sum()).round(4)
    lbs = prod.set_index("hatchery").query("production_units == 'lbs'").production_value
    t["production_lbs"] = lbs.reindex(t.index)
    t["lbs_share"] = (t.production_lbs / lbs.sum()).round(4)
    in_lbs = t.production_lbs.notna()
    t["share_lbs_set"] = (t.stream_fish_2026.where(in_lbs) / t.stream_fish_2026[in_lbs].sum()).round(4)
    t["in_production_csv"], t["in_hatcheries_gpkg"] = t.index.isin(prod.hatchery), t.index.isin(gpkg_names)
    return t.reset_index()


def coverage(ev: pd.DataFrame, sections: pd.DataFrame) -> None:
    cand = sections[sections.total_2026.fillna(0) > 0]
    on = set(ev.section_id.dropna())
    missing = cand[~cand.section_id.isin(on)]
    log.info("2026 candidate sections with a schedule record: %d of %d; without: %d %s", len(cand) - len(missing),
             len(cand), len(missing), missing[["section_id", "water_name", "county", "total_2026"]].values.tolist())
    covered = cand[cand.section_id.isin(on)].total_2026.sum()
    log.info("2026 stream fish on sections with a schedule record: %d of %d (%.2f%%)", covered,
             cand.total_2026.sum(), 100 * covered / cand.total_2026.sum())
    not_2026 = sorted(on - set(cand.section_id))
    log.info("scheduled sections not stocked in the 2026 layer: %d %s", len(not_2026), not_2026)
    alloc = ev.alloc_fish.sum()
    assert abs(alloc - covered) < 5, (alloc, covered)  # allocations are rounded to 0.01 fish


def main() -> None:
    setup_logging("09_stocking_schedule")
    try:
        pages = download(PoliteSession())
    except ServerRefused as e:
        log.error("STOP: server refused (%s). Not retrying further; report before continuing.", e)
        raise SystemExit(1)
    sections = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    ev = match(parse(pages))

    unmatched = ev[ev.match_method == "unmatched"].copy()
    # reviewer hint only (not a match): layer sections with the same name in that county, and their years
    s = sections.assign(k_name=sections.water_name.map(norm), k_county=sections.county.map(norm))
    unmatched["same_name_sections"] = [
        "; ".join(f"{x.section_id} ({x.years_stocked})" for x in s[(s.k_name == k) & s.k_county.str.contains(
            norm(c), regex=False)].itertuples()) for k, c in zip(unmatched.k_name, unmatched.county)]
    cols_u = ["query_county", "water", "county", "sec_num", "upper_limit", "lower_limit", "date", "week_of",
              "hatchery", "ul_lat", "ul_lon", "same_name_sections"]
    unmatched[cols_u].to_csv(LOG_DIR / "09_schedule_unmatched.csv", index=False)
    log.info("unmatched stream records: %d (%d distinct waters) -> logs/09_schedule_unmatched.csv", len(unmatched),
             unmatched.drop_duplicates(["water", "sec_num", "upper_limit"]).shape[0])

    ev = allocate(dedupe(ev), sections)
    coverage(ev, sections)
    cols = ["section_id", "water_type", "lake_key", "match_method", "water", "sec_num", "listed_counties",
            "upper_limit", "lower_limit", "date", "week_of", "week_of_only", "season", "hatchery", "meeting_place",
            "meeting_time", "run_id", *SPECIES, "regulation", "ul_lat", "ul_lon", "ll_lat", "ll_lon", "ul_dist_m",
            "alloc_brook", "alloc_brown", "alloc_rainbow", "alloc_golden", "alloc_brood", "alloc_fish"]
    out = ev[cols].sort_values(["water_type", "section_id", "lake_key", "date", "week_of"]).reset_index(drop=True)
    text = ["upper_limit", "lower_limit", "meeting_place", "regulation"]
    out[text] = out[text].replace("", pd.NA)  # missing = NA (lakes have no limits; one event has no meeting place)
    out.to_parquet(PROCESSED_DIR / "stocking_events.parquet", index=False)
    out.to_csv(PROCESSED_DIR / "stocking_events.csv", index=False)
    log.info("stocking_events: %d rows (%s; %s)", len(out), out.water_type.value_counts().to_dict(),
             out.match_method.value_counts().to_dict())

    t = hatchery_table(out)
    t.to_csv(PROCESSED_DIR / "hatchery_schedule_supply.csv", index=False)
    log.info("hatchery_schedule_supply:\n%s", t.drop(columns=["in_production_csv", "in_hatcheries_gpkg"]).to_string())

    # validation: the Bear Creek test case (CLAUDE.md Known facts) is stocked from Tylersville in the schedule
    bear = out[out.section_id.isin(["3197_2", "3197_3"])]
    log.info("Bear Creek events:\n%s", bear[["section_id", "date", "season", "hatchery", "meeting_place",
                                             "brown", "rainbow", "alloc_fish"]].to_string())
    assert set(bear.section_id) == {"3197_2", "3197_3"}
    assert abs(bear.alloc_fish.sum() - 1950) < 0.1, "3197_2 + 3197_3 = 1,030 + 920 fish in 2026"


if __name__ == "__main__":
    main()
