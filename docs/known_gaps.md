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
   spring 2024); the layer covers the 2024 stocking year. Our three years are similar (2.60M, 2.62M,
   2.61M), so this likely matters little.
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

## Gavin's stocked-streams layer vs our sections (checked 2026-09-27)
- His `travel_arcs` distances are built on `data/raw/pa_stocked_trout_streams.gpkg`: 1,064 rows, 1,059
  unique `GIS_Key`s, source and year not recorded. It matches none of our layers (2024: 1,036, 2025: 1,044,
  2026: 1,031 rows).
- 1,039 of its keys are among our 1,045 sections. 8 of our 1,022 candidate sections (stocked in 2026) are
  missing from it, so they would have no distance when his table is joined on `section_id` (Prompt 7).

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
  the density cap, the midpoint for the tighter sensitivity (`model_design.md` § Density bound).

## Tailwater sections (checked 2026-09-27: no flag; list assembled 2026-09-28)
- PFBC stocks "those few short tailwater sections" at their own rate (Operational Guidelines Table 45, pdf
  p. 80: 266/acre High access, 247 Good) instead of Table 18. A section qualifies if it is ≤ 2 mi long and
  directly below a major reservoir's cold-water outflow, with trout year-round. Longer tailwater reaches use the
  normal program rates (criterion 1). No stocked-section field says which sections are tailwaters: not
  `Description` (category labels only), `reg_name` or `program_name`.
- Two sections are treated as tailwaters: Youghiogheny 1327_1 (below the Youghiogheny River Lake dam; PFBC
  stocks it at 297 fish/acre) and Conneauttee Creek 2649_1 (below the Edinboro Lake dam; team knowledge,
  2026-09-28). Conneauttee's cap doesn't change: its access rate (323) is already above the tailwater rate
  (247), and at 665 fish/acre today it stays held at its 2026 count.
- The tailwater rate only raises a cap where the section's own rate is lower: rivers at widths 1S/1L/4 or Low
  access. At widths 2–3 the access rate (323–361) is already higher, so a missed narrow tailwater loses nothing.
- Other stocked sections just below dams (web search 2026-09-28, major tailwaters only; fish/acre = 2026
  stocking over the class-top area):

  | Section | Water (dam) | Length | Why it isn't treated as a Table 45 tailwater |
  |---|---|---|---|
  | 2968_11 | Raystown Branch Juniata (Raystown) | 0.90 mi | Short, but the only source (an angler forum) describes a mostly warmwater tailwater; stocked at 66/acre, under Table 18's 91 |
  | 2923_4 | Tionesta Creek (Tionesta) | 0.90 mi | Open year-round, but no source calls it a trout tailwater; stocked at 75/acre |
  | 2928_2 | East Branch Clarion (East Branch) | 1.17 mi | A cold bottom-release tailwater, but PFBC runs it as DHALO (176/acre, near DHALO's 190); its access rate (361) is higher anyway |
  | 2254_2 | Black Moshannon Creek (Black Moshannon) | 0.56 mi | Width 3: its access rate (361) is already higher |
  | 3351_11 | Kettle Creek (Alvin R. Bush) | 2.15 mi | Over 2 mi, though a PFBC biologist calls this exact reach a coldwater tailwater ([kettlecreek.org](http://www.kettlecreek.org/uploads/2/5/6/0/25607137/4fisheries_compa.pdf)); stocked at 99/acre |
  | 3072_6 | Tulpehocken Creek (Blue Marsh) | 2.03 mi | Over 2 mi; DHALO |
  | 1989_2, 6228_4, 2280_6, 1817_3, 2281_4, 2603_3, 2730_6 | N. Br. Little Conemaugh (Wilmore), Pohopoco (Beltzville; Class A), W. Br. Lackawaxen (Prompton), Mahoning (Mahoning Creek; [PFBC "Mahoning Dam Tailrace"](https://pfbc.pa.gov/images/fisheries/afm/2001/afmmdt.html/)), Dyberry (Jadwin, a dry dam), Woodcock ([PFBC "Tailwater Trout Fishery"](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/conservation/habitat/lake-plans/woodcock_creek.pdf)), Lehigh (F.E. Walter) | 2.5–9.9 mi | Over 2 mi |

- The Allegheny River below Kinzua Dam, a well-known tailwater, has no 2026 stocked section (only the
  Potter/McKean headwaters do). Fingerling stocking isn't in the adult layers.
- **Upgrade:** add Raystown Branch 2968_11 and Tionesta 2923_4 if a source shows a year-round cold-water trout
  fishery (each cap would rise from 1,954 to 5,712 fish at High access). Or get a PFBC list of tailwater
  sections from the Area Fisheries Managers.

## Natural Reproduction river miles shorter than the line (18 sections missed)
- Overlap uses PFBC's river miles only (assumption, `data_methods.md` § Wild-trout overlap). But about 191
  Natural Reproduction records have a line more than 1.5× their river-mile length, and their Limits text
  agrees with the line, not the river miles. Example: Little Yellow Creek's reach reads "Headwaters to Mouth"
  but carries river miles 7.85–12.9.
- So 18 stocked sections lie at least 0.5 mi along a same-water Natural Reproduction line but share no river
  miles with it, and aren't flagged (`nat_repro_missed_by_rm` in `logs/02_overlap_check.csv`). A geometry rule
  flagged them until 2026-09-27.
  - 17 are stocked in 2026 with 29,630 fish (1.1%). West Branch Briar Creek 209_2 is one of the 23 dropped
    sections, and Mauch Chunk Creek 2744_2 is a Class A overlap (capped at today's stocking anyway).
  - Biomass: 15 D, 1 C, 2 E. The simple impact score (natural reproduction or biomass B–D) still counts the 16
    C/D sections as wild-trout water; only Muddy Creek 2033_3 and 2033_4 (York, biomass E) drop out. The
    weighted score loses its +1 for natural reproduction on all 18.
  - Others: Mahoning Creek 181_3, Little Yellow Creek 6188_2, Sherman Creek 3306_2, Fishing Creek 275_2 and
    275_3, South Branch Middle Creek 2208_2, White Deer Creek 2175_6, White Deer Hole Creek 2192_2, Laurel
    Run 2086_2, Toms Creek 1818_2, Moose Creek 2253_2, Locust Creek 3117_3, North Branch Middle Creek 2216_2,
    Willow Creek 2887_3.
- Sensitivity "Natural reproduction by geometry too" (`scenarios_and_extensions.md`) flags them back.

## Wild trout species outside Class A (checked 2026-09-27: not published)
- Only the Class A layer names species (`Fishery` text). Natural Reproduction and Wilderness have no species
  field, so `environment.wild_brook_present` is NA (unknown) for 1,028 sections.
- The 17 Class A overlaps PFBC stocks are all brown trout fisheries, and Buffalo Creek 3190_2's Class A record
  has no species text. So "no stocked brook trout over wild brook trout" binds on no section with today's
  data, and the wild-brook term in the weighted impact score is zero everywhere.
- Possible fill: EcoSHEDS brook trout occupancy (`env_research.md` § 4); it's modelled, not observed.

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

## Angler numbers by county: license sales (checked 2026-09-27)
PFBC's *2024 Pennsylvania Annual Fishing License & Permit Sales by Agent County*
(`data/raw/pfbc_docs/2026-09-27/fishinglicensesalesbycounty2024.pdf`) is the only county-level count of anglers
we found. Proximity demand turns it into a county angler rate (`model_design.md` § Angler benefit). Its limits:
- **Store county, not home county.** Sales are counted where the license was sold. Some counties look low,
  probably because residents buy across the county line (Montour, Adams), and visitors' licenses land in
  destination counties (Pike, Wayne, Tioga, Crawford). We subtract non-resident and tourist licenses from the
  permit count; this overcorrects a little, since not every visitor buys a trout permit.
- **Online sales have no county.** 291,065 of 746,726 annual licenses (39%) and 164,051 of 490,514 annual trout
  and combo permits were sold online (172,027 with multi-year permits; 117,500 after subtracting online
  non-resident and tourist licenses). We split online resident permits by population (assumption); splitting
  them like store sales is a sensitivity. At the median, rural counties come out 1.9× the state's angler rate
  by population and 2.2× like store sales.
- **In-state travel can't be measured.** Anglers who buy their license where they fish inflate destination
  counties. The survey limits how much this can matter: 65–89% of each region's favorite-water mentions are in
  its home region (p85), and the median typical trip is 15 mi one way (p93).
- **Multi-year permits bought before 2024 are missing.** About 20,000 3-, 5- and 10-year trout and combo permits
  were sold in 2024 and are counted; holders who bought one in an earlier year aren't. Where they live only
  matters if they cluster in some counties. They also lower the statewide total: if 2024's sales are typical,
  3-year permits from 2022–23 and 5-year permits from 2020–23 add about 47,000 anglers (11% of 421,615; 10-year
  holders unknown). That scales every section's angler-days alike, so it only shifts the benefit curve's
  fish per angler-day, well inside the k sweep (0.5–2).
- **Permits cover more than stocked-stream fishing.** Lake and wild-trout anglers buy them too, and Erie
  County's combo permits are mostly Lake Erie steelhead anglers.
- **Fix:** a PFBC table of permit holders by home county or ZIP, e.g. through a Right-to-Know request (counts by
  county aren't personal data). `county_anglers` keeps every input as a column so that table can replace it
  (`scenarios_and_extensions.md` § Data upgrades).

## Survey favorite waters vs stocked sections (checked 2026-09-27; crosswalk built 2026-09-28)
- The survey names waters, not sections: 221 named waters, plus "Other" (30%) and "Do not know" (8%). The
  crosswalk (`scripts/07_survey_crosswalk.py`) places 63.1% of all mentions on 160 rivers stocked in 2026.
  The rest: 39 lakes, 2 waters not stocked in 2026, 5 with no PFBC section (e.g. the Clarion and Swatara main
  stems), and 16 names left for review (6.4% of mentions: e.g. Bush Kill, Mill Creek, Spring Creek, which
  match several rivers the regional table can't tell apart). Their share is spread like proximity demand
  until someone decides them in `logs/07_survey_crosswalk_review.csv`.
- A named river can be much bigger than its stocked part. The Youghiogheny's only stocked section is the
  1.1 mi dam tailwater 1327_1, so all of its survey preference lands there. Such waters get a per-mile flag
  (`model_design.md` § Angler benefit).
- Lakes aren't in the section set, and "other county or not sure" rows (e.g. Pine Creek, 2%) can't be placed.
  Their share is spread like proximity demand.
- 98 named waters show as "<0.5%" (counted as 0.25%) and 97 as 1%, so the survey resolves only the 26 waters at
  2% or more with any precision.

## Stocking schedule (checked 2026-09-28)
PFBC's schedule (`scripts/09_stocking_schedule.py`) gives the hatchery and truck meeting for every 2026 event.
What it lacks:
- **No fish counts**, only species marks. Per-event and per-hatchery fish come from splitting each section's
  2026 GIS count equally over its events (assumption, `data_methods.md` § Stocking schedule).
- **Planned, not actual:** "All stocking events are subject to change without notice."
- **2026 only.** No schedule is served for 2024–25, so hatchery assignments and runs describe one year.
- **Lakes:** 372 events on 127 lakes, and no lake counts in any source. Lake fish are NA and the schedule-based
  hatchery supply is stream fish only (streams are about 83% of adult trout, § Our stocking data vs PFBC's
  published totals). Lake events per hatchery are in `hatchery_schedule_supply.csv`.
- **Sections outside the 2026 layer:** the schedule stocks 8 sections that aren't in the 2026 GIS layer (102_5
  and 102_6 Muncy Creek, whose limits changed; 1326_2, 1767_3, 202_2, 209_2, 2287_2, 52_2) and 4 waters that
  match nothing (Brush Creek, Beaver; Little Fishing Creek; Yellow Creek, Indiana; North Deer Creek, Mercer:
  `logs/09_schedule_unmatched.csv`). Their 19 stream events have no 2026 count, so they're missing from the
  baseline and from hatchery supply.
- **Hatcheries:** 9 deliver to streams. Tionesta stocks 10 sections (15,257 fish, 0.6%) and 13 lake events,
  but has no production figure and isn't flagged TROUT in PFBC's hatchery layer (it's a supply node anyway
  since 2026-09-29, `../CLAUDE.md` Units of analysis). Linesville and Pleasant Mount stock no
  scheduled stream section (consistent with Pleasant Mount's figure being fingerlings and warmwater fish).
- **Runs vs trucks:** a run is one listed meeting. One truck may make several meetings in a day, or several
  trucks may share one; the schedule can't tell. 74 events give only a week and have no run.
- **Location QA:** 11 matched sections have the schedule's upper-limit point 0.8–4.2 km from our line although
  the limit text agrees (kept; `ul_dist_m`).
- **Changes over time (rechecked 2026-09-29):** a fresh pull a day later matched 2,731 of 2,734 records. Oil Creek
  1909_6's upper limit was reworded ("OIL CK STATE PARK HIKING TRAIL BRIDGE") and its two events gained a golden
  mark; one fall lake event moved from 09:00 to 10:30 (Briar Creek Lake); one fall lake event was added (Lake
  Took A While, Luzerne). None changes a stream section's hatchery or run (the reworded Oil Creek limit still
  matches 1909_6 by name, county and section number), so the processed tables stay on the 2026-09-28 pull;
  the 2026-09-29 raw pull is kept. The schedule is "subject to change", so rerun and compare before relying on
  late-season events.
