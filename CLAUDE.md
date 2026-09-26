# PA Trout Stocking Optimization

School project (From Data to Action), two-person repo. `git pull` before starting; commit small.
**Practical over perfect:** take the simplest defensible approach, label assumptions, and treat
thorough versions as optional upgrades.

## What the data is for
Everything here feeds a multi-objective stocking model (Gurobi, `notebooks/02_optimization.ipynb`):

```
x[h, s] = adult trout per year trucked from hatchery h to destination s
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
| Transport cost | Hatchery supply, hatchery -> section distance, cost parameters | `hatcheries`, `cost_matrix`, `parameters` |
| Environment | Exclusions, wild brook trout, natural reproduction, area for density bound, (temperature) | `environment` |

The historical allocation is the **baseline** the optimized plan is compared against. Keep it as observed:
don't smooth, impute, or "fix" it.

## Agreed simplifications
- **Hatchery -> section assignment isn't published.** The model chooses it; the baseline's cost assumes each
  section is served by its nearest hatchery.
- **Hatchery supply** = baseline statewide total, split across the 10 trout hatcheries by their share of trout
  production (lbs, `data/raw/pa_hatchery_production.csv`). Pleasant Mount's figure is a fish count
  that likely includes warmwater species: exclude it unless a trout-only number turns up.
- **Distance** = straight-line x circuity factor, with the factor checked against ~15 routes looked up by
  hand. A local OpenStreetMap road network is an optional upgrade. No Google Maps API (cost; terms bar
  storing results).
- **Demand for waters the survey doesn't name** = population weighted by the survey's own travel-distance
  distribution (p93): the share of anglers willing to travel at least that far. Calibrating against the
  county tables (p85) is optional.
- **Density bound** = PFBC's maximum stocking rate (trout/acre/yr, Operational Guidelines Table 18) x
  estimated area (length x width from drainage area). Call it a policy/crowding bound, not carrying capacity.
  The rate is an exact lookup on AllocationCode (`max_trout_per_acre` in sections, from
  `data/processed/pfbc_stocking_rates.csv`). 11 biomass-A sections (width 2–3) have no Table 18 rate: NA.
- **Environment** follows `docs/env_research.md`: exclude Wilderness and non-exempt Class A sections, no stocked
  brook trout over wild brook trout. Everything else is the **wild-trout impact objective** (its own goal, not
  a penalty on benefit): a per-fish weight from biomass class, natural reproduction, wild brook trout, and
  (if time) thermal marginality. Versions are in `docs/modeling_notes.md`.

## Units of analysis
- **Section** = PFBC stream section, key `section_id = f"{RFP_WaterID}_{SecNum}"`. Base unit for all joins.
  The 2026 stocked-sections layer has ~1,031 features. trout.app's "3,520 reaches" includes non-stocked reaches.
- **River** = a named water, key `river_id` (NHD GNIS_ID, else levelpath). Never WtrName alone: names repeat
  across counties. Survey preferences are at this level and are apportioned to sections by length.
- **Lake** = its own destination with `water_type = "lake"` (~20% of stocked trout). Kept out of stream-only
  covariates; whether lakes are decision variables or fixed is an open question.
- **Hatchery** = one of the 10 PFBC trout hatcheries. Co-op nurseries and fingerlings are fixed, not decisions.

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
7. Parameters no source gives directly (circuity factor, cost per mile, fish per load, impact weights) live in
   `data/processed/parameters.csv` with value, units, low/high range, and `source` (citation, or `assumption`
   plus reasoning). Never hard-code them in notebooks.
8. Wild-trout overlap is measured as shared river-mile length on the same RFP_WaterID (or > 100 m of overlap in
   EPSG:26918), never a plain intersect: adjacent sections share endpoints. Exception: some Natural
   Reproduction river miles understate the line, so `nat_repro_flag` also counts same-RFP geometric overlap
   ≥ 0.5 mi. Class A and Wilderness stay river-miles only (geometry wrongly flags Bear Creek 3197_2 Class A).

## Stack
Python 3.11+, venv. pandas, geopandas, shapely, pyproj, requests, requests-cache, beautifulsoup4, lxml, tqdm,
pyarrow, duckdb, pdfplumber, pynhd (HyRiver). Solver: gurobipy (academic license). Tests: pytest.
Optional: pyrosm + networkx (OSM routing). CRS: EPSG:26918 for distances/lengths/areas; store in EPSG:4326.

## Layout
```
data/raw/<source>/<date>/  untouched downloads. GITIGNORED except manifest.csv, which is enough to re-fetch.
data/interim/              scratch parsed tables (gitignored, regenerable)
data/processed/            model-ready tables (parquet + csv), COMMITTED. Keep each file < 50 MB.
data/references/           trout.app snapshots (local only, validation only)
scripts/                   numbered pipeline scripts, each re-runnable end to end
tests/                     pytest tests for scripts/
notebooks/                 01_data_prep (EDA), 02_optimization, 03_sensitivities: read data/processed only
docs/                      source_inventory, data_dictionary, methods, known_gaps, env_research
logs/                      run logs and QA reports
outputs/                   figures and tables for the report
```

**File formats.** Tables are parquet plus a csv copy. Geometry lives only in `data/processed/pa_trout.gpkg`
(EPSG:4326; layers sections, hatcheries, class_a, nat_repro, wilderness). Join everything on `section_id`.
GeoJSON is for ad-hoc export only (e.g. folium maps). The gpkg's wild-trout context layers are simplified to
5 m; compute overlaps from the full-resolution raw data.

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
  count once, union geometry (raw sums overcount ~0.7%). TotalAdultStocked_minusBrood = brook + brown +
  rainbow; golden and brood are extra. Null brook/brown = 0. Sherman Creek 3306_2 river-mile limits are
  reversed: flagged (`rm_limits_reversed`), not fixed.
- Class A: the 13 biomass-A sections (all wild brown, none brook) are the proxy for PFBC's ~13 exempt
  sections; verify if the official list turns up. 18 sections overlap Class A by river mile (the 13 + 5).
  None overlap Wilderness.
- Stream layers ≈ 83% of PFBC's adult trout. The FY23–24 annual report has 3.14M adults + 1.56M fingerlings
  = 4.70M; our 2024 streams total 2.60M. The gap is most likely lakes, which have no counts in any GIS
  service. Scale hatchery supply to the stream total. Details: `docs/known_gaps.md`.
- Bear Creek (Schuylkill) is RFP_WaterID 3197 (sections 3197_2 and 3197_3).
- 2023 angler survey (Responsive Management for PFBC) describes **2022** fishing. Regions are the six PFBC
  regions by angler **home** county, not where they fish. The named-water tables cover ~223 waters.
- Bear Creek (Schuylkill) test case: Class A (brook trout) is Section 01. The stocked sections 02-03 are
  downstream and only touch it, so they must NOT be flagged Class A. They do sit inside the Natural
  Reproduction reach, so they MUST be flagged for natural reproduction.
  2026 stocking: 150 brown + 1,750 rainbow (3197_2: 150 brown + 850 rainbow; 3197_3: 900 rainbow).

## Workflow expectations
- One phase at a time. At the end of each phase: 5 sample rows per new table, row counts, and null rates for
  key columns, then stop for review.
- Commit after each phase with a descriptive message.
- Keep `docs/data_dictionary.md` updated for every column in `data/processed/`.
- Credit PFBC per their license: data used unaltered is credited; all modifications are described in
  `docs/methods.md`.
