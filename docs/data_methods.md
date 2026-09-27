# Data methods: changes to PFBC data and data-handling assumptions

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
  once. The pair is always one "Stocked Trout Water" row and one "Commonwealth Inland Waters" row, and their
  lines don't describe the same stretch, so we keep the "Stocked Trout Water" row's limits, length and line
  (decision 2026-09-27; an earlier build unioned the lines and overstated length). County and regulation
  text are joined across the two rows, and special regulations count if either row has them. Summing the raw
  layer would overcount by about 0.7%; for example, 2026 rainbow is 1,818,685 raw and 1,800,505 after the
  merge.
- **Placeholder text.** PFBC's literal `<Null>` in `Wtr_Prog_Name` is read as missing.
- **County names.** Converted to title case (the layers mix "Cambria" and "CAMBRIA").
- **No other changes.** Counts are otherwise as published: no smoothing, imputation or corrections.

**Section attributes**
- **Which year's attributes.** They come from the latest year a section appears in.
- **Length.** `length_mi` (used for area) is one of PFBC's two lengths, and `length_source` says which
  (decision 2026-09-27: PFBC numbers only).
  - `pfbc_length_mi` = PFBC's `Length_MI_`. It's the default and matches PFBC river miles (median ratio 1.02).
  - `rm_length_mi` = upper minus lower river mile, both PFBC fields.
  - We don't use our own measurement of the line. It runs ~8% longer than `Length_MI_` at the median, more
    so on lines with more vertices per mile, which suggests PFBC measured an earlier, less detailed version
    of the line.
- **Length check.** `length_check_flag` marks the 57 sections where the two PFBC lengths differ by more than
  25%. PFBC allocates fish as rate × acres, so a section's stocking shows which length PFBC used:
  - Among the unflagged sections, fish per (Table 18 rate × mile) gives a typical value and a normal range
    (10th–90th percentile) per width class. Working within a width class avoids needing a width.
  - A flagged section's mean fish per year then give an expected length range. If only river miles fall in
    it, `length_mi` uses river miles (9 sections). If only `Length_MI_` does (14), both do (21), or neither
    does (12, plus 1 with no rate), `Length_MI_` stays.
  - `length_check_result` records the outcome; the details are in `logs/02_length_check.csv`. This only
    picks between PFBC's two lengths: the stocking baseline itself is never changed.
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
- The 13 are stocked Class A sections (their Class A key is their own section id). Which exemption covers
  them: `docs/known_gaps.md` § Class A exemptions.

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
