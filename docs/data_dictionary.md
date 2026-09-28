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
`scripts/00_extract_angler_survey.py`. Not keyed by `section_id`: survey waters need a crosswalk first
(Prompt 6). File list, columns and caveats: `data/processed/angler_survey/README.md`.

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
