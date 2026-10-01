# Data dictionary: data/processed

Key for every table: `section_id` = `f"{RFP_WaterID}_{SecNum}"` (PFBC water id + section number).
Source layers: PFBC fbweb stocked sections 2024–26 and the PASDA PAFishBoat wild-trout layers
(`docs/source_inventory.md`, `data/raw/manifest.csv`). Built by `scripts/02_build_sections.py`; scripts 03–05
add columns and tables, as noted per section below. Changes to PFBC data are described in
`docs/data_methods.md`.

## stocking_section_year (.parquet, .csv)
The baseline. One row per section × year × species (15,450 rows), including zeros.

| Column | Meaning | Units / values | Source |
|---|---|---|---|
| section_id | Section key | text | RFP_WaterID + SecNum |
| year | Stocking year | 2024, 2025, 2026 | StockingYear |
| species | Species | brook, brown, rainbow, golden, brood | Total{Brook,Brown,Rainbow,Golden,Brood}Stocked |
| count | Adult trout stocked that year | fish | as published (null brook/brown → 0) |
| source_layer | Layer the row came from | stocked_2024 … | |

Sections only appear in years they are in that year's layer. PFBC's own `TotalAdultStocked_minusBrood` =
brook + brown + rainbow (golden and brood are extra).

## sections (.parquet, .csv)
One row per section stocked in any of 2024–26 (1,045 rows). No geometry; the geometry is in
`pa_trout.gpkg`. Attributes come from the latest year the section appears in.

**Identity and location**

| Column | Meaning | Units / values | Source |
|---|---|---|---|
| section_id | Section key | text | |
| rfp_water_id | PFBC water id (same across a stream's sections) | int | RFP_WaterID |
| sec_num | Section number on the water | int | SecNum |
| gis_key | PFBC key | "RFP-Sec" | GIS_Key |
| water_name | Water name (not unique across counties) | text | WtrName |
| county | County, title case; "; "-joined when a section spans counties | text | County |
| water_type | Destination type | "stream" (lakes added later) | constant |
| latest_year | Latest year the section is in a stocked layer | year | |
| upper_limit, lower_limit | Section limits as text | text | SecUpper_1, SecLower_1 |
| upper_rm, lower_rm | Section limits as river miles from the mouth | mi | SecUpperLi, SecLowerLi |
| length_mi | Section length used for area: pfbc_length_mi, or rm_length_mi where the stocking check picks it (9 sections) | mi | PFBC (see length_source) |
| length_source | Which PFBC length length_mi uses: "pfbc_length" (1,036) or "river_miles" (9) | text | computed |
| pfbc_length_mi | PFBC's own section length | mi | Length_MI_ |
| rm_length_mi | \|upper_rm − lower_rm\| (PFBC river miles) | mi | computed |
| length_check_flag | pfbc_length_mi and rm_length_mi differ by more than 25%, or rm_length_mi is 0 (57 sections; `logs/02_length_check.csv`) | bool | computed |
| length_check_result | Flagged sections only: which length the stocking fits. fits_pfbc_length (14), fits_river_miles (9), both_plausible (21), neither (12), no_rate_or_fish (1); NA if not flagged | text | computed |
| rm_limits_reversed | upper_rm < lower_rm in PFBC's data (only Sherman Creek 3306_2) | bool | computed |
| mid_lat, mid_lon | Point halfway along the section line | EPSG:4326 degrees | computed |
| n_pieces | Rows the section had in the layer (2 = a "Stocked Trout Water" + a "Commonwealth Inland Waters" row; the first is kept) | int | computed |

**PFBC management category**

| Column | Meaning | Units / values | Source |
|---|---|---|---|
| allocation_code | PFBC stocking category code, [biomass][use][population][width] | e.g. DGS3 | AllocationCode |
| pfbc_category | PFBC category label ("OPTIMUM YIELD 2" is a name, not a width) | text | Description |
| biomass_class | Wild trout biomass class (A = Class A) | A–E | allocation_code char 1 |
| use_potential | Recreational use potential (access, parking, ownership) | High, Good, Low | char 2 (H/G/L) |
| pop_density | Human population density class | Metro, Urban, Suburban, Rural | char 3 (M/U/S/R) |
| width_class | PFBC width class: 1L >30 m, 1S 20–30 m, 2 = 10–20 m, 3 = 4–10 m, 4 <4 m | text | chars 4+ |
| max_trout_per_acre | PFBC maximum stocking rate for the category | trout/acre/yr | Operational Guidelines Table 18 via `pfbc_stocking_rates.csv` |
| max_trout_per_acre_missing_reason | Why the rate is NA (all 11 are biomass class A) | text | |
| reg_name | Regulation(s); "; "-joined for merged pieces | text | Reg_Name |
| special_reg | Any special regulation | bool | SpecReg == "Y" |
| best_fishing_water | PFBC "Best Fishing Waters" | bool | Best_Fishing_Wtr == "Y" |
| mentored_youth_water | Mentored youth water | bool | Mentored_Youth_Wtr == "Y" |
| program_name | PFBC program name, if any (KSSTW = Keystone Select Stocked Trout Waters); PFBC's `<Null>` read as missing | text | Wtr_Prog_Name |

**Stocking history (wide; NA = section not in that year's layer)**

| Column | Meaning | Units |
|---|---|---|
| {brook,brown,rainbow,golden,brood}_{2024,2025,2026} | Fish stocked by species and year | fish |
| total_{2024,2025,2026} | Sum of all five species | fish |
| years_stocked | Years the section is in a stocked layer | e.g. "2024,2025,2026" |
| n_years_stocked | Count of those years | 1–3 |

**Wild-trout overlap** (see `docs/data_methods.md`; a flag needs > 100 m of overlap)

| Column | Meaning | Units |
|---|---|---|
| class_a_overlap_mi | River miles shared with Class A sections on the same water | mi |
| class_a_flag | class_a_overlap_mi > 100 m | bool |
| nat_repro_overlap_mi | River miles shared with Natural Reproduction reaches on the same water | mi |
| nat_repro_flag | nat_repro_overlap_mi > 100 m (river miles only; 18 sections this misses are in `known_gaps.md`) | bool |
| wilderness_overlap_mi, wilderness_flag | Same as Class A, for Wilderness Trout Streams | mi, bool |
| class_a_gis_keys | Overlapping Class A sections | "RFP-Sec; …" |
| class_a_fishery | Class A species text as published (messy) | text |
| class_a_biomass | Class A layer biomass class | A–E |
| class_a_wild_brook, class_a_wild_brown, class_a_wild_rainbow | Species named in class_a_fishery | bool (NA if no Class A overlap) |

**Co-op nurseries** (added by `scripts/03_coop_stockings.py`)

| Column | Meaning | Units |
|---|---|---|
| coop_stocked | A co-op nursery lists this exact PFBC section (stream + county + section number). The list may be out of date: see `logs/03_coop_review.csv` | bool |
| coop_species | Species the co-op(s) stock here | e.g. "brown,rainbow" |
| coop_n_nurseries | Number of nurseries listing this section | int |

**River, region, area and density cap** (added by `scripts/04_river_cap.py`; the cap is explained in
`docs/model_design.md` "Density bound")

| Column | Meaning | Units / values |
|---|---|---|
| river_id | River key = rfp_water_id: shared by a stream's sections across counties, distinct for same-named streams (695 rivers) | int |
| region | PFBC region of the section's county (`county_region.csv`); no section spans two regions | Northwest, Northcentral, Northeast, Southwest, Southcentral, Southeast |
| width_top_m | Top of the width class (`parameters.csv` width_m value): 4 → 4, 3 → 10, 2 → 20, 1S → 30, 1L → 60 (assumption) | m |
| width_mid_m | Class midpoint, the tighter sensitivity (`parameters.csv` width_m low): 3, 7, 15, 25, 40 | m |
| area_acres, area_acres_mid | length_mi × width_top_m (or width_mid_m) × 0.398 acres per mile-metre | acres |
| program | Special program with its own Guidelines stocking rate: "DHALO" (Delayed Harvest Artificial Lures Only, from `reg_name`; 56) or "tailwater" (Youghiogheny 1327_1 and Conneauttee Creek 2649_1; listed by hand, as no layer flags tailwaters); NA otherwise | text |
| program_rate | The program's rate: Table 46 DHALO 190 at widths 2–3, 133 at 1S/1L; Table 45 tailwater 266 High, 247 Good access. NA outside a program | trout/acre/yr |
| access_rate | Highest Table 18 rate for the section's biomass + width at its own use potential (access) or any worse one, over all population classes. Lifts 17 biomass-B High sections at widths 2–3 from Table 18's 147 to 323. Biomass A at widths 2–3 (11 sections) has none and uses B's 323 (assumption, `parameters.csv`) | trout/acre/yr |
| cap_rate | **The rate cap_fish uses:** the higher of access_rate and program_rate | trout/acre/yr |
| cap_rate_river | The rate cap_fish_river uses: the highest Table 18 rate over access and population for the section's biomass + width (same biomass-A rule), or program_rate if higher | trout/acre/yr |
| cap_source | What sets cap_fish: "access_rate" (1,012), "program_rate" (9 sections where the program rate is higher), "class_a" (the 17 Class A overlaps stocked in 2026), "baseline" (7 sections PFBC stocks above their cap) | text |
| cap_fish | Density bound for the model: max(cap_rate × area_acres, 300); total_2026 where cap_source is class_a or baseline. Exclusions are separate (`environment`) | fish/yr |
| cap_fish_mid | Same with area_acres_mid (sensitivity); the class_a and baseline sections keep total_2026 | fish/yr |
| cap_fish_river | Sensitivity "river cap": max(cap_rate_river × area_acres, 300, total_2026); the 17 Class A sections keep total_2026 | fish/yr |
| cap_fish_class_a_grow | Scenario "Class A allowed to grow": cap_fish, but the 17 Class A sections get max(cap_rate × area_acres, 300, total_2026) | fish/yr |

Per-section 2026 stocking vs the cap (top and midpoint) is in `logs/04_cap_check.csv`.

## environment (.parquet, .csv)
One row per section (1,045). Built by `scripts/05_environment.py` from `sections`; overlaps aren't re-measured.

| Column | Meaning | Units / values |
|---|---|---|
| section_id | Section key | text |
| exclude | x_s = 0 in the model | bool (23 True) |
| exclude_reason | "; "-joined: wilderness (none), class_a_not_stocked (Buffalo Creek 3190_2), not_stocked_2026 (the other 22 stocked in 2024–25 only), health (Blue Hole Creek 3656_2, cadmium/lead). Scenario "dropped sections back" lifts rows whose reason is exactly "not_stocked_2026" | text, NA if not excluded |
| wild_brook_present | Class A Fishery text mentions brook trout. NA where no overlapping Class A record has species text: the other layers have no species, so NA means unknown, not absent | bool (17 False, 1,028 NA) |
| nat_repro_flag | Copied from sections (river-mile overlap > 100 m) | bool |
| nat_repro_share | nat_repro_overlap_mi / rm_length_mi, capped at 1 (both PFBC river miles); 0 where not flagged. For the "partial overlap" impact score | 0–1 |
| biomass_class | Copied from sections (allocation code) | A–E |

## county_region.csv
The 67 counties and their PFBC region, parsed from the regulated trout waters lists in PFBC's 2026
Pennsylvania Fishing Summary (`docs/data_methods.md`). Columns: county (title case, as in `sections.county`),
region, source.

## county_anglers.csv
Resident anglers per county (67 rows) from PFBC's *2024 Annual Fishing License & Permit Sales by Agent County*,
built by `scripts/06_county_anglers.py`. Every input is a column, so a PFBC count of permit holders by home
county could replace it. Method and limits: `docs/data_methods.md`, `docs/known_gaps.md` § Angler numbers by
county.

| Column | Meaning | Units |
|---|---|---|
| county, county_fips, region | County (spelled as in `sections.county`), 5-digit FIPS, PFBC region | text |
| pop_2020 | 2020 Census population (block groups summed) | people |
| annual_trout_combo | Annual trout + combo (trout and Lake Erie) permits sold by the county's agents in 2024 | permits |
| multi_trout_combo | 3-, 5- and 10-year trout + combo permits sold there in 2024 (earlier multi-year sales aren't in the source) | permits |
| nonres_licenses | Non-resident, non-resident PA student and 7/3/1-day tourist licenses sold there (annual + multi-year) | licenses |
| resident_permits | annual_trout_combo + multi_trout_combo − nonres_licenses | permits |
| pop_share | pop_2020 / PA population | 0–1 |
| online_permits | Online resident permits (117,500; no county in the source) × pop_share | permits |
| anglers | resident_permits + online_permits (421,615 statewide) | anglers |
| angler_rate | anglers / pop_2020 (state 0.032) | anglers per resident |
| online_permits_by_sales, anglers_by_sales, angler_rate_by_sales | Sensitivity: online permits split like the county's store sales instead of by population | as above |

## survey_water_crosswalk.csv
Survey favorite waters (p76–77) → PFBC rivers, built by `scripts/07_survey_crosswalk.py`. One row per
(waterbody, river_id): 232 rows for the 223 survey rows. Waters with no river have one row with river_id NA.
Undecided names are in `logs/07_survey_crosswalk_review.csv`.

| Column | Meaning | Values |
|---|---|---|
| waterbody, name_base, county_qualifier, pct_overall, lt_0_5_pct | As in `angler_survey/p76-77_preferred_waters_overall.csv` (waterbody is the join key) | text / % / bool |
| water_type | stream, lake (Lake/Reservoir/Pond/Dam in the name), unplaced (Other, Do not know, "other county or not sure") | text |
| river_id | Matched PFBC river (`sections.river_id`) | int, NA if none |
| water_name, river_region | PFBC's name and region(s) for the river | text |
| match_share | Share of the water's mentions going to this river; sums to 1 per matched water | 0–1, NA if none |
| stocked_mi_2026, n_sections_2026 | Length and count of the river's 2026-stocked sections | mi / count |
| match_method | unique_name, name_county, regional_split, manual (reason in the script), lake, unplaced, not_stocked_2026, no_pfbc_section, review | text |
| confidence | high, medium (e.g. a regional split, or a unique name whose region supplies few mentions), low (listed in the review file) | text, NA for the 16 review rows |
| note | Why, for splits, manual and doubtful rows | text |

## demand (.parquet, .csv)
Angler-days per year for each of the 1,022 sections stocked in 2026, built by `scripts/08_demand.py`. The two
signals are kept separate; the model blends them as `(1 − w) · prox_days + w · pref_days` (`blend_weight_w`).
Every angler-day column sums to the same statewide total, 8,717,541. Method: `docs/data_methods.md`; design:
`docs/model_design.md` § Angler benefit.

| Column | Meaning | Units / values |
|---|---|---|
| section_id, river_id | Keys | text / int |
| prox_days | Proximity demand: block-group angler-days sent out by each home region's p93 trip-distance bands, split within a band by section length | angler-days/yr |
| prox_days_pooled | Same, with one in-state distance curve (sensitivity) | angler-days/yr |
| prox_days_pop | Same, with every county at the state angler rate, rescaled to the statewide total (sensitivity) | angler-days/yr |
| pref_days_named | Preference demand from the survey waters matched to this river, split over its sections by length | angler-days/yr, 0 if none |
| pref_days | pref_days_named + the unplaced share spread like prox_days | angler-days/yr |
| survey_waterbody | Survey water(s) matched to the river, "; "-joined | text, NA if none |
| pref_per_mi_flag | The river's preference per stocked mile exceeds the state's highest prox_days per mile (review flag, not a cap) | bool (Youghiogheny 1327_1 only) |
| destination_index | River's pref_days_named ÷ its prox_days: ~1 = popular because people live nearby, 5+ = a destination | ratio, NA if not named |
| dhalo, catch_release, keystone_select, open_year_round | Regulation flags from `reg_name` / `program_name` (counts in data_methods.md) | bool |

## stocking_events (.parquet, .csv)
PFBC's planned 2026 stocking schedule, one row per section × date (2,474 rows: 2,102 stream, 372 lake), built
by `scripts/09_stocking_schedule.py`. Lakes and the 6 unmatched stream events are kept with `section_id` NA.
Method: `docs/data_methods.md` § Stocking schedule.

| Column | Meaning | Units / values |
|---|---|---|
| section_id | Matched section; NA for lakes and unmatched records. 8 scheduled sections aren't in the 2026 layer (`known_gaps.md`) | text |
| water_type, lake_key | stream or lake (schedule section 0); lakes get "name @ lat,lon" (the schedule has no lake id) | text |
| match_method | limits, name_county, coords, unmatched, lake (`same_listing` rows were merged away) | text |
| water, sec_num, listed_counties, upper_limit, lower_limit | As listed (water keeps ", Trib To ..."; sec 0 = lake); counties whose listing includes the event, "; "-joined | text / int |
| date, week_of, week_of_only | Stocking date; the week given instead (74 events have only a week, date NA) | date / bool |
| season | P pre-season, I in-season, F fall, W winter | text |
| hatchery | PFBC hatchery named for the event (never NA) | text |
| meeting_place, meeting_time | Truck meeting as listed (a few afternoon times print as "01:00") | text |
| run_id | date \| hatchery \| meeting-place key \| time; NA for week-of-only events | text |
| brook, brown, rainbow, golden | Species marked on any listing of the event (the schedule has no counts) | bool |
| regulation | Regulation label(s), "; "-joined | text |
| ul_lat, ul_lon, ll_lat, ll_lon | Upper and lower limit points from the schedule | EPSG:4326 |
| ul_dist_m | Metres from the upper-limit point to the matched section line (QA) | m |
| alloc_brook … alloc_brood, alloc_fish | 2026 fish credited to the event by the equal-split assumption; NA for lakes, unmatched records and sections not in the 2026 layer | fish |

## hatchery_schedule_supply.csv
Each hatchery's 2026 stream fish from the schedule (11 rows: the 10 in `pa_hatchery_production.csv` plus
Tionesta), built by `scripts/09_stocking_schedule.py`. The proposed hatchery supply; the lbs split is kept as a
check and sensitivity (`../CLAUDE.md` Agreed simplifications).

| Column | Meaning | Units |
|---|---|---|
| hatchery | PFBC hatchery | text |
| n_sections, n_stream_events, n_stream_events_uncounted, n_lake_events | 2026 sections it stocks, its stream events, stream events with no 2026 count (19 statewide), lake events | count |
| brook, brown, rainbow, golden, brood, stream_fish_2026 | Credited 2026 stream fish by species and in total | fish |
| share | stream_fish_2026 ÷ all 2026 stream fish | 0–1 |
| production_lbs, lbs_share | Gavin's lbs figure and its share of the 8 lbs figures (Pleasant Mount's is a fish count, Linesville has none) | lbs / 0–1 |
| share_lbs_set | Schedule share among those same 8 hatcheries (compare with lbs_share) | 0–1 |
| in_production_csv, in_hatcheries_gpkg | Name found in each of Gavin's files | bool |

## section_schedule (.parquet, .csv)
One row per 2026-stocked section (1,022): scheduled hatchery, runs, cluster and detour, built by
`scripts/10_runs_clusters.py`. Method: `docs/data_methods.md` § Runs and clusters.

| Column | Meaning | Units / values |
|---|---|---|
| n_events, n_runs | Schedule events; distinct dated runs | count |
| primary_hatchery, primary_hatchery_share | Hatchery with the most events (ties alphabetical) and its share of events | text / 0–1 |
| multi_hatchery, hatcheries | More than one hatchery (49 sections); all of them, most events first | bool / text |
| cluster_id, cluster_source, cluster_size | Run cluster under the default rule (`cluster_share_min` ≥ 0.5); schedule for all 1,022 (no_schedule_singleton would mark a section with no record) | text / count |
| detour_mi, detour_singleton | Road-mi to the nearest same-cluster section; 0 and True for the 103 singletons | mi / bool |
| detour_nn_mi | Road-mi to the nearest 2026-stocked section of any cluster (geographic fallback) | mi |
| cluster_id_strict, cluster_size_strict, detour_mi_strict | The same under the strict-majority rule (528 clusters) | text / count / mi |

## section_medoid_clusters (.parquet, .csv)
One row per 2026-stocked section (1,022), built by `scripts/13_medoid_clusters.py`. Geography-only clusters (k-medoids on
section-to-section road miles, split until each is at most `cluster_max_width_mi` wide and `cluster_max_sections`
sections). They never use the schedule or hatcheries, so they carry none of PFBC's hatchery choices.

| Column | Meaning | Units |
|---|---|---|
| section_id | Join key | text |
| medoid_cluster_id | Cluster, e.g. M001 (407 clusters) | text |
| medoid_section_id | The cluster's most central section | text |
| cluster_size | Sections in the cluster | count |
| dist_to_medoid_mi | Road distance from the section to its medoid | road mi |
| silhouette | How well the section fits its cluster (1 best, below 0 misplaced) | -1 to 1 |

Cluster cost for hatchery h = average of h's road distance (`hatchery_to_section_road_distance`) to the cluster's sections.

## clusters.csv
One row per default-rule cluster (351), built by `scripts/10_runs_clusters.py`.

| Column | Meaning | Units |
|---|---|---|
| cluster_id, cluster_source, n_sections, section_ids | Cluster and members | text / count |
| centroid_lat, centroid_lon | Mean of member midpoints | EPSG:4326 |
| cluster_mi | Minimum spanning tree over member midpoints × circuity (route-length proxy; 0 for singletons) | road mi |
| span_mi, span_flag | Farthest member pair × circuity; flag when over `cluster_span_check_mi` (none) | road mi / bool |
| hatcheries, n_runs, n_events | Hatcheries by events, most first; runs and events on members | text / count |

## parameters.csv
Values no source gives directly, or that we apply beyond what the source says (CLAUDE.md rule 7). One row per
value; scripts read them from here.

| Column | Meaning |
|---|---|
| parameter | Name, e.g. width_m, biomass_a_rate_per_acre, min_fish_per_section |
| applies_to | Width class or biomass/width the row applies to; blank if general |
| value | Central value used by the scripts |
| units | Units |
| low, high | Sensitivity range (for width_m, low is the class midpoint) |
| source | Citation, or "assumption" |
| note | Reasoning and how the value is used |

## coop_stockings (.parquet, .csv)
PFBC co-op nursery stocking list (`cnu-stockings-website.xlsx`), one row per nursery × water (786 rows). It
has no fish counts and no years. Co-op fish are not part of PFBC's allocation.

| Column | Meaning | Values |
|---|---|---|
| sponsor, nursery, county, stream, section | As published (section = PFBC section number, blank for ponds) | text / int |
| brook, brown, rainbow, golden | Species stocked ("X" in the source) | bool |
| water_type | Name contains lake/pond/dam/reservoir/impoundment | stream, lake_pond |
| match_method | How the water was located | pfbc_section, pfbc_stream_other_section (PFBC stream, but a section PFBC doesn't stock), wild_layer_stream (Natural Reproduction / Class A layer), unmatched_lake_pond, unmatched |
| section_id | Our section, when match_method = pfbc_section | text |
| nursery_located_by | How the nursery was found in Gavin's `Coop_nurseries.geojson` | nursery_name, sponsor_name, name_contains, NA |
| nursery_lat, nursery_lon | Nursery location (layer precision ~0.01°) | EPSG:4326 |
| nursery_to_water_mi | Straight-line miles from the nursery to the matched water | mi |

## pfbc_stocking_rates.csv
Operational Guidelines Table 18, expanded to one row per allocation code (234 rows).

| Column | Meaning |
|---|---|
| allocation_code | Code as in `sections.allocation_code` |
| biomass_class, use_code, pop_code, width_class | Code parts |
| max_trout_per_acre | Maximum stocking rate (trout/acre/yr) |
| membership | High Yield, Optimum Yield, Low Yield, River |
| source | Citation |

Table 18 has no biomass-A rows for widths 2–4 and no Metro river rows.

## angler_survey/ (.csv)
Tables from the 2023 PFBC trout angler survey (Responsive Management), one CSV per question, built by
`scripts/00_extract_angler_survey.py`. Not keyed by `section_id`: survey waters join to rivers through
`survey_water_crosswalk.csv`. File list, columns and caveats: `data/processed/angler_survey/README.md`.

## pa_trout.gpkg (GeoPackage, EPSG:4326)
For mapping and spatial joins; join to the tables on `section_id`. Gitignored (16 MB): rebuild it with
`scripts/01_download_pfbc_layers.py` and `scripts/02_build_sections.py`.

| Layer | Features | Contents |
|---|---|---|
| sections | 1,045 | Section lines (duplicate pieces: "Stocked Trout Water" row kept) + key fields: section_id, water_name, county, latest_year, years_stocked, allocation_code, pfbc_category, reg_name, length_mi, length_source, total_2024–2026, class_a/nat_repro/wilderness flags |
| hatcheries | 10 | PFBC trout hatcheries (TROUT == "y") from `data/raw/pa_hatcheries.gpkg`. Placeholder until merged with Gavin's cleaned hatchery and co-op layers |
| class_a | 1,361 | PASDA PAFishBoat #9, all fields; geometry simplified to 5 m |
| nat_repro | 6,224 | PASDA PAFishBoat #25, all fields; geometry simplified to 5 m |
| wilderness | 134 | PASDA PAFishBoat #31, all fields; geometry simplified to 5 m |
