# Claude Code prompts: PA trout stocking optimization data

Paste these one at a time and review each phase before sending the next. `CLAUDE.md` holds the model framing,
the agreed simplifications, and the rules, so the prompts don't repeat them.

Order: 0 → 1 → 2 → 3 gets the baseline. 4–7 each build one model component (4 first, since 5 and 6 use its
area and river_id). 8–9 assemble and check. Upgrades are at the end, for when time allows.

**Status (2026-09-28):** built on branch `sections-pull`: the angler-survey tables
(`scripts/00_extract_angler_survey.py`), the sections pull (`scripts/01_download_pfbc_layers.py`,
`scripts/02_build_sections.py`), the co-op stocking list (`scripts/03_coop_stockings.py`, `coop_stocked`
flag), the river key, region, area and density cap (`scripts/04_river_cap.py`), the environment table
(`scripts/05_environment.py`) and angler demand (`scripts/06_county_anglers.py`,
`scripts/07_survey_crosswalk.py`, `scripts/08_demand.py`). Gavin's main (distance notebooks) was merged into it
2026-09-27. `sections-pull` is pushed but not merged into main: the pull request (main ← sections-pull) is
drafted, not opened yet. Done so far, so skip these parts when sending the prompts:
- Prompt 0 (4 partner raw files still need a source from Gavin)
- Prompt 1 in part: `docs/source_inventory.md` lists the sources in use
- Prompt 2 for the stocked-section and wild-trout layers; Prompts 3, 4, 5, 6 (p153 skipped by decision)

**Waiting on Gavin** (questions for the pull request): sources for his 4 raw files (`docs/source_inventory.md`
§ Partner data); distances for the 8 sections stocked in 2026 that his layer lacks (`docs/known_gaps.md`
§ Gavin's stocked-streams layer); OK to `git rm --cached` his raw files (Prompt 0 step 1). From the 2026
schedule (2026-09-28): Tionesta hatchery stocks 10 sections but isn't flagged TROUT in `pa_hatcheries.gpkg`,
so his distances need it as a node (Linesville and Pleasant Mount stock no streams); and does he agree to cost
the baseline from the scheduled hatchery and to take supply from the schedule instead of pounds?
**Waiting on us:** decide the 22 rows of `logs/07_survey_crosswalk_review.csv` (16 undecided names, 6.4% of
survey mentions, until then spread like proximity) and `logs/03_coop_review.csv`; the detour charge
(`docs/model_design.md` § Open questions); optionally Raystown/Tionesta as tailwaters (`docs/known_gaps.md`
§ Tailwater sections).

**Next:** Prompt 7 once Gavin's distances are keyed on `section_id` (its schedule-clusters upgrade is built);
Prompt 8 can start on everything else.
Script order: 00 → 01 → 02 → 03 → 04 → 05, then 06 → 07 → 08 and 09 → 10 (00 stands alone; 03 and 04 add
columns to `sections`, so rerun them after 02; 06–10 read `sections` and don't change it).

---

## Prompt 0: Housekeeping

```
Read CLAUDE.md. Tidy the repo to match its Layout section.
1. [DONE 2026-09-26. 2026-09-27: pa_trout.gpkg and data/references/ (except angler_survey/) gitignored
   too; the partner's raw files are in the manifest, but 4 still need a source from Gavin.]
   Git: gitignore data/raw/** except manifest.csv and .gitkeep files; stop ignoring data/processed/
   (keep a rule that blocks files over 50 MB). Also ignore data/references/*.html and the requests-cache
   database. The new rules only affect new raw files. Add each already-committed raw file to
   data/raw/manifest.csv with its source URL so it can be re-downloaded. ON HOLD: untracking them with
   `git rm --cached` waits for the partner's OK (LoydGC committed some on purpose).
2. [DONE 2026-09-27] Angler survey: the PDF is an official PFBC source. Move data/references/troutanglersurveyreport-2023.pdf
   to data/raw/pfbc_angler_survey_2023/ and add its PFBC URL to the manifest. Move
   data/references/angler_survey/extract_angler_survey_2023.py to scripts/00_extract_angler_survey.py,
   point it at the new paths, and have it write to data/processed/angler_survey/. Re-run it and confirm
   the CSVs match the current ones exactly, then delete the old copies and files.zip (check the zip
   holds nothing extra first).
3. [DONE 2026-09-26] requirements.txt: add everything in CLAUDE.md's Stack (01_data_prep already uses geopandas). Create a
   venv and install.
4. [DONE 2026-09-26] scripts/common.py with:
   - a cached, rate-limited HTTP session (requests-cache, 1 req/sec per host, retries with backoff)
   - save_raw(source, name, content, url): writes to data/raw/<source>/<date>/ and appends to manifest.csv
   - fetch_layer(layer_url): ArcGIS REST pager. Read ?f=pjson, get the count with returnCountOnly=true,
     page with resultOffset/resultRecordCount, outFields=*, outSR=4326, f=geojson (f=json for tables).
     Save raw pages; assert downloaded count == server count.
   Add pytest tests for the pager with mocked responses.
5. [DONE 2026-09-26] data/README.md: point to data/raw/manifest.csv and docs/source_inventory.md instead of keeping its own list.
Stop when tests pass and show the resulting tree and `git status`.
```

## Prompt 1: Source inventory (no bulk downloading)

Partly done 2026-09-27: `docs/source_inventory.md` lists the layers and documents already in use. Still to
do: the crawl in step 1, saving the trout plans in step 2, and step 3. Add to the file; don't rewrite it.

```
Build docs/source_inventory.md with one short table per model component. For each source give the
verified URL, format, record count, key fields, years covered, and how it joins to section_id.
1. PFBC/PASDA GIS: crawl https://fbweb.pa.gov/arcgis/rest/services and
   https://mapservices.pasda.psu.edu/server/rest/services/pasda/PAFishBoat/MapServer (?f=pjson). List what
   exists, but only detail layers we need: trout stocked sections for every available year, Approved Trout
   Waters, Class A, Natural Reproduction, Wilderness Trout Streams, special regulations (DHALO, Keystone
   Select), Access, Hatcheries, and a PFBC regions layer. Add a short "fields by stocking year" comparison
   and say whether any year covers 2022 (the survey year): 2024–26 don't; checking for a 2023 layer is optional.
2. PFBC documents (save PDFs to data/raw): Operational Guidelines for trout management (5th ed., already in
   data/raw/pfbc_docs/), the 2020–24 and 2025–29 trout plans, and the current Class A stocking exemption list (only the Jan 2026 batch found so far: GoErie 2026-01-31; Guidelines Appendix A describes, without naming, the 13 Class A sections PFBC itself kept stocking).
   Links are in docs/env_research.md.
3. Population: Census ACS 5-year block-group population and TIGER block-group centroids for PA.
Do not bulk download.
```

## Prompt 2: Download GIS layers

```
scripts/01_download_pfbc_layers.py: using fetch_layer, download the layers flagged in
docs/source_inventory.md. The sections pull already covers fbweb stocked sections 2024, 2025, 2026 and PASDA
PAFishBoat #9 Class A, #25 Natural Reproduction, #31 Wilderness; add the rest (lakes, access, hatcheries,
regions, special regulations). Save raw GeoJSON to data/raw/pfbc_gis/<date>/ and append to manifest.csv.
Write logs/phase2_qa.md with row counts vs server counts, null rates per field, duplicate section_id counts,
and stocking years per layer.
```

## Prompt 3: Sections and baseline stocking

```
scripts/02_build_sections.py. Key: section_id = f"{RFP_WaterID}_{SecNum}". Log counts before/after each step.
1. data/processed/sections.parquet + sections.csv: flat, NO geometry, one row per stocked stream section
   (union of the 2024–26 layers). Columns: ids (section_id, RFP_WaterID, SecNum, WtrName, County);
   location (mid_lat, mid_lon, upper/lower limit text, river miles, length_mi); management (AllocationCode
   parsed into biomass, use, population and width class; max_trout_per_acre from Table 18; Description as a
   label only; Reg_Name, SpecReg, program flags); stocking (wide counts by species for 2024, 2025, 2026;
   years stocked); overlap per rule 8 (class_a_overlap_mi, Class A species/Fishery, TroutBioma,
   nat_repro_overlap_mi, wilderness_overlap_mi).
2. data/processed/stocking_section_year.parquet (long, the baseline): section_id x year x species
   (brook|brown|rainbow|golden|brood) -> count. Map Total*Stocked fields to species. Sections split into 2 rows
   carry the full total in each: count once. Keep TotalAdultStocked_minusBrood as a check and log mismatches
   instead of fixing them.
3. data/processed/pa_trout.gpkg (EPSG:4326), layers: sections (lines: section_id plus a few key fields),
   hatcheries (points), class_a, nat_repro, wilderness.
Validate Bear Creek (Schuylkill) 2026: 3197_2 = 150 brown + 850 rainbow; 3197_3 = 900 rainbow;
total 150 brown + 1,750 rainbow. Overlap flags as in CLAUDE.md Known facts.
Report: years available, sections per year, total fish by species and year.
```

## Prompt 4: River key and area (add columns to sections)

[DONE 2026-09-27, `scripts/04_river_cap.py`. Changes from the text below: "baseline" = the 2026 count, not the
mean, so 4 sections, not 3, are above the river cap (Roaring Brook 1767_5 added); region comes from PFBC's 2026 Fishing
Summary (county lists by region). Area converts mi × m to acres in the script. Revised 2026-09-27: the cap now counts
the section's access (step 4 below, rerun); the river cap is kept as the sensitivity cap_fish_river, and
cap_fish_class_a_river was renamed cap_fish_class_a_grow. Then the Guidelines' special-program rates were added
(Tables 45-46: program, program_rate), leaving 7 sections above the cap, and the rate cap_fish uses was stored
as cap_rate (river_rate renamed cap_rate_river; parameter river_rate_per_acre renamed biomass_a_rate_per_acre).]

Decision 2026-09-27: use PFBC's own water id and width classes. No NHDPlus (that's an upgrade).

```
0. [DONE 2026-09-27] Fix the duplicate-row merge in scripts/02_build_sections.py (decision 2026-09-27). Duplicate section rows
   are always one "Stocked Trout Water" row + one "Commonwealth Inland Waters" row with the same counts, and
   their lines don't describe the same stretch. Unioning them overstated length and geometry (e.g. Hinckston
   Run 2079_2: merged line 7.4 mi vs 1.9 river miles). Instead, keep the "Stocked Trout Water" row's limits,
   Length_MI_ and line; count fish once as now. Add length_check_flag to every section where PFBC
   Length_MI_ and rm_length_mi differ by more than 25% (e.g. Brodhead Creek 2662_2: 6.9 vs 1.6 mi), and write
   the flagged sections to logs/ for review. Rebuild, then re-run 03.
data/processed/sections.parquet already exists (flat; length_mi, width_class from AllocationCode). ADD
columns on section_id:
1. river_id = rfp_water_id. Check it: log any river_id with more than one water_name, and any water_name +
   county with more than one river_id.
2. PFBC region (from county).
3. pfbc_length_mi = PFBC's own Length_MI_ from the stocked-sections layer (decision 2026-09-27: use PFBC's
   length for consistency with its per-acre rates). It matches PFBC river miles (median ratio 1.02). [DONE in
   step 0; our own geometric length was dropped 2026-09-27: PFBC numbers only. length_mi = Length_MI_, or
   river miles for the 9 flagged sections whose stocking fits river miles (length_source).] Duplicate
   sections use the "Stocked Trout Water" row's Length_MI_ (step 0).
   Width (decision 2026-09-27): width_top_m = top of the PFBC width class (Guidelines Table 14): 4 -> 4 m,
   3 -> 10, 2 -> 20, 1S -> 30, 1L -> 60 (1L is open-ended; 60 m is an assumption). width_mid_m = class
   midpoint for the tighter sensitivity: 3, 7, 15, 25, 40. No PFBC layer publishes a measured width or acres
   (searched 2026-09-27; docs/known_gaps.md). Put both in data/processed/parameters.csv (source = Guidelines
   Table 14; 1L top, class-4 midpoint and all midpoints = assumption). area_acres = length_mi x width_top_m;
   area_acres_mid = length_mi x width_mid_m.
4. Density cap (decision 2026-09-27, replacing the river cap; docs/model_design.md "Density bound"):
   access_rate = max Table 18 rate over population for the section's biomass + width at its own use potential
   (access) or any worse one (Low < Good < High), so better access never lowers the cap (Table 18 gives
   B + High at widths 2-3 a flat 147, below B + Good's 323). cap_rate_river = the max over access too (the
   sensitivity). Biomass A at widths 2-3 (no Table 18 rate) uses B's 323 (assumption; only used in the
   "Class A allowed to grow" scenario, cap_fish_class_a_grow).
   program_rate = the Guidelines' own rate for special programs: Table 46 for Delayed Harvest Artificial Lures
   Only (reg_name; 190/acre at widths 2-3, 133 at 1S/1L) and Table 45 for tailwaters (Youghiogheny 1327_1
   and Conneauttee 2649_1, listed by hand; 266 High, 247 Good). cap_rate = the higher of access_rate and program_rate; cap_rate_river likewise includes program_rate.
   cap_fish = max(cap_rate x area_acres, 300); cap_fish_mid the same with area_acres_mid;
   cap_fish_river the same with cap_rate_river. Sections whose 2026 stocking is above cap_fish get
   cap_fish = total_2026 and cap_source = "baseline" (7). Class A overlaps stocked in 2026 (17) get
   cap_fish = total_2026, cap_source = "class_a". Others cap_source = "program_rate" where the program rate
   set the cap, else "access_rate". (Exclusions are set in
   Prompt 5, not here.) Keep max_trout_per_acre (formula) for the "PFBC formula as cap" scenario. Log
   baseline / cap per section; report how many exceed cap_fish and cap_fish_mid.
Lakes are added later as rows with water_type = "lake".
Validate: Bear Creek (Schuylkill) sections share river_id 3197.
Upgrade: NHDPlus COMID + Chaplin 2005 width from drainage area.
```

## Prompt 5: Environment

[DONE 2026-09-27, `scripts/05_environment.py`. wild_brook_present is NA outside Class A (no species data;
`docs/known_gaps.md`). Step 5 dropped: nothing in the model uses historical density, and with no measured width
it mostly reflects the width assumption; 2026 stocking vs the cap is in `logs/04_cap_check.csv`. Added
nat_repro_share (continuous overlap) for the "partial overlap" impact score.]

```
Build data/processed/environment.parquet, one row per section. Follow docs/env_research.md.
The overlap columns (class_a_overlap_mi, Class A species/Fishery, TroutBioma, nat_repro_overlap_mi,
wilderness_overlap_mi) already exist in sections from 02_build_sections (rule 8). Build on them; don't
re-measure.
1. Exclusions (decision 2026-09-27): exclude + exclude_reason. "wilderness" (none today);
   "class_a_not_stocked" = Class A overlap AND not stocked in 2026 (Buffalo Creek 3190_2);
   "not_stocked_2026" = the other sections stocked in 2024-25 only (22), with Blue Hole Creek 3656_2 also
   "health" (cadmium/lead). Class A overlaps stocked in 2026 (17, incl. the 2 partial ones) are NOT
   excluded: Prompt 4 caps them at today's stocking. Scenario "dropped sections back" lifts
   not_stocked_2026 only.
2. wild_brook_present: from the Class A species/Fishery text (log how the text was parsed).
3. Natural reproduction: use nat_repro_flag as built (river miles only, rule 8).
4. Density bound: already built in Prompt 4 (cap_fish, cap_source; the density cap). Nothing to add here.
   The "PFBC formula as cap" scenario uses max_trout_per_acre x area_acres directly; the 11 sections with
   no Table 18 rate stay NA with a reason.
5. Historical density (trout/acre) and its ratio to max_trout_per_acre. Flag sections stocked above the
   Table 18 rate. (Baseline vs cap_fish is already logged in Prompt 4.)
Validate Bear Creek: stocked sections are NOT Class A overlap but ARE natural reproduction.
Report: excluded sections that were stocked in the baseline, and wild-brook sections stocked with brook trout.
```

## Prompt 6: Angler benefit

```
Build data/processed/demand.parquet: angler-days per section from two signals, kept as separate columns
(the model blends them). Plan revised 2026-09-27: the decisions and their reasoning are in
docs/model_design.md § Angler benefit, and the values no source gives are in data/processed/parameters.csv.
1. [DONE 2026-09-27; p153 skipped by decision]
   Extend scripts/00_extract_angler_survey.py with these survey tables (PDF pages): near-home
   importance (95), catching-trout importance (140), overall satisfaction (153), more stocking on
   high-use waters (175), moving stocking off wild trout waters (178; asked of all trout anglers). Use the
   same format and validation.
2. [DONE 2026-09-28: scripts/06_county_anglers.py]
   County anglers: parse PFBC's 2024 license sales by agent county
   (data/raw/pfbc_docs/2026-09-27/fishinglicensesalesbycounty2024.pdf, pages 1-4). Numbers are
   right-aligned with blank cells, so assign columns by x position and check every row against the PDF's
   own totals. anglers = trout + combo permits (annual + multi-year sold in 2024) - non-resident and tourist
   licenses + online resident permits split by county population (Census 2020 block groups summed).
   Write data/processed/county_anglers.csv with every input as a column, so a PFBC table of permit
   holders by home county could replace it later.
3. [DONE 2026-09-28: scripts/07_survey_crosswalk.py; 22 rows await review]
   Survey water crosswalk: match each named water (p76-77) to a 2026-stocked river_id (or lake) by name
   and county qualifier. Resolve ambiguous names with the by-home-region table (p78-83), e.g. Elk Creek
   -> Erie's. Anything still ambiguous goes to logs/07_survey_crosswalk_review.csv for me; don't guess.
   Write data/processed/survey_water_crosswalk.csv with match_method and confidence.
4. [DONE 2026-09-28: scripts/08_demand.py, also steps 5-6]
   Proximity demand (band version), per 2026-stocked section:
   - angler-days per Census block group = population x county angler rate x mean days fished in its home
     region (p115, with "over 50 days" from parameters.csv)
   - distance = straight-line miles from the block group's center of population to the section midpoint
     x circuity (parameters.csv)
   - each block group sends its angler-days out by its home region's p93 bands ("Don't know" dropped; the
     last band runs to the farthest pair in PA). Within a band, split among its sections by length_mi; a
     band with no section passes its share to the other bands in proportion. Assert the sections sum to
     the statewide total.
   - columns: prox_days (regional curves), prox_days_pooled (one in-state curve), prox_days_pop (every
     county at the state angler rate). Document the method in data_methods.md.
5. [DONE 2026-09-28] Preference demand: a water's share = its % / all mentions (incl. Other and Don't know; "<0.5%" from
   parameters.csv) x statewide angler-days, split over its stocked sections by length. Spread the unplaced
   share (Other, Don't know, lakes, unmatched) like prox_days. Flag, don't cap, waters whose preference per
   stocked mile exceeds the state's highest prox_days per mile (the Youghiogheny keeps its full share).
   Add destination_index = preference / proximity for each matched water.
6. [DONE 2026-09-28] Regulation flags: DHALO, catch-and-release (5 spellings in reg_name), Keystone Select (program_name
   KSSTW) and open year-round, from the existing regulation columns. Access is not a demand input: PFBC's
   access rating (use_potential) already sets the density cap (Prompt 4), and no access-point layer is used
   (decision 2026-09-27, docs/model_design.md § Angler benefit).
Report: the share of 2026 fish on survey-named waters, survey waters with no stocked section, the flagged
waters, each home region's share of angler-days landing in its own region vs p85, and rank correlations of
prox_days with 2026 fish, fish per acre and prox_days_pop.
```

## Prompt 7: Transport cost (distances come from Gavin)

Road distances from each hatchery to each section are built by Gavin in
`notebooks/travel_arcs.ipynb`. Don't rebuild them. Run this once his distance table is keyed on `section_id`.

```
1. Supply: merge Gavin's cleaned hatchery layer into data/processed/hatcheries.parquet. Hatchery supply =
   stream_fish_2026 from data/processed/hatchery_schedule_supply.csv (decision 2026-09-28: the 9 hatcheries
   on the 2026 schedule, Tionesta included); the lbs split (baseline stream total x share of production
   pounds, Pleasant Mount excluded) is the sensitivity. Co-ops are fixed background, not supply nodes (see
   CLAUDE.md).
2. Add the transport parameters from docs/transport_research.md to data/processed/parameters.csv:
   cost_per_truck_mile, fish_per_load, transport_mortality_pct and the others, each with a low/high range
   and a source.
3. data/processed/cost_matrix.parquet (long): node_id, section_id, road_mi (from Gavin), and
   cost_per_fish = 2 x road_mi x cost_per_truck_mile / fish_per_load.
4. baseline_node = each section's scheduled hatchery (section_schedule; split by event share for the 49
   multi-hatchery sections), if the team confirms (docs/model_design.md § Transport cost); the nearest
   hatchery is the sensitivity. Report the implied baseline cost under both and each node's load vs supply. Calibration check: the implied fleet miles vs the ~300,000 mi/yr reported
   (docs/transport_research.md).
```

### Prompt 7 upgrade: stocking-schedule clusters (added 2026-09-28) [DONE 2026-09-28: scripts/09_stocking_schedule.py, scripts/10_runs_clusters.py]

Built with explicit runs (date + hatchery + meeting place + time) in place of step 6's same-date + 30 mi rule,
since the schedule names the hatchery and meeting for every event, and a link rule of share ≥ 0.5 (strict
majority as the sensitivity). It also gives each hatchery's 2026 stream fish (hatchery_schedule_supply.csv),
now the hatchery supply. Which detour version enters the model is still open (docs/model_design.md § Open
questions).

Group 2026-stocked sections into the runs PFBC actually makes, so the transport cost can charge per run
(cluster) instead of per section. Background: `docs/model_design.md` § Open questions (detour charge).
Clusters are a logistics proxy: sections PFBC stocks on the same day and close together are likely on the
same truck route. The past bias is acceptable because run structure mostly reflects roads, hatcheries and
crews, and the model still chooses fish counts and which hatchery serves each section. Label this as an
assumption. The same download serves the "Stocking schedule and seasons" upgrade below.

```
Phase 1: inspect only, then stop and report to me.
1. Look at fbweb.pa.gov/TroutStocking (and any ArcGIS or JSON endpoint behind it). Check robots.txt first.
   Verify each endpoint (?f=pjson or HEAD) before building on it (rule 5).
2. Report: what each record holds (date, meeting time/place, water name, section number or GIS key, county,
   species, counts?); how records key to section_id; which years are available (2026 only, or also
   2024-25?); how many requests a full pull needs; whether pre-season shows many trucks on the same day.
3. Don't bulk-download until I OK the plan.

Phase 2: after my OK.
4. Download the 2026 schedule (plus earlier years if they're available cheaply). Max 1 request/second,
   exponential backoff, cached, and STOP if the server refuses. Save raw responses untouched under
   data/raw/pfbc_schedule/<date>/ and log them in manifest.csv. Add the source to docs/source_inventory.md.
5. data/processed/stocking_events.{parquet,csv}: one row per section x date (plus time/meeting point if
   given). Log unmatched schedule rows to logs/ for review. Don't guess matches.
6. Clusters: link two sections if, on the dates both are stocked, they share a date a majority of the time
   AND are within a road-distance threshold (straight-line midpoint distance x 1.3 circuity; 30 mi
   default, 20/45 as a sensitivity). Clusters = connected components.
   - Put the threshold and majority rule in parameters.csv.
   - Log cluster sizes, singletons, and any cluster wider than ~60 mi (likely two trucks merged).
   - Hand-check a few, e.g. Bear Creek 3197_2/3197_3's neighbours.
   - Sections with no schedule record get their own singleton cluster, flagged.
7. Write cluster_id (and cluster_source) onto sections (or its own table keyed on section_id). Compute
   detour_s as the distance to the nearest same-cluster neighbour. Also compute a cluster-level trip
   charge input (cluster centroid, total cluster miles) for the richer version: binary y_c per cluster
   with x_s <= cap_s * y_c. Hatchery -> section road distances stay Gavin's (travel_arcs): don't rebuild
   them.
Checkpoints: data_methods.md (method and the "same day ~ same run" assumption), data_dictionary.md,
known_gaps.md (whatever the schedule lacks), model_design.md (update the detour open question: cluster
version proposed, still undecided), scenarios_and_extensions.md (geographic-only clusters as the fallback
and a comparison), parameters.csv, tests for documented counts. Show sample rows and cluster stats, then
stop for review before committing.
```

## Prompt 8: Assemble model inputs

```
Build data/processed/model_input.parquet, one row per destination: baseline fish by species, species mix,
cap_fish (+ cap_fish_mid, max_trout_per_acre for scenarios), exclusion flags, penalty inputs, demand
inputs, and a completeness flag per component. Report how many destinations are fully usable and what
blocks the rest. Check that docs/data_dictionary.md covers every column (meaning, units, source,
transformation) and docs/data_methods.md every change to PFBC data; both are updated at each phase
checkpoint, so fill gaps only. Then add a short EDA section to notebooks/01_data_prep.ipynb: baseline density vs demand, vs
hatchery distance, and vs wild-trout flags.
```

## Prompt 9: Validate and QA

```
Parse data/references/*.html (local files only) and compare named-water counts, stocking records, counties,
and the full Bear Creek record with our tables; explain differences. QA checks: negative counts, stocked
sections with zero length or area, density outliers (> 3 SD), year-over-year swings > 50%, and destinations
missing a cost_matrix row. Write logs/final_qa.md.
```

---

## Upgrades (if time allows)

- **Thermal flag:** EcoSHEDS temperature model (see docs/env_research.md). Spatially join its catchments to
  sections, compute max 30-day mean temperature, and set thermal_marginal = ≥ 21 °C. Large rivers will be NA;
  record why in temp_missing_reason.
- **Full PFBC rate table:** done. Exact Table 18 lookup on AllocationCode (`max_trout_per_acre`,
  `data/processed/pfbc_stocking_rates.csv`).
- **Distance-decay calibration:** replaced 2026-09-27. Proximity demand now uses each home region's p93
  bands directly (Prompt 6 step 4), and p85 is a check on it.
- **Stocking schedule and seasons:** scrape event dates from fbweb.pa.gov/TroutStocking to split decisions by
  pre-season, in-season, and fall/winter. The schedule download is shared with the stocking-schedule clusters
  (Prompt 7 upgrade).
- **History:** the 2024–26 layers don't reach 2022. Check for a 2023 layer, then Wayback Machine captures of
  past schedules.
- **PFBC records request:** hatchery assignments, truck costs, and production by species, to replace our
  assumptions.
