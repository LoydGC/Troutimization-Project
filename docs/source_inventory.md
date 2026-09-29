# Source inventory

Every source the pipeline and docs use: where it is, what it holds and how it joins to `section_id`. Each
download is also logged in `data/raw/manifest.csv` (URL, retrieval time, record count). Started 2026-09-27
with the sources already in use; Prompt 1 adds the rest (the full GIS crawl).

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
| Natural Reproduction | PASDA `25` | 6,224 | AnglerUse (no species) | river-mile overlap on the same RFP_WaterID (rule 8) | nat_repro_flag |
| Wilderness Trout Streams | PASDA `31` | 134 | | river-mile overlap | wilderness overlap (none) |
| Stocked lakes | fbweb `PFBC_Stocked_Trout_Waters/MapServer/5` | 131 polygons | no stocking counts | not used yet | checked 2026-09-26, `known_gaps.md` |

URL notes (rule 5):
- The 2025 service's section layer is `/2`, not `/0`.
- The 2024 layer's maxRecordCount is 1000, so it is paged.
- PASDA's 2026 stocked layer (PAFishBoat #26) has no counts: stocking counts come from fbweb only.
- No stocked-section layer reaches 2022, the survey year.

## Trout stocking schedule (runs, hatchery per event)
Found from the page's own script (`/TroutStocking/Scripts/StockedWaters.js`) and checked with small requests
(2026-09-28), then downloaded by `scripts/09_stocking_schedule.py`: 68 requests, raw responses in
`data/raw/pfbc_schedule/2026-09-28/` (31 MB, gitignored). `https://fbweb.pa.gov/robots.txt` returns 404, so no
robots rules apply. The page has no terms-of-use link (footer: "Copyright © 2023 Commonwealth of Pennsylvania").
It says "All stocking events are subject to change without notice": this is PFBC's **planned** schedule, not a
record of what was stocked. Only 2026 is served: a 2025 date range returns "No Stockings in this Date Range".

Base URL: `https://fbweb.pa.gov/TroutStocking/`.

| Endpoint | Request | Returns | Verified | Used in |
|---|---|---|---|---|
| `Home/GetCountyBySeason?intputSelectedSeasons=` (sic) | GET | JSON list of the 67 counties, each with `IsEnable` | GET | the county list (script 09) |
| `Home/Secondpage` | POST, JSON body `{"County": "<county>", "StartDate": "", "EndDate": "", "PageNumber": "", "Water": "", "Season": ""}`. Season blank = all (`P,I`, `F`, `W` filter); dates optional | HTML fragment with all of the county's events for the year in one response (the 10-per-page paging is done in the browser). Each `.stocksDiv` has `data-mapatt`, 17 fields separated by `\|`: Water, County, Sec, Upper_Limit, Lower_Limit, StkgingDate, WeekOf, Brook, Brown, Rainbow, Golden (X marks, no counts), MtgPlc, MtgTime, Hatchery, TroutRegulation1, Reg_Link, Season (P/I/F/W); plus upper and lower limit lat/long | POST for 3 counties, then all 67 (2,734 records). A blank County returns no records | stocking_events, hatchery_schedule_supply (09); section_schedule, clusters (10) |
| `Home/GetDates` | GET | JSON `[start, end]` of the upcoming fall/winter window (`["2026-10-01","2026-12-17"]`) | GET | not used |

URL notes (rule 5):
- There is no ArcGIS layer for the schedule: `PFBC_Map_Services` (46 services), `PFBC_Stocked_Trout_Waters` and
  `TroutStockedSections_2026` have no schedule layer or table (checked 2026-09-28).
- The page's "Print All Trout Stockings" CSV is built in the browser from the same fields; there is no server export.
- A section on a county line is listed under each of its counties (merged in script 09).

## PFBC files and documents
| Source | URL | Retrieved | Local copy | Used for |
|---|---|---|---|---|
| Cooperative nursery stocking list (xlsx, 786 rows) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/fishing/stocking/coop-nurseries/cnu-stockings-website.xlsx | 2026-09-27 | `data/raw/pfbc_coop/` | coop_stockings, `coop_stocked` (script 03) |
| Operational Guidelines for the Management of Trout Fisheries, 5th ed. | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/operationguidelinestroutmgt.pdf | 2026-09-26 | `data/raw/pfbc_docs/` | Table 14 widths, Table 18 rates (`pfbc_stocking_rates.csv`), Appendix A (Class A) |
| 2026 Pennsylvania Fishing Summary (summary book, 42 pages) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/fishing/regulations/summarybook.pdf | 2026-09-27 | `data/raw/pfbc_docs/` | county → region (`county_region.csv`, script 04), from the regulated trout waters lists (pdf pp. 25–36) |
| 2023 trout angler survey: Responsive Management for PFBC, *Trout Fishing in Pennsylvania* (PDF, 201 pages; describes 2022 fishing). Byte-identical to the copy saved by hand 2026-09-26 that the tables were first extracted from | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/troutanglersurveyreport-2023.pdf | 2026-09-27 | `data/raw/pfbc_angler_survey_2023/` | survey tables in `data/processed/angler_survey/` (script 00); demand (Prompt 6) |
| 2024 Pennsylvania Annual Fishing License & Permit Sales by Agent County (PDF, 4 pages: annual and multi-year licenses and permits by the county of the selling agent, plus Internet and out-of-state rows) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/reports/fishinglicensesalesbycounty2024.pdf | 2026-09-27 | `data/raw/pfbc_docs/` | county angler rate for proximity demand (Prompt 6). Sales are by store county, not home county (`known_gaps.md` § Angler numbers by county) |
| 2020–24 Trout Management Plan | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/reports/troutplan2020.pdf | not downloaded | | `env_research.md` |
| 2025–29 Trout Management Plan | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/troutplan2025.pdf | not downloaded | | `env_research.md`, report hook (Obj. 9.1) |
| Summary of the 165th Commission meeting (Jan 2026) | https://www.pa.gov/agencies/fishandboat/newsroom/summary-165th-meeting-pfbc-jan2026 | web page, not saved | | Class A exemptions (`env_research.md` § 3) |

## Census
Verified with a HEAD request before download (2026-09-27).

| Source | URL | Retrieved | Local copy | Used for |
|---|---|---|---|---|
| 2020 Census centers of population by block group, Pennsylvania (10,173 block groups: population and population-weighted latitude/longitude) | https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG42.txt | 2026-09-27 | `data/raw/census/` | proximity demand and county population (Prompt 6) |
| 2020 Census Gazetteer, counties (national file; names, land area) | https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_Gaz_counties_national.zip | 2026-09-27 | `data/raw/census/` | county names and land area (rural-county check) |

## Local reference copies (`data/references/`, gitignored)
Saved by hand, not by a script, so they aren't in the manifest. This table is the record of where each came
from.

| File | Source | Used for |
|---|---|---|
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
