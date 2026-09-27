# Known gaps

## Our stocking data vs PFBC's published totals
Source: PFBC 2024 Annual Report, "Trout Stocked by PFBC", fiscal year July 2023–June 2024
(`data/references/2024annualreport.pdf`).

The report's **4,699,507 trout stocked** = 3,143,145 adults + 1,556,362 fingerlings. A further 1,135,658
fingerlings went to co-op nurseries, making 5,835,165 including co-ops.

Our stream layers only cover **adult trout in stream sections**. Stocking year 2024 is 2,599,733 fish,
about 83% of the report's adults:

| Species | Report (FY23–24 adults) | Our 2024 stream sections | Share |
|---|---|---|---|
| Brook | 184,374 | 74,675 | 41% |
| Brown | 894,027 | 664,285 | 74% |
| Rainbow | 2,049,362 | 1,785,740 | 87% |
| Golden rainbow | 15,382 | 11,723 | 76% |
| Brood (listed separately in our layer) | — | 63,310 | |
| **Adults** | **3,143,145** | **2,599,733** | **83%** |

**Why they differ:**
1. **Fingerlings (1.56M) are a different program.** They're small fish, mostly for lakes and larger
   waters, and they aren't in the adult stocking layers (all rows are `SpeciesLifestage = ADULT`).
   They're out of scope; CLAUDE.md treats fingerlings and co-ops as fixed.
2. **Lakes: most of the ~543k adult gap (likely).**
   - About 131 stocked lakes get adult trout, but no PFBC GIS service has lake counts. Checked
     2026-09-26: the 2024, 2025 and 2026 stocked services each hold one stream-section layer, and
     `PFBC_Stocked_Trout_Waters` lakes have no counts.
   - Brook trout have the lowest stream share (41%), which fits heavy lake or other non-stream use.
     *Unverified.*
3. **The years are defined differently.** The report covers fiscal year Jul 2023–Jun 2024 (fall 2023 plus
   spring 2024); the layer covers the 2024 stocking year. Our three years are similar (2.60M, 2.63M,
   2.62M), so this likely matters little.
4. **Brood fish** are a separate field in our layer. The report probably counts them within each
   species. *Unverified.*

**Implications for the model:**
- The decision covers about 83% of PFBC's adult trout: the stream allocation.
- Hatchery supply must be scaled to the **stream** total (baseline stream fish × each hatchery's share),
  not the report's 3.14M. Otherwise the supply constraints are about 20% too loose.
- Lakes stay out of the decision until we find counts. Options:
  - a PFBC records request
  - the stocking schedule pages (event lists)
  - treating lakes as fixed demand that uses up hatchery capacity

## Co-op nurseries as supply nodes
The team decided (2026-09-26) that co-op nurseries are supply points in the model. Still unknown:
- **How many adult trout each co-op supplies.** The FY23–24 annual report gives only the input: 1,135,658
  fingerlings distributed to co-ops (brook 100,725; brown 281,214; rainbow 742,999; golden 10,720), across
  ~160 co-ops.
- **Co-op stocking is not in our baseline.** PFBC's Cooperative Nursery Statement of Policy (Jan 2017,
  `data/references/statement_policy.pdf`) §III.12 says "Fish stocked by cooperative nurseries will not be
  included as part of the PFBC allocation of stocked trout to a water."
- **Where co-op fish go.** Sponsors (the clubs) choose the waters, dates and numbers. PFBC reviews the list
  but doesn't allocate it (§IV.9–10, §VII.2–3). Co-op waters need not be stocked trout waters, so many
  destinations may be outside our 1,045 sections.
- **Who pays for trucking.** PFBC trucks deliver fingerlings *to* the nurseries (§V). The clubs stock
  from the nursery to the water.
- **Co-op destinations are public, but counts aren't.** PFBC's co-op page publishes the stocking list
  (which waters each nursery stocks, and which species), which is now in `data/processed/coop_stockings`.
  Numbers per water and per year are reported to the Cooperative Nursery Unit by July 15 (§IV.12) but not
  published, so they would need a request. They're needed only for the "state coordinates more" extension.
- **Matching gaps:**
  - 10 of 133 nurseries have no location in Gavin's layer (names in `logs/03_coop_stockings.log`).
  - 189 listings didn't match a stream or pond geometry: 57 ponds or lakes, and 132 streams, often
    non-stocked tributaries or spelling differences.
  - They don't affect the section flags, which need an exact PFBC section match.
- **The co-op list may be out of date.**
  - 10 listed sections were dropped by PFBC by 2026, 8 of them wild-trout waters.
  - 4 listed sections overlap Class A.
  - The web file was unchanged from Feb 2025 to Sep 2026.
- **Manual review file:** `logs/03_coop_review.csv`. It covers everything above, with suggested names for
  near-miss spellings; fill in `review_note`.
- **Locations.** Gavin's `data/raw/Coop_nurseries.geojson`.

## Duplicate section rows: merge overstated length (fix scheduled in Prompt 4, step 0)
- In each year's layer, 5–9 sections appear twice: always one "Stocked Trout Water" row plus one
  "Commonwealth Inland Waters" row, with the same counts. Their lines and limits don't describe the same
  stretch.
- `02_build_sections.py` currently unions the two lines, which overstates length and geometry. For example,
  Hinckston Run 2079_2's merged line is 7.4 mi against 1.9 river miles, and Loyalsock Creek 117_3's is
  11.4 mi against 8.6.
- The fix: keep the "Stocked Trout Water" row, and flag sections where PFBC's length and the river-mile
  length disagree by more than 25%.
