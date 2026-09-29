# Model design

The optimization model: objectives, constraints, assumptions and open questions (started 2026-09-26).
Environmental background and citations are in `docs/env_research.md`. The data pipeline plan is in `PROMPTS.md`.
Scenarios, sensitivity runs and extensions are in `docs/scenarios_and_extensions.md`.

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
  3. **Goal-swap scenarios.** See `scenarios_and_extensions.md` § Goal-swap scenarios. Report the sections
     that gain or lose fish in every scenario (robust changes) separately from those that move only under
     some goals.
- **Keep PFBC's physical rules as constraints, not its preferences.** The exclusions and a per-acre
  crowding cap keep plans realistic. The cap drops the part of PFBC's formula that encodes demand
  (population) but keeps access (see "Density bound"); a "PFBC formula as cap" scenario puts population back.
- **One-line pitch:** "PFBC allocates by formula. We make the goals explicit and ask what the formula
  leaves on the table, and what it costs to favour anglers, the budget, or wild trout."
- **Caveat:** if our demand measure ends up close to population density, the model may just rebuild
  PFBC's formula. That's a result in itself ("the rules are close to demand-optimal"). The survey
  preferences and travel distances are what add new information. How close demand sits to population
  depends on the travel curve (see Angler benefit).

## Model shape
- **Decision:** `x[h,s]` = adult trout per year from PFBC hatchery `h` to destination `s`. Add a binary
  `y[s]` (section stocked or not) if we use the minimum-stocking rule.
- **Species** stay out of the transport part. Each section keeps its historical species mix (shares from
  2024–26), except that brook trout are never stocked over wild brook trout. A per-species model is an upgrade.
  Wild brook presence is known only for Class A, and none of the stocked Class A sections is brook water, so
  this rule binds nowhere today (`known_gaps.md` § Wild trout species outside Class A).
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
- **Hatchery supply:** `Σ_s x[h,s] ≤ supply_h`. `supply_h` = hatchery h's 2026 stream fish from PFBC's stocking
  schedule (`hatchery_schedule_supply.csv`; decision 2026-09-28): each section's 2026 count is credited to the
  hatcheries of its scheduled events. This measures what each hatchery actually puts into streams, where the
  earlier split by production pounds mixed in lake and other fish. 9 hatcheries deliver to streams, Tionesta
  included; Linesville and Pleasant Mount deliver none.
  - **Sensitivity:** the pounds split (`data/raw/pa_hatchery_production.csv`) over the 8 hatcheries with a
    pounds figure, with Tionesta kept at its schedule amount. It also serves as a check: shares differ by up
    to 4 points (Tylersville 12.6% by schedule vs 16.5% by pounds, Corry 9.7% vs 6.5%).
- **Co-op nurseries are fixed background** (team decision 2026-09-27), not supply nodes. See "Co-op
  nurseries" below.
- **Total fish:** fixed at the baseline total (same fish, better placement), or relaxed as a scenario.
- **Density bound (`cap_fish`, decision 2026-09-27; replaced the "river cap" the same day):**
  `x_s ≤ cap_s = max(cap_rate_s × length_mi_s × top_width_s, 300)`. The rate depends on wild biomass, width
  and access, never population; `cap_rate` is the higher of `access_rate` and `program_rate` (both below).
  - **Why not Table 18 directly.** Table 18 is PFBC's allocation formula. Its four inputs are wild biomass,
    recreational use potential (access), human population density and width. Using the section's exact
    rate as the cap would lock in PFBC's preferences: a rural section could never pass 95/acre.
  - **Population is dropped** (the cap takes the highest rate over all four population classes). It's purely
    a guess at how many anglers will come, and our benefit objective models that directly.
  - **Access is kept.** Recreational use potential (Guidelines printed pp. 41–43, Tables 15–16) is measured on
    the stream: the share of the section within 100 m or 300 m of a road, parking spaces per km, and bank
    ownership (public, private, % posted). Nothing else in the model sees those, and they limit a section
    whatever the demand:
    - Road frontage and parking limit how many anglers a section can hold at once. Crowding is stocked-trout
      anglers' top complaint in the 2023 survey (9–17% by home region, survey PDF p. 169).
    - Ownership is about landowners. The Guidelines cut stocking on posted private water because "continued
      high intensity stocking on waters with existing posting problems may lead to additional posting and
      the eventual total closure of these waters" (printed p. 43).
  - **Finding: Table 18 isn't monotone in access** (checked against the PDF, printed p. 45). For biomass B at
    widths 2–3, High access gets a flat 147/acre, while Good access gets 323 (Metro), 285, 190 and 95. The
    Guidelines don't say why; a likely reason is protecting wild trout on easy-to-reach B water, which our
    wild-trout impact objective already covers. Taken literally, 17 sections (16 stocked in 2026: 14 rural,
    2 metro; 23,580 fish) would get a lower cap for having better access.
  - **Decision: better access never lowers the cap.** `access_rate` = the highest Table 18 rate for the
    section's biomass + width at its own access rating *or any worse one*, over all population classes. It
    only changes those 17 sections (147 → 323, the same as the Good row). Rates in trout/acre/yr:

    | Biomass | Access | Width 4 | 3 | 2 | 1S | 1L |
    |---|---|---|---|---|---|---|
    | C, D, E | High | 57 | 361 | 361 | 137 | 91 |
    | B | High | 57 | 323* | 323* | 137 | 91 |
    | B–E | Good | 57 | 323 | 323 | 84 | 53 |
    | B–E | Low | 57 | 57 | 57 | 34 | 30 |

    \* Lifted from Table 18's 147 by the rule above. Biomass A follows the same rows, except that at widths
    2–3 it has no Table 18 rate and uses B's 323 (all 11 are Good or High; assumption, `parameters.csv`).

    High sections keep the old river cap's rate. Good sections get the Good row's top, 323 at widths 2–3
    (about 11% below 361 for C–E); the 6 Low sections get 57 or less.
  - **River cap = the looser sensitivity** (`cap_fish_river`, rate `cap_rate_river`): the highest rate over access too (361 at widths
    2–3 for C–E, 323 for B). Class A stays at today's stocking, and no section drops below its 2026 count.
  - **Special programs use their own rate where it's higher** (found and decided 2026-09-27). Table 18 isn't
    PFBC's only rate table: some programs replace it, and our first cap read Table 18 alone.
    - **Delayed Harvest Artificial Lures Only (DHALO), Table 46** (Guidelines pdf p. 85): 190/acre at widths
      2–3, 133 at 1S/1L. 56 sections, flagged by `reg_name`. It matters on big rivers, where Table 18's Good
      rate is far lower (84 at 1S, 53 at 1L). Before this fix, 5 DHALO rivers sat above their cap: Wiconisco
      Creek is stocked at exactly 133/acre.
    - **Tailwater trout fisheries, Table 45** (pdf p. 80): 266/acre at High access, 247 at Good, for "those
      few short tailwater sections" (≤ 2 mi) below a major reservoir's cold-water outflow. No PFBC layer
      flags tailwaters, so two are listed by hand: Youghiogheny 1327_1 and Conneauttee Creek 2649_1
      (assumption). The rate only matters on wide rivers: at widths 2–3 the access rate (323–361) is higher.
      The other dam sections we checked are too long, not cold-water or already DHALO (`known_gaps.md`
      § Tailwater sections).
    - `cap_rate` is the higher of `access_rate` and `program_rate`, and `cap_rate_river` likewise includes
      the program rate. It raises 11 sections: 10 DHALO rivers at 1S/1L and the
      Youghiogheny. At widths 2–3, DHALO's 190 is below Table 18's 323, so nothing changes there.
  - **Width = top of the class** (4, 10, 20, 30 m; 60 m for open-ended 1L, an assumption). It's the most
    PFBC's rules allow on a stream of that class, so the cap doesn't bind just because our width guess is
    off. The class midpoints (3, 7, 15, 25, 40 m) are the tighter sensitivity.
  - **Minimum 300** fish, so any section can take one load (`300·y_s ≤ x_s`).
  - **Fit to the baseline** (`logs/04_cap_check.csv`). Statewide, `cap_fish` is 3.06× 2026 stocking at class
    tops (the river cap 3.45×) and 2.23× at midpoints. 2026 stocking exceeds the cap in 7 sections, which are
    capped at their 2026 stocking (`cap_source = "baseline"`):
    - Conneauttee Creek 2649_1 (a 0.19 mi tailwater, 2.1×), Roaring Brook 1767_5 (Lackawanna, 1.4×; its stocking
      went 1,315 → 2,660 → 3,965 in 2024–26, so a multi-year mean would have kept it under), Youghiogheny
      River 1327_1 (1.1×, see below), Black Moshannon Creek 2254_2 (6% over), Fishing Creek 183_9 (Low
      access, 6% over), West Branch Susquehanna River 4029_7 (1% over) and Wiconisco Creek 2892_3 (1 fish
      over: stocked at exactly its DHALO rate, and the cap rounds down).
    - The access rule alone put 11 sections over (7 more big Good- or Low-access rivers). The special-program
      rates brought 5 of those DHALO rivers back under.
  - **"Today's stocking" = the 2026 count** (`total_2026`, all five species; decision 2026-09-27), for both
    the Class A and the above-cap sections.
  - **Midpoint sensitivity** (`cap_fish_mid`): 49 sections stocked in 2026 are above it and would have to be
    cut (32 of them width 3).
  - **Youghiogheny 1327_1** (EHS1L, dam outflow to Casselman River, open year-round): PFBC stocks 7,900
    fish on 1.1 mi. It's a tailwater, so its rate is Table 45's 266/acre, not Table 18's. At our assumed
    60 m top width that caps it at 7,070 (1.1× over); 266/acre fits 7,900 fish at 67 m. (Corrected
    2026-09-27: read against Table 18's 72/acre it looked 3.3× over, needing a ~250 m wide river.) Today's
    stocking is its cap.
  - **Class A** (decision 2026-09-27): the 17 Class A-overlap sections PFBC stocks in 2026 are capped at
    today's stocking (keep or cut, never add). They are the 13 biomass-A sections plus Mauch Chunk Creek
    2744_2, West Branch Hicks Run 4363_3, Freeman Run 3546_4 and Penns Creek 2207_6 (two of these only
    partly overlap; same rule). Stocking Class A needs Commission approval. The 13 biomass-A sections are very
    likely the guidelines' 13 continued-stocking Class A sections; the other 4 have no documented basis
    (`known_gaps.md` § Class A exemptions).
    With the normal cap the 13 biomass-A sections alone could take 2.4× today (84k vs 34.5k fish; up to
    5.4× on Yellow Creek 59_4), mostly near Allentown/Bethlehem in an "anglers first" run.
    **Scenario "Class A allowed to grow"** (`cap_fish_class_a_grow`): the normal cap instead, never below
    today (Monocacy Creek 2717_9 is already above it: 2,815 fish vs 2,357).
  - The exact Table 18 rate stays in `max_trout_per_acre` for the baseline and the "PFBC formula as
    cap" scenario, which uses `program_rate` instead for the 57 special-program sections (PFBC's formula
    for them). Width class comes from the code; `Description` ("OPTIMUM YIELD 2 SUBURBAN") is only a
    label, and its "2" is not a width class.
  - Call it a policy/crowding bound, not ecological carrying capacity.
- **Candidate sections** (decision 2026-09-27): the 1,022 sections PFBC stocks in 2026. `x_s = 0` for the
  23 stocked in 2024–25 only (~37,500 fish/yr). PFBC dropped them for reasons we mostly can't see; 18 are
  natural-reproduction waters. Two have known reasons: Buffalo Creek 3190_2 became Class A, and Blue Hole
  Creek 3656_2 was removed for cadmium and lead (GoErie, 2026-01-31, reporting the Jan 30 Commission meeting).
  **Scenario "dropped sections back":** allow them again, except Blue Hole Creek (health) and Buffalo Creek
  3190_2 (Class A).
- **Exclusions:** `x_s = 0` for Wilderness (no stocked section overlaps it) and Buffalo Creek 3190_2, which
  became Class A in Jan 2026 and wasn't stocked in 2026. The other 17 Class A overlaps are capped at
  today's stocking (see "Density bound"). Why PFBC stocks them, and how the Jan 2026 exemptions differ:
  `known_gaps.md` § Class A exemptions.
  - Why today's stocking is the cap: for outside groups' Class A exemptions, the Commission sets numbers
    "consistent with … historical stocking rates … to minimize impacts to the Class A wild trout population"
    (Operational Guidelines p. 119). By analogy, that supports capping PFBC's own stocked Class A sections
    at today's stocking.
- **Stability (optional):** `x_s ≥ (1−δ)·baseline_s`. The survey found 43% of anglers oppose dropping
  low-use waters (34% support).
- **Wild-trout lever (scenario):** `Σ_wild x_s ≤ (1−ρ)·Σ_wild baseline_s`, with ρ ∈ {0, .25, .5, 1}.

## Angler benefit
Decided 2026-09-27, built 2026-09-28 (`scripts/06`–`08`, table `demand`). Numbers marked *exploratory* come
from scratchpad prototypes of rejected alternatives; the rest are from the built tables. Values no source
gives are in `data/processed/parameters.csv`.

- **Unit: angler-days of stocked-trout fishing.** Both demand signals are angler-days per section and add up
  to the same statewide total (8.72M).
  - Why: a common unit makes the blend a fair mix and gives readable results (fish per angler-day,
    angler-days with a catch). Counting days rather than people gives avid anglers their weight:
    Northcentral anglers fish about 27 days a year, the other regions 19–22 (p115).
  - What it gives up: demand is fixed on today's map, and anything missing from the section set pushes its
    anglers onto our sections (see Assumptions no scenario tests).
- **Benefit per section:** `benefit_s = D_s × g(x_s / D_s)`, with `g(r) = 1 − e^(−r/k)`. `D_s` is the
  section's angler-days and `r` is stocked fish per angler-day.
  - **Why this structure,** rather than `g(x_s)` or `D_s × f(x_s)`: benefit scales with both fish and
    anglers (double both and benefit doubles), so a busy section needs proportionally more fish before it
    levels off. With `D_s × f(x_s)`, every section would level off at the same fish count, whether it has
    100 angler-days or 10,000.
  - **What it does:** the value of the next fish depends only on the section's fish per angler-day. With no
    other limits, the model gives every section the same fish per angler-day; caps, transport cost and
    wild-trout impact are what move it off that. So the structure matters more than the exact curve, which
    only sets how hard the model trades against those limits.
  - **Why this curve:** if each stocked fish is caught with probability p and catches fall at random across
    angler-days, the share of angler-days that catch at least one stocked trout is `1 − e^(−p·r)`. So benefit
    reads as **angler-days with a catch** (81% of anglers say catching trout matters, p140). It levels off (a
    day can only succeed once), and its slope at zero is finite, so the model may leave a costly section
    empty, consistent with the 300-fish minimum. Rejected: a straight line (fills the top sections to their
    caps and leaves hundreds empty), log and power curves (never level off, and power curves force fish into
    every section), and an expected-catch curve capped at the creel limit (almost straight at realistic
    stocking levels).
  - **k = 1 fish per angler-day,** swept 0.5 and 2. Every stream management option in the Operational
    Guidelines has the objective "one angler trip generated per trout stocked" (e.g. High Yield, p. 47). The
    guideline anchors the scale; the curve's shape is our assumption. Upgrade: k = 1 ÷ the share of stocked
    trout that get caught, if a PFBC return-to-creel figure turns up. The saturating ratio `r/(r + k)` is a
    one-run shape sensitivity (it penalizes overstocking less).
  - **In Gurobi:** each section's curve is piecewise linear, with breakpoints at r = 0, 0.25, 0.5, 1, 2, 4, 8
    (× `D_s`). Maximizing a concave curve keeps it an LP.
- **Demand:** `D_s = (1 − w) · proximity_s + w · preference_s`, with `w = 0.5`, swept 0 / 0.5 / 1.
  - The two signals estimate the same thing (where anglers fish), so they form one objective, not a fourth
    goal. The ends of the sweep read as "near-home anglers first" (w = 0) and "favorite waters first"
    (w = 1). Cost and impact are handled separately by the ε-constraints.
  - They measure slightly different things: proximity is where typical trips land (p93 asks about an average
    trip), while preference is where anglers' favorite waters are, and naming a favorite doesn't mean most
    days are spent there. w absorbs that.
- **Proximity demand ("band version")**, for every stocked section:
  1. **Anglers per Census block group** = 2020 population × the county's trout-permit angler rate: 2024
     trout + combo permits sold in the county (annual and multi-year), minus non-resident and tourist
     licenses, plus the county's population share of online resident permits, ÷ population. Permits because
     they must be bought every year (lifetime license holders still buy one) and are trout-specific. Limits
     (sales are by store county; online sales have no county): `known_gaps.md` § Angler numbers by county.
  2. **Angler-days** = anglers × the mean days fished for stocked trout in the block group's home region
     (p115). The survey publishes only the statewide mean (20.6 days); the open "over 50 days" band is set to
     105 days, the value that reproduces it.
  3. **Distance** = straight-line miles from the block group's center of population to the section's
     midpoint × 1.3, because the survey's travel distances are driving miles.
  4. **Allocation:** each block group sends its angler-days out by its home region's trip-distance bands
     (p93, "Don't know" dropped; pooled in-state, 38% of trips are within 10 mi and 25% at 10–20 mi). Within a
     band, the angler-days are split among the stocked sections in that band by length. A band with no
     section passes its share to the block group's other bands in proportion. The last band (more than
     150 mi) runs to the farthest block group–section pair in PA (about 416 road mi), so every section is
     reachable. Every angler-day is placed exactly once.
  - **Why not the simpler sum of population × P(travel ≥ d):** it counts each angler at every section within
    reach (about 58 times, *exploratory*), so it measures "how many people live within a long drive" and every
    section near a metro scores high: 46% of Bear Creek 3197_2's value came from people 50–100 mi away.
    Splitting anglers across sections fixes it: 55% of Bear Creek's demand then comes from within 10 mi
    (built, regional curves). Splitting each block group's anglers in proportion to P(travel ≥ d) didn't help, because
    P falls off too gently (14% at 50 mi, times millions of people).
  - **Regional curves,** by the angler's home region (the survey's regions are home regions too). Southeast
    anglers take 47% of trips within 10 mi, Southwest anglers 28% (mean 40 mi), so Philadelphia-area demand
    stays close to home and Pittsburgh-area demand spreads 30–100 mi out. The pooled in-state curve is the
    sensitivity. The survey has no county-level curve (about 33 in-state respondents per county).
  - **Length split:** a longer section has more water to fish and draws more anglers; survey preference is
    split the same way.
  - **The curve decides how local demand is:** a steep curve makes demand track where people live, which
    pulls the plan toward PFBC's population-density formula (see the caveat in Framing); a flatter one leaves
    more to cost, impact and the preference signal.
  - Columns: `prox_days` (default), `prox_days_pooled`, `prox_days_pop` (population only: every county at
    the state angler rate).
  - **Check:** each home region's share of angler-days that land inside its own region vs the survey's p85.
    Built: 74–84%, against 65–89% of each region's favorite waters in the home region ("Not sure of county"
    left out). Northcentral keeps less than the survey says (74% vs 89%) and the Southwest and Southeast more
    (76% vs 65%, 84% vs 72%): the regional curves are the same for every block group in a region, whether it
    sits at the region's center or its edge.
- **Preference demand** (2023 survey, p76–83):
  - A water's share of anglers = its % ÷ the sum of all mentions (about 220%: up to three waters each, plus
    "Other" and "Don't know"); "<0.5%" counts as 0.25%. That share × statewide angler-days is split across the
    water's stocked sections by length. Kettle Creek: 3% → about 1.4% of anglers → 6.9× what proximity
    gives its sections.
  - The share we can't place ("Other", "Don't know", lakes, unmatched names, "other county" rows) is spread
    like `prox_days`, so preference also sums to the statewide total.
  - Ambiguous names are resolved with the by-home-region table (p78–83): Elk Creek is Erie's (Northwest 10%),
    Bald Eagle Creek mostly Centre's, and French Creek splits between Chester's and Erie's. The rest go to the
    review list. Built: 63.1% of all mentions land on 160 stocked rivers, and 16 names (6.4%) wait in
    `logs/07_survey_crosswalk_review.csv`, spread like proximity until decided (`known_gaps.md`).
  - **Per-mile flag:** a water whose preference angler-days per stocked mile exceed the state's highest
    proximity per mile is flagged for review, not capped. Only the Youghiogheny is flagged: all its preference lands on the 1.1 mi tailwater 1327_1. It keeps its full share (decision
    2026-09-27): the dam tailwater is among the most heavily fished spots in the state and is open
    year-round.
- **Favorite boost: tested and dropped (2026-09-27).** Boosting favorite waters within each distance band
  until each draws its survey share would honor both survey facts in one number. Remote favorites needed
  boosts of ×60–1,500 (Kettle Creek ×220), which took about 95% of the demand of small streams next to them
  (e.g. Cross Fork and Long Run in Potter and Tioga), and a version limited to trips of 30+ mi couldn't reach
  the targets at all. The two survey facts conflict for remote waters, so the blend is the honest merge. The
  ratio of preference draw to proximity draw is kept as a **destination index** for the report: about 1× =
  popular because many people live nearby (Tulpehocken 1.0), 5–7× = a true destination (Pine Creek 5.0,
  Kettle Creek 6.9) (`demand.destination_index`, `figure_ideas.md`).
- **Access is in the cap, not in demand** (decision 2026-09-27). PFBC's access rating (`use_potential`: road
  frontage, parking, ownership) limits how many anglers a section holds, so it sets the density bound (see
  Constraints). It isn't a demand weight: no source says how much parking shifts where anglers go, and the
  only number to hand, PFBC's High-to-Good stocking ratio, would make demand partly repeat PFBC's formula
  and the "stocking vs demand" comparison circular. The preference signal already reflects where anglers
  actually fish, access included. An access-weighted length split is an idea in `scenarios_and_extensions.md`.
  PFBC's access-point layer isn't used: the rating is measured per section and covers the same thing.
- **Other benefit inputs (optional):** special-regulation waters, catch importance (p140: 81% say catching a
  trout matters), and thermal suitability (fish in warm water die by summer, so benefit falls). On
  catch-and-release and delayed-harvest waters a stocked trout can be caught more than once, which in the
  benefit curve would mean a smaller k there. Collected in Prompt 6; whether they enter the score is an open
  question.

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
- **Baseline assignment:** PFBC's schedule names the hatchery for every 2026 event
  (`section_schedule.primary_hatchery`; 49 sections get fish from two). Proposed, not yet decided with Gavin:
  cost the baseline from the scheduled hatcheries (split by event share), with nearest hatchery as the
  sensitivity. The nearest-hatchery version understates today's cost: in a 3-county sample only 10 of 54
  sections were served by their nearest hatchery. The model still chooses its own assignment.
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
  - 25 sections coded E ("no wild trout") are on the natural-reproduction list.
  - 111 sections coded D are not on it.
- **Score versions to explore:** each is a different definition of the goal, and all are reported in
  plain units.
  1. **Simple:** fish stocked on any wild-trout water. `w_s` = 1 if `nat_repro_flag` or biomass B–D,
     else 0. Unit: "fish on wild-trout water". Easiest to explain; start here.
  2. **Weighted:** `w_s` = biomass weight (B=3, C=2, D=1, E=0), +1 if natural reproduction, +2 if wild
     brook trout, and optionally +1 if thermally marginal (upgrade: EcoSHEDS max 30-day mean ≥ 21 °C).
  3. **Partial overlap:** scale `w_s` by the share of the section on natural-reproduction water
     (`environment.nat_repro_share`, river miles). Most flagged sections are almost fully on it (496 of 531
     at ≥ 90%), but a few large ones aren't: Kettle Creek 3351_9 (5,900 fish, 1%), Sugar Creek 1898_4
     (11,620 fish, 11%). Fish on natural-reproduction water in 2026: 1.08M by flag, 1.00M weighted by share.

  Weights within a score are a judgement call, so show that the conclusions hold across versions 1–2.
- **The survey supports the goal:** 58% of anglers support moving stocking off quality wild trout waters
  to nearby spots, and 16% oppose. The trade-off curve shows how much angler benefit or cost that move
  takes.
- **The "wild-trout lever" constraint** (`Σ_wild x_s ≤ (1−ρ)·baseline`) is just an ε-constraint on this
  objective's simple version.
- **Measuring overlap:** use shared river miles (`SecUpperLi`/`SecLowerLi` on the same RFP_WaterID), never
  a plain intersect. The Class A layer also has a `TroutBioma` (biomass) field that could scale `w_s`.
  - River miles only, for natural reproduction too (assumption, decision 2026-09-27): 531 sections flagged.
    Some Natural Reproduction records' river miles are shorter than their own line, so 18 sections are
    missed (`known_gaps.md` § Natural Reproduction river miles shorter than the line); a sensitivity run
    flags them back.
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
    `D_s × g((x_s + c_s) / D_s)`. With diminishing returns, PFBC fish shift toward waters co-ops
    don't cover.
  - Co-op fish have no PFBC trucking cost, and they are constant in the impact score (report only).
  - Use only listings that pass manual review; drop the stale ones on wild-trout water.
  - The per-acre cap applies to PFBC fish only, per policy.
  - `c_s` needs counts: a records request to the Cooperative Nursery Unit (sponsors report every July),
    or an assumed per-nursery total split evenly across its waters.
  - Caveat: this assumes co-ops keep their waters when PFBC shifts fish. Clubs plan after PFBC's schedule;
    modeling their reaction would be a leader-follower (bilevel) problem, out of scope.

## Assumptions no scenario tests
Decided assumptions that no scenario varies. List them in the report's limitations, and add a scenario to
`docs/scenarios_and_extensions.md` if one could change the results. Data-handling choices (duplicate rows,
null counts as 0, overlap by river miles, length choice) are in `docs/data_methods.md` with their checks.
- The 17 stocked Class A sections are capped at today's stocking, never excluded (an "exclude all Class A"
  scenario would test it). See Constraints.
- Benefit scales with anglers: `D_s × g(fish per angler-day)`. The curve's scale k and one alternative shape
  are swept; the structure isn't. See Angler benefit.
- Survey preference, and proximity demand within a distance band, are split across sections by length. See
  Angler benefit.
- Fish count only where they're stocked. Stocked trout drift downstream, so a tailwater like Youghiogheny
  1327_1 also serves the reaches below it; the model credits only the stocked section (extension idea
  "Downstream drift").
- Demand is fixed on today's section map: the anglers of a section that gets no fish don't move to other
  sections. Modeling that would need a choice model, where demand depends on the plan.
- Only Pennsylvania residents create demand (out-of-state anglers are left out, decision 2026-09-27).
  Sections in neighboring states aren't in the set, so block groups near the border send all their anglers
  to PA sections. Lakes aren't in the set either (~20% of PFBC's adult trout), so lake anglers are pushed
  onto streams.
- License sales by store county stand in for anglers by home county (`known_gaps.md` § Angler numbers by
  county).
- Trip distances are per angler (p93), not per day. If avid anglers fish closer to home, trips are more local
  than modeled; the survey doesn't cross-tabulate days by distance.
- The survey describes 2022 fishing and is applied to the 2026 sections.
- Biomass letter class is the only measure of wild-trout abundance; numeric biomass is only in scattered
  biologist reports (`docs/env_research.md` § 5).
- Hatchery supply and the baseline assignment come from one year's planned schedule (2026), and supply
  credits each section's fish equally to its scheduled events (`known_gaps.md` § Stocking schedule).
- Shipments are direct hatchery → section legs, with no multi-stop routes. See Transport cost.
- Transit mortality is a flat 1%, not scaled by distance (`docs/transport_research.md` § 3).
- Gavin's road distances are used as given.
- Hatchery supply is scaled to the stream total, ~83% of PFBC's adult trout (`docs/known_gaps.md`).

## Report hooks
- PFBC's 2025–29 trout plan (Obj. 9.1) says allocation rates "need to be reviewed."
- The survey found 80% support extra stocking on high-use waters.
- 79% of stocked-trout anglers say fishing near home is important (p95), which supports proximity demand.
- PFBC's own 2005 study of 28 stocked stream sections found 0.63 angler trips per trout stocked over the first
  eight weeks of the season, ranging from 0.07 to 2.76 (Operational Guidelines pp. 63–64, citing Greene et al.
  2006). That's below the guidelines' one-trip-per-trout objective, and a 40-fold spread between sections is
  exactly what reallocation works on.

## Open questions
- Are lakes decisions or fixed? (~20% of fish, 131 stocked waterbodies, no per-lake counts found in GIS yet.)
- One annual decision, or split by season (pre-season / in-season / fall-winter)?
- Include golden and brood in the model's fish total? (PFBC's TotalAdultStocked_minusBrood is brook + brown +
  rainbow only.)
- Which optional inputs (special regulations, catch importance, thermal suitability) enter the
  benefit score, beyond being collected in Prompt 6?
- Transport cost: charge each section for the visit's detour, on top of the hatchery → section haul
  (team discussion 2026-09-27)? Still undecided. Two versions are built (`section_schedule`, `clusters`,
  2026-09-28):
  - **Geographic (the earlier preference):** detour_s = 2 × `detour_nn_mi` (nearest stocked section, road
    miles) × 2 visits × $1.90/truck-mile, added as detour_s·y_s.
  - **Run clusters (proposed):** sections PFBC stocks on the same runs form a cluster; `detour_mi` is the
    distance to the nearest section in the same cluster (0 for the 103 singletons). Richer version: a binary
    y_c per cluster with x_s ≤ cap_s · y_c and a trip charge from `cluster_mi`.
  - Caveat for y_c: the default rule (share ≥ 0.5) chains clusters up to 18 sections and 119 route-miles,
    more than one truck's run (at most 7 sections). The strict rule (> 0.5, up to 7 sections) fits a per-trip
    charge better; the default fits the detour.
  - Real truck routing stays out of scope.
