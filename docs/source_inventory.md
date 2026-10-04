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
| State Fish Hatcheries | fbweb `Hatcheries/MapServer/0` | 13 points | NAME (trailing spaces), FULL_NAME, TROUT / WARM_COOL / STEEL_SALMON flags, Lat, Long_ | hatchery name, as in the stocking schedule | **the authoritative hatchery set** (decision 2026-09-29); downloaded by script 01 on 2026-09-29 |

URL notes (rule 5):
- The 2025 service's section layer is `/2`, not `/0`.
- The 2024 layer's maxRecordCount is 1000, so it is paged.
- PASDA's 2026 stocked layer (PAFishBoat #26) has no counts: stocking counts come from fbweb only.
- No stocked-section layer reaches 2022, the survey year.
- State Fish Hatcheries is the layer behind PennMAP's "State Fish Hatcheries" page
  (https://pa-geo-data-pennmap.hub.arcgis.com/maps/25b8cd8915674873add59c31c5bdfc12_0/about; item owner
  PFBC_GIS_Admin2, credit "Pennsylvania Fish and Boat Commission"; resolved through the ArcGIS item API
  2026-09-29). Its `TROUT` flag doesn't match the 2026 schedule: it marks Linesville and Pleasant Mount, which
  stock no streams, and not Tionesta, which does. The model's supply nodes come from the schedule instead
  (`../CLAUDE.md` Units of analysis).

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
- **2026-09-29: the county list came back empty** (`[]`, even with every season selected), so the page's county
  menu is empty too, while each county's schedule still loads. Script 09 falls back to the 67 counties in
  `county_region.csv` (spelled "McKean", as the schedule spells it). A fresh pull that day is saved in
  `data/raw/pfbc_schedule/2026-09-29/` (68 files; `counties.json` is the empty list).

## PFBC files and documents
| Source | URL | Retrieved | Local copy | Used for |
|---|---|---|---|---|
| Cooperative nursery stocking list (xlsx, 786 rows) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/fishing/stocking/coop-nurseries/cnu-stockings-website.xlsx | 2026-09-27 | `data/raw/pfbc_coop/` | coop_stockings, `coop_stocked` (script 03) |
| Operational Guidelines for the Management of Trout Fisheries, 5th ed. | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/operationguidelinestroutmgt.pdf | 2026-09-26 | `data/raw/pfbc_docs/` | Table 14 widths, Table 18 rates (`pfbc_stocking_rates.csv`), Appendix A (Class A) |
| 2026 Pennsylvania Fishing Summary (summary book, 42 pages) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/fishing/regulations/summarybook.pdf | 2026-09-27 | `data/raw/pfbc_docs/` | county → region (`county_region.csv`, script 04), from the regulated trout waters lists (pdf pp. 25–36) |
| 2023 trout angler survey: Responsive Management for PFBC, *Trout Fishing in Pennsylvania* (PDF, 201 pages; describes 2022 fishing). Byte-identical to the copy saved by hand 2026-09-26 that the tables were first extracted from | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/troutanglersurveyreport-2023.pdf | 2026-09-27 | `data/raw/pfbc_angler_survey_2023/` | survey tables in `data/processed/angler_survey/` (script 00); demand (Prompt 6) |
| 2024 Pennsylvania Annual Fishing License & Permit Sales by Agent County (PDF, 4 pages: annual and multi-year licenses and permits by the county of the selling agent, plus Internet and out-of-state rows) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/reports/fishinglicensesalesbycounty2024.pdf | 2026-09-27 | `data/raw/pfbc_docs/` | county angler rate for proximity demand (Prompt 6). Sales are by store county, not home county (`known_gaps.md` § Angler numbers by county) |
| 2020–24 Trout Management Plan | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/reports/troutplan2020.pdf | 2026-10-03 | `data/raw/pfbc_creel/` | `env_research.md` |
| 2025–29 Trout Management Plan | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/troutplan2025.pdf | 2026-10-03 | `data/raw/pfbc_creel/` | `env_research.md`, report hook (Obj. 9.1) |
| Summary of the 165th Commission meeting (Jan 2026) | https://www.pa.gov/agencies/fishandboat/newsroom/summary-165th-meeting-pfbc-jan2026 | web page, not saved | | Class A exemptions (`env_research.md` § 3) |

## Angler-use studies (creel and residence surveys, recall bias)
Found by a research pass on 2026-10-03 (the request list and every download are in `data/raw/manifest.csv`;
none was refused). Used for the demand checks and the k evidence in `model_design.md` § Angler benefit and
`known_gaps.md` § Angler-use data. Downloads that held nothing we use (Youghiogheny and Big Spring plans, WV
appendix, NYSDEC comment assessment, PFBC news pages, a bioRxiv preprint, Semantic Scholar abstract records for
paywalled papers) are only in the manifest.

| Source | URL | Retrieved | Local copy | Used for |
|---|---|---|---|---|
| PFBC Pine Creek Fisheries Management Plan (2012), Appendix B: Kristine & Detar, angler use, catch and harvest survey, Sections 11–13, Apr–Oct 2008 | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/fisheries-mgmt-plans/pine-creek-plan-apdxb.pdf | 2026-10-03 | `data/raw/pfbc_creel/` | trips, trips per trout, return to creel, reasons for choosing the spot |
| Same plan, Appendix C: Graefe et al. 2010 (Penn State), on-site and mail survey | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/fisheries-mgmt-plans/pine-creek-plan-apdxc.pdf | 2026-10-03 | `data/raw/pfbc_creel/` | anglers' home regions (demand origin check), trip length, overnight stays |
| Same plan, main text (Hollender et al. 1982 creel summary) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/fisheries-mgmt-plans/pine-creek-plan.pdf | 2026-10-03 | `data/raw/pfbc_creel/` | return to creel 43% |
| PFBC Lehigh River management plan (Pierce & Arnold 2007 creel summary) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/fisheries-mgmt-plans/5_lehigh_plan.pdf | 2026-10-03 | `data/raw/pfbc_creel/` | anglers' home county (demand origin check, 2730_6) |
| Carline et al. 2011, Spring Creek fishery (PFBC technical report) | https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/fisheries-mgmt-plans/springck_fishery.pdf | 2026-10-03 | `data/raw/pfbc_creel/` | angler use before and after stocking stopped |
| Pa. Bulletin 53-49, doc. 1685 (Dec 2023): Class A + stocked sections final rule | https://www.pacodeandbulletin.gov/Display/pabull?file=/secure/pabulletin/data/vol53/53-49/1685.html | 2026-10-03 | `data/raw/pfbc_creel/` | Bald Eagle Creek 2021 harvest, opening-day counts |
| Connelly & Brown 1995, angler diaries vs 12-month recall (via SEDAR) | https://sedarweb.org/documents/s17rd19-use-of-angler-diaries-to-examine-biases-associated-with-12-month-recall-on-mail-questionnaires/ | 2026-10-03 | `data/raw/angler_use_literature/` | recall bias (+44–45%) |
| Fisher et al. 1991, recall period and the National Survey (via SEDAR) | https://sedarweb.org/documents/s24rd63-length-of-recall-period-and-accuracy-of-estimates-from-the-national-survey-of-fishing-hunting-and-wildlife-associated-recreation/ | 2026-10-03 | `data/raw/angler_use_literature/` | recall bias (annual vs quarterly +34%) |
| Ready, Delavan & Epp 2003, PA trout license demand (USDA FS) | https://research.fs.usda.gov/download/treesearch/21141.pdf | 2026-10-03 | `data/raw/angler_use_literature/` | license sales vs trout stocked, 1970–2000 |
| NYSDEC, Catch Rate Oriented Trout Stocking evaluation (Alexiades et al. 2014) | https://extapps.dec.ny.gov/docs/fish_marine_pdf/crots.pdf | 2026-10-03 | `data/raw/angler_use_literature/` | New York's allocation method (comparison) |
| NYSDEC Trout Stream Management Plan (2020) | https://extapps.dec.ny.gov/docs/fish_marine_pdf/troutstreammp.pdf | 2026-10-03 | `data/raw/angler_use_literature/` | New York's allocation rules (comparison) |
| Virginia DWR Stocked Trout Management Plan 2016–2025 | https://dwr.virginia.gov/wp-content/uploads/stocked-trout-management-plan-final.pdf | 2026-10-03 | `data/raw/angler_use_literature/` | Virginia's allocation formula (comparison) |
| Hyman 2015, Virginia stocked trout program (Virginia Tech thesis) | https://vtechworks.lib.vt.edu/server/api/core/bitstreams/98cc031c-5d61-4ada-9fec-7481a26d80da/content | 2026-10-03 | `data/raw/angler_use_literature/` | Virginia return to creel, travel distance |
| NJ DFW 2018 trout allocation meeting slides | https://www.nj.gov/dep/fgw/pdf/2018/trout_allocations_mtg.pdf | 2026-10-03 | `data/raw/angler_use_literature/` | New Jersey's lake allocation (comparison) |
| Iowa DNR 2016 trout angler survey | https://publications.iowa.gov/35021/1/Trout%20Angler%20Survey.pdf | 2026-10-03 | `data/raw/angler_use_literature/` | anglers following stocking schedules |
| Wisconsin DNR 2014, *Trout Fishing in Wisconsin: Angler Behavior, Program Assessment and Regulation and Season Preferences* (Petchenik) | https://dnr.wisconsin.gov/sites/default/files/topic/Fishing/Trout_TroutReportJan2014.pdf | 2026-10-04 | `data/raw/angler_use_literature/` | public-access preference (Table V-4, p. 52): the access sensitivity |

## Census
Verified with a HEAD request before download (2026-09-27); the TIGERweb rows with `?f=pjson` (2026-10-04).

| Source | URL | Retrieved | Local copy | Used for |
|---|---|---|---|---|
| 2020 Census centers of population by block group, Pennsylvania (10,173 block groups: population and population-weighted latitude/longitude) | https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG42.txt | 2026-09-27 | `data/raw/census/` | **No longer used (2026-10-04).** Was proximity demand and county population (Prompt 6); replaced by the county-subdivision counts below. Raw files and manifest rows kept |
| 2020 Census Gazetteer, counties (national file; names, land area) | https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_Gaz_counties_national.zip | 2026-09-27 | `data/raw/census/` | county names and land area (rural-county check) |
| 2020 Census population by county subdivision, PA (`POP100` = PL 94-171 total population; 2,573 rows, 1 Jan 2020 boundaries). TIGERweb Census 2020, layer 20 "County Subdivisions"; attribute query, no geometry, one request (`maxRecordCount` 100,000) | https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/20/query?where=STATE='42'&outFields=GEOID,STATE,COUNTY,NAME,POP100&returnGeometry=false&orderByFields=GEOID&f=json | 2026-10-04 | `data/raw/census_pop/2026-10-04/` (`cousub2020_pa_pop.json`, layer and service metadata) | proximity-demand origins (`subdivision_anglers`) and county population (script 06) |
| 2020 Census population by county, PA (`POP100`; 67 rows). TIGERweb Census 2020, layer 82 "Counties"; same query | https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/82/query (same parameters) | 2026-10-04 | `data/raw/census_pop/2026-10-04/county2020_pa_pop.json` | check: each county's subdivisions add to its count (67 of 67) |
| 2026 county subdivision holding each 2020 subdivision with no 2026 code (7 point queries on the 2020 internal points, from a `GEOID IN (...)` query of layer 20) | https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2026/MapServer/22/query (`geometry=<lon,lat>`, `esriGeometryPoint`, `returnGeometry=false`) | 2026-10-04 | `data/raw/census_pop/2026-10-04/cousub2026_containing_<GEOID>.json`, `cousub2020_gone_by_2026.json` | 2020 → 2026 crosswalk (`SUCCESSOR_2026` in script 06) |

**Census Data API: refused without a key (2026-10-04).** The plan was 2020 PL 94-171 `P1_001N` by county subdivision from
`https://api.census.gov/data/2020/dec/pl?get=NAME,P1_001N&for=county%20subdivision:*&in=state:42&in=county:*`. Its
`geography.json` and `variables/P1_001N.json` answered (summary level 060 requires state and county, with county
wildcardable; `P1_001N` = "Total"), but the data request was redirected to a "Missing Key" page ("A valid key must be
included with each data API request"). No key was used. The metadata and the refusal page are saved under
`data/raw/census_pop/2026-10-04/`. No 2020 Centers of Population file exists for county subdivisions either (the
`cenpop2020/` folder has state, county, tract and block group only).

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
| `pa_hatcheries.gpkg` | 13 | ArcGIS Online `https://services9.arcgis.com/6EuFgO4fLTqfNOhu/arcgis/rest/services/PA_Hatcheries/FeatureServer/0`. An older copy of PFBC's State Fish Hatcheries layer (checked 2026-09-29: same 13 points at the same coordinates and the same flags; older web links, and Union City's old name). Superseded by the fbweb layer above | placeholder `hatcheries` layer in pa_trout.gpkg (script 02); `trout_hatcheries.gpkg` and the road distances; hatchery names in script 09 |
| `pa_boundary.gpkg` | 1 | Census cartographic boundaries, `https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_500k.zip`, filtered to PA | his maps |
| `pa_hatchery_production.csv` | 10 | Scraped with Claude from PFBC's official [State Fish Hatcheries](https://www.pa.gov/agencies/fishandboat/about-us/agency-overview/bureaus/state-fish-hatcheries) pages, one per row (`source_url` column; e.g. [Bellefonte](https://www.pa.gov/agencies/fishandboat/about-us/agency-overview/bureaus/state-fish-hatcheries/bellefonte-state-fish-hatchery)). The "Average Trout Production" figure was rechecked against that page on 2026-10-03 (338,918 lbs, matches) | the pounds-based supply sensitivity (supply itself comes from the stocking schedule since 2026-09-28) |
| `pa_class_a_trout_streams.gpkg` | 1,361 | not recorded (same count as PASDA #9) | his maps |
| `pa_natural_repro_trout_streams.gpkg` | 6,224 | not recorded (same count as PASDA #25) | not referenced |
| `pa_stocked_trout_streams.gpkg` | 1,064 | not recorded (matches none of our year layers; see `known_gaps.md`) | his maps and `travel_arcs` distances |
| `Coop_nurseries.geojson` | 165 | PFBC Cooperative Nurseries layer on PASDA, [dataset 970](https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=970) (2020 release; [download](https://www.pasda.psu.edu/download/pafish/CooperativeNurseries202002.zip)); source named by Gavin 2026-10-03, and the page confirms the layer. PASDA states no record count, so the 165 is not checked against it | nursery locations (script 03); co-ops are out of the model (team decision 2026-09-27), so this only feeds the `coop_stocked` flag and maps |

## County subdivisions (Census TIGERweb; Gavin)
- **Endpoint:** `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2026/MapServer/22` (County Subdivisions).
  `?f=pjson` verified 2026-10-03: geoJSON and pagination supported, maxRecordCount 100,000; service description "ACS 2026 Legal and Statistical
  Entities Web Map Service; January 1, 2026 vintage". Filtered to `STATE='42'`: 2,568 features in 67 counties, pulled as 11 pages of 250
  (about 18 KB of polygon per feature). Key: `GEOID` (10 digits: state + county + subdivision), kept as `subdivision_id`. Credit: U.S. Census Bureau.
- **Why this service (the "most recent 2026 version" check, 2026-10-03):** its boundaries are as of 1 Jan 2026, the newest Census publishes.
  The downloadable TIGER/Line shapefiles stop at 2025 (`TIGER2025/COUSUB/tl_2025_42_cousub.zip`, boundaries as of 1 Jan 2025, released
  2025-09-22; `TIGER2026/COUSUB/tl_2026_42_cousub.zip` and `GENZ2026` return 404). `tigerWMS_Current` serves the same 1 Jan 2026 data as
  `tigerWMS_ACS2026` (attributes identical, checked) but rolls to the next vintage, so the script pins ACS2026 and stops if the service
  description stops saying "January 1, 2026". For PA the 2025 and 2026 vintages agree on all 2,568 GEOIDs, names, types, land areas and points.
- **Reference guide:** [Guide to 2010 State and Local Census Geography, Pennsylvania](https://www.census.gov/geographies/reference-files/2010/geo/state-local-geo-guides-2010/pennsylvania.html)
  defines the geography: 2,575 county subdivisions in 2010 (1,546 townships, 1 inactive township, 1,027 boroughs, cities and towns, 1 undefined
  water-area MCD). It is a 2010 description, not a data vintage: the current set has 2,568, with the same water placeholder.
- **Used in:** `scripts/19_subdivision_road_distances.py`. Raw pages: `data/raw/census_cousub/2026-10-03/` (manifest rows).

## Road distances (OSRM public demo server; Gavin)
- **Endpoint:** `https://router.project-osrm.org/table/v1/driving/` (OSRM table service, driving profile, fastest route; road data
  from OpenStreetMap, credit "(c) OpenStreetMap contributors"). First used 2026-09-28; works for up to about
  200 coordinates per request.
- **Used in:** `scripts/11_road_distances.py` (13 hatcheries x 1,045 sections), `scripts/12_section_road_distances.py` (1,022 x 1,022
  sections in 121 blocks of 100 x 100) and `scripts/19_subdivision_road_distances.py` (2,567 county subdivisions x 1,045 sections in 286
  blocks of 100 x 100). Pause between requests: 1.5 s. Method and checks: `data_methods.md` § Road distances.
- **Note:** this is the public demo server that CLAUDE.md rule 3 says never to bulk-query. See `known_gaps.md` § OSRM demo server for
  the waiver and what was done.
