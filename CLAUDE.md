# PA Trout Stocking Optimization

School project (From Data to Action), two-person repo. `git pull` before starting; commit small.
**Division of work:** Gavin (LoydGC) owns hatchery and co-op data and hatchery -> section road distances
(`notebooks/travel_arcs.ipynb`; co-op distances are for maps/context only). This pipeline owns sections, the stocking baseline, environment and demand.
Join his outputs on `section_id`, don't rebuild them. Hatchery data and branches get merged/synced later.
**Practical over perfect:** take the simplest defensible approach, label assumptions, and treat
thorough versions as optional upgrades.

## What the data is for
Everything here feeds a multi-objective stocking model (Gurobi, `notebooks/02_optimization.ipynb`):

```
x[h, s] = adult trout per year trucked from PFBC hatchery h to destination s
          (species handled at the destination: keep each section's historical species mix)

objectives, kept separate (never pre-weighted in the data):
  max  angler benefit        min  transport cost        min  wild-trout impact
solve: ε-constraint sweeps (max benefit s.t. cost ≤ C, impact ≤ E) to trace trade-off curves

constraints: hatchery supply, per-section density bound, environmental exclusions,
             optional stability vs. baseline (x ≥ (1-δ)·historical)
```

| Component | Needs | Output table(s) |
|---|---|---|
| Base (all components join to it on `section_id`) | Stocked sections 2024–26: ids, location, allocation category, counts, wild-trout overlap; geometry | `sections`, `pa_trout.gpkg` |
| Baseline | What PFBC actually stocked: section x species x year | `stocking_section_year` |
| Angler benefit | Survey preference for named waters; population-by-distance for the rest; access | `demand` |
| Transport cost | Hatchery supply, road distance (Gavin, travel_arcs), cost parameters | `hatcheries`, `cost_matrix`, `parameters` |
| Environment | Exclusions, wild brook trout, natural reproduction, area for density bound, (temperature) | `environment` |

The historical allocation is the **baseline** the optimized plan is compared against. Keep it as observed:
don't smooth, impute, or "fix" it.

## Agreed simplifications
- **Hatchery -> section assignment isn't published.** The model chooses it; the baseline's cost assumes each
  section is served by its nearest hatchery.
- **Hatchery supply** = baseline statewide total, split across the 10 trout hatcheries by their share of trout
  production (lbs, `data/raw/pa_hatchery_production.csv`). Pleasant Mount's figure is a fish count
  that likely includes warmwater species: exclude it unless a trout-only number turns up.
- **Co-op nurseries are fixed background, not decisions** (team decision 2026-09-27). The clubs choose their
  waters and PFBC leaves co-op fish out of its allocation (co-op policy §III.12, §IV.10), so the base model
  optimizes PFBC hatchery fish only. Co-op waters are a flag on sections (`coop_stocked`, 292 sections, from
  `scripts/03_coop_stockings.py`). **Extension "what if the state coordinated more?"**: add a fixed co-op
  fish count per section to the angler-benefit score (needs counts; see `docs/model_design.md`).
- **Distance** = road distance from each supply node to each section, built by Gavin in
  `notebooks/travel_arcs.ipynb`. Not on our slate: join it on `section_id`. No Google Maps API (cost;
  terms bar storing results).
- **Angler demand** (decision 2026-09-27; reasoning in `docs/model_design.md` § Angler benefit): angler-days
  per section from two signals, kept as separate columns and blended in the model with weight `w` (0.5,
  swept 0 / 0.5 / 1). PA residents only.
  - **Proximity ("band version"):** each Census block group's angler-days (population × county trout-permit
    rate from PFBC's 2024 sales by store county × home region's mean days fished, p115) go out by its home
    region's trip-distance bands (p93; straight-line miles × 1.3), split within each band by section length.
    Every angler-day is placed once.
  - **Preference:** each named water's share of survey mentions (p76-77) × statewide angler-days, split over
    its stocked sections by length; the unplaced share is spread like proximity.
  - **Benefit** = `D_s × (1 − e^(−r/k))`, r = fish per angler-day, k = 1 (PFBC's "one angler trip per trout").
- **Density bound** (`cap_fish`; decision 2026-09-27, replacing the "river cap"; details in
  `docs/model_design.md`): `cap_rate` x `length_mi` x top of the PFBC width class, and at least 300 fish.
  The rate depends on biomass, width and access, never population. `cap_rate` is the higher of `access_rate`
  and `program_rate` (below).
  - `access_rate` = the highest Table 18 rate for the section's biomass + width at its own recreational use
    potential (access: road frontage, parking, ownership) or any worse one, over all population classes.
    Population is PFBC's demand proxy, which our benefit objective replaces. Access limits how many anglers a
    section holds and ties to landowner posting, which nothing else in the model sees.
  - "Or any worse one": Table 18 gives biomass B + High access at widths 2–3 a flat 147/acre but B + Good up
    to 323, so taken literally 17 sections would get a lower cap for better access. Better access never
    lowers the cap: they get 323.
  - Rates at widths 2–3: C–E High 361, everything else High or Good 323, Low 57. Widths 4/1S/1L: 57 for
    all; 137/91 High, 84/53 Good, 34/30 Low.
  - Special programs use their own Guidelines rate where it's higher (`program`, `program_rate`): Delayed
    Harvest Artificial Lures Only (Table 46: 190/acre at widths 2–3, 133 at 1S/1L; 56 sections by `reg_name`)
    and tailwaters (Table 45: 266 High, 247 Good; ≤ 2 mi below a cold-water dam release. No layer flags them:
    Youghiogheny 1327_1 and Conneauttee 2649_1 by hand, other dam sections checked in `docs/known_gaps.md`).
  - Sensitivity: the "river cap" (`cap_fish_river`, rate `cap_rate_river`), the highest rate over access too (C–E
    361 at widths 2–3).
  - Width tops: 4, 10, 20, 30 m, plus 60 m for open-ended 1L (assumption). Midpoints are the tighter
    sensitivity. No NHDPlus.
  - Table 18 itself (`max_trout_per_acre`, exact lookup on AllocationCode) is PFBC's allocation formula:
    sections are stocked at about rate x acres. It's kept for the baseline and a "PFBC formula as cap"
    scenario.
  - "Today's stocking" = the 2026 count (`total_2026`, decision 2026-09-27). Built in `scripts/04_river_cap.py`
    (`access_rate`, `cap_fish`, `cap_source`).
  - Class A (decision 2026-09-27): the 17 Class A-overlap sections PFBC stocks in 2026 are capped at today's
    stocking (keep or cut, never add). Scenario: the normal cap instead (`cap_fish_class_a_grow`; biomass A at
    widths 2–3 uses B's 323).
  - The 7 sections PFBC stocks above the cap in 2026 are capped at today's stocking: Conneauttee 2649_1 (tailwater),
    Roaring Brook 1767_5, Youghiogheny 1327_1 (tailwater, 1.1× at our 60 m width), Black Moshannon 2254_2,
    Fishing Creek 183_9, West Branch Susquehanna 4029_7 and Wiconisco 2892_3 (1 fish over).
  - Call it a policy/crowding bound, not carrying capacity.
- **Candidate sections:** only the 1,022 sections PFBC stocks in 2026. The 23 it dropped (18 are natural
  reproduction waters, including Buffalo Creek 3190_2, now Class A, and Blue Hole Creek 3656_2, removed for
  cadmium/lead) get no fish; a scenario lets them back.
- **Environment** follows `docs/env_research.md`: exclude Wilderness and Buffalo Creek 3190_2 (Class A since
  Jan 2026, not stocked in 2026), cap the other Class A overlaps at today's stocking, no stocked
  brook trout over wild brook trout. Everything else is the **wild-trout impact objective** (its own goal, not
  a penalty on benefit): a per-fish weight from biomass class, natural reproduction, wild brook trout, and
  (if time) thermal marginality. Versions are in `docs/model_design.md`.

## Units of analysis
- **Section** = PFBC stream section, key `section_id = f"{RFP_WaterID}_{SecNum}"`. Base unit for all joins.
  The 2026 stocked-sections layer has ~1,031 features. trout.app's "3,520 reaches" includes non-stocked reaches.
- **River** = a named water, key `river_id` = PFBC `RFP_WaterID` (decision 2026-09-27). It is shared across a
  stream's sections and counties, and distinct for same-named streams. Never WtrName alone: names repeat
  across counties. Survey preferences are at this level and are apportioned to sections by length.
- **Lake** = its own destination with `water_type = "lake"` (~20% of stocked trout). Kept out of stream-only
  covariates; whether lakes are decision variables or fixed is an open question.
- **Supply node** = one of the 10 PFBC trout hatcheries. Co-op nurseries (~160) and fingerlings are fixed, not
  decisions. Gavin's cleaned layers (`trout_hatcheries.gpkg`, `data/raw/Coop_nurseries.geojson`) are the
  reference. The `hatcheries` layer in `pa_trout.gpkg` is a placeholder until we merge.

## Hard rules
1. Official/public sources only. **Never request anything from trout.app** (robots.txt disallows it).
   `data/references/*.html` are saved trout.app pages used ONLY to validate output. Keep them local (gitignored).
2. Save every raw response untouched to `data/raw/<source>/<YYYY-MM-DD>/` before transforming.
   Record URL, retrieval timestamp, and record count in `data/raw/manifest.csv`.
3. Be polite to servers: max 1 request/second to fbweb.pa.gov and pasda; exponential backoff on errors;
   cache so re-runs never re-fetch. If a server starts refusing, STOP and report.
   Never bulk-query public demo services (e.g. the OSRM demo server).
4. Never silently drop records. Every filter/dedupe/join step logs counts before/after to `logs/`.
5. Verify every endpoint (`?f=pjson` or HEAD) before building on it. Note moved/wrong URLs in
   `docs/source_inventory.md`.
6. Don't invent values. Missing = NA, with a `*_source` or `*_missing_reason` column where useful.
7. Parameters no source gives directly (cost per mile, fish per load, impact weights) live in
   `data/processed/parameters.csv` with value, units, low/high range, and `source` (citation, or `assumption`
   plus reasoning). Never hard-code them in notebooks.
8. Wild-trout overlap is measured as shared river-mile length (> 100 m) on the same RFP_WaterID, never a plain
   intersect: adjacent sections share endpoints. River miles only, for every layer (decision 2026-09-27);
   geometry is just a logged cross-check (it wrongly flags Bear Creek 3197_2 Class A). Some Natural
   Reproduction river miles are shorter than their own line, so 18 sections are missed (`docs/known_gaps.md`).

## Stack
Python 3.11+, venv. pandas, geopandas, shapely, pyproj, requests, requests-cache, beautifulsoup4, lxml, tqdm,
pyarrow, duckdb, pdfplumber, pynhd (optional NHDPlus upgrade). Solver: gurobipy (academic license). Tests: pytest.
Road routing lives in Gavin's notebook. CRS: EPSG:26918 for distances/lengths/areas; store in EPSG:4326.

## Layout
```
data/raw/<source>/<date>/  untouched downloads. GITIGNORED except manifest.csv, which is enough to re-fetch.
data/interim/              scratch parsed tables (gitignored, regenerable)
data/processed/            model-ready tables (parquet + csv), COMMITTED. Keep each file < 50 MB.
                           Exception: pa_trout.gpkg is GITIGNORED (16 MB; rebuilt by scripts 01-02).
                           angler_survey/: survey tables, csv only (script 00; column notes in its README).
data/references/           reference PDFs and trout.app snapshots. GITIGNORED (local only); where each came
                           from is in docs/source_inventory.md.
scripts/                   numbered pipeline scripts, each re-runnable end to end
tests/                     pytest tests for scripts/, and test_processed.py (facts data/processed must match)
notebooks/                 01_data_prep (EDA), 02_optimization, 03_sensitivities: read data/processed only
docs/                      source_inventory, data_dictionary, data_methods (data handling + assumptions),
                           model_design (model + assumptions + open questions), scenarios_and_extensions,
                           known_gaps, figure_ideas (figures to make for the report); env_research,
                           transport_research (research snapshots, not maintained)
logs/                      run logs and QA reports
outputs/                   figures and tables for the report
```

**File formats.** Tables are parquet plus a csv copy. Geometry lives only in `data/processed/pa_trout.gpkg`
(gitignored, rebuilt by scripts 01-02; EPSG:4326; layers sections, hatcheries, class_a, nat_repro,
wilderness). Join everything on `section_id`. GeoJSON is for ad-hoc export only (e.g. folium maps). The
gpkg's wild-trout context layers are simplified to 5 m; compute overlaps from the full-resolution raw data.

## Known facts
- Verified 2026-09-26. Stocking counts come from fbweb, not PASDA. PASDA's 2026 stocked layer (#26) has no counts.
  `https://fbweb.pa.gov/arcgis/rest/services/PFBC_Map_Services/`
  `TroutStockedSections_2026/MapServer/0` (1,031), `TroutStocked2025/MapServer/2` (1,044),
  `TroutStocked2024/MapServer/0` (1,036; maxRecordCount 1000, so page). Fields include Total{Brook,Brown,
  Rainbow,Golden,Brood}Stocked, AllocationCode, Description (category label only, e.g.
  "OPTIMUM YIELD 2 SUBURBAN"; the "2" is NOT width), SecUpperLi/SecLowerLi (river miles), Mid_Lat/Mid_Long,
  Reg_Name, SpecReg, GIS_Key (= "RFP_WaterID-SecNum").
  Wild-trout layers: PASDA PAFishBoat MapServer #9 Class A (1,361; has TroutBioma, Fishery, RFP_WaterI),
  #25 Natural Reproduction (6,224; has AnglerUse), #31 Wilderness. Lakes:
  `PFBC_Stocked_Trout_Waters/MapServer/5` (131 polygons, no counts).
- AllocationCode = the full Table 18 category: [biomass A–E][use H/G/L][population M/U/S/R][width 1S|1L|2|3|4]
  (all 1,045 sections match). Bear Creek DGS3 = D, Good, Suburban, width 3 (4–10 m) → 190 trout/acre/yr.
- Sections pull: 1,045 sections stocked 2024–26 (1,007 all three years). ~2.6M stream fish/yr. No layer
  reaches 2022. 5–9 sections/year appear as 2 rows (regulation piece or county), each with the FULL total:
  count once, keep the "Stocked Trout Water" row's limits/length/line (raw sums overcount ~0.7%). TotalAdultStocked_minusBrood = brook + brown +
  rainbow; golden and brood are extra. Null brook/brown = 0. Sherman Creek 3306_2 river-mile limits are
  reversed: flagged (`rm_limits_reversed`), not fixed.
- Class A: 18 sections overlap Class A by river mile (the 17 stocked in 2026 + Buffalo Creek 3190_2); none
  overlap Wilderness. 13 are coded biomass A and are Class A sections themselves (Class A key = own section
  id): very likely the Operational Guidelines' 13 continued-stocking sections (Appendix A). The other 4 have
  no documented basis. Evidence, and the separate Jan 2026 exemptions: `docs/known_gaps.md`.
- Stream layers ≈ 83% of PFBC's adult trout. The FY23–24 annual report has 3.14M adults + 1.56M fingerlings
  = 4.70M; our 2024 streams total 2.60M. The gap is most likely lakes, which have no counts in any GIS
  service. Scale hatchery supply to the stream total. Details: `docs/known_gaps.md`.
- Bear Creek (Schuylkill) is RFP_WaterID 3197 (sections 3197_2 and 3197_3), in the Southeast region.
- PFBC regions by county come from the 2026 Fishing Summary's regulated-waters lists (`county_region.csv`;
  all 67 counties, matches PFBC's region polygons). No stocked section spans two regions.
- 2023 angler survey (Responsive Management for PFBC) describes **2022** fishing. Regions are the six PFBC
  regions by angler **home** county, not where they fish. The named-water tables cover ~223 waters.
- Bear Creek (Schuylkill) test case: Class A (brook trout) is Section 01. The stocked sections 02-03 are
  downstream and only touch it, so they must NOT be flagged Class A. They do sit inside the Natural
  Reproduction reach, so they MUST be flagged for natural reproduction.
  2026 stocking: 150 brown + 1,750 rainbow (3197_2: 150 brown + 850 rainbow; 3197_3: 900 rainbow).

## Workflow expectations
- One phase (one PROMPTS.md prompt) at a time. At the end of each phase:
  1. Update the checkpoint files below that the phase touched.
  2. Run pytest. Show 5 sample rows per new table, row counts, and null rates for key columns.
  3. Commit with a descriptive message, then stop for review.

| Checkpoint file | Update when |
|---|---|
| `docs/data_dictionary.md` | Any column in `data/processed/` is added or changed |
| `docs/data_methods.md` | Source data is modified or a data-handling assumption is made (PFBC license: credit unaltered data, describe every change) |
| `docs/scenarios_and_extensions.md` | A new scenario, sensitivity or extension idea comes up (additional analysis only) |
| `docs/figure_ideas.md` | A figure or report-table idea comes up |
| `docs/known_gaps.md` | Missing data or a source problem is found |
| `docs/model_design.md` | The model formulation changes, an assumption is decided (flag it if no scenario tests it), or an open question comes up |
| `data/processed/parameters.csv` | A value no source gives directly is used (rule 7) |
| `docs/source_inventory.md` | A new endpoint is used, or a URL moved or was wrong (rule 5) |
| `PROMPTS.md` | The prompt is done (mark [DONE date] and update the Status line), or the plan changed |
| `CLAUDE.md` | A team decision is made (Agreed simplifications) or a fact is verified (Known facts) |
| `tests/test_processed.py` | A documented count changes on purpose (also fix the doc its failing assert names) |
