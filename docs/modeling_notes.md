# Modeling notes (to return to)

Decisions and ideas from planning, 2026-09-26. Environmental background and citations are in
`docs/env_research.md`. The data pipeline plan is in `PROMPTS.md`.

## Framing: formula vs optimization
- **PFBC allocates by formula, not optimization.**
  - Each section gets a category from its own traits: wild biomass class, recreational use potential
    (access, parking, ownership), human population density, and width.
  - The category sets the allocation rate (trout/acre/yr, Operational Guidelines Table 18, "Summary of
    allocation and distribution options"), which is also the category's ceiling ("will not exceed").
  - Check (2026-09-27): backing each section's width out of its stocking (fish ÷ its Table 18 rate ÷
    length) lands in the middle of its width class (class 3: median 6.2 m of 4–10; class 2: 12.4 of
    10–20; 1S: 24.8 of 20–30). So PFBC stocks most sections at about rate × measured acres: the table is
    the formula for what they put, not a loose maximum.
- **What the formula can't see:**
  - **Trade-offs between waters.** Supply is fixed, but each section is judged alone. Nothing asks where
    the marginal fish does the most good.
  - **Trucking.** Hatchery distance plays no part.
  - **Where anglers go.** Demand is only 4 population bands plus access. The survey's named waters and
    how far anglers travel (p85, p93) aren't used.
  - **Wild trout beyond one letter.** The code carries the biomass class, but not natural reproduction
    or wild brook presence.
- **PFBC's own goals are per-section targets**, e.g. High Yield:
  - ≥ 800 angler-hours/acre in spring
  - one angler trip per trout stocked
  - more fall fish where possible

  They make good yardsticks, but we have no creel data to measure them directly. "One trip per trout"
  is the idea behind diminishing returns: a fish only counts if an angler shows up for it. Our demand
  estimate stands in for angler use.
- **What we deliver: swap the goals and compare.**
  1. **Scorecard.** Score any plan on the same metrics: angler benefit, transport cost, wild-trout
     impact, and optionally fairness (e.g. share of people within X miles of stocked water). PFBC's
     actual 2026 plan is one row.
  2. **Trade-off curves.** Show where PFBC's plan sits relative to them.
     - Inside the curve: the same fish could do more for anglers at the same cost and impact.
     - On the curve: the formula is close to efficient. That's a legitimate finding too.
  3. **Goal-swap scenarios.** See "Scenarios" below. Report the sections that gain or lose fish in
     every scenario (robust changes) separately from those that move only under some goals.
- **Keep PFBC's physical rules as constraints, not its preferences.** The exclusions and a per-acre
  crowding cap keep plans realistic. The cap drops the parts of PFBC's formula that encode demand (see
  "Density bound"); a "PFBC formula as cap" scenario puts them back.
- **One-line pitch:** "PFBC allocates by formula. We make the goals explicit and ask what the formula
  leaves on the table, and what it costs to favour anglers, the budget, or wild trout."
- **Caveat:** if our demand measure ends up close to population density, the model may just rebuild
  PFBC's formula. That's a result in itself ("the rules are close to demand-optimal"). The survey
  preferences and travel distances are what add new information.

## Model shape
- **Decision:** `x[h,s]` = adult trout per year from PFBC hatchery `h` to destination `s`. Add a binary
  `y[s]` (section stocked or not) if we use the minimum-stocking rule.
- **Species** stay out of the transport part. Each section keeps its historical species mix (shares from
  2024–26), except that brook trout are never stocked over wild brook trout. A per-species model is an upgrade.
- **Three objectives, kept separate:** angler benefit (max), transport cost (min), wild-trout impact (min).
  Other docs call the third one the "environmental penalty". It is its own objective, never subtracted
  from benefit.
- **Solve method:** ε-constraint. Maximize benefit subject to cost ≤ C and impact ≤ E, then sweep C and E to
  trace trade-off curves. This is easier to explain than arbitrary weights. Alternatives: Gurobi's built-in
  multi-objective (`setObjectiveN`, with priorities or weights) or a weighted-sum sweep.
- **Baseline:** the historical allocation (2024–26 PFBC stocked-section layers), evaluated on the same three
  objectives, is the point we compare against. 1,045 sections (1,007 stocked all three years), ~2.6M stream
  fish/yr. 2026: brook 68,305; brown 659,290; rainbow 1,800,505; golden 15,123; brood 63,245. No layer
  reaches 2022, the survey year.

## Constraints
- **Hatchery supply:** `Σ_s x[h,s] ≤ supply_h`. `supply_h` = the baseline statewide total × hatchery h's share
  of trout production in pounds (`data/raw/pa_hatchery_production.csv`). Exclude Pleasant Mount (its figure
  is a fish count that likely includes warmwater species).
- **Co-op nurseries are fixed background** (team decision 2026-09-27), not supply nodes. See "Co-op
  nurseries" below.
- **Total fish:** fixed at the baseline total (same fish, better placement), or relaxed as a scenario.
- **Density bound ("river cap", decision 2026-09-27):**
  `x_s ≤ cap_s = max(river_rate_s × length_mi_s × top_width_s, 300)`.
  - **Why not Table 18 directly.** Table 18 is PFBC's allocation formula, and two of its four inputs, use
    potential and population density, are PFBC's proxies for angler demand. Our benefit objective models
    demand, so a formula cap would lock in PFBC's preferences (a rural section could never pass 95/acre).
    The cap should describe the river, not PFBC's preferences.
  - **River rate** = the highest Table 18 rate over use and population for the section's biomass + width:

    | Biomass | Width 4 | 3 | 2 | 1S | 1L |
    |---|---|---|---|---|---|
    | B | 57 | 323 | 323 | 137 | 91 |
    | C, D, E | 57 | 361 | 361 | 137 | 91 |

    Biomass still has an effect: B is ~10% lower at widths 2–3. We do not assume "no biomass reduction".
  - **Width = top of the class** (4, 10, 20, 30 m; 60 m for open-ended 1L, an assumption). It's the most
    PFBC's rules allow on a stream of that class, so the cap doesn't bind just because our width guess is
    off. The class midpoints (3, 7, 15, 25, 40 m) are the tighter sensitivity.
  - **Minimum 300** fish, so any section can take one load (`300·y_s ≤ x_s`).
  - **Fit to the baseline.** River cap statewide ≈ 2.5× the baseline at midpoints, more at class tops.
    Stocking exceeds the river cap × class top in only 7 sections: four width-4 streams at exactly 300
    fish (fixed by the minimum), Conneauttee Creek 2649_1 (a 0.19 mi section), Black Moshannon Creek
    2254_2 (4% over) and Youghiogheny River 1327_1. Those last 3 are capped at today's stocking.
  - **Youghiogheny 1327_1** (EHS1L, dam outflow to Casselman River, open year-round): PFBC stocks 7,900
    fish on 1.1 mi, 3.3× the river cap at 60 m. Table 18 would need a ~250 m wide river. It's a special
    tailwater fishery that PFBC deliberately stocks above formula, so today's stocking is its cap.
  - **Class A** (decision 2026-09-27): the 17 Class A-overlap sections PFBC stocks in 2026 are capped at
    today's stocking (keep or cut, never add). They are the 13 biomass-A sections plus Mauch Chunk Creek
    2744_2, West Branch Hicks Run 4363_3, Freeman Run 3546_4 and Penns Creek 2207_6 (two of these only
    partly overlap; same rule). Stocking Class A needs Commission approval. The 13 biomass-A sections are very
    likely the guidelines' 13 continued-stocking Class A sections; the other 4 have no documented basis (see
    Exclusions).
    With the river cap the 13 biomass-A sections alone could take 2.5× today (85k vs 34.5k fish; up to
    5.4× on Yellow Creek 59_4), mostly near Allentown/Bethlehem in an "anglers first" run.
    **Scenario "Class A allowed to grow":** the river cap instead. Table 18 has no biomass-A rate at widths
    2–3 (11 sections), so they use B's 323 (assumption: A has more wild biomass than B, and rates fall as
    wild biomass rises).
  - The exact Table 18 rate stays in `max_trout_per_acre` for the baseline and the "PFBC formula as
    cap" scenario. Width class comes from the code; `Description` ("OPTIMUM YIELD 2 SUBURBAN") is only a
    label, and its "2" is not a width class.
  - Call it a policy/crowding bound, not ecological carrying capacity.
- **Candidate sections** (decision 2026-09-27): the 1,022 sections PFBC stocks in 2026. `x_s = 0` for the
  23 stocked in 2024–25 only (~37,500 fish/yr). PFBC dropped them for reasons we mostly can't see; 18 are
  natural-reproduction waters, and Blue Hole Creek 3656_2 was removed for cadmium and lead (GoErie, 2026-01-31, reporting the Jan 30 Commission meeting).
  **Scenario "dropped sections back":** allow them again, except Blue Hole Creek (health) and Buffalo Creek
  3190_2 (Class A).
- **Exclusions:** `x_s = 0` for Wilderness (no stocked section overlaps it) and Buffalo Creek 3190_2, which
  became Class A in Jan 2026 and wasn't stocked in 2026. The other 17 Class A overlaps are capped at
  today's stocking (see "Density bound").
  - Why PFBC stocks 17 Class A sections. Operational Guidelines Appendix A (p. 118): "13 stream sections that
    support strong Class A wild Brown Trout populations were officially designated … during the 2015-2017
    timeframe …, and stocking was continued", all "heavily fished waters, most located in high-density human
    population centers". Our 13 biomass-A sections fit (all wild brown, 8 Metro/Urban/Suburban). The
    guidelines don't name them, so it's a strong match, not proof. The other 4 have no documented basis.
  - The Jan 2026 exemptions (13 on 12 Class A sections, up to 5 years, for derbies and private stockings;
    GoErie, 2026-01-31) are a separate mechanism for outside groups and cover none of PFBC's stocked
    sections. Some sit just upstream (Penns Creek 01 ends where our 2207_2 starts; Monocacy, Yellow Creek,
    Marvin Creek likewise).
  - For such exemptions the Commission sets numbers "consistent with … historical stocking rates … to
    minimize impacts to the Class A wild trout population" (p. 119). By analogy, that supports capping PFBC's
    own stocked Class A sections at today's stocking.
- **Stability (optional):** `x_s ≥ (1−δ)·baseline_s`. The survey found 43% of anglers oppose dropping
  low-use waters (34% support).
- **Wild-trout lever (scenario):** `Σ_wild x_s ≤ (1−ρ)·Σ_wild baseline_s`, with ρ ∈ {0, .25, .5, 1}.

## Angler benefit
- **Diminishing returns:** make benefit concave in `x_s` (piecewise-linear in Gurobi). The 300th fish is
  worth more than the 3,000th.
- **Two demand signals, blended:**
  1. **Survey preference** (2023 survey, p76–83): % of stocked-trout anglers naming the water in their top
     three. Covers ~223 waters, matched to river_id and split across sections by length.
  2. **Proximity demand** for every section: the sum over Census block groups of
     `population × P(angler travels ≥ d)`, where `d` is the distance to the section and P comes from the
     survey's travel-distance distribution (p93). In plain terms, nearby people count fully and people
     100+ miles away barely count.
- **Optional calibration:** replace the p93 curve with `exp(−d/β)` and choose β so the predicted "county
  where anglers from region R fish" matches the survey's p85 table.
- **Other benefit inputs (optional):** access points nearby, special-regulation waters, catch importance
  (p140: 81% say catching a fish matters), and thermal suitability (fish in warm water die by summer, so
  benefit falls).

## Transport cost
- **Cost per fish:** `cost[h,s] = 2 × road_mi × cost_per_truck_mile / fish_per_load`.
  - Central values from `docs/transport_research.md`: $1.90/truck-mile and 2,500 fish/load, i.e. about
    $0.0015 per fish per one-way mile (range $0.0007–0.0041). A 50-mile haul is about $0.08/fish.
  - Don't multiply by stockings per year: one truckload is split across sections.
  - Transit mortality is a flat ~1% (0–2%), or left out.
  - Truck capital is a fixed cost, left out of the per-mile cost; "+$1/mi" is a sensitivity.
- **Trucking is small in dollars:** about 4–7% of PFBC's cost per stocked trout. Hatchery output is the
  scarce resource, which is worth saying in the report.
- **Distance:** road distance per supply node → section, built by Gavin (`notebooks/travel_arcs.ipynb`) and
  joined on `section_id`. Not on our slate. Don't use the Google API: it costs money and its terms bar
  storing results.
- **Calibration check:** implied fleet miles vs the ~300,000 mi/yr reported (unverified). At 2,500
  fish/load, that implies ~120 mi one-way hauls, which seems long, so fish_per_load or that figure may be off.
- **Baseline assignment:** nearest hatchery (the real assignment isn't published).
- **Simplification to state in the report:** real trucks make multi-stop routes. We model direct
  shipments, a transportation problem, not vehicle routing.
- Truck cost per mile and fish per load go in `parameters.csv` with source or assumption and a low/high range.

## Wild-trout impact (third objective)
- **Its own goal:** minimize `Impact = Σ w_s · x_s`, the stocked fish on wild-trout water weighted by how
  much is there. Hard rules (Class A, Wilderness, no brook over wild brook) stay as constraints. The
  impact score covers the grey zone of B/C/D and natural-reproduction waters that PFBC does stock.
- **Three inputs, each measuring something different:**
  - **`biomass_class`**, from the allocation code: how much wild trout lives in the section. A = abundant,
    D = sparse, E = none. It's rated for the whole section and may be old. It's our only abundance measure.
  - **`class_a_flag`**: the section overlaps the official Class A list, a legal designation with its own
    limits, updated yearly. It drives the exclusion rule.
  - **`nat_repro_flag`**: wild trout reproduce there at all (presence, no amount or species).
- **Where they disagree** (so all three are kept):
  - 5 sections coded B–D are partly Class A, e.g. West Branch Hicks Run is coded D but 2.85 of its 3.15
    miles are Class A.
  - 27 sections coded E ("no wild trout") are on the natural-reproduction list.
  - 96 sections coded D are not on it.
- **Score versions to explore:** each is a different definition of the goal, and all are reported in
  plain units.
  1. **Simple:** fish stocked on any wild-trout water. `w_s` = 1 if `nat_repro_flag` or biomass B–D,
     else 0. Unit: "fish on wild-trout water". Easiest to explain; start here.
  2. **Weighted:** `w_s` = biomass weight (B=3, C=2, D=1, E=0), +1 if natural reproduction, +2 if wild
     brook trout, and optionally +1 if thermally marginal (upgrade: EcoSHEDS max 30-day mean ≥ 21 °C).
  3. **Partial overlap:** scale `w_s` by the overlapping share of the section (`*_overlap_mi / length_mi`).

  Weights within a score are a judgement call, so show that the conclusions hold across versions 1–2.
- **The survey supports the goal:** 58% of anglers support moving stocking off quality wild trout waters
  to nearby spots, and 16% oppose. The trade-off curve shows how much angler benefit or cost that move
  takes.
- **The "wild-trout lever" constraint** (`Σ_wild x_s ≤ (1−ρ)·baseline`) is just an ε-constraint on this
  objective's simple version.
- **Measuring overlap:** use shared river miles (`SecUpperLi`/`SecLowerLi` on the same RFP_WaterID), never
  a plain intersect. The Class A layer also has a `TroutBioma` (biomass) field that could scale `w_s`.
  - Natural reproduction also counts same-RFP geometric overlap ≥ 0.5 mi, because 191 records have a line
    more than 1.5× their river-mile length. That adds 18 sections, for 549 flagged. Disagreements are in
    `logs/02_overlap_check.csv`.
  - No 2026 brook stocking lands on Class A wild-brook water.

## Co-op nurseries
- **What the policy says** (Cooperative Nursery Statement of Policy, Jan 2017):
  - PFBC sets how many fingerlings each nursery gets.
  - The clubs choose waters, dates and numbers: a tentative schedule is due Mar 5, PFBC reviews it, and
    actual stockings are reported by Jul 15.
  - Co-op fish "will not be included as part of the PFBC allocation" (§III.12). They should complement
    PFBC's schedule, e.g. by not stocking the same week.
- **What the data shows** (`data/processed/coop_stockings`, 786 listings, 133 nurseries):
  - Nurseries stock close to home: median 4 mi straight-line, 77% within 10 mi.
  - The list was identical in Feb 2025 and Sep 2026. That means either stable waters or a rarely updated
    file, and parts of it look out of date (next bullet).
  - It has no fish counts or years, only which species go to which water.
  - 292 of our 1,045 PFBC sections (28%) are also co-op waters, and they get 30% of PFBC's 2026 fish.
  - 10 of the 23 sections PFBC dropped by 2026 are still on the co-op list. 8 of those 10 are wild-trout
    waters (natural reproduction, biomass B–D). So PFBC likely dropped them to let wild trout take over, and
    the co-op list is probably stale there; co-ops are not filling a gap.
  - The same goes for the 4 co-op listings on Class A sections (co-ops may not stock Class A, §VII.2). Two are
    Little Lehigh sections (Class A) that PFBC itself still stocks; two only partly overlap.
  - All of these are in `logs/03_coop_review.csv` for manual review.
- **Version A, the base model:** optimize PFBC hatchery fish only. Co-op waters are a flag (`coop_stocked`,
  `coop_species`) that we report but that doesn't affect decisions. This mirrors PFBC's policy today.
- **Version B, the extension "What if the state coordinated more with co-ops?":**
  - Each co-op section gets a fixed co-op count `c_s`, and benefit becomes
    `demand_s × f(PFBC fish + c_s)`. With diminishing returns, PFBC fish shift toward waters co-ops
    don't cover.
  - Co-op fish have no PFBC trucking cost, and they are constant in the impact score (report only).
  - Use only listings that pass manual review; drop the stale ones on wild-trout water.
  - The per-acre cap applies to PFBC fish only, per policy.
  - `c_s` needs counts: a records request to the Cooperative Nursery Unit (sponsors report every July),
    or an assumed per-nursery total split evenly across its waters.
  - Caveat: this assumes co-ops keep their waters when PFBC shifts fish. Clubs plan after PFBC's schedule;
    modeling their reaction would be a leader-follower (bilevel) problem, out of scope.

## Scenarios for 03_sensitivities
The running list of scenarios, sensitivities and extensions is in `docs/scenarios_and_extensions.md`.
- **Co-op coordination (Version B above):** PFBC counts co-op fish when placing its own.
- **Goal-swap set:** each is scored on the full scorecard.
  - PFBC baseline (the actual plan)
  - angler demand first (max benefit)
  - wild trout first (min impact, subject to benefit ≥ baseline)
  - lowest cost (min cost, subject to benefit ≥ baseline)
  - balanced (a knee point on the trade-off curve)
- **Rates revisited:** replaced (2026-09-27) by the river cap plus the "PFBC formula as cap" and "tighter
  cap" scenarios.
- ε / λ sweeps (trade-off curves)
- cost per truck-mile and fish per load, low vs high
- stability δ and wild-trout lever ρ
- converting the non-trout hatcheries (Tionesta, Fairview, Union City) to trout, an idea from `01_data_prep`
- climate warming (EcoSHEDS +2 °C scenario), if the thermal flag gets built
- total fish fixed vs flexible

## Report hooks
- PFBC's 2025–29 trout plan (Obj. 9.1) says allocation rates "need to be reviewed."
- The survey found 80% support extra stocking on high-use waters.

## Open questions
- Are lakes decisions or fixed? (~20% of fish, 131 stocked waterbodies, no per-lake counts found in GIS yet.)
- One annual decision, or split by season (pre-season / in-season / fall-winter)?
- Blend weight between survey preference and proximity demand.
- Include golden and brood in the model's fish total? (PFBC's TotalAdultStocked_minusBrood is brook + brown +
  rainbow only.)
