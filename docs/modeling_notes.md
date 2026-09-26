# Modeling notes (to return to)

Decisions and ideas from planning, 2026-09-26. Environmental background and citations are in
`docs/env_research.md`. The data pipeline plan is in `PROMPTS.md`.

## Framing: formula vs optimization
- **PFBC allocates by formula, not optimization.**
  - Each section gets a category from its own traits: wild biomass class, recreational use potential
    (access, parking, ownership), human population density, and width.
  - The category sets a max rate (trout/acre/yr, Operational Guidelines Table 18).
  - Quick check (2026, rough width per class): rate × area tracks actual stocking closely, log-scale
    correlation 0.86. The median section gets ~0.8 of its cap; redo this once Prompt 4 gives real areas.
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
- **Keep PFBC's rules as constraints.** The per-acre caps and the exclusions keep our plans inside
  current policy. A "rates revisited" scenario relaxes the caps.
- **One-line pitch:** "PFBC allocates by formula. We make the goals explicit and ask what the formula
  leaves on the table, and what it costs to favour anglers, the budget, or wild trout."
- **Caveat:** if our demand measure ends up close to population density, the model may just rebuild
  PFBC's formula. That's a result in itself ("the rules are close to demand-optimal"). The survey
  preferences and travel distances are what add new information.

## Model shape
- **Decision:** `x[h,s]` = adult trout per year from hatchery `h` to destination `s`. Add a binary
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
- **Total fish:** fixed at the baseline total (same fish, better placement), or relaxed as a scenario.
- **Density bound:** `x_s ≤ rate(category_s) × acres_s`.
  - The rate is now exact: the stocking layer's `AllocationCode` is the full Table 18 category
    ([biomass A–E][use H/G/L][population M/U/S/R][width]). E.g. Bear Creek DGS3 → 190 trout/acre/yr.
    `max_trout_per_acre` covers 1,034 of 1,045 sections; the 11 without a Table 18 rate are biomass A.
  - Width class also comes from the code: 3 = 4–10 m (621 sections), 2 = 10–20 m (320), 1S (54), 1L (43),
    4 = <4 m (7). It gives a rough width for estimating area. `Description` ("OPTIMUM YIELD 2 SUBURBAN")
    is only a label; its "2" is not a width class.
  - Call it a PFBC policy/crowding bound, not ecological carrying capacity.
- **Minimum per stocking:** `300·y_s ≤ x_s` (PFBC rule).
- **Exclusions:** `x_s = 0` for Wilderness and non-exempt Class A sections.
  - The 13 biomass-A sections (all wild brown, none brook) are the exempt Class A sections: fix them at
    baseline, or treat them as a scenario.
  - 18 sections overlap Class A by river mile, so 5 are non-exempt. One, Buffalo Creek 3190_2, was stocked
    in 2024–25 but not 2026. No section overlaps Wilderness.
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
- **Cost per fish:** `cost[h,s] = est_road_mi × cost_per_truck_mile / fish_per_load`, doubled for the round
  trip. It could also scale with stockings per year.
- **Distance:** `est_road_mi` = straight-line × circuity. Use 1.3 as a placeholder, then check it against
  ~15 routes looked up by hand. OpenStreetMap routing (major roads, pyrosm + networkx) is an upgrade.
  Don't use the Google API: it costs money and its terms bar storing results.
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

## Scenarios for 03_sensitivities
- **Goal-swap set:** each is scored on the full scorecard.
  - PFBC baseline (the actual plan)
  - angler demand first (max benefit)
  - wild trout first (min impact, subject to benefit ≥ baseline)
  - lowest cost (min cost, subject to benefit ≥ baseline)
  - balanced (a knee point on the trade-off curve)
- **Rates revisited:** relax the Table 18 caps (e.g. ×1.25, or no cap) to answer PFBC's "need to be reviewed".
- ε / λ sweeps (trade-off curves)
- circuity factor and cost per mile, low vs high
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
