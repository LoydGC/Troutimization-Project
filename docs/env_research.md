# Environmental inputs for the stocking model: research notes

Web research done 2026-09-26 to decide what environmental data is worth collecting for a class project.
Claims about PFBC policy link to the source. Anything marked *unverified* wasn't confirmed. The Bear Creek
finding was checked against our saved trout.app page.

## 1. What harm can stocking do?

- **Competition and displacement.** Hatchery trout push wild trout off feeding spots, mostly in the short
  term ([Weber & Fausch 2003](https://www.noaa.gov/sites/default/files/legacy/document/2020/Oct/07354626295.pdf)).
- **Drawing anglers.** Stocking brings crowds, and they also catch wild fish. For Class A waters PFBC aims to
  "minimize the potential of over harvest of wild trout due to attraction of anglers through stocking"
  ([Operational Guidelines, 5th ed.](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/operationguidelinestroutmgt.pdf) §2.1.6).
- **Disease and parasites.** Gill lice on brook trout is a PFBC priority
  ([2020–24 Trout Plan](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/reports/troutplan2020.pdf), Issue 7).
  Whirling disease has been in PA since the 1950s, but outbreaks have only happened in hatcheries
  ([USGS](https://pubs.usgs.gov/publication/70171132)).
- **Genetic mixing (introgression).** Hatchery brook trout breed with wild brook trout. A PA study found
  only 5.6% of wild fish were mixed ([White et al. 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6183464/)).
- **Predation.** Minor for 11-inch put-and-take trout. PA evidence: *unverified*.

PFBC's own list is in the 2020–24 plan, Issue 34. Hatchery brook trout stocked over wild brook trout cause
"introgression…, increased angling mortality…, spread of diseases…, and displacement." PFBC's response was to
stop stocking brook trout in those watersheds and use rainbows instead. The
[2025–29 plan](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/troutplan2025.pdf)
adds sterile (triploid) trout (Obj. 9.5) and fish-health monitoring.

**For the model: species matters, not only fish count.** Stocking brook trout over wild brook trout is the
worst case.

## 2. Is a stream-area cap sensible?

Yes, but as a **policy/crowding bound, not an ecological carrying capacity.** Stocked adults are mostly
caught or dead within weeks, so they never reach a steady population. PFBC already allocates in
**trout per acre per year** (Operational Guidelines §2.2).

Each section's category comes from four factors:
- wild trout biomass class (A–E)
- width class: 1L >30 m, 1S 20–30 m, 2 = 10–20 m, 3 = 4–10 m, 4 <4 m
- recreational use potential: road access, parking, ownership, posting
- human population density: Metro ≥300/km², Urban ≥125, Suburban ≥40, Rural <40

Maximum rates (Table 18):

| Category | Max trout/acre/yr |
|---|---|
| High Yield (biomass C–E, high access, width 2–3) | 361 Metro / 323 other |
| Optimum Yield, good access, width 2–3 | 323 / 285 / 190 / 95 (Metro → Rural) |
| Biomass B, high access | 147 |
| Width 4 or low access | 57 |
| Large rivers (1S/1L) | 30–137 |

Other rules:
- at least 300 trout per stocking
- new sections must be ≥2 miles long and ≥75% open to the public
- the table values are maximums, and managers can go lower

The 2025–29 plan (Obj. 9.1) says these rates "need to be reviewed," which is a useful hook for the report.

## 3. PFBC policy on stocking over wild trout

- **Class A:** "with rare exceptions… no stocking." Since 2015, stocking a Class A section needs Commission
  approval. Exemptions last at most 5 years
  ([Jan 2026 meeting](https://www.pa.gov/agencies/fishandboat/newsroom/summary-165th-meeting-pfbc-jan2026)).
  There are two separate groups (Operational Guidelines Appendix A, pp. 118–119):
  - **PFBC's own continued stocking:** "13 stream sections that support strong Class A wild Brown Trout
    populations" were designated in 2015–2017 and stocking continued, because they're heavily fished, mostly
    in high-density areas. Our 13 biomass-A stocked sections very likely are these (not named in the
    guidelines).
  - **Exemptions for outside groups** (derbies, private stockings), under four criteria. Only criterion 4 bars
    waters with wild brook trout. The Jan 2026 meeting approved 13 such exemptions on 12 Class A sections
    (GoErie, 2026-01-31). None overlaps a PFBC stocked section, and one (Marvin Creek 01) is brook trout water.
  See `docs/known_gaps.md`.
- **Wilderness Trout Streams:** never stocked.
- **Removed sections** are replaced as close as possible, in the same watershed first. That is
  effectively "remove and stock nearby."
- **Other wild trout waters are stocked:** 611 of 5,701 Class B/C/D sections, 93% of them Class C/D.

**Bear Creek (Schuylkill) is not a Class A conflict.**
- Class A is Section 01, river miles 10.47–7.05, brook trout.
- The 2026 stocked sections 02 and 03 run from mile 7.05 to 2.21, downstream of Class A. They share only an
  endpoint.
- The Natural Reproduction listing covers miles 10.47–2.21, so it does overlap the stocked sections.

**Measure overlap as river-mile intervals on the same RFP_WaterID, or require >100 m of overlap.** A plain
intersect would flag shared endpoints.

## 4. Temperature

**Why it matters:** PFBC won't add waters that pass 24 °C before June 1. It removes stocked waters that
regularly pass 70 °F by June 1. In warm water, stocked fish die by early summer, which lowers the benefit too.

**Dataset:** EcoSHEDS Northeast Stream Temperature Model v1.4.0 (USGS, 2024).
- Downloadable: [predictions CSV, 128 MB](https://ecosheds.s3.amazonaws.com/northeast-temp-model/output/sheds-temp-model-v1.4.0.csv)
  and [catchment shapefiles](https://ecosheds.github.io/necd/catchment-delineation.html).
- Metrics: mean summer temperatures, max 30-day mean, days above 18/20/22 °C, and warming scenarios.
- It is keyed by `featureid`, not NHDPlus COMID, so it needs a spatial join.
- It covers drainage areas under 200 km² only, so large rivers are NA.
- Effort: about a day.

**EBTJV brook trout status:** access is by request form, and it can't be reposted.
[EcoSHEDS brook trout occupancy](https://ecosheds.github.io/northeast-bto-model/downloads.html) is a free
alternative.

## 5. Feasibility

| Input | Value | Where | Effort |
|---|---|---|---|
| Class A / Wilderness overlap | High | [PASDA PAFishBoat](https://mapservices.pasda.psu.edu/server/rest/services/pasda/PAFishBoat/MapServer) layers 9, 31 | 2–4 h |
| Wild brook trout flag | High | Class A layer `Fishery` field (messy text) | 2 h |
| Natural Reproduction overlap | Med | PASDA layer 25 (no species) | 1–2 h |
| Width → area | High | [Chaplin 2005](https://pubs.usgs.gov/sir/2005/5147/SIR2005-5147.pdf) bankfull width vs drainage area | 2–4 h |
| Historical density | High | our baseline counts | 1 h |
| Modelled temperature | Med–High | EcoSHEDS | 6–12 h |
| EBTJV | Med | request form | days' wait + 4 h |
| DEP Ch. 93 HQ/EV | Low | [PASDA](https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=1098); often based on insects, not trout | 2–3 h |
| Numeric Class A biomass | Med | only in biologist reports | skip |

## 6. Suggested formulation

**Variables:** `x_i` = trout per year to section `i`, `y_i` ∈ {0,1} = section is stocked.
`A_i` = estimated area in acres, `h_i` = historical count.

**Constraints:**
- `x_i = 0` for Wilderness and for Class A sections PFBC no longer stocks (Buffalo Creek 3190_2). Class A
  sections PFBC stocks in 2026 are capped at `h_i` (team decision 2026-09-27, `docs/modeling_notes.md`);
  the normal river cap is a scenario.
- No stocked brook trout where wild brook trout are present.
- `300·y_i ≤ x_i ≤ r_max(category_i)·A_i·y_i`. Simple version: 361/acre, or 57/acre if width < 4 m.
  (Superseded by the river cap, `docs/modeling_notes.md` "Density bound".)
- Stability (optional): `x_i ≥ (1−δ)·h_i`. The survey found 43% opposed dropping low-use waters.

**Penalty:** `Env = Σ w_i·x_i`, where `w_i` = 1 for natural reproduction, +2 for wild brook trout present,
+1 if thermally marginal (e.g. max 30-day mean ≥ 21 °C). Report it as a separate objective and trace the
trade-off with ε-constraints.

**Survey support:** 58% of trout anglers support moving stocking off quality wild trout waters to nearby
spots, and 16% oppose. That supports making the penalty large enough that the model shifts fish to nearby
non-wild sections.
