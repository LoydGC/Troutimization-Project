# Data

Processed data is committed, including `pa_trout.gpkg` (16 MB, all geometry; scripts `01` and `02` rebuild it), so
the model and every figure script run from a clone. Raw downloads and `references/` are git-ignored, except
`manifest.csv` (enough to re-fetch) and four small partner files in `raw/` that the scripts read
(`pa_boundary.gpkg`, `pa_hatcheries.gpkg`, `pa_hatchery_production.csv`, `Coop_nurseries.geojson`).
Don't keep a separate source list here:
- `data/raw/manifest.csv` – every download, with URL, retrieval timestamp and record count (enough to re-fetch)
- `docs/source_inventory.md` – endpoints, fields, join keys, and where each reference document came from
- `docs/data_dictionary.md` – every column in `data/processed/`

## Processed outputs
Tables are parquet with a csv copy unless noted. Section tables are keyed by `section_id = f"{RFP_WaterID}_{SecNum}"`.
Every column is described in `docs/data_dictionary.md`; this is only the map.

| Table | One row per | Built by |
|---|---|---|
| **Sections and baseline** | | |
| `sections` | section stocked in any of 2024–26 (1,045): ids, location, allocation category, counts, wild-trout overlap, density cap. No geometry | 02, 03, 04 |
| `stocking_section_year` | section × year × species: the stocked count (the baseline) | 02 |
| `environment` | section: exclusions, wild brook trout, wild-trout impact inputs | 05 |
| `pfbc_stocking_rates.csv` | allocation code: Operational Guidelines Table 18 rate | 02 |
| `coop_stockings` | co-op nursery × water (no fish counts) | 03 |
| `county_region.csv` | county: PFBC region | 04 |
| **2026 schedule and clusters** | | |
| `stocking_events` | section × date on PFBC's planned 2026 schedule | 09 |
| `hatchery_schedule_supply.csv` | hatchery: 2026 stream fish from the schedule | 09 |
| `section_schedule` | 2026-stocked section (1,022): scheduled hatchery, runs, schedule cluster | 10 |
| `clusters.csv` | schedule cluster (351) | 10 |
| `section_medoid_clusters` | 2026-stocked section: k-medoids cluster labels (the model uses 310 clusters) | 13 |
| `section_hierarchical_clusters` | 2026-stocked section: hierarchical cluster labels (comparison only) | 15 |
| **Road distances** | | |
| `hatchery_to_section_road_distance` | hatchery × section (13 × 1,045) | 11 |
| `section_to_section_road_distance` (parquet only) | ordered pair of 2026-stocked sections | 12 |
| `county_subdivisions` | county subdivision (2,567): the demand origins | 19 |
| `subdivision_to_section_road_distance` (parquet only) | subdivision × section | 19 |
| `cluster_hatchery_distance` | cluster method × cluster × hatchery: average road miles | 18 |
| **Angler demand** | | |
| `angler_survey/*.csv` (csv only) | answer option, named water or county: 13 tables from the 2023 PFBC trout angler survey. Columns: its README | 00 |
| `county_anglers.csv` | county: resident trout anglers | 06 |
| `subdivision_anglers` | county subdivision: resident anglers and angler-days | 06 |
| `survey_water_crosswalk.csv` | survey favorite water × PFBC river | 07 |
| `demand` | 2026-stocked section: angler-days (proximity and preference, kept separate) | 08 |
| **Model inputs** | | |
| `hatcheries` | state fish hatchery (13): location, 2026 stream supply | 20_transport_cost |
| `cost_matrix` | hatchery × 2026-stocked section: road miles and haul cost | 20_transport_cost |
| `baseline_flows` | hatchery → section flow in PFBC's 2026 plan | 20_transport_cost |
| `model_input` | 2026-stocked section: everything the optimization reads per section | 21_model_input |
| `parameters.csv` | parameter: values no source gives directly, with ranges and sources | by hand |
| **Geometry** | | |
| `pa_trout.gpkg` | feature, per layer, EPSG:4326: sections (lines), hatcheries (points), class_a, nat_repro, wilderness | 01, 02 |
| `trout_hatcheries.gpkg` | hatchery: an early placeholder; no script reads it | `notebooks/01_data_prep.ipynb` |

The model (`scripts/optimization.py`) reads only `model_input`, `hatcheries`, `cost_matrix`, `baseline_flows` and
`parameters.csv`.

## Credits
Data from the Pennsylvania Fish and Boat Commission (PFBC; fbweb.pa.gov ArcGIS services) and PASDA
(Pennsylvania Spatial Data Access, PAFishBoat map service). All modifications to PFBC data are described in
`docs/data_methods.md`.
