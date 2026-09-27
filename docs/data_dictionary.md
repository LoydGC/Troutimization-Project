# Data dictionary: data/processed

Key for every table: `section_id` = `f"{RFP_WaterID}_{SecNum}"` (PFBC water id + section number).
Source layers: PFBC fbweb stocked sections 2024–26 and the PASDA PAFishBoat wild-trout layers
(`docs/source_inventory.md`, `data/raw/manifest.csv`). Built by `scripts/02_build_sections.py`. Changes to
PFBC data are described in `docs/data_methods.md`.

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
| nat_repro_geom_overlap_mi | Length of the section within 30 m of Natural Reproduction lines on the same water | mi |
| nat_repro_flag | river-mile overlap > 100 m, or geometric overlap ≥ 0.5 mi | bool |
| nat_repro_flag_source | Which rule set the flag | river_miles, geometry, NA |
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
