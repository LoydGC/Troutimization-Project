# Data

Raw data is git-ignored; processed data is committed. Don't keep a separate source list here:
- `data/raw/manifest.csv` – every download, with URL, retrieval timestamp and record count (enough to re-fetch)
- `docs/source_inventory.md` – verified endpoints, fields and join keys (to be written in Prompt 1)
- `docs/data_dictionary.md` – every column in `data/processed/`

## Processed outputs
All keyed by `section_id = f"{RFP_WaterID}_{SecNum}"`.

| File | One row per | Contents |
|---|---|---|
| `sections.parquet` + `.csv` | stocked stream section (union of 2024–26 layers) | ids, location, allocation category, stocking counts by species and year, wild-trout overlap. No geometry. |
| `stocking_section_year.parquet` | section x year x species | stocked count (the baseline) |
| `pa_trout.gpkg` | feature, per layer | geometry in EPSG:4326: sections (lines), hatcheries (points), class_a, nat_repro, wilderness |

Later phases add columns to `sections` or separate tables joined on `section_id` (demand, cost_matrix,
environment). Lakes are added later as rows with `water_type = "lake"`.

## Credits
Data from the Pennsylvania Fish and Boat Commission (PFBC; fbweb.pa.gov ArcGIS services) and PASDA
(Pennsylvania Spatial Data Access, PAFishBoat map service). All modifications to PFBC data are described in
`docs/methods.md`.
