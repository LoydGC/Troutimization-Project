# 2023 PA Trout Angler Survey: extracted tables

Source: Responsive Management, *Trout Fishing in Pennsylvania* (2023 PFBC trout angler survey),
`data/references/troutanglersurveyreport-2023.pdf`. Page numbers are PDF page numbers.
Regenerate with `python scripts/extract_angler_survey_2023.py` (pdfplumber).

All respondents are **stocked trout anglers**. All values are percentages unless `row_type` says otherwise.

| File | PDF pages | Contents |
|---|---|---|
| p76-77_preferred_waters_overall.csv | 76–77 | Waters named among an angler's top three for stocked trout, statewide, ranked |
| p78-83_preferred_waters_by_region.csv | 78–83 | Same question broken out by the angler's home region + overall |
| p84_preferred_water_county_overall.csv | 84 | County where the preferred water is located, statewide, ranked |
| p85_preferred_water_county_by_region.csv | 85 | Same, by home region |
| p93_travel_distance_typical_trip_by_region.csv | 93 | One-way miles on an average stocked trout trip |
| p94_travel_distance_farthest_by_region.csv | 94 | Farthest one-way miles traveled for stocked trout |
| p115_days_fished_stocked_2022_by_region.csv | 115 | Days fished for stocked trout in 2022 |
| p127_stocked_trout_harvest_per_year_by_region.csv | 127 | Stocked trout harvested per year |
| p174_support_removing_low_use_waters_by_region.csv | 174 | Support/oppose moving stocking from low-use waters to higher-use waters |

## Column notes
- Region columns (`northwest` … `nonresident`) are the angler's **home** region, not where they fish.
- `*` in the report (less than 0.5%) is stored as NA with `lt_0_5_pct = True`.
- Preferred-water and county tables are multi-response (up to three waters each), so columns sum to more than 100.
- `name_base` / `county_qualifier` split names like "Pine Creek (Lycoming or Tioga County)". Report spellings are kept as-is (e.g. "Schuykill").
- Distribution tables: `row_type` = `n`, `percent`, `mean`, or `median`. `statewide_all` includes non-residents;
  `statewide_instate` is residents only (reported only for travel distance). Statewide values come from each page's bar
  chart and were checked against the rendered page; regional values come from the page's table.

## Validation (see validation_log.txt)
- Distribution columns sum to 99–102% (rounding).
- The "overall" column of the regional water table matches the statewide table for every water; "West Branch Hicks Run"
  appears only in the regional table (overall 0%).
- County overall values match between pages 84 and 85.

## Caveats
- Page 174 is an opinion question about removing low-use waters; it does not list which waters are low-use.
- Survey water names are not PFBC section IDs. They need a crosswalk to `WtrName` + county before joining to stocking data.
