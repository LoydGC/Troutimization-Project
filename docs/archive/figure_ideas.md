# Figure ideas

Figures and report tables worth making, with the data each needs. This is the running list: add ideas as they
come up. The analyses behind them live elsewhere (scenarios in `scenarios_and_extensions.md`, the model in
`model_design.md`); this file only tracks what to show. Finished figures go in `outputs/figures/`.

Last updated: 2026-10-04

**Status legend:** **ready** = data is in `data/processed/` now · **Prompt 6** = needs the demand table ·
**model** = needs model runs. Numbers marked *exploratory* come from scratchpad checks on 2026-09-27; confirm
them once the pipeline builds the data.

## How PFBC allocates today

| Figure | What it shows | Data | Status |
|---|---|---|---|
| Fish per acre by population class | PFBC's formula stocks Metro sections at ~3× the rate of Rural ones (2026: Metro 216, Urban 125, Suburban 111, Rural 66 fish/acre) | sections (`pop_density`, `total_2026`, `area_acres`) | ready |
| Fish per acre by access rating | PFBC stocks High-access sections (road frontage, parking, public banks) at about twice the rate of Good ones (2026 medians 163 vs 73 fish/acre at class-top widths; 216 High, 800 Good, 6 Low). Pairs with the population figure: access is the part of PFBC's formula our cap keeps | sections (`use_potential`, `total_2026`, `area_acres`) | ready |
| Fish follow streams, not people | County map or bars: share of population vs trout permits vs 2026 fish. The 48 rural counties hold 26% of people, 44% of resident anglers and 70% of 2026 stream fish | sections + county anglers table | Prompt 6 |
| Stocking vs demand | Scatter of fish per acre against proximity demand per mile, colored by PFBC's population class. Overall rank correlation 0.39, but about 0 within each class (−0.05 to 0.05): PFBC's allocation sees demand only through its four population classes. Not chance (5,000 shuffles never pass 0.11) and not PFBC straying from its formula: the Table 18 rate itself gives 0.38, and the population class alone 0.72, so biomass, width and access dilute the demand signal. Metro sections get 3.4× the fish per acre of rural ones for 6× the angler-days per mile, so fish per angler-day runs 0.25–0.26 in the Southeast and Southwest vs 0.54 in the Northcentral (section medians, stream angler-days, rebuilt 2026-10-04) | sections + demand | Prompt 6 |

## Anglers and demand

| Figure | What it shows | Data | Status |
|---|---|---|---|
| How far anglers travel | The p93 trip-distance bands as curves, one per home region (Southeast anglers stay closest, Southwest travel farthest) | angler survey p93 | ready |
| Anglers per 1,000 residents by county | Map of the trout-permit angler rate: rural counties 1.0–2.7× the state rate (median 1.9×, 10th–90th percentile), Philadelphia and Delaware under a third | county anglers table | Prompt 6 |
| Where a section's anglers come from | Methods figure for Bear Creek 3197_2: counting everyone within reach puts 46% of its demand 50–100 mi away; splitting anglers across sections (band version, regional curves) puts 31% within 10 road mi, 54% within 20 and 16% at 50–100 mi (the first number is *exploratory*, from block groups) | demand build | Prompt 6 |
| Destination index | Map of each top favorite's survey draw ÷ its proximity draw: ~1× = popular because people live nearby (Tulpehocken 1.1, Yellow Breeches 1.3), 6–10× = a true destination (Pine Creek 6.6, Kettle Creek 10.5); per river in `logs/08_demand_waters.csv` | demand, survey crosswalk | Prompt 6 |
| Road barriers in demand | Map of each section's proximity demand on road miles ÷ on straight-line miles × 1.3: sections behind rivers and ridges lose up to 60% (East Licking Creek, Conoy and York's Fishing Creek across the Susquehanna), sections that gain a city inside 10 road mi rise up to 2.6×. Shows why measured road miles matter at short range (road ÷ straight-line 1.5 under 5 mi) | demand vs the block-group build (old side rebuilt from the raw `CenPop2020_Mean_BG42.txt` and the previous `08_demand.py` in git) | needs that rebuild |
| Favorite waters close to home | Share of each home region's favorite-water mentions inside its own region: 67% (Southwest) to 88% (Northcentral) | angler survey p85 + `county_region.csv` | ready |
| The benefit curve | Methods figure: g(r) = 1 − e^(−r/k) for k = 0.5, 1 and 2, with the state's typical fish per angler-day marked, showing where the next fish still pays and where it doesn't | `parameters.csv` | ready |
| Angler-days per stocked trout | By region, against PFBC's "one angler trip per trout" yardstick (statewide 3.3 angler-days per 2026 stream trout; lake fish would lower it) | demand + sections | Prompt 6 |

## Model results

| Figure | What it shows | Data | Status |
|---|---|---|---|
| Trade-off curves | Benefit vs cost and benefit vs impact, with PFBC's 2026 plan as a point (inside or on the curve) | ε-sweeps | model |
| Scorecard table | Each goal-swap scenario × benefit, cost, impact | scenario runs | model |
| Robust changes map | Sections that gain or lose fish in every scenario vs only some | scenario runs | model |
| Near-home vs favorites | How the plan shifts as the blend weight w goes from 0 (near-home anglers) to 1 (favorite waters) | w sweep | model |
