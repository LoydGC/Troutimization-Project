# Data dictionary: data/processed

Key for every table: `section_id` = `f"{RFP_WaterID}_{SecNum}"` (PFBC water id + section number).
Source layers: PFBC fbweb stocked sections 2024–26 and the PASDA PAFishBoat wild-trout layers
(`docs/source_inventory.md`, `data/raw/manifest.csv`). Built by `scripts/02_build_sections.py`. Changes to
PFBC data are described in `docs/methods.md`.

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
| length_mi | GIS length of the section line | mi (EPSG:26918) | computed |
| rm_length_mi | \|upper_rm − lower_rm\| (GIS length is ~10% longer at the median) | mi | computed |
| rm_limits_reversed | upper_rm < lower_rm in PFBC's data (only Sherman Creek 3306_2) | bool | computed |
| mid_lat, mid_lon | Point halfway along the section line | EPSG:4326 degrees | computed |
| n_pieces | Rows the section had in the layer (2 = split by regulation or county, merged) | int | computed |

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
| program_name | PFBC program name, if any | text | Wtr_Prog_Name |

**Stocking history (wide; NA = section not in that year's layer)**

| Column | Meaning | Units |
|---|---|---|
| {brook,brown,rainbow,golden,brood}_{2024,2025,2026} | Fish stocked by species and year | fish |
| total_{2024,2025,2026} | Sum of all five species | fish |
| years_stocked | Years the section is in a stocked layer | e.g. "2024,2025,2026" |
| n_years_stocked | Count of those years | 1–3 |

**Wild-trout overlap** (see `docs/methods.md`; a flag needs > 100 m of overlap)

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
For mapping and spatial joins; join to the tables on `section_id`.

| Layer | Features | Contents |
|---|---|---|
| sections | 1,045 | Section lines (duplicate pieces unioned) + key fields: section_id, water_name, county, latest_year, years_stocked, allocation_code, pfbc_category, reg_name, length_mi, total_2024–2026, class_a/nat_repro/wilderness flags |
| hatcheries | 10 | PFBC trout hatcheries (TROUT == "y") from `data/raw/pa_hatcheries.gpkg` |
| class_a | 1,361 | PASDA PAFishBoat #9, all fields; geometry simplified to 5 m |
| nat_repro | 6,224 | PASDA PAFishBoat #25, all fields; geometry simplified to 5 m |
| wilderness | 134 | PASDA PAFishBoat #31, all fields; geometry simplified to 5 m |
