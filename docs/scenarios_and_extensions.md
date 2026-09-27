# Scenarios and extensions

Additional analysis beyond the base model: every scenario, sensitivity run, extension and data upgrade for
the trout stocking optimization. This is the running list: add new ideas here. The base model, its
assumptions and its open questions are in `model_design.md` (data handling in `data_methods.md`); when a
decision changes a row, update both.

Last updated: 2026-09-27

**Status legend:** **base** = in the base model · **planned** = will run · **idea** = not decided ·
**open** = decision pending · **dropped/replaced** = superseded (see the row for what replaced it)

## Goal-swap scenarios

Each is scored on the full scorecard (angler benefit, transport cost, wild-trout impact), per
`model_design.md § Scenarios for 03_sensitivities` ("Goal-swap set").

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| PFBC baseline | Nothing — the actual 2024–26 historical allocation, scored on the same 3 objectives | Where does PFBC's current plan sit on cost/benefit/impact? | base | — | model_design.md § Model shape (Baseline) |
| Angler demand first | Maximize benefit only (subject to constraints) | Best case for anglers if cost and impact aren't weighed? | planned | benefit objective | model_design.md § Scenarios for 03_sensitivities |
| Wild trout first | Minimize impact, subject to benefit ≥ baseline | Best case for wild trout without losing angler benefit? | planned | impact objective | model_design.md § Scenarios for 03_sensitivities |
| Lowest cost | Minimize cost, subject to benefit ≥ baseline | Can PFBC spend less trucking without losing benefit? | planned | cost objective, cost_matrix | model_design.md § Scenarios for 03_sensitivities |
| Balanced | A knee point on the trade-off curve | What's a reasonable compromise plan? | planned | ε-sweep results | model_design.md § Scenarios for 03_sensitivities |
| ε / λ sweeps | Sweep cost cap C and impact cap E instead of one point, to trace the full trade-off curve | How much benefit does a dollar or a wild-trout fish trade for? | base | — | model_design.md § Model shape (Solve method) |

## Constraint / policy scenarios

Each changes a rule of the model (the cap, an exemption, a stability or supply constraint), not an
objective.

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| PFBC formula as cap | cap_s = the exact Table 18 rate (`max_trout_per_acre`) × area, instead of the river cap | How does using PFBC's literal formula as the ceiling change the plan? | planned | `max_trout_per_acre`, `area_acres` | model_design.md § Constraints (Density bound); `../CLAUDE.md` § Agreed simplifications |
| Tighter cap (width midpoints) | area uses width-class midpoints (3, 7, 15, 25, 40 m) instead of class tops | How sensitive is the river cap to the width assumption? | planned | `area_acres_mid`, `cap_fish_mid` | model_design.md § Constraints (Density bound); `../PROMPTS.md` § Prompt 4 step 4 |
| Class A: cap at today's stocking | The 17 Class A-overlap sections PFBC stocks in 2026 are capped at today's stocking (incl. the 2 partial overlaps, Penns Creek 2207_6 and Mauch Chunk 2744_2); Buffalo Creek 3190_2 (Class A since Jan 2026, not stocked in 2026) is excluded. Decided 2026-09-27 | — | base | exclusion flags (Prompt 5) | model_design.md § Constraints (Density bound; Exclusions); known_gaps.md § Class A exemptions |
| Class A allowed to grow | Those 17 sections get the river cap (biomass A at widths 2–3 uses B's 323/acre) instead of today's stocking | What if PFBC let its stocked Class A sections grow like other waters? | planned | `cap_fish_class_a_river` | model_design.md § Constraints (Density bound) |
| Only sections stocked in 2026 | The 23 sections stocked in 2024–25 but dropped by 2026 (~37,500 fish/yr; 18 natural-reproduction waters; Blue Hole Creek 3656_2 for cadmium/lead) get no fish. Decided 2026-09-27 | — | base | exclude_reason (Prompt 5) | model_design.md § Constraints (Candidate sections) |
| Dropped sections back | Allow the 23 dropped sections again, except Blue Hole Creek (health) and Buffalo Creek (Class A) | Was dropping them costly for anglers, and does the model want any of them back? | planned | — | model_design.md § Constraints (Candidate sections) |
| Youghiogheny margin | Idea only, not adopted: allow today's stocking + a margin (e.g. +25%) instead of a hard cap at today's 7,900 fish | Should the one true above-cap tailwater get room to grow instead of being frozen? | idea | — | model_design.md § Constraints (Density bound, Youghiogheny 1327_1); team discussion 2026-09-27 |
| Wild-trout lever (ρ) | Σ_wild x_s ≤ (1−ρ)·Σ_wild baseline, ρ ∈ {0, .25, .5, 1} | How much benefit or cost does pulling fish off wild-trout water take? | planned | impact objective, simple version | model_design.md § Constraints; § Wild-trout impact |
| Stability (δ) | x_s ≥ (1−δ)·baseline_s | How much can low-use waters be protected from big cuts? | planned | — (baseline already built) | model_design.md § Constraints; env_research.md § 6 |
| Total fish fixed vs. flexible | Relax "same total fish as baseline" | Do the objectives actually want more or fewer total fish? | planned | hatchery supply constraint | model_design.md § Constraints (Total fish); § Scenarios for 03_sensitivities |
| Rates revisited | *Dropped/replaced.* Was: relax Table 18 caps directly (×1.25, or no cap) to test PFBC's "need to be reviewed" language | superseded — the river cap (Density bound, decided 2026-09-27) replaced a direct Table-18 relaxation with a river-based cap; "PFBC formula as cap" and "Tighter cap" above now cover this angle | dropped/replaced | — | model_design.md § Scenarios for 03_sensitivities (stale bullet); replaced by § Constraints (Density bound) |

## Sensitivity runs

Assumption and parameter perturbations, run to check conclusions don't hinge on one number or one
judgement call.

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| Transport cost, low vs. high | cost_per_truck_mile and fish_per_load swept together to the low ($0.00071/fish-mi) and high ($0.00413/fish-mi) ends of their ranges | Does the cost-optimal plan change much if trucking is 3–6× costlier per fish-mile? | planned | cost_matrix rebuilt at each end | transport_research.md § Proposed parameters; § 7 Recommendations |
| Truck capital, +$1/mi | Add ~$1.00/truck-mile (range $0.40–2.50) for capital, on top of the operating cost | Does including capital change which plan is cost-optimal? | planned | — | model_design.md § Transport cost; transport_research.md § 7 |
| Length-check sensitivity | Drop the cap (or the section) for the 12 sections where neither PFBC length fits their stocking (`length_check_result == "neither"`), or all 57 `length_check_flag` sections | Do the ~4% of fish on length-ambiguous sections change the conclusions? | planned | `length_check_flag`, `length_check_result` | known_gaps.md § PFBC length vs river miles |
| Wild-trout impact, "simple" score | w_s = 1 if natural reproduction or biomass B–D, else 0 | Baseline definition of the impact objective — easiest to explain | base | — | model_design.md § Wild-trout impact |
| Wild-trout impact, "weighted" score | w_s = biomass weight (B=3,C=2,D=1,E=0) +1 natural reproduction +2 wild brook (+1 if thermally marginal) | Do conclusions hold once wild-trout amount, not just presence, is weighted? | planned | thermal flag optional | model_design.md § Wild-trout impact |
| Wild-trout impact, "partial overlap" score | Scale w_s by the section's overlapping share (`*_overlap_mi / rm_length_mi`: both in river miles) | Does partial overlap change which sections the model avoids? | idea | — | model_design.md § Wild-trout impact |

## Extensions

Bigger additions beyond the base 3-objective model. The base model keeps co-op nurseries as fixed
background (Version A) and lakes and species mix as fixed; these rows are what change if that's revisited.

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| Co-op "Version B" | Each co-op section gets a fixed co-op count c_s; benefit becomes demand_s × f(PFBC fish + c_s). Co-op fish have no PFBC trucking cost and are constant (report-only) in the impact score. Per-acre cap still applies to PFBC fish only | What if the state placed its own fish knowing what co-ops already stock? | idea | co-op fish counts (records request to Cooperative Nursery Unit, or an assumed per-nursery split of the ~1.1M/yr statewide total, GoErie 2026-01-31); reviewed listings (drop stale ones on wild-trout water) | model_design.md § Co-op nurseries (Version B); `../CLAUDE.md` § Agreed simplifications; known_gaps.md § Co-op nurseries |
| Lakes as decision variables | ~20% of PFBC's adult trout (131 lakes) become x[h,s] decisions instead of being left out | Does the model's demand/cost logic extend to lakes, or are they structurally different? | open | per-lake stocking counts (none found in any GIS service yet) | model_design.md § Open questions; § Units of analysis (Lake) |
| Fairness metric | Scorecard gains a 4th reported number, e.g. share of PA population within X miles of a stocked section | Does an efficient plan on the 3 objectives leave some regions underserved? | idea | proximity demand data (already built for benefit) | model_design.md § Framing ("What we deliver," Scorecard) |
| Per-species allocation | Model chooses species mix per section instead of keeping each section's historical species shares fixed | Does letting species shift (no brook over wild brook) find a better plan? | idea | per-species benefit/impact weights | model_design.md § Model shape (Species) |
| Convert non-trout hatcheries | Add Tionesta, Fairview and Union City as supply nodes | Would more/closer supply change the cost-optimal plan? | idea | production/feasibility data for those hatcheries | model_design.md § Scenarios for 03_sensitivities (idea from 01_data_prep) |
| Climate warming (+2 °C) | Shift the thermal-marginal flag warmer under an EcoSHEDS warming scenario | How much benefit erodes, or how many more sections lose benefit, under warming? | idea | thermal marginality flag built first | model_design.md § Scenarios for 03_sensitivities; env_research.md § 4 |
| Peak-day truck constraint | Add a per-hatchery limit on truckloads/day at the preseason peak | Does the fleet's daily capacity bind before the general supply constraint does? | idea | fleet size, schedule dates | transport_research.md § 7 (Leave as upgrades) |
| Seasonal fish_per_load | fish_per_load varies by season instead of one annual value (cold hauls carry more, warm hauls less) | Does seasonality change the fish_per_load calibration check? | idea | stocking schedule dates | transport_research.md § 6 |
| cost_per_stop | Add ~$0.02/fish for crew time at each stocking visit, on top of the per-mile haul cost | Does counting visit time (not just miles) change the cost-optimal plan? | idea | `stockings_per_section_per_year` (already in parameters.csv) | transport_research.md § Proposed parameters (cost_per_stop); § 7 |


## Data upgrades

Data collection or processing that would replace an assumption, if time allows.

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| NHDPlus width | width_top_m/width_mid_m come from a NHDPlus COMID join + Chaplin 2005 drainage-area regression, instead of the PFBC width-class assumption | Does a modeled width move the river cap much from the class-based one? | idea | NHDPlus COMID join | `../PROMPTS.md` § Prompt 4 (Upgrade); env_research.md § 5 |
| Distance-decay calibration | Proximity demand curve becomes exp(−d/β), β fit to match the survey's p85 county table, instead of the p93 travel-distance bands directly | Does a calibrated curve move section-level demand much from the direct approach? | idea | survey p85 county table (already extracted) | model_design.md § Angler benefit (Optional calibration); `../PROMPTS.md` § Upgrades |
| Thermal marginality flag | Adds `thermal_marginal` (EcoSHEDS max 30-day mean ≥ 21 °C) as a section attribute | Which sections run too warm for stocked fish to survive summer? | idea | EcoSHEDS spatial join (large rivers will be NA) | `../PROMPTS.md` § Upgrades (Thermal flag); env_research.md § 4–5 |
| EBTJV / EcoSHEDS brook trout occupancy | An independent source for wild-brook presence, as a cross-check on the Class-A-text `wild_brook_present` flag | Does an independent occupancy model agree with the text-parsed flag? | idea | EBTJV request form, or EcoSHEDS occupancy download | env_research.md § 4–5 |
| DEP Ch. 93 HQ/EV designations | Adds a regulatory water-quality tier as a possible extra wild-trout impact input | Does it add information beyond biomass class / natural reproduction, given it's often insect-based? | idea | PASDA download | env_research.md § 5 (Low priority) |
| Historical stocking coverage | Check for a 2023 fbweb layer, or Wayback Machine captures of past schedules | Can the baseline reach back toward 2022, the survey year? | idea | — | `../PROMPTS.md` § Upgrades (History) |
| PFBC records request | Replaces the nearest-hatchery assumption, transport cost assumptions, and hatchery-share-by-production-lbs assumption with PFBC's own figures | How far off are the current assumptions from PFBC's actual numbers? | idea | a records request | `../PROMPTS.md` § Upgrades (PFBC records request); `../CLAUDE.md` § Agreed simplifications |
