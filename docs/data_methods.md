# Data methods: changes to PFBC data and data-handling assumptions

Data from the Pennsylvania Fish and Boat Commission (PFBC), via fbweb.pa.gov and PASDA. Anything used
unaltered is credited to PFBC. Every change is listed here. Raw downloads are kept untouched in
`data/raw/` (see `manifest.csv`).

## Sections pull (scripts 01–02, 2026-09-26)

**Download.** We downloaded the stocked-section layers for 2024, 2025 and 2026 from fbweb, and Class A (#9),
Natural Reproduction (#25) and Wilderness (#31) from PASDA's PAFishBoat MapServer. Each was paged by
object id, and the downloaded count matched the server count for every layer.

**Stocking counts**
- **Missing counts.** Null brook/brown counts (10–20 per year) are set to 0. PFBC's
  `TotalAdultStocked_minusBrood` equals brook + brown + rainbow only when they are 0.
- **Duplicate rows.** Each year, 5–9 sections appear as two rows: pieces split by regulation (e.g. a DHALO
  stretch) or by county. Both rows carry the full section total, with identical counts. We count them
  once. The pair is always one "Stocked Trout Water" row and one "Commonwealth Inland Waters" row, and their
  lines don't describe the same stretch, so we keep the "Stocked Trout Water" row's limits, length and line
  (decision 2026-09-27; an earlier build unioned the lines and overstated length). County and regulation
  text are joined across the two rows, and special regulations count if either row has them. Summing the raw
  layer would overcount by about 0.7%; for example, 2026 rainbow is 1,818,685 raw and 1,800,505 after the
  merge.
- **Placeholder text.** PFBC's literal `<Null>` in `Wtr_Prog_Name` is read as missing.
- **County names.** Converted to title case (the layers mix "Cambria" and "CAMBRIA").
- **No other changes.** Counts are otherwise as published: no smoothing, imputation or corrections.

**Section attributes**
- **Which year's attributes.** They come from the latest year a section appears in.
- **Length.** `length_mi` (used for area) is one of PFBC's two lengths, and `length_source` says which
  (decision 2026-09-27: PFBC numbers only).
  - `pfbc_length_mi` = PFBC's `Length_MI_`. It's the default and matches PFBC river miles (median ratio 1.02).
  - `rm_length_mi` = upper minus lower river mile, both PFBC fields.
  - We don't use our own measurement of the line. It runs ~8% longer than `Length_MI_` at the median, more
    so on lines with more vertices per mile, which suggests PFBC measured an earlier, less detailed version
    of the line.
- **Length check.** `length_check_flag` marks the 57 sections where the two PFBC lengths differ by more than
  25%. PFBC allocates fish as rate × acres, so a section's stocking shows which length PFBC used:
  - Among the unflagged sections, fish per (Table 18 rate × mile) gives a typical value and a normal range
    (10th–90th percentile) per width class. Working within a width class avoids needing a width.
  - A flagged section's mean fish per year then give an expected length range. If only river miles fall in
    it, `length_mi` uses river miles (9 sections). If only `Length_MI_` does (14), both do (21), or neither
    does (12, plus 1 with no rate), `Length_MI_` stays.
  - `length_check_result` records the outcome; the details are in `logs/02_length_check.csv`. This only
    picks between PFBC's two lengths: the stocking baseline itself is never changed.
- **Midpoint.** The point halfway along the line.
- **Sherman Creek 3306_2.** Its river-mile limits are reversed in PFBC's data. We flag it
  (`rm_limits_reversed`) and don't change it.

**Allocation category**

`AllocationCode` is decoded as [biomass class A–E][recreational use potential H/G/L]
[population density M/U/S/R][width class 1S/1L/2/3/4]. We checked this against the category definitions
in the Operational Guidelines (Tables 15, 16 and 18). All 1,045 codes match the pattern.

`max_trout_per_acre` is looked up from Table 18.
- Table 18 has no biomass-A rows for widths 2–4, so 11 of the 13 biomass-A (Class A) sections have NA with
  a reason.
- The other two are large rivers (1S/1L), where the rate doesn't depend on biomass.
- The 13 are stocked Class A sections (their Class A key is their own section id). Which exemption covers
  them: `docs/known_gaps.md` § Class A exemptions.

**Wild-trout overlap** (CLAUDE.md rule 8)
- **Method:** river miles shared with wild-trout records on the same `RFP_WaterID`, for Class A, Natural
  Reproduction and Wilderness alike. It counts only above 100 m, so sections that only touch share an
  endpoint and aren't flagged. 531 sections are flagged natural reproduction.
- **Assumption: PFBC's river miles only** (decision 2026-09-27). We use PFBC's recorded river miles even where
  a record's river miles are shorter than its own line and Limits text, and don't patch them with our own
  geometry. This misses 18 natural-reproduction sections (~1% of 2026 fish); which ones and what it changes:
  `docs/known_gaps.md` § Natural Reproduction river miles shorter than the line.
- **Cross-check (log only):** the length of the section within 30 m of wild-trout lines on the same water.
  Sections where the two methods disagree are in `logs/02_overlap_check.csv`; `nat_repro_missed_by_rm`
  marks the 18. Geometry isn't used for flags because it's imprecise at section boundaries: it puts 0.47 mi
  of Bear Creek 3197_2 in Class A, when PFBC's listing shows the two only touch.
- **Class A species flags** come from keyword matches on the Class A `Fishery` text: brook, brown,
  rainbow.

**Co-op nursery list** (`scripts/03_coop_stockings.py`, 2026-09-27)
- **Source:** PFBC's co-op nursery page spreadsheet, used as published. It has no counts or years, and it
  was identical to a Feb 2025 copy.
- **Name matching.** Names are lowercased with punctuation removed.
  - A listing flags a section only on an exact stream + county + section-number match to our sections (349
    listings, 292 sections).
  - Other listings are located at stream level: on a PFBC stream, or in the Natural Reproduction / Class A
    layers by name + county. Those are used only for distances.
- **Nursery locations** come from Gavin's `Coop_nurseries.geojson`, matched by nursery name, then sponsor
  name, then a unique name-contains match (e.g. "Kenny Stewart Memorial Nursery" → "Kenny Stewart"). That
  locates 123 of 133 nurseries.
- **Distances** are straight lines from the nursery to the nearest point of the matched water.
- **Manual review:** `logs/03_coop_review.csv` lists the following. Suggested names are same-county names
  with a string similarity of at least 0.85; they are hints only.
  - unmatched waters
  - unlocated nurseries
  - listings on sections PFBC no longer stocks
  - listings on Class A sections

**River key, region, area and cap** (`scripts/04_river_cap.py`, 2026-09-27)
- **River key.** `river_id` = PFBC's `RFP_WaterID` (695 rivers). No river_id has two names. Five name +
  county pairs have two or three river_ids (e.g. Mill Creek, Berks: 3080, 3180, 3182): different streams with
  the same name, which is why names are never the key.
- **Region.** From PFBC's 2026 *Pennsylvania Fishing Summary*, which lists regulated trout waters region by
  region under county headings ("BERKS:"). A county's region is the region whose list it heads.
  - Two-county headings ("MIFFLIN/UNION:" for Penns Creek) are boundary waters printed in both regions'
    lists, so they're skipped.
  - All 67 counties are found, each in exactly one region. A one-time cross-check against PFBC's
    law-enforcement region polygons (fbweb `LawEnforcement_Regions`) agreed for all 67 by majority of county
    area (not kept: the polygons split Northumberland 71/29 and Armstrong 95/5).
  - Sections spanning two counties never span two regions.
- **Area.** `area_acres` = `length_mi` × width (m) × 1,609.344 m/mi ÷ 4,046.856 m²/acre. No PFBC layer
  publishes a measured width or acreage (`known_gaps.md`), so the width is the top of the PFBC width class,
  or the midpoint for `area_acres_mid` (`parameters.csv`).
- **Density cap.** `access_rate` is taken from `pfbc_stocking_rates.csv` (Table 18) as the highest rate for
  the section's biomass + width at its own use potential or a worse one (Low < Good < High), over all
  population classes. Table 18 gives biomass B + High at widths 2–3 a flat 147/acre, below B + Good's 323;
  counting worse access levels lifts those 17 sections to 323 so better access never lowers the cap
  (decision 2026-09-27, `model_design.md` § Density bound). `cap_rate_river` (the sensitivity) is the highest
  rate for the biomass + width at any access.
- **Special-program rates.** `program_rate` holds the Guidelines' own rate for programs that replace Table 18,
  transcribed into `scripts/04_river_cap.py` with the table numbers: Table 46 for Delayed Harvest Artificial
  Lures Only sections (`reg_name` contains "Delayed Harvest"; 56) and Table 45 for tailwaters. No layer flags
  tailwaters, so the script lists them by hand: Youghiogheny 1327_1 and Conneauttee Creek 2649_1 (assumption;
  the other dam sections checked are in `known_gaps.md`). `cap_rate`
  (the rate `cap_fish` uses) is the higher of `access_rate` and `program_rate`; `cap_rate_river` likewise. The "today's stocking" that caps the Class A and above-cap
  sections is the 2026 count (`total_2026`, all five species; decision 2026-09-27), not a multi-year mean.

**Environment** (`scripts/05_environment.py`, 2026-09-27)
- **Exclusion reasons** come from rules on the existing columns (`class_a_flag`, `wilderness_flag`,
  `total_2026`). The one reason not in the data, Blue Hole Creek's cadmium/lead removal (GoErie, 2026-01-31),
  is written into the script with its source.
- **Wild brook trout.** `wild_brook_present` comes from the same Class A `Fishery` keyword match as
  `class_a_wild_brook`. The 17 Class A overlaps PFBC stocks are all brown trout fisheries ("Brown", "Wild
  Brown Trout Fishery"); Buffalo Creek's Class A record has no species text. Every other section is NA:
  Natural Reproduction and Wilderness have no species field.
- **Natural reproduction share.** `nat_repro_share` = shared river miles ÷ the section's river-mile length
  (`rm_length_mi`, so both are PFBC river miles), capped at 1. It's 0 where the overlap is 100 m or less,
  matching the flag.

**Angler survey tables** (`scripts/00_extract_angler_survey.py`, 2026-09-27)
- **Source:** PFBC's 2023 trout angler survey report (Responsive Management), downloaded from pa.gov. Tables
  are read from the PDF text with pdfplumber; values are as printed.
- **Statewide values** come from each page's bar chart, typed into the script and checked against the
  rendered page. A bar the chart doesn't show is NA (p140 "Do not know"), not 0. Regional values come from the
  page's table.
- **Changes from the published tables:**
  - `*` (less than 0.5%) is stored as NA with `lt_0_5_pct = True`.
  - Water names are split into `name_base` and `county_qualifier` ("Pine Creek (Lycoming or Tioga County)" →
    "Pine Creek", "Lycoming or Tioga"; "(other county or not sure of county)" → "other/unsure"). The full
    name is kept in `waterbody`, spelled as printed.

**County anglers** (`scripts/06_county_anglers.py`, 2026-09-28)
- **Source:** PFBC's *2024 Annual Fishing License & Permit Sales by Agent County* (4 pages: annual, then
  multi-year). Numbers are right-aligned and blank cells print nothing, so each number goes to the column
  whose right edge is nearest. Every row is checked against the PDF's own row totals, and the county rows
  against its Total, Internet and Grand Total rows (all match).
- **Anglers** = trout + combo permits sold by the county's agents (annual, plus 3-, 5- and 10-year permits
  sold in 2024) − non-resident and tourist licenses sold there + online resident permits × the county's share
  of PA population. Online resident permits = online trout + combo permits − online non-resident and tourist
  licenses (117,500). Result: 421,615 resident anglers, 3.2 per 100 residents.
- **Changes:** "Out of State" agents (818 permits, fewer than their 1,015 non-resident licenses) are dropped as
  non-residents. "Mckean" is matched to the Census "McKean" case-insensitively.
- **Population:** 2020 Census block groups (Centers of Population file) summed to counties.

**Proximity demand** (`scripts/08_demand.py`, 2026-09-28; design in `model_design.md` § Angler benefit)
- **Days fished:** each home region's mean days fished for stocked trout (p115) from band midpoints (41–50 →
  45.5, ..., 6–10 → 8) and 105 for "Over 50 days" (`parameters.csv`), with "Don't know" dropped. This
  reproduces the published statewide mean (20.57 vs 20.6). Northcentral 26.7, the others 19.1–21.4.
- **Angler-days per block group** = 2020 population × county angler rate × home-region days: 8.72M statewide.
  68 block groups have no population.
- **Distance:** straight-line miles in EPSG:26918 from the block group's center of population (Census) to
  the section midpoint, × 1.3 (`circuity_factor`). The farthest pair is 417 road mi.
- **Bands:** each home region's p93 shares ("Don't know" dropped), with a distance in (0, 10] going to
  "0–10 miles", (10, 20] to "11–20 miles", and so on; "More than 150 miles" is open-ended. Within a band a
  block group's angler-days are split among the 2026-stocked sections in it by `length_mi`. A band with no
  section passes its share to the block group's other bands in proportion (783 of 122,076 block group × band
  cells; 2.4% of angler-days).
- **Variants:** `prox_days_pooled` uses one in-state curve, the regional curves weighted by each region's
  angler-days. `prox_days_pop` puts every county at the state angler rate and is rescaled to the same
  statewide total (it was 8.52M, since the regional mix of days changes), so it only moves demand around.
- **Checks:** all three columns sum to the statewide total (asserted). Each home region's share of angler-days
  landing in its own region is 74–84%, against 65–89% of favorite waters in the home region in the survey
  (p85, "Not sure of county" left out; by region in `logs/08_demand.log`).
- **Candidates:** the 1,022 sections stocked in 2026. A scenario that lets dropped sections back needs a rerun
  with them in the section set, since demand is split among the sections that exist.

**Survey water crosswalk** (`scripts/07_survey_crosswalk.py`, 2026-09-28)
- **Matching:** each survey water (p76–77) is matched to a 2026-stocked `river_id` by normalized name
  (case, punctuation, Br/W/E/N/S/Cr abbreviations), restricted to the named county when the survey gives one.
  A wrong match costs more than no match (an unmatched share still gets placed, just not on that water), so
  anything unclear goes to `logs/07_survey_crosswalk_review.csv` with no river.
- **Several rivers with one name:** each home region's mentions (p78–83 % × the region's share of resident
  anglers from `county_anglers.csv`) go to the candidate in that region when there is exactly one. The water
  is split across candidates in proportion to those mentions when at least 80% of the mentions from regions
  holding a candidate are resolved this way and at least half of all its mentions are; a candidate under 10%
  is dropped. Examples: French Creek 75% Chester's / 25% Erie's, Bald Eagle Creek 71% Centre's, Elk Creek
  all Erie's.
- **Hand decisions** (in the script with reasons): "Raystown Branch" is PFBC's Raystown Branch Juniata River,
  and "Big Swickley Creek" is Big Sewickley Creek. Six doubtful name matches (e.g. Bush Kill, which could be
  Pike County's or Northampton's Bushkill Creek) are sent to review instead.
- **Not matched:** 39 lakes (name contains Lake, Reservoir, Pond or Dam), "Other", "Do not know" and "other
  county or not sure" rows, 2 waters not stocked in 2026 and 5 with no PFBC section at all (e.g. the main stem
  of the Clarion River; only its branches are stocked).
- **Result:** 63.1% of all mentions (including Other and Don't know) land on 160 rivers stocked in 2026; 16
  waters (6.4% of mentions) wait for review. The survey's county spelling "Schuykill" is read as Schuylkill.

**Preference demand** (`scripts/08_demand.py`, 2026-09-28)
- A water's share = its % ÷ all mentions (219.5%: up to three waters each, incl. Other and Don't know;
  "<0.5%" counts as 0.25%, `parameters.csv`). Share × `match_share` × statewide angler-days is split over the
  river's 2026-stocked sections by `length_mi` (`pref_days_named`).
- The unplaced 36.9% is spread in proportion to `prox_days`, so `pref_days` sums to the same statewide total
  (asserted).
- **Per-mile flag:** a river whose preference per stocked mile exceeds the state's highest `prox_days` per
  mile (39,537, Cascade Creek in Erie) is flagged, not capped. Only the Youghiogheny is (71,302 per mile on its
  1.1 mi tailwater).
- **Destination index** = the river's preference ÷ its proximity angler-days (median 1.4; Tulpehocken 1.0,
  Yellow Breeches 1.3, Pine Creek 5.0, Kettle Creek 6.9). Per-river detail: `logs/08_demand_waters.csv`.

**Regulation flags** (`scripts/08_demand.py`) come from PFBC's own fields: `dhalo` = `reg_name` contains
"Delayed Harvest" (56), `catch_release` = any of its 5 catch-and-release spellings (30), `keystone_select` =
`program_name` "KSSTW" (24), `open_year_round` = "Stocked Trout Waters Open Year-Round" (16).

**Stocking schedule** (`scripts/09_stocking_schedule.py`, 2026-09-28)
- **Source:** PFBC's planned 2026 adult trout stocking schedule (fbweb.pa.gov/TroutStocking; endpoints in
  `source_inventory.md`), one request per county. It says events are "subject to change without notice", and
  only 2026 is served. Each record gives the water, section number, limits, date (or only a week), species as
  X marks (no counts), meeting place and time, hatchery, regulation and season.
- **Matching** (2,734 records): a stream record gets the `section_id` of the first rule that gives exactly one
  section: (1) section number + upper and lower limit text; (2) water name (before any ", Trib To ...") +
  county + section number; (3) upper-limit point within 100 m of a same-name, same-number section line; (4) an
  identical listing already matched under another county. Nothing else is guessed: 4 waters stay unmatched
  (`logs/09_schedule_unmatched.csv`). Lakes (section 0) get a `lake_key` (name @ coordinates), no section.
- **Repeats:** a section on a county line is listed under each county, and some events are listed once per
  regulation piece (like the GIS layer's two-row sections). The 256 repeats are merged to one row per section ×
  date: the best-matched listing is kept, species marks are OR-ed and regulations joined. Result: 2,474 events,
  2,102 on streams (all 1,022 candidate sections have at least one) and 372 on 127 lakes. 74 events give only a
  week.
- **Assumption: equal split of fish over events.** A section's 2026 count of a species (GIS layer) is split
  equally over its events marked with that species. Brood fish are split over all of its events. Each event's
  fish are credited to its hatchery, and the sum per hatchery is its 2026 **stream supply**
  (`hatchery_schedule_supply.csv`). Every 2026 stream fish is placed once (checked per section). Lake events
  have no counts in any source, so lake fish stay NA.
- **Comparison with the lbs split:** shares among the 8 hatcheries with a lbs figure differ by up to 4 points
  (Tylersville 12.6% vs 16.5%, Corry 9.7% vs 6.5%). The lbs figures cover all production, lakes included,
  while the schedule shares are stream fish only.

**Runs and clusters** (`scripts/10_runs_clusters.py`, 2026-09-28)
- **Run** = one truck meeting as PFBC lists it: date + hatchery + meeting place + time (1,015 runs on 2026
  stream sections, 1–7 sections each). Spellings of a meeting place on the same date, hatchery and time are
  merged when their string similarity is ≥ 0.85 (5 merged; variants scored ≥ 0.89, different places ≤ 0.53).
  Week-of-only events have no run.
- **Assumption: sections that share half their runs share a truck route.** Two sections are linked when
  runs holding both ÷ the smaller of their run counts ≥ `cluster_share_min` (0.5); clusters are the connected
  components. Default: 351 clusters, 103 singletons, up to 18 sections. Strict majority (> 0.5, the
  sensitivity): 528 clusters, 237 singletons, up to 7. Most sections have 2 or 3 runs, so 362 of the 1,107
  linked pairs sit at exactly 0.5 and the rule matters.
- **Distances** (assumption: straight-line miles between section midpoints × `circuity_factor` 1.3 = road miles):
  `detour_mi` to the nearest section in the same cluster (0 for singletons; median 3.8, max 55.8),
  `detour_nn_mi` to the nearest 2026 section of any cluster (the geographic fallback; median 3.3),
  `cluster_mi` = minimum spanning tree over the members (a route-length proxy), `span_mi` = the farthest pair.
  No cluster spans more than `cluster_span_check_mi` (60); the widest, Codorus Creek with Falling Spring Branch
  (56.9 mi), is kept because PFBC lists both runs at one meeting place.
- **Check:** Bear Creek 3197_2 and 3197_3 share both of their Tylersville runs (Feb 26, May 7) and are each
  other's nearest section (2.7 road-mi).

**Road distances** (`scripts/11_road_distances.py`, `scripts/12_section_road_distances.py`, first used 2026-09-28; Gavin)
- **Source:** the public OSRM table service (driving, fastest route; data (c) OpenStreetMap contributors). `source_inventory.md` § Road
  distances; the rule 3 waiver is in `known_gaps.md`.
- **Points:** each section's midpoint (`mid_lat`, `mid_lon` in `sections.parquet`, Nate's) is snapped by OSRM to the nearest road. Median snap is 97 m
  (90th percentile 327 m); 7 sections snap more than 1 km (maximum 2,302 m). They are kept, not corrected.
- **Hatchery table:** all 13 State Fish Hatcheries x the 1,045 sections stocked 2024-26 = 13,585 rows (km, mi, drive minutes, snap distances).
- **Section-to-section table:** the 1,022 sections stocked in 2026, every ordered pair = 1,044,484 rows, queried as 11 x 11 = 121 blocks of 100 x 100.
  Asymmetry is small (median 0.3%), so the clustering scripts use the mean of the two directions.
- **Checks (reported by script 12, all pass):** row count, no duplicate pairs, no missing routes, zero diagonal, snap distances equal the hatchery
  table's, road never shorter than straight-line beyond the snap, median road / straight-line ratio 1.34, asymmetry, triangle check.
- **Circuity:** measured road / straight-line runs about 1.5 under 10 mi and 1.3 over 80 mi (`outputs/tables/section_road_distance/circuity_by_distance.csv`),
  against the flat `circuity_factor` 1.3 Nate's scripts use for straight-line distances.

**Map layers.** The wild-trout context layers in `pa_trout.gpkg` are simplified to a 5 m tolerance to keep
the file small. All overlaps are computed from the full-resolution layers first.

**Validation (it's asserted in the script).** Bear Creek (Schuylkill), 2026:
- 3197_2 = 150 brown + 850 rainbow, and 3197_3 = 900 rainbow, for a total of 150 brown + 1,750 rainbow.
- Neither section is flagged Class A: Class A is Section 01, river miles 10.47–7.05, and it only touches
  them.
- Both are flagged natural reproduction (reach 10.47–2.21).
