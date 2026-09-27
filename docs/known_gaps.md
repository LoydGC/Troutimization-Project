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

## Co-op nurseries (fixed background)
The team first planned (2026-09-26) to make co-op nurseries supply points, then decided (2026-09-27) to keep
them as fixed background, with a "state coordinates more" extension (`docs/model_design.md`). Still unknown
for that extension:
- **Statewide total:** co-ops add about 1.1 million trout a year to public waters (GoErie, 2026-01-31, reporting the Jan 30 Commission meeting).
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

## Duplicate section rows (fixed 2026-09-27)
- In each year's layer, 5–9 sections appear twice: always one "Stocked Trout Water" row plus one
  "Commonwealth Inland Waters" row, with the same counts. Their lines and limits don't describe the same
  stretch.
- The first build unioned the two lines, which overstated length (Hinckston Run 2079_2: 7.4 mi of line
  against 1.9 river miles). `02_build_sections.py` now keeps the "Stocked Trout Water" row's limits, length
  and line (Hinckston Run: 2.2 mi of line, PFBC length 1.97 mi). The "Stocked Trout Water" row also carries
  the Best Fishing Waters flag for Brodhead Creek 2662_2 and Neshannock Creek 329_3, which the old merge
  missed.

## PFBC length vs river miles (`length_check_flag`, 57 sections)
- PFBC's `Length_MI_` (used for area) agrees with its own river-mile limits for most sections (median
  ratio 1.02). 57 sections differ by more than 25%: 30 longer, 26 shorter, and Muncy Creek 102_6, whose
  river-mile limits are equal (0 mi).
- The two are separate PFBC values (a measured line length vs. two recorded river-mile positions), so either
  can be the wrong one. Spot checks go both ways:
  - River miles wrong: Shenango River 322_3 (3.5 mi vs 33.8 river miles) and Lackawaxen River 2271_3 have a
    lower river mile of 0 (the mouth), but their lower limit text isn't the mouth.
  - Line wrong: Brodhead Creek 2662_2's line is 6.9 mi, but its river miles (1.6) and its other row
    (2.2 river miles, 1.8 mi PFBC length) both say about 2 mi.
- Resolved with the stocking check (see `docs/data_methods.md`): the fish confirm `Length_MI_` for 14 sections
  (including Shenango 322_3 and Lackawaxen 2271_3), and switch 9 to river miles (e.g. Locust Creek 3117_2:
  5.6 instead of 7.8 mi). 21 are within normal stocking variation either way, and 12 fit neither (including
  Brodhead 2662_2); those keep `Length_MI_` and stay flagged, so sensitivity runs can drop them. Together
  the flagged sections carry about 4% of the fish. `logs/02_length_check.csv` has the details.

## Precise stream width (searched 2026-09-27: none published)
- No PFBC layer publishes a measured width or surface acres per section: not the stocked-section layers,
  `Fisheries_AllSections` (all flowing-water sections, length only), or PASDA's Class A, Natural
  Reproduction and Wilderness layers. Biologist reports give survey-site data for some streams only, not a
  bulk per-section width.
- So area uses the PFBC width class from AllocationCode (Operational Guidelines Table 14): the class top for
  the river cap, the midpoint for the tighter sensitivity (`model_design.md` § Density bound).

## Class A exemptions: which stocked sections are exempt
- 17 stocked sections overlap Class A (13 coded biomass A); PFBC stocks all of them in 2026. Stocking Class A
  needs Commission approval.
- **The 13 biomass-A sections: very likely documented.** Operational Guidelines Appendix A (p. 118) says 13
  sections with strong Class A wild brown trout were designated in 2015–2017 and "stocking was continued";
  all are "heavily fished waters, most located in high-density human population centers". Ours are all wild
  brown and 8 of 13 are Metro/Urban/Suburban. The guidelines don't list them by name, so this is a strong
  match, not proof.
- **The other 4 (Mauch Chunk 2744_2, West Branch Hicks Run 4363_3, Freeman Run 3546_4, Penns Creek 2207_6):
  basis unknown.** They aren't coded biomass A, and two only partly overlap Class A.
- **The Jan 2026 batch is a different mechanism** (GoErie, 2026-01-31, reporting the Jan 30 Commission
  meeting; saved locally in `data/references/`): 13 exemptions on 12 Class A sections for outside groups'
  derbies and private stockings, 8 renewals and 5 new, each for up to 5 years. None of the 12 overlaps a PFBC
  stocked section, though some sit just upstream (Penns Creek 01 ends where our 2207_2 starts; Monocacy,
  Yellow Creek and Marvin Creek likewise). One (Marvin Creek 01, McKean) is wild *brook* trout water, which is allowed because only
  exemption criterion 4 bars brook trout waters.
- An earlier note here called the "13 = 13" match a coincidence; that was wrong. The model rule doesn't
  change: Class A sections PFBC stocks are capped at today's stocking, and Buffalo Creek 3190_2 (Class A since
  Jan 2026, not stocked in 2026) is excluded.
- Same meeting: Riggles Gap Run (Blair; our 2710_2, stocked 2024 only) and Little Mill Creek (Lycoming)
  were added to the wild trout list, and Blue Hole Creek 02 (Somerset; our 3656_2) was removed from
  stocking for cadmium and lead.
