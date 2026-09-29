# Scenarios and extensions

Additional analysis beyond the base model: every scenario, sensitivity run, extension and data upgrade for
the trout stocking optimization. This is the running list: add new ideas here. The base model, its
assumptions and its open questions are in `model_design.md` (data handling in `data_methods.md`); when a
decision changes a row, update both.

Last updated: 2026-09-28

**Status legend:** **base** = in the base model · **planned** = will run · **idea** = not decided ·
**open** = decision pending · **dropped/replaced** = superseded (see the row for what replaced it)

## Goal-swap scenarios

Each is scored on the full scorecard (angler benefit, transport cost, wild-trout impact).

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| PFBC baseline | Nothing — the actual 2024–26 historical allocation, scored on the same 3 objectives | Where does PFBC's current plan sit on cost/benefit/impact? | base | — | model_design.md § Model shape (Baseline) |
| Angler demand first | Maximize benefit only (subject to constraints) | Best case for anglers if cost and impact aren't weighed? | planned | benefit objective | model_design.md § Framing |
| Wild trout first | Minimize impact, subject to benefit ≥ baseline | Best case for wild trout without losing angler benefit? | planned | impact objective | model_design.md § Framing |
| Lowest cost | Minimize cost, subject to benefit ≥ baseline | Can PFBC spend less trucking without losing benefit? | planned | cost objective, cost_matrix | model_design.md § Framing |
| Balanced | A knee point on the trade-off curve | What's a reasonable compromise plan? | planned | ε-sweep results | model_design.md § Framing |
| ε / λ sweeps | Sweep cost cap C and impact cap E instead of one point, to trace the full trade-off curve | How much benefit does a dollar or a wild-trout fish trade for? | base | — | model_design.md § Model shape (Solve method) |
| PFBC's information only | Demand from the allocation code instead of our demand: D_s = Table 18 rate × `area_acres` (PFBC's implied angler use; the code's population class is its only demand signal). Run the same ε-sweeps. Variant: one objective per code letter (population class for benefit, biomass class for impact) | Splits the gain into "optimizing alone" (baseline → this) and "knowing where anglers are" (this → base). Also a check on the machinery: with only a supply limit, the benefit curve gives every section the same fish per angler-day, so this should reproduce PFBC's allocation where caps, cost and impact don't bind. The variant asks whether PFBC's plan sits on its own trade-off curve | idea | `max_trout_per_acre` (`program_rate` for the 57 program sections; 11 biomass-A sections have none, so keep them at today's stocking), `area_acres` | discussion 2026-09-28; figure_ideas.md (Stocking vs demand) |

## Constraint / policy scenarios

Each changes a rule of the model (the cap, an exemption, a stability or supply constraint), not an
objective.

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| PFBC formula as cap | cap_s = PFBC's exact rate × area: `program_rate` for the 57 DHALO and tailwater sections, else the Table 18 rate (`max_trout_per_acre`), instead of the density cap (puts population back in) | How does using PFBC's literal formula as the ceiling change the plan? | planned | `max_trout_per_acre`, `area_acres` | model_design.md § Constraints (Density bound); `../CLAUDE.md` § Agreed simplifications |
| Tighter cap (width midpoints) | area uses width-class midpoints (3, 7, 15, 25, 40 m) instead of class tops | How sensitive is the density cap to the width assumption? | planned | `area_acres_mid`, `cap_fish_mid` | model_design.md § Constraints (Density bound); `../PROMPTS.md` § Prompt 4 step 4 |
| River cap (ignore access) | cap_s uses `cap_rate_river`, the highest Table 18 rate over access too (C–E 361/acre at widths 2–3 instead of 323 for Good-access sections); Class A stays at today's stocking. The base cap until 2026-09-27 | Does limiting sections by road frontage, parking and ownership change the plan? | planned | `cap_fish_river` | model_design.md § Constraints (Density bound) |
| Class A: cap at today's stocking | The 17 Class A-overlap sections PFBC stocks in 2026 are capped at today's stocking (incl. the 2 partial overlaps, Penns Creek 2207_6 and Mauch Chunk 2744_2); Buffalo Creek 3190_2 (Class A since Jan 2026, not stocked in 2026) is excluded. Decided 2026-09-27 | — | base | `cap_fish`, `cap_source`, `environment.exclude` | model_design.md § Constraints (Density bound; Exclusions); known_gaps.md § Class A exemptions |
| Class A allowed to grow | Those 17 sections get the normal cap, never below today (biomass A at widths 2–3 uses B's 323/acre) instead of today's stocking | What if PFBC let its stocked Class A sections grow like other waters? | planned | `cap_fish_class_a_grow` | model_design.md § Constraints (Density bound) |
| Only sections stocked in 2026 | The 23 sections stocked in 2024–25 but dropped by 2026 (~37,500 fish/yr; 18 natural-reproduction waters, including Buffalo Creek 3190_2, now Class A, and Blue Hole Creek 3656_2, removed for cadmium/lead) get no fish. Decided 2026-09-27 | — | base | `environment.exclude_reason` | model_design.md § Constraints (Candidate sections) |
| Dropped sections back | Allow the 23 dropped sections again, except Blue Hole Creek (health) and Buffalo Creek (Class A) | Was dropping them costly for anglers, and does the model want any of them back? | planned | demand rerun with the 21 in the section set (`scripts/08_demand.py` splits demand among the sections that exist) | model_design.md § Constraints (Candidate sections) |
| Youghiogheny margin | Idea only, not adopted: allow today's stocking + a margin (e.g. +25%) instead of a hard cap at today's 7,900 fish | Should the Youghiogheny tailwater (1.1× its Table 45 cap at our assumed 60 m width) get room to grow instead of being frozen? | idea | — | model_design.md § Constraints (Density bound, Youghiogheny 1327_1); team discussion 2026-09-27 |
| Wild-trout lever (ρ) | Σ_wild x_s ≤ (1−ρ)·Σ_wild baseline, ρ ∈ {0, .25, .5, 1} | How much benefit or cost does pulling fish off wild-trout water take? | planned | impact objective, simple version | model_design.md § Constraints; § Wild-trout impact |
| Stability (δ) | x_s ≥ (1−δ)·baseline_s | How much can low-use waters be protected from big cuts? | planned | — (baseline already built) | model_design.md § Constraints; env_research.md § 6 |
| Total fish fixed vs. flexible | Relax "same total fish as baseline" | Do the objectives actually want more or fewer total fish? | planned | hatchery supply constraint | model_design.md § Constraints (Total fish) |
| Rates revisited | *Dropped/replaced.* Was: relax Table 18 caps directly (×1.25, or no cap) to test PFBC's "need to be reviewed" language | superseded — the density cap (Density bound, decided 2026-09-27; it now counts access) replaced a direct Table-18 relaxation with a river-based cap; "PFBC formula as cap" and "Tighter cap" above now cover this angle | dropped/replaced | — | replaced by model_design.md § Constraints (Density bound) |

## Sensitivity runs

Assumption and parameter perturbations, run to check conclusions don't hinge on one number or one
judgement call.

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| Transport cost, low vs. high | cost_per_truck_mile and fish_per_load swept together to the low ($0.00071/fish-mi) and high ($0.00413/fish-mi) ends of their ranges | Does the cost-optimal plan change much if trucking is 3–6× costlier per fish-mile? | planned | cost_matrix rebuilt at each end | transport_research.md § Proposed parameters; § 7 Recommendations |
| Truck capital, +$1/mi | Add ~$1.00/truck-mile (range $0.40–2.50) for capital, on top of the operating cost | Does including capital change which plan is cost-optimal? | planned | — | model_design.md § Transport cost; transport_research.md § 7 |
| Hatchery supply by pounds | supply_h from the production-pounds split (the 8 hatcheries with a pounds figure; Tionesta kept at its schedule amount) instead of each hatchery's 2026 stream fish from the schedule | Does the supply source change which hatcheries bind or where fish go? | planned | `pa_hatchery_production.csv`, `hatchery_schedule_supply.csv` | model_design.md § Constraints (Hatchery supply) |
| Nearest-hatchery baseline | Cost the baseline from each section's nearest hatchery instead of its scheduled one | How much of the savings comes from PFBC's real assignment being longer than the nearest one? | planned (if the scheduled baseline is confirmed) | `cost_matrix`, `section_schedule` | model_design.md § Transport cost (Baseline assignment) |
| Detour version | Detour charge from geographic nearest neighbours (`detour_nn_mi`, the fallback) vs run clusters (`detour_mi`) vs strict-majority clusters (`detour_mi_strict`), or none | Does how stops are grouped into runs change the plan? | idea (the detour charge itself is undecided) | `section_schedule`, `clusters` | model_design.md § Open questions |
| Length-check sensitivity | Drop the cap (or the section) for the 12 sections where neither PFBC length fits their stocking (`length_check_result == "neither"`), or all 57 `length_check_flag` sections | Do the ~4% of fish on length-ambiguous sections change the conclusions? | planned | `length_check_flag`, `length_check_result` | known_gaps.md § PFBC length vs river miles |
| Wild-trout impact, "simple" score | w_s = 1 if natural reproduction or biomass B–D, else 0 | Baseline definition of the impact objective — easiest to explain | base | — | model_design.md § Wild-trout impact |
| Wild-trout impact, "weighted" score | w_s = biomass weight (B=3,C=2,D=1,E=0) +1 natural reproduction +2 wild brook (+1 if thermally marginal) | Do conclusions hold once wild-trout amount, not just presence, is weighted? | planned | thermal flag optional | model_design.md § Wild-trout impact |
| Natural reproduction by geometry too | Also flag the 18 sections that lie ≥ 0.5 mi along a same-water Natural Reproduction line but share no river miles with it (`nat_repro_missed_by_rm` in `logs/02_overlap_check.csv`) | Does the river-miles-only assumption move fish onto wild-trout water? (~1% of 2026 fish; in the simple score only 2 biomass-E sections change) | idea | the 18 section ids | known_gaps.md § Natural Reproduction river miles shorter than the line |
| Wild-trout impact, "partial overlap" score | Scale w_s by the section's share on natural-reproduction water (`nat_repro_share`, river miles) | Does partial overlap change which sections the model avoids? | idea | `environment.nat_repro_share` | model_design.md § Wild-trout impact |
| Blend weight w | D_s = (1 − w)·proximity + w·preference, with w = 0, 0.5 (base), 1 | Does the plan change if demand follows where anglers live (w = 0) or their favorite waters (w = 1)? | planned | `demand` proximity and preference columns | model_design.md § Angler benefit; parameters.csv `blend_weight_w` |
| Benefit saturation k | k = 0.5, 1 (base), 2 fish per angler-day | How much do results depend on how fast extra fish stop adding benefit? | planned | — | model_design.md § Angler benefit; parameters.csv `benefit_saturation_k` |
| Benefit curve shape | g(r) = r/(r + k) instead of 1 − e^(−r/k) | Does a curve that penalizes overstocking less change the plan? | planned | — | model_design.md § Angler benefit |
| Pooled travel curve | Every block group uses one in-state p93 curve instead of its home region's | Do regional travel habits move demand much? | planned | `prox_days_pooled` | model_design.md § Angler benefit (Proximity) |
| Population-only proximity | Every county at the state angler rate: no license weighting | Does the license-based rural plus-up change the plan? | planned | `prox_days_pop` | model_design.md § Angler benefit; known_gaps.md § Angler numbers by county |
| Online permits like store sales | Split online resident permits across counties like store sales instead of by population | How much does the unknown home county of online buyers matter? (rural median rate 2.2× vs 1.9× the state's) | idea | `county_anglers` inputs | known_gaps.md § Angler numbers by county |
| Even split within a band | Proximity angler-days split evenly among a band's sections instead of by length | Does favoring long sections drive any result? | idea | — | model_design.md § Angler benefit (Proximity) |
| Access-weighted proximity split | Within each distance band, split angler-days by length × an access weight (e.g. PFBC's High-to-Good stocking ratio, ~1.5) instead of length alone | Would favoring easy-to-reach sections in demand, not just in the cap, change the plan? Caveat: the weight partly repeats PFBC's formula | idea | `use_potential` | model_design.md § Angler benefit (Access is in the cap, not in demand) |
| Favorite boost | *Dropped/replaced.* Was: boost favorite waters within each distance band until each draws its survey share | superseded: tested 2026-09-27, remote favorites needed ×60–1,500 boosts that emptied nearby small streams, and a long-trips-only version couldn't reach the targets; replaced by the blend weight w and the destination index figure | dropped/replaced | — | model_design.md § Angler benefit |

## Extensions

Bigger additions beyond the base 3-objective model. The base model keeps co-op nurseries as fixed
background (Version A) and lakes and species mix as fixed; these rows are what change if that's revisited.

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| Co-op "Version B" | Each co-op section gets a fixed co-op count c_s; benefit becomes D_s × g((PFBC fish + c_s) / D_s). Co-op fish have no PFBC trucking cost and are constant (report-only) in the impact score. Per-acre cap still applies to PFBC fish only | What if the state placed its own fish knowing what co-ops already stock? | idea | co-op fish counts (records request to Cooperative Nursery Unit, or an assumed per-nursery split of the ~1.1M/yr statewide total, GoErie 2026-01-31); reviewed listings (drop stale ones on wild-trout water) | model_design.md § Co-op nurseries (Version B); `../CLAUDE.md` § Agreed simplifications; known_gaps.md § Co-op nurseries |
| Lakes as decision variables | ~20% of PFBC's adult trout (131 lakes) become x[h,s] decisions instead of being left out | Does the model's demand/cost logic extend to lakes, or are they structurally different? | open | per-lake stocking counts (none found in any GIS service yet) | model_design.md § Open questions; § Units of analysis (Lake) |
| Fairness metric | Scorecard gains a 4th reported number, e.g. share of PA population within X miles of a stocked section | Does an efficient plan on the 3 objectives leave some regions underserved? | idea | proximity demand data (already built for benefit) | model_design.md § Framing ("What we deliver," Scorecard) |
| Per-species allocation | Model chooses species mix per section instead of keeping each section's historical species shares fixed | Does letting species shift (no brook over wild brook) find a better plan? | idea | per-species benefit/impact weights | model_design.md § Model shape (Species) |
| Convert non-trout hatcheries | Add Tionesta, Fairview and Union City as supply nodes | Would more/closer supply change the cost-optimal plan? | idea | production/feasibility data for those hatcheries | idea from `notebooks/01_data_prep.ipynb` |
| Climate warming (+2 °C) | Shift the thermal-marginal flag warmer under an EcoSHEDS warming scenario | How much benefit erodes, or how many more sections lose benefit, under warming? | idea | thermal marginality flag built first | env_research.md § 4 |
| Peak-day truck constraint | Add a per-hatchery limit on truckloads/day at the preseason peak | Does the fleet's daily capacity bind before the general supply constraint does? | idea | fleet size, schedule dates | transport_research.md § 7 (Leave as upgrades) |
| Seasonal fish_per_load | fish_per_load varies by season instead of one annual value (cold hauls carry more, warm hauls less) | Does seasonality change the fish_per_load calibration check? | idea | stocking schedule dates | transport_research.md § 6 |
| cost_per_stop | Add ~$0.02/fish for crew time at each stocking visit, on top of the per-mile haul cost | Does counting visit time (not just miles) change the cost-optimal plan? | idea | `stockings_per_section_per_year` (already in parameters.csv) | transport_research.md § Proposed parameters (cost_per_stop); § 7 |
| Downstream drift | Credit part of a section's fish to the sections below it on the same river (ordered by river miles on the same RFP_WaterID), e.g. a share that decays per mile | Does counting fish that drift downstream (tailwaters like Youghiogheny 1327_1) change where fish should go? | idea | river-mile order of sections; a drift assumption | model_design.md § Assumptions no scenario tests; team discussion 2026-09-27 |
| Spread the fish | Add a spread rule: a minimum per stocked section (e.g. 50% of baseline or 500 fish), a minimum number of sections or counties stocked, or a coverage metric (share of anglers with a stocked section inside their typical trip distance) as a constraint or reported score | Does spreading fish, which anglers ask for ("spread it out" / float stocking, survey PDF pp. 168, 191), cost much benefit or trucking? The benefit curve already spreads fish by demand; this spreads them by place | idea | demand, candidate sections | model_design.md § Angler benefit (benefit curve); team discussion 2026-09-27 |


## Data upgrades

Data collection or processing that would replace an assumption, if time allows.

| Name | What changes vs. base | Question it answers | Status | Needs | Source |
|---|---|---|---|---|---|
| NHDPlus width | width_top_m/width_mid_m come from a NHDPlus COMID join + Chaplin 2005 drainage-area regression, instead of the PFBC width-class assumption | Does a modeled width move the density cap much from the class-based one? | idea | NHDPlus COMID join | `../PROMPTS.md` § Prompt 4 (Upgrade); env_research.md § 5 |
| Distance-decay calibration | *Dropped/replaced.* Was: proximity curve exp(−d/β), β fit to the survey's p85 county table | superseded 2026-09-27: the band version uses each home region's p93 bands directly, and p85 becomes a check on it | dropped/replaced | — | model_design.md § Angler benefit (Proximity); `../PROMPTS.md` § Upgrades |
| Permit holders by home county | A PFBC table of trout-permit holders by home county or ZIP (Right-to-Know request) replaces sales by store county | How much do anglers who buy at their fishing destination inflate rural counties? | idea | a records request to PFBC | known_gaps.md § Angler numbers by county |
| Return-to-creel rate for k | A PFBC figure for the share of stocked trout that get caught sets k = 1 ÷ that share | Is the benefit curve's saturation point realistic? | idea | a PFBC creel study figure (the Operational Guidelines give trips per trout, not return rates) | model_design.md § Angler benefit |
| Thermal marginality flag | Adds `thermal_marginal` (EcoSHEDS max 30-day mean ≥ 21 °C) as a section attribute | Which sections run too warm for stocked fish to survive summer? | idea | EcoSHEDS spatial join (large rivers will be NA) | `../PROMPTS.md` § Upgrades (Thermal flag); env_research.md § 4–5 |
| EBTJV / EcoSHEDS brook trout occupancy | A source for wild-brook presence outside Class A, where `wild_brook_present` is NA (1,028 sections) | Would the no-brook-over-wild-brook rule and the weighted score's brook term bind anywhere? | idea | EBTJV request form, or EcoSHEDS occupancy download | env_research.md § 4–5 |
| DEP Ch. 93 HQ/EV designations | Adds a regulatory water-quality tier as a possible extra wild-trout impact input | Does it add information beyond biomass class / natural reproduction, given it's often insect-based? | idea | PASDA download | env_research.md § 5 (Low priority) |
| Historical stocking coverage | Check for a 2023 fbweb layer, or Wayback Machine captures of past schedules | Can the baseline reach back toward 2022, the survey year? | idea | — | `../PROMPTS.md` § Upgrades (History) |
| PFBC records request | Replaces the transport cost assumptions with PFBC's own figures, and adds what the 2026 schedule lacks: lake counts, per-event counts, and what was actually stocked (the schedule already gives each section's hatchery, 2026-09-28) | How far off are the current assumptions from PFBC's actual numbers? | idea | a records request | `../PROMPTS.md` § Upgrades (PFBC records request); `../CLAUDE.md` § Agreed simplifications |
