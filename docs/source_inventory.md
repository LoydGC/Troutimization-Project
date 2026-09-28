# Source inventory

Every source the pipeline and docs use: where it is, what it holds and how it joins to `section_id`. Each
download is also logged in `data/raw/manifest.csv` (URL, retrieval time, record count). Started 2026-09-27
with the sources already in use; Prompt 1 adds the rest (the full GIS crawl, Census population).

## GIS layers (base, baseline, environment)
Verified with `?f=pjson` and a count query, then paged by object id (`scripts/01_download_pfbc_layers.py`,
2026-09-26). Downloaded counts matched the server counts.

Base URLs: fbweb = `https://fbweb.pa.gov/arcgis/rest/services/PFBC_Map_Services/`,
PASDA = `https://mapservices.pasda.psu.edu/server/rest/services/pasda/PAFishBoat/MapServer/`.

| Layer | Path | Records | Key fields | Join to section_id | Used in |
|---|---|---|---|---|---|
| Stocked sections 2026 | fbweb `TroutStockedSections_2026/MapServer/0` | 1,031 | Total{Brook,Brown,Rainbow,Golden,Brood}Stocked, AllocationCode, SecUpperLi/SecLowerLi, Length_MI_, GIS_Key | `RFP_WaterID` + `SecNum` | sections, stocking_section_year |
| Stocked sections 2025 | fbweb `TroutStocked2025/MapServer/2` | 1,044 | same | same | same |
| Stocked sections 2024 | fbweb `TroutStocked2024/MapServer/0` | 1,036 | same | same | same |
| Class A | PASDA `9` | 1,361 | RFP_WaterI, TroutBioma, Fishery | river-mile overlap on the same RFP_WaterID (rule 8) | Class A overlap columns |
| Natural Reproduction | PASDA `25` | 6,224 | AnglerUse (no species) | river miles, plus ≥ 0.5 mi same-water geometry (rule 8) | nat_repro_flag |
| Wilderness Trout Streams | PASDA `31` | 134 | | river-mile overlap | wilderness overlap (none) |
| Stocked lakes | fbweb `PFBC_Stocked_Trout_Waters/MapServer/5` | 131 polygons | no stocking counts | not used yet | checked 2026-09-26, `known_gaps.md` |

URL notes (rule 5):
- The 2025 service's section layer is `/2`, not `/0`.
- The 2024 layer's maxRecordCount is 1000, so it is paged.
- PASDA's 2026 stocked layer (PAFishBoat #26) has no counts: stocking counts come from fbweb only.
- No stocked-section layer reaches 2022, the survey year.

## PFBC files and documents
| Source | URL | Retrieved | Local copy | Used for |
|---|---|---|---|---|
| Cooperative nursery stocking list (xlsx, 786 rows) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/fishing/stocking/coop-nurseries/cnu-stockings-website.xlsx | 2026-09-27 | `data/raw/pfbc_coop/` | coop_stockings, `coop_stocked` (script 03) |
| Operational Guidelines for the Management of Trout Fisheries, 5th ed. | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/operationguidelinestroutmgt.pdf | 2026-09-26 | `data/raw/pfbc_docs/` | Table 14 widths, Table 18 rates (`pfbc_stocking_rates.csv`), Appendix A (Class A) |
| 2020–24 Trout Management Plan | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/reports/troutplan2020.pdf | not downloaded | | `env_research.md` |
| 2025–29 Trout Management Plan | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/troutplan2025.pdf | not downloaded | | `env_research.md`, report hook (Obj. 9.1) |
| Summary of the 165th Commission meeting (Jan 2026) | https://www.pa.gov/agencies/fishandboat/newsroom/summary-165th-meeting-pfbc-jan2026 | web page, not saved | | Class A exemptions (`env_research.md` § 3) |

## Local reference copies (`data/references/`, gitignored)
Saved by hand, not by a script, so they aren't in the manifest. This table is the record of where each came
from.

| File | Source | Used for |
|---|---|---|
| `troutanglersurveyreport-2023.pdf` | Responsive Management for PFBC, *Trout Fishing in Pennsylvania* (2023 trout angler survey). URL from web research, not re-verified: https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/troutanglersurveyreport-2023.pdf. Prompt 0 moves it to `data/raw/`. | `angler_survey/` extracts; demand (Prompt 6) |
| `angler_survey/` (tracked in git) | Tables extracted from the survey PDF by `extract_angler_survey_2023.py` | demand (Prompt 6) |
| `2024annualreport.pdf` | PFBC 2024 Annual Report (fiscal year Jul 2023–Jun 2024). URL not recorded. | stream vs statewide totals (`known_gaps.md`) |
| `statement_policy.pdf` | PFBC Cooperative Nursery Statement of Policy (Jan 2017). URL not recorded. | co-op rules (`known_gaps.md`, `model_design.md`) |
| `Stocking exemptions, fishing regulations changes made on Pa waters.pdf` | GoErie, 2026-01-31, reporting the Jan 30 Commission meeting | Class A exemptions, co-op total, Blue Hole Creek |
| `Day in the life - 'Always work to do' - Corry hatchery manager ….pdf` | Erie Times-News (PA), 2026-03-29, p. A1 | hatchery background; not cited yet |
| `*.html` (2 files) | trout.app pages, saved by hand. Never fetched by a script (robots.txt disallows it). | validation only (Prompt 9) |

## Partner data (Gavin)
Files Gavin committed to `data/raw/` (2026-09-21 and 09-26) before the manifest existed. They are in the
manifest as `partner_loydgc` rows with record counts and checksums; retrieval dates are unknown. Sources come
from his `notebooks/01_data_prep.ipynb` where it names them; we haven't verified them.

| File | Records | Source | Used in |
|---|---|---|---|
| `pa_hatcheries.gpkg` | 13 | ArcGIS Online `https://services9.arcgis.com/6EuFgO4fLTqfNOhu/arcgis/rest/services/PA_Hatcheries/FeatureServer/0` | placeholder `hatcheries` layer in pa_trout.gpkg (script 02) |
| `pa_boundary.gpkg` | 1 | Census cartographic boundaries, `https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_500k.zip`, filtered to PA | his maps |
| `pa_hatchery_production.csv` | 10 | PFBC hatchery web pages, one per row (`source_url` column) | hatchery supply shares |
| `pa_class_a_trout_streams.gpkg` | 1,361 | not recorded (same count as PASDA #9) | his maps |
| `pa_natural_repro_trout_streams.gpkg` | 6,224 | not recorded (same count as PASDA #25) | not referenced |
| `pa_stocked_trout_streams.gpkg` | 1,064 | not recorded (matches none of our year layers; see `known_gaps.md`) | his maps and `travel_arcs` distances |
| `Coop_nurseries.geojson` | 165 | not recorded | nursery locations (script 03) |
