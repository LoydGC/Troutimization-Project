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
- **Population** (since 2026-10-04): 2020 Census counts (`POP100`, the PL 94-171 total population) per county
  subdivision from TIGERweb's Census 2020 layers, summed to counties (`source_inventory.md` § Census). Before,
  2020 block groups were summed; the numbers are the same. Checks (asserted): the 2,573 subdivisions add to
  PA's 13,002,700, and each county's subdivisions add to its own TIGERweb county count. Those counts equal the
  block-group sums used before (67 of 67), so `county_anglers` didn't change. The plan was the Census Data API
  (`api.census.gov`, 2020 PL 94-171 `P1_001N`), but it now refuses data requests without a key.

**Subdivision anglers** (`scripts/06_county_anglers.py`, 2026-10-04): the proximity origins.
- **Origins** are Gavin's 2,567 county subdivisions (1 Jan 2026 boundaries, `county_subdivisions`). The 2020
  counts are matched on GEOID: 2,565 keep their code. Each of the 7 2020 subdivisions with no 2026 code goes
  to the 2026 subdivision that holds its 2020 internal point (TIGERweb ACS2026 point queries, saved raw):
  - Mount Lebanon and Penn Hills, Allegheny: renamed from township to municipality, with a new code.
  - South New Castle borough (647 people) → Shenango township, Lawrence.
  - Wheatland borough (585) → Hermitage city, Mercer.
  - Callimont borough (56) → Larimer township, Somerset.
  - East Keating township (7) → Noyes township, Clinton.
  - Falls Creek borough's Clearfield County part (42) → Falls Creek borough, Jefferson County: the only
    county change.

  Lake Erie's "County subdivisions not defined" (0 people) has no origin. Boundary changes that kept their
  codes (annexations) can't be seen, so the 2020 count of each code sits on its 2026 polygon.
- **Anglers** = 2020 population × the angler rate of the subdivision's (2026) county. Falls Creek's 42 people
  take Jefferson's rate, so Clearfield's subdivisions hold 42 fewer people than its 2020 count, Jefferson's
  42 more, and statewide anglers are 421,614.3 instead of 421,615. One subdivision has no population (Ashland
  borough's Columbia County part).

**Proximity demand** (`scripts/08_demand.py`, 2026-09-28; origins and distance changed 2026-10-04; design in
`model_design.md` § Angler benefit)
- **Days fished:** each home region's mean days fished for stocked trout (p115) from band midpoints (41–50 →
  45.5, ..., 6–10 → 8) and 105 for "Over 50 days" (`parameters.csv`), with "Don't know" dropped. This
  reproduces the published statewide mean (20.57 vs 20.6). Northcentral 26.7, the others 19.1–21.4.
- **Lake days removed** (decision 2026-10-03): the survey's days fished include lake days, and lakes aren't in
  the section set. Each home region's lake share of days = % primarily fishing lakes + 0.5 × % fishing both about
  equally (p88; `lake_days_both_share` in `parameters.csv`), so 'primarily streams' anglers count no lake days
  and 'primarily lakes' anglers all lake days (assumed to offset). Northwest and Southeast 13.1%, Southcentral
  14.5%, Northcentral 19.0%, Southwest 25.5%, Northeast 29.0%; 18.3% statewide, close to PFBC's ~20% of adult
  trout stocked in lakes.
- **Stream angler-days per county subdivision** = `subdivision_anglers.anglers` × home-region days ×
  (1 − home-region lake share), with the home region taken from the subdivision's county: 7,121,847 statewide
  (8,717,546 with lake days). It was 7,121,842 on block groups. That build multiplied population by county
  rates rounded to 6 decimals (about 21 angler-days low), and Falls Creek's 42 people now take Jefferson's
  lower rate (about 16 fewer).
- **Distance:** Gavin's OSRM road miles from each subdivision's centroid to the section midpoint
  (`subdivision_to_section_road_distance`), with no circuity factor. Kept: the 2,623,474 pairs to the 1,022
  sections stocked in 2026, of 2,682,515 (the other 23 sections are left out). Every pair has a route. No
  pair is 0 mi (0 would go to the first band); the median nearest section is 5.2 road mi and the farthest pair
  440.2.
- **Bands:** each home region's p93 shares ("Don't know" dropped), with a distance in [0, 10] going to
  "0–10 miles", (10, 20] to "11–20 miles", and so on. "More than 150 miles" runs to the farthest pair. Within a
  band a subdivision's angler-days are split among the 2026-stocked sections in it by `length_mi`. A band with
  no section passes its share to the next band out that has one (decision 2026-10-04; to the nearest band in if
  none farther out does, which never happens in the build): 312 of 30,804 subdivision × band cells, 4.9% of
  angler-days (2.4% on block groups, where the share was re-spread over the other bands in proportion). Nearly all of it (4.8 points) is first-band trips from
  origins whose nearest stocked section is just past 10 road mi, because a city is a single point:
  Pittsburgh 10.2 mi, State College 10.9, Wilkes-Barre 11.0. Their first-band share lands in 11–20 mi. Against
  the proportional re-spread, section `D_s` moves −6% to +5% (p5–p95), rank correlation 0.999.
- **Variants:** `prox_days_pooled` uses one in-state curve, the regional curves weighted by each region's
  angler-days. `prox_days_pop` puts every county at the state angler rate and is rescaled to the same
  statewide total (it was 7.04M, since the regional mix of days changes), so it only moves demand around.
- **Checks:** all three columns sum to the statewide total (asserted). Each home region's share of angler-days
  landing in its own region is 77–86% (74–84% on block groups), against 65–89% of favorite waters in the home
  region in the survey (p85, "Not sure of county" left out; by region in `logs/08_demand.log`).
- **Change from the block-group build** (2026-10-04, per section; `D_s` at w = 0.5):
  - New ÷ old `D_s`: 0.78 at p5, 1.00 at the median, 1.29 at p95, rank correlation 0.99. For `prox_days`:
    0.73 / 1.00 / 1.34, rank correlation 0.97. Each region's share of demand moves 0.3 points or less.
  - The biggest drops (×0.4–0.6) sit behind rivers and ridges, where road miles run 1.7–2.8× the straight
    line. Towns that were within 10 mi by straight line × 1.3 are now 15–30 road mi away: East Licking Creek
    2888_4 (Lewistown), Conoy Creek 396_2 and Fishing Creek 63_2 (across the Susquehanna), West Branch
    Conestoga 418_2. Another drop: a city whose centroid lands just past 10 road mi (Gardner Creek 1759_2 and
    Scranton, 10.5).
  - The biggest gains (×1.6–2.6): a city centroid now inside 10 road mi (Lycoming Creek 113_4 and
    Williamsport, Blair Gap Run 3211_2 and Logan township), or less first-band competition (Rose Pond Branch
    2105_2, Meadow Creek 3131_2).
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
  waters (6.4% of mentions) wait for review. With lake mentions left out (Preference demand below), that's
  69.5% and 7.0% of stream mentions. The survey's county spelling "Schuykill" is read as Schuylkill.

**Preference demand** (`scripts/08_demand.py`, 2026-09-28)
- A water's share = its % ÷ all stream mentions: 219.5% in all (up to three waters each, incl. Other and
  Don't know; "<0.5%" counts as 0.25%, `parameters.csv`), minus the 39 lakes' 20.25%, which leave with the lake
  days (decision 2026-10-03), = 199.25%. Share × `match_share` × statewide stream angler-days is split over the
  river's 2026-stocked sections by `length_mi` (`pref_days_named`).
- The unplaced 30.5% (Other, Don't know, unmatched, not stocked in 2026) is spread in proportion to
  `prox_days`, so `pref_days` sums to the same statewide total (asserted).
- **Per-mile flag:** a river whose preference per stocked mile exceeds the state's highest `prox_days` per
  mile (28,484, Cascade Creek in Erie; 34,338 on block groups) is flagged, not capped. Two are: the Youghiogheny
  (64,171 per mile on its 1.1 mi tailwater) and, since the 2026-10-04 rebuild, White Clay Creek 2027_1 (32,201
  per mile on 1.1 mi in Chester County).
- **Destination index** = the river's preference ÷ its proximity angler-days (median 1.5; Tulpehocken 1.1,
  Yellow Breeches 1.3, Pine Creek 6.6, Kettle Creek 10.5). Per-river detail: `logs/08_demand_waters.csv`.

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

**Road distances** (`scripts/11_road_distances.py`, `scripts/12_section_road_distances.py`, first used 2026-09-28; Gavin; the subdivision table below uses the same method)
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

**County subdivisions** (`scripts/19_subdivision_road_distances.py`, 2026-10-03; Gavin)
- **Source and vintage:** Census TIGERweb, County Subdivisions layer of `tigerWMS_ACS2026`: boundaries as of 1 Jan 2026, the newest Census publishes
  (downloadable TIGER/Line stops at 2025; PA's set is identical in both). `source_inventory.md` § County subdivisions has the check and the endpoint.
  Saved raw under `data/raw/census_cousub/2026-10-03/` (11 pages, 2,568 features, manifest rows).
- **Changes to the Census data:** the one row with no land (Lake Erie's "County subdivisions not defined", GEOID 4204900000) is left out, leaving 2,567
  subdivisions in 67 counties. Nothing else is filtered, repaired or moved. County names come from `county_anglers.csv` by FIPS.
- **Origin point:** each polygon's geometric centroid, computed in EPSG:26918 and stored in EPSG:4326. It equals Census's own CENTLAT/CENTLON to within
  1.6 m. 44 centroids fall outside their subdivision (at most 1,075 m); they are flagged, not moved, and Census's internal point is kept alongside
  (`known_gaps.md` § County subdivisions). OSRM snaps each origin to the nearest road: median 51 m, 90th percentile 330 m, 23 over 1 km, maximum
  2,164 m (McNett township, Lycoming) (`road_snap_m`). They are kept, not corrected, as with the section midpoints.
- **One origin moved:** Pine township (Armstrong)'s centroid snaps 6 m onto a road fragment cut off from the rest of the road network, so it had no
  route to any section (1,045 missing pairs on the first run; Census's internal point is on the same fragment). The script now looks, on a 250 m grid
  inside the polygon, for the point nearest the centroid that does route, and routes from it (418 m away, snaps 97 m): `origin_point`,
  `origin_shift_m`. Every other subdivision is routed from its centroid. The grid point is saved beside the block cache so reruns make no requests.
- **Table:** every county subdivision x every section stocked 2024-26 (the same 1,045 midpoints as the hatchery table) = 2,682,515 rows, from the same OSRM
  service and settings as the other road tables, queried as 26 x 11 = 286 blocks of 100 x 100 in the direction home to stream. Parquet only.
- **Checks (reported by script 19):** row count, no duplicate pairs, no missing routes, section snap distances equal the hatchery table's, road never shorter
  than straight-line beyond the snap, median road / straight-line ratio 1.32, our centroids against Census's, origins within 5 km of a road, and a cross-check
  against the hatchery table (the drive times from a hatchery and from the subdivision it sits in to any section differ by no more than the drive time
  between them, the triangle inequality; 0 of 13,585 pairs break it). All 9 pass. Results: `outputs/tables/subdivision_road_distance/validation.csv`; circuity by distance band: `circuity_by_distance.csv`
  (road / straight-line median 1.49 under 5 mi, 1.38 at 20-40 mi, 1.31 over 80 mi).
- **What the table says:** road miles run from 0 to 440 (median 152); the nearest stocked section is a median 5.1 road miles from a subdivision (90th percentile
  10.4, maximum 22.7). The parquet is 29.8 MB.

**Transport cost inputs** (`scripts/20_transport_cost.py`, 2026-10-04; design in `model_design.md` § Transport cost)
- **Supply nodes:** PFBC's State Fish Hatcheries layer (13), names stripped of trailing spaces. Supply is each hatchery's
  2026 stream fish from the schedule (`hatchery_schedule_supply.csv`); the 4 with no 2026 stream events get 0. No
  production-pounds split (decision 2026-10-04).
- **Haul miles:** Gavin's road miles and cluster averages are joined, not rebuilt. The script recomputes each cluster's mean
  from `road_mi` and asserts it matches `cluster_hatchery_distance` (all three labellings). Cluster average vs a section's
  own miles: mean gap 3.2 mi for k-medoids (p90 7.0), 4.2 for the schedule clusters, 3.1 for hierarchical.
- **Baseline flows:** the 2,102 stream events of the 2026 schedule; 19 on sections with no 2026 count (stocked in 2025, or
  unmatched) carry no fish and are left out. Flows sum to each section's `total_2026` (largest gap 0.03 fish).
- **Checks (logged):** loads vs supply, baseline cost under scheduled and nearest hatcheries, and implied truck-miles vs the
  reported ~300,000 fleet miles.

**Model input** (`scripts/21_model_input.py`, 2026-10-04): a 1:1 join of `sections`, `environment` and `demand` on
`section_id` for the 1,022 candidates (every join matched all rows, logged). No values are changed; the impact weights
(`impact_weighted`, `impact_simple`, `impact_overlap`) are computed from `biomass_class` and `nat_repro_share` with
the `impact_weight` rows of `parameters.csv`.

**Map layers.** The wild-trout context layers in `pa_trout.gpkg` are simplified to a 5 m tolerance to keep
the file small. All overlaps are computed from the full-resolution layers first.

**Validation (it's asserted in the script).** Bear Creek (Schuylkill), 2026:
- 3197_2 = 150 brown + 850 rainbow, and 3197_3 = 900 rainbow, for a total of 150 brown + 1,750 rainbow.
- Neither section is flagged Class A: Class A is Section 01, river miles 10.47–7.05, and it only touches
  them.
- Both are flagged natural reproduction (reach 10.47–2.21).
