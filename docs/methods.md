# Methods: changes to source data and assumptions

Data from the Pennsylvania Fish and Boat Commission (PFBC), via fbweb.pa.gov and PASDA. Anything used
unaltered is credited to PFBC. Every change is listed here. Raw downloads are kept untouched in
`data/raw/` (see `manifest.csv`).

## Sections pull (scripts 01–02, 2026-09-26)

**Download.** We downloaded the stocked-section layers for 2024, 2025 and 2026 from fbweb, and Class A (#9),
Natural Reproduction (#25) and Wilderness (#31) from PASDA's PAFishBoat MapServer. Each was paged by
object id, and the downloaded count matched the server count for every layer.

**Stocking counts**
- **Missing counts.** Null brook/brown counts (10–20 per year) are set to 0. PFBC's
  `TotalAdultStocked_minusBrood` equals brook + brown + rainbow only when they are 0.
- **Duplicate rows.** Each year, 5–9 sections appear as two rows: pieces split by regulation (e.g. a DHALO
  stretch) or by county. Both rows carry the full section total, with identical counts. We count them
  once, union the geometry, take the widest river-mile limits and join the text fields. Summing the raw
  layer would overcount by about 0.7%; for example, 2026 rainbow is 1,818,685 raw and 1,800,505 after the
  merge.
- **County names.** Converted to title case (the layers mix "Cambria" and "CAMBRIA").
- **No other changes.** Counts are otherwise as published: no smoothing, imputation or corrections.

**Section attributes**
- **Which year's attributes.** They come from the latest year a section appears in.
- **Length.** Computed from the line in EPSG:26918. PFBC's `Length_MI_` field differs from the line's length by more than 0.1 mi for most rows, so we don't use it.
  River-mile length is kept separately; GIS length runs about 10% longer at the median.
- **Midpoint.** The point halfway along the line.
- **Sherman Creek 3306_2.** Its river-mile limits are reversed in PFBC's data. We flag it
  (`rm_limits_reversed`) and don't change it.

**Allocation category**

`AllocationCode` is decoded as [biomass class A–E][recreational use potential H/G/L]
[population density M/U/S/R][width class 1S/1L/2/3/4]. We checked this against the category definitions
in the Operational Guidelines (Tables 15, 16 and 18). All 1,045 codes match the pattern.

`max_trout_per_acre` is looked up from Table 18.
- Table 18 has no biomass-A rows for widths 2–4, so 11 of the 13 biomass-A (Class A) sections have NA with
  a reason.
- The other two are large rivers (1S/1L), where the rate doesn't depend on biomass.
- The 13 appear to be the Commission-exempt Class A wild brown trout sections.

**Wild-trout overlap** (CLAUDE.md rule 8)
- **Primary method:** river miles shared with wild-trout records on the same `RFP_WaterID`. It counts only
  above 100 m, so sections that only touch share an endpoint and aren't flagged.
- **Cross-check:** the length of the section within 30 m of wild-trout lines on the same water.
  Sections where the two methods disagree are in `logs/02_overlap_check.csv`.
- **Class A and Wilderness** (exclusions) use river miles only. Geometry is imprecise at section
  boundaries: it puts 0.47 mi of Bear Creek 3197_2 in Class A, when PFBC's listing shows the two only touch.
- **Natural Reproduction** (a soft penalty) is also flagged when the geometric overlap is ≥ 0.5 mi.
  - About 191 of its records have a line more than 1.5× their river-mile length. Their Limits text agrees
    with the line (e.g. "Headwaters to Mouth"), not with the river miles.
  - For example, Little Yellow Creek's reach is listed as "Headwaters to Mouth" but carries river miles
    7.85–12.9.
  - This rule adds 18 sections, for 549 in total.
- **Class A species flags** come from keyword matches on the Class A `Fishery` text: brook, brown,
  rainbow.

**Co-op nursery list** (`scripts/03_coop_stockings.py`, 2026-09-27)
- **Source:** PFBC's co-op nursery page spreadsheet, used as published. It has no counts or years, and it
  was identical to a Feb 2025 copy.
- **Name matching.** Names are lowercased with punctuation removed.
  - A listing flags a section only on an exact stream + county + section-number match to our sections (349
    listings, 292 sections).
  - Other listings are located at stream level: on a PFBC stream, or in the Natural Reproduction / Class A
    layers by name + county. Those are used only for distances.
- **Nursery locations** come from Gavin's `Coop_nurseries.geojson`, matched by nursery name, then sponsor
  name, then a unique name-contains match (e.g. "Kenny Stewart Memorial Nursery" → "Kenny Stewart"). That
  locates 123 of 133 nurseries.
- **Distances** are straight lines from the nursery to the nearest point of the matched water.
- **Manual review:** `logs/03_coop_review.csv` lists the following. Suggested names are same-county names
  with a string similarity of at least 0.85; they are hints only.
  - unmatched waters
  - unlocated nurseries
  - listings on sections PFBC no longer stocks
  - listings on Class A sections

**Map layers.** The wild-trout context layers in `pa_trout.gpkg` are simplified to a 5 m tolerance to keep
the file small. All overlaps are computed from the full-resolution layers first.

**Validation (it's asserted in the script).** Bear Creek (Schuylkill), 2026:
- 3197_2 = 150 brown + 850 rainbow, and 3197_3 = 900 rainbow, for a total of 150 brown + 1,750 rainbow.
- Neither section is flagged Class A: Class A is Section 01, river miles 10.47–7.05, and it only touches
  them.
- Both are flagged natural reproduction (reach 10.47–2.21).
