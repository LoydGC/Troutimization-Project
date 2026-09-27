# Claude Code prompts: PA trout stocking optimization data

Paste these one at a time and review each phase before sending the next. `CLAUDE.md` holds the model framing,
the agreed simplifications, and the rules, so the prompts don't repeat them.

Order: 0 → 1 → 2 → 3 gets the baseline. 4–7 each build one model component (4 first, since 5 and 6 use its
area and river_id). 8–9 assemble and check. Upgrades are at the end, for when time allows.

**Status (2026-09-26):** the "sections pull" (`scripts/01_download_pfbc_layers.py`,
`scripts/02_build_sections.py`) is BUILT, the Bear Creek checks pass, and it is committed on branch
`sections-pull` (not yet pushed or merged). It covers part of Prompt 0 (venv, common.py + tests, .gitignore), Prompt 2 for the stocked-section
and wild-trout layers, Prompt 3, and Prompt 5's overlap flags and Table 18 rate (`max_trout_per_acre`). Skip
those parts when sending the prompts. `scripts/03_coop_stockings.py` (committed 2026-09-27) adds the co-op
stocking list and the `coop_stocked` flag on sections.

**Next (2026-09-27):** Prompts 4 + 5 as one phase, using the simplified Prompt 4 below. Then Prompt 6 (needs
Prompt 0's angler-survey leftovers). Prompt 7 waits on Gavin's distances.

---

## Prompt 0: Housekeeping

```
Read CLAUDE.md. Tidy the repo to match its Layout section.
1. Git: gitignore data/raw/** except manifest.csv and .gitkeep files; stop ignoring data/processed/
   (keep a rule that blocks files over 50 MB). Also ignore data/references/*.html and the requests-cache
   database. The new rules only affect new raw files. Add each already-committed raw file to
   data/raw/manifest.csv with its source URL so it can be re-downloaded. ON HOLD: untracking them with
   `git rm --cached` waits for the partner's OK (LoydGC committed some on purpose).
2. Angler survey: the PDF is an official PFBC source. Move data/references/troutanglersurveyreport-2023.pdf
   to data/raw/pfbc_angler_survey_2023/ and add its PFBC URL to the manifest. Move
   data/references/angler_survey/extract_angler_survey_2023.py to scripts/00_extract_angler_survey.py,
   point it at the new paths, and have it write to data/processed/angler_survey/. Re-run it and confirm
   the CSVs match the current ones exactly, then delete the old copies and files.zip (check the zip
   holds nothing extra first).
3. requirements.txt: add everything in CLAUDE.md's Stack (01_data_prep already uses geopandas). Create a
   venv and install.
4. scripts/common.py with:
   - a cached, rate-limited HTTP session (requests-cache, 1 req/sec per host, retries with backoff)
   - save_raw(source, name, content, url): writes to data/raw/<source>/<date>/ and appends to manifest.csv
   - fetch_layer(layer_url): ArcGIS REST pager. Read ?f=pjson, get the count with returnCountOnly=true,
     page with resultOffset/resultRecordCount, outFields=*, outSR=4326, f=geojson (f=json for tables).
     Save raw pages; assert downloaded count == server count.
   Add pytest tests for the pager with mocked responses.
5. data/README.md: point to data/raw/manifest.csv and docs/source_inventory.md instead of keeping its own list.
Stop when tests pass and show the resulting tree and `git status`.
```

## Prompt 1: Source inventory (no bulk downloading)

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
   data/raw/pfbc_docs/), the 2020–24 and 2025–29 trout plans, and the current Class A stocking exemption list.
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

Decision 2026-09-27: use PFBC's own water id and width classes. No NHDPlus (that's an upgrade).

```
data/processed/sections.parquet already exists (flat; length_mi, width_class from AllocationCode). ADD
columns on section_id:
1. river_id = rfp_water_id. Check it: log any river_id with more than one water_name, and any water_name +
   county with more than one river_id.
2. PFBC region (from county).
3. width_m = PFBC width-class midpoint: 4 (<4 m), 3 (4-10), 2 (10-20), 1S (20-30), 1L (>30, open-ended).
   Put the midpoints and low/high (the class bounds) in data/processed/parameters.csv with source =
   Operational Guidelines width classes, midpoint = assumption. area_acres = length_mi x width_m, plus
   area_acres_low / area_acres_high.
4. Redo the "stocked vs PFBC cap" check (max_trout_per_acre x area_acres) with these areas.
Lakes are added later as rows with water_type = "lake".
Validate: Bear Creek (Schuylkill) sections share river_id 3197.
Upgrade: NHDPlus COMID + Chaplin 2005 width from drainage area.
```

## Prompt 5: Environment

```
Build data/processed/environment.parquet, one row per section. Follow docs/env_research.md.
The overlap columns (class_a_overlap_mi, Class A species/Fishery, TroutBioma, nat_repro_overlap_mi,
wilderness_overlap_mi) already exist in sections from 02_build_sections (rule 8). Build on them; don't
re-measure.
1. Exclusions: Wilderness and Class A overlap from those columns; class_a_exempt = biomass_class == "A"
   (13 sections, all wild brown; check against the official exemption list if found); exclude = Wilderness
   OR (Class A AND not exempt).
2. wild_brook_present: from the Class A species/Fishery text (log how the text was parsed).
3. Natural reproduction: use nat_repro_flag as built (river miles OR same-RFP geometry, rule 8).
4. Density bound: max_trout = max_trout_per_acre (already in sections) x area_acres (from Prompt 4).
   The 11 sections with no Table 18 rate stay NA with a reason.
5. historical density (trout/acre) and the ratio to max_trout. Flag sections already stocked above it.
Validate Bear Creek: stocked sections are NOT Class A overlap but ARE natural reproduction.
Report: excluded sections that were stocked in the baseline, and wild-brook sections stocked with brook trout.
```

## Prompt 6: Angler benefit

```
Build data/processed/demand.parquet.
1. Extend scripts/00_extract_angler_survey.py with these stocked-angler tables (PDF pages): near-home
   importance (95), catching-trout importance (140), overall satisfaction (153), more stocking on
   high-use waters (175), moving stocking off wild trout waters (178). Use the same format and validation.
2. Survey water crosswalk: match each named survey water to river_id (or lake) using name, county
   qualifier, and whether it's stocked. Write data/processed/survey_water_crosswalk.csv with
   match_method and confidence. Put ambiguous names (e.g. several Elk Creeks) in
   logs/survey_crosswalk_review.csv for me; don't guess. Apportion each water's preference % to its
   stocked sections by length.
3. Proximity demand per section: sum block-group population x P(angler travels ≥ d), where d is
   straight-line miles and P comes from the p93 statewide travel-distance distribution. Use band
   midpoints and document the curve in methods.md.
4. Access: count of PFBC access points within 1 km, plus special-regulation flags (DHALO, Keystone Select).
Report: the share of baseline fish on survey-named waters, survey waters with no stocked section, and the
correlation between proximity demand and baseline stocking.
```

## Prompt 7: Transport cost (distances come from Gavin)

Road distances from each hatchery to each section are built by Gavin in
`notebooks/travel_arcs.ipynb`. Don't rebuild them. Run this once his distance table is keyed on `section_id`.

```
1. Supply: merge Gavin's cleaned hatchery layer into data/processed/hatcheries.parquet. Hatchery supply =
   baseline stream total x share of trout production (exclude Pleasant Mount unless a trout-only figure is
   found). Co-ops are fixed background, not supply nodes (see CLAUDE.md).
2. Add the transport parameters from docs/transport_research.md to data/processed/parameters.csv:
   cost_per_truck_mile, fish_per_load, transport_mortality_pct and the others, each with a low/high range
   and a source.
3. data/processed/cost_matrix.parquet (long): node_id, section_id, road_mi (from Gavin), and
   cost_per_fish = 2 x road_mi x cost_per_truck_mile / fish_per_load.
4. baseline_node = the nearest hatchery for each section. Report the implied baseline cost and each node's
   load vs supply. Calibration check: the implied fleet miles vs the ~300,000 mi/yr reported
   (docs/transport_research.md).
```

## Prompt 8: Assemble model inputs

```
Build data/processed/model_input.parquet, one row per destination: baseline fish by species, species mix,
max_trout, exclusion flags, penalty inputs, demand inputs, and a completeness flag per component. Report
how many destinations are fully usable and what blocks the rest. Write docs/data_dictionary.md (every
column: meaning, units, source, transformation) and docs/methods.md (every change to PFBC data and every
assumption). Then add a short EDA section to notebooks/01_data_prep.ipynb: baseline density vs demand, vs
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
- **Distance-decay calibration:** fit the proximity curve so predicted county choices by home region match
  the survey's p85 table.
- **Stocking schedule and seasons:** scrape event dates from fbweb.pa.gov/TroutStocking to split decisions by
  pre-season, in-season, and fall/winter.
- **History:** the 2024–26 layers don't reach 2022. Check for a 2023 layer, then Wayback Machine captures of
  past schedules.
- **PFBC records request:** hatchery assignments, truck costs, and production by species, to replace our
  assumptions.
