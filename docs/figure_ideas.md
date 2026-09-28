# Figure ideas

Figures and report tables worth making, with the data each needs. This is the running list: add ideas as they
come up. The analyses behind them live elsewhere (scenarios in `scenarios_and_extensions.md`, the model in
`model_design.md`); this file only tracks what to show. Finished figures go in `outputs/figures/`.

Last updated: 2026-09-27

**Status legend:** **ready** = data is in `data/processed/` now · **Prompt 6** = needs the demand table ·
**model** = needs model runs. Numbers marked *exploratory* come from scratchpad checks on 2026-09-27; confirm
them once the pipeline builds the data.

## How PFBC allocates today

| Figure | What it shows | Data | Status |
|---|---|---|---|
| Fish per acre by population class | PFBC's formula stocks Metro sections at ~3× the rate of Rural ones (2026: Metro 216, Urban 125, Suburban 111, Rural 66 fish/acre) | sections (`pop_density`, `total_2026`, `area_acres`) | ready |
| Fish per acre by access rating | PFBC stocks High-access sections (road frontage, parking, public banks) at about twice the rate of Good ones (2026 medians 163 vs 73 fish/acre at class-top widths; 216 High, 800 Good, 6 Low). Pairs with the population figure: access is the part of PFBC's formula our cap keeps | sections (`use_potential`, `total_2026`, `area_acres`) | ready |
| Fish follow streams, not people | County map or bars: share of population vs trout permits vs 2026 fish. Rural counties hold ~26% of people, ~50% of permits and ~69% of fish (*exploratory*) | sections + county anglers table | Prompt 6 |
| Stocking vs demand | Scatter of fish per acre against proximity demand per mile; PFBC's allocation barely tracks where anglers live (rank correlation ~0.3, *exploratory*) | sections + demand | Prompt 6 |

## Anglers and demand

| Figure | What it shows | Data | Status |
|---|---|---|---|
| How far anglers travel | The p93 trip-distance bands as curves, one per home region (Southeast anglers stay closest, Southwest travel farthest) | angler survey p93 | ready |
| Anglers per 1,000 residents by county | Map of the trout-permit angler rate: rural counties 1.5–3× the state rate, metro counties well below (*exploratory*) | county anglers table | Prompt 6 |
| Where a section's anglers come from | Methods figure for Bear Creek 3197_2: counting everyone within reach puts 46% of its demand 50–100 mi away; splitting anglers across sections puts 44% within 10 mi (*exploratory*) | demand build | Prompt 6 |
| Destination index | Map of each top favorite's survey draw ÷ its proximity draw: ~1× = popular because people live nearby (Tulpehocken), ~10× = a true destination (Kettle Creek) (*exploratory*) | demand, survey crosswalk | Prompt 6 |
| Favorite waters close to home | Share of each home region's favorite-water mentions inside its own region: 67% (Southwest) to 88% (Northcentral) | angler survey p85 + `county_region.csv` | ready |
| The benefit curve | Methods figure: g(r) = 1 − e^(−r/k) for k = 0.5, 1 and 2, with the state's typical fish per angler-day marked, showing where the next fish still pays and where it doesn't | `parameters.csv` | ready |
| Angler-days per stocked trout | By region, against PFBC's "one angler trip per trout" yardstick (statewide roughly 3 days per stream trout, *exploratory*, rough) | demand + sections | Prompt 6 |

## Model results

| Figure | What it shows | Data | Status |
|---|---|---|---|
| Trade-off curves | Benefit vs cost and benefit vs impact, with PFBC's 2026 plan as a point (inside or on the curve) | ε-sweeps | model |
| Scorecard table | Each goal-swap scenario × benefit, cost, impact | scenario runs | model |
| Robust changes map | Sections that gain or lose fish in every scenario vs only some | scenario runs | model |
| Near-home vs favorites | How the plan shifts as the blend weight w goes from 0 (near-home anglers) to 1 (favorite waters) | w sweep | model |
