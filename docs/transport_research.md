# Transport cost inputs for the stocking model: research notes

Web research done 2026-09-26 for the transport objective in `docs/modeling_notes.md`
(`cost[h,s] = 2 × est_road_mi × cost_per_truck_mile / fish_per_load`). Distance is out of scope here.
Every number links to its source. *Unverified* means no official or primary source confirmed it. *Derived*
means our own arithmetic, which is shown.

## Summary

- **Running a stocking truck costs about $1.90 per truck-mile ($1.25–3.10).** The build-up is fuel $0.60,
  repair $0.22, tires $0.05, insurance $0.05, and crew $1.00. About 45% scales with miles and 55% with
  time. This matches ATRI's 2025 heavy-truck average ($2.34/mi) once truck and trailer payments are taken
  out ($1.94/mi).
- **One PFBC truck carries at most ~3,500 adult trout**, about 2,000 lb at 0.58 lb per fish
  ([PFBC 2013](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/education/activitiesandeducationportal/play-2013-pfbcthenandnow_allpages.pdf);
  [CBF 2023](https://www.cbf.org/stories/a-trouts-journey-behind-the-scenes-of-pennsylvanias-fish-hatcheries/)).
  Not every trip is full, so use **2,500 fish per load (1,500–3,500)**. Check it against the fleet's
  reported ~300,000 miles a year.
- **A 50-mile one-way haul costs about $0.08 per fish ($0.04–0.21).** Statewide that comes to about $0.6M a
  year, or $0.18 per adult trout. That is roughly 4% of PFBC's all-in cost per stocked trout (~$4.20 in
  2025 dollars), or about 7% with truck capital. Trucking is a real cost but a small one: the hatcheries,
  not the trucks, are the scarce resource.
- **Few fish die in transit, and the loss doesn't grow with distance at PA haul lengths.** A Minnesota test
  found 1.6% mortality within 48 h from hauling plus stocking. Use a **flat 1% (0–2%)**, or leave it out.
- **Loading limits aren't binding in PA.** Piper et al. (1982) allow up to 2.5–3.5 lb/gal for 8–11-inch
  trout on 8–10-hour hauls, minus 5.6% per °F of warmer water. PA hauls take a few hours, so the model
  needs no maximum-distance rule.
- **Capital is a fixed cost, not a per-mile one.** No PFBC truck price was found. Our *unverified*
  assumption is ~$200k per truck ($120–300k). The fleet averaged ~20 years old in 2020. Three new trucks
  arrived in 2024 and 7 more were expected in 2025. Leave capital out of `cost_per_truck_mile` and test it
  as a sensitivity (+~$1.00/mi).
- **Each section is stocked about twice a year** (1 preseason + 1–2 in-season; Operational Guidelines
  Table 44). Don't multiply the per-fish cost by this: a truck splits one load across several sections. A
  per-stop cost is an optional upgrade, and it is small (~$0.02 per fish).

## Proposed parameters (rows for `data/processed/parameters.csv`)

| parameter | value | units | low | high | source |
|---|---|---|---|---|---|
| cost_per_truck_mile | 1.90 | $/truck-mile (operating, excl. capital) | 1.25 | 3.10 | Derived bottom-up (§1). Cross-check: ATRI 2025 $2.336/mi minus $0.40 truck/trailer payments = $1.94 ([ATRI 2026](https://truckingresearch.org/2026/07/new-atri-report-details-accelerating-costs-and-low-profitability-despite-cuts/), [FleetOwner](https://www.fleetowner.com/operations/article/55392569/atri-report-breaks-down-class-8-truck-operating-costs-by-region-and-expense-category)) |
| diesel_price | 3.90 | $/gal | 3.50 | 4.54 | [EIA](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=pet&s=emd_epd2d_pte_r1y_dpg&f=a) Central Atlantic (PADD 1B) 2025 annual avg; high = 2023 avg; low = assumption (possible tax exemption for state fleets, *unverified*) |
| truck_mpg_loaded | 6.5 | mi/gal diesel | 5 | 8 | assumption, anchored on [AFDC](https://afdc.energy.gov/data/10310) (FHWA VM-1): Class 8 truck 6.3, refuse truck 5.2, delivery truck 7.2 mi/GGE |
| crew_cost_per_hour | 40 | $/truck-hour, wages + benefits | 24 | 64 | assumption. PFBC Fish Culturist 1 pays $16.45–24.19/h ([2022 posting](https://www.governmentjobs.com/careers/pabureau/jobs/3594711/fish-culturist-1)) plus benefits at ATRI's 26% ratio. Low = 1 person, high = 2-person crew at $32/h |
| avg_truck_speed | 40 | mph | 30 | 50 | assumption, used to turn hourly costs into per-mile costs |
| fish_per_load | 2,500 | adult trout per truck trip (effective average) | 1,500 | 3,500 | assumption. Max 3,500 per truck ([PFBC 2013](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/education/activitiesandeducationportal/play-2013-pfbcthenandnow_allpages.pdf)). PFBC tracks how many trips run full ([Trout Plan 2020–24](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/reports/troutplan2020.pdf), Issue 25). Calibrate (§2) |
| truck_capacity_max | 3,500 | adult trout per truck | 2,900 | 3,500 | PFBC 2013 (10-inch fish); CBF 2023 (11-inch fish). Low is derived for 11-inch fish (§2) |
| lb_per_fish | 0.58 | lb | 0.51 | 0.67 | [PFBC 2026 release](https://www.pa.gov/agencies/fishandboat/newsroom/2026-trout-stocking-schedules-now-available-jan2026); low = NJ Pequest 2021 ([304,586 lb / 597,150 fish](https://nj.gov/dep/fgw/pdf/fwfisheries/trtmtg22_hatchery_production.pdf)); high = Huntsdale 370,000 lb / 550,000 adults (CBF 2023; its lb include fingerlings) |
| lb_per_load_max | 2,030 | lb fish per truck | 1,680 | 2,030 | derived: 3,500 × 0.58; low = 2,900 × 0.58 |
| max_loading_density | 3.0 | lb fish per gal water | 2.5 | 3.5 | [Piper et al. 1982](https://archive.org/details/fishhatcherymana00pipe) p. 361: 8–11-inch trout, 8–10 h haul, "ideal conditions" (a ceiling, not a target) |
| loading_temp_adjust | 5.6 | % load change per °F | | | Piper et al. 1982 p. 356 (cut the load 5.6% per 1 °F warmer) |
| transport_mortality_pct | 1.0 | % of fish loaded | 0 | 2 | assumption, anchored on 1.6% at 48 h after hauling and stocking ([Cunningham & Anderson 1992](https://www.lrl.mn.gov/docs/pre2003/other/920576.pdf), MN DNR IR 421) |
| truck_capital_cost | 200,000 | $ per truck (chassis + insulated tank + aeration/O2) | 120,000 | 300,000 | assumption, *unverified*: no PFBC price found. Michigan spent ~$1.7M on 18 units, ~$94k each, older and partly refurbished ([MI DNR](https://www.michigan.gov/dnr/managing-resources/fisheries/hatcheries/fish-transportation)) |
| truck_life_years | 20 | years | 12 | 25 | PFBC fleet averaged ~20 years old in 2020 (Trout Plan 2020–24, Issue 25); Michigan retired a unit after 20 years (MI DNR) |
| truck_life_miles | 200,000 | miles | 120,000 | 300,000 | derived: ~10,000 mi/truck/yr (300,000 fleet miles ÷ ~30 trucks, fleet size *unverified*) × life years |
| capital_cost_per_truck_mile | 1.00 | $/truck-mile | 0.40 | 2.50 | derived: capital ÷ life miles. **Sensitivity only** (§7) |
| fleet_miles_per_year | 300,000 | truck-miles/yr | 200,000 | 300,000 | "almost 300,000 miles" to stock 3.2M trout (CBF 2023, not found in a PFBC document). Low = assumption, since the figure may include non-trout trips |
| fleet_size | 30 | stocking trucks | 20 | 40 | derived, *unverified* (§4) |
| stockings_per_section_per_year | 2 | stocking visits per section | 1 | 4 | [Operational Guidelines](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/about-us/agencyoverview/species-mgmt-plans/operationguidelinestroutmgt.pdf) Table 44: 1 preseason + 1–2 in-season, tailwaters 2+ in-season, plus optional fall/winter |
| cost_per_stop (upgrade) | 20 | $ per stocking visit | 10 | 40 | assumption: 0.5 h (0.25–1 h) × $40/h crew time at the stream |
| cost_per_fish_road_mile | 0.00152 | $ per fish per one-way road mile | 0.00071 | 0.00413 | derived: 2 × cost_per_truck_mile ÷ fish_per_load (the only product the model needs) |

## Worked example: 50 road miles one way

`cost_per_fish = 2 × 50 × cost_per_truck_mile / fish_per_load / (1 − mortality)`

| case | $/truck-mile | fish/load | mortality | per truckload | **per fish** |
|---|---|---|---|---|---|
| central | 1.90 | 2,500 | 1% | 100 × 1.90 = $190 | 190 / 2,500 / 0.99 = **$0.077** |
| low cost | 1.25 | 3,500 | 0% | 100 × 1.25 = $125 | 125 / 3,500 = **$0.036** |
| high cost | 3.10 | 1,500 | 2% | 100 × 3.10 = $310 | 310 / 1,500 / 0.98 = **$0.21** |
| central + capital | 1.90 + 1.00 | 2,500 | 1% | $290 | **$0.117** |
| high + capital | 3.10 + 2.50 | 1,500 | 2% | $560 | **$0.38** |

The central case is about $0.13 per lb of fish (0.077 / 0.58). Distance moves the cost linearly: 10 miles
costs ~$0.015 per fish, and 150 miles ~$0.23.

**Statewide check (derived):** 300,000 truck-miles × $1.90 = $570k a year. Spread over 3,143,145 adult trout
(FY2023–24, PFBC 2024 Annual Report) that is **$0.18 per fish**. Adding capital (30 trucks × $200k ÷ 20
years = $300k a year) gives $870k, or $0.28 per fish.

## 1. Cost per mile of operating a stocking truck

**What the truck is.** PFBC stocking trucks are described as 25-foot, "14-ton" white tankers
([CBF 2023](https://www.cbf.org/stories/a-trouts-journey-behind-the-scenes-of-pennsylvanias-fish-hatcheries/)).
Hatchery staff drive them and need a CDL for vehicles of 26,000 lb or more
([Fish Culturist 1 posting](https://www.governmentjobs.com/careers/pabureau/jobs/3594711/fish-culturist-1)).
Heavy-truck benchmarks are therefore a fair fit. Unlike a for-hire carrier, though, PFBC pays no trailer
payments, few tolls, and likely no commercial insurance (a state fleet is probably self-insured, *unverified*).

**Benchmark.** ATRI's 2025 average for Class 8 trucks is $2.336/mi
([ATRI 2026](https://truckingresearch.org/2026/07/new-atri-report-details-accelerating-costs-and-low-profitability-despite-cuts/)),
and $2.52/mi in the Northeast
([FleetOwner](https://www.fleetowner.com/operations/article/55392569/atri-report-breaks-down-class-8-truck-operating-costs-by-region-and-expense-category)).
The line items (FleetOwner's summary of the ATRI report), all in $/mi:
- fuel 0.48
- truck payments 0.28 and trailer payments 0.12
- repair and maintenance 0.22
- insurance 0.11
- tires 0.05
- tolls 0.043
- permits 0.008
- driver wages 0.818 and benefits 0.210

**Bottom-up for a PFBC truck ($ per truck-mile):**

| component | central | low | high | scales with | basis |
|---|---|---|---|---|---|
| fuel | 0.60 | 0.44 | 0.91 | miles | diesel $3.90 ÷ 6.5 mpg; low $3.50 ÷ 8; high $4.54 ÷ 5 |
| repair & maintenance | 0.22 | 0.15 | 0.40 | miles | ATRI; high allows for an old fleet (assumption) |
| tires | 0.05 | 0.04 | 0.06 | miles | ATRI |
| insurance, permits | 0.05 | 0 | 0.12 | time/fixed | ATRI 0.12, reduced for a state fleet (assumption) |
| crew | 1.00 | 0.60 | 1.60 | time | $40 / $24 / $64 per hour ÷ 40 mph. ATRI's driver pay is $1.03/mi ($1.10 in the Northeast) |
| **total** | **1.92 → 1.90** | **1.23 → 1.25** | **3.09 → 3.10** | | |

- **Miles vs time.** Fuel, repairs and tires scale with miles. Crew pay and insurance scale with time,
  converted here at an assumed 40 mph. Crew time spent loading at the hatchery and at each stream stop is
  *not* in the per-mile figure (see `cost_per_stop`, §6).
- **Oxygen and aeration.** Pumps, aerators and bottled or liquid oxygen are minor extras. PFBC's liquid
  oxygen bill for hatcheries *and* stocking combined was $276k–353k a year in FY2007–09
  ([LBFC 2010](https://www.legis.state.pa.us/WU01/LI/TR/Reports/2010_0083R.pdf) p. 52). Leave them out.
- **Consistency check (derived).** The Bureau of Fisheries spent $733k on vehicle fuel in FY2007–08
  (LBFC 2010 p. 52). Stocking trucks at 300,000 mi ÷ 6.5 mpg ≈ 46,000 gal × $3.99 (2008 PADD 1B diesel) ≈
  $184k, about a quarter of that bill. That is plausible for a bureau that also runs pickups, boats and
  hatchery equipment.

## 2. Capacity

**PFBC-specific**
- "A Maximum of 3,500 10-inch Trout per Truck"
  ([Pennsylvania Angler & Boater, Sept/Oct 2013, p. 50](https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/documents/education/activitiesandeducationportal/play-2013-pfbcthenandnow_allpages.pdf)).
  CBF (2023) describes a Huntsdale truck's "payload of 3,500 trout".
- The [Inquirer (2025)](https://www.inquirer.com/news/pennsylvania/trout-fishing-pennsylvania-stock-20250405.html)
  instead says "approximately 3,500 pounds of fish". That would be ~6,000 fish and conflicts with the two
  sources above, so we treat it as *unverified*.
- Today's fish average 11 inches and 0.58 lb
  ([PFBC 2026](https://www.pa.gov/agencies/fishandboat/newsroom/2026-trout-stocking-schedules-now-available-jan2026)),
  so a full load is ~2,000 lb.
- **Derived for 11-inch fish.** Piper's rule is that allowable pounds scale with length. Weight scales with
  length³. So the fish count scales by 1.10 / 1.33, and 3,500 → ~2,900 fish. The 2023 CBF figure of 3,500
  suggests the newer trucks hold that many.
- Trucks have multiple compartments "so that we can separate different species and sometimes different
  sizes" ([Butler Eagle 2025](https://www.butlereagle.com/20250226/how-does-pennsylvania-stock-its-waters-with-trout/)).
- **Fleet renewal.** Three new trucks with "double walled insulated aluminum" tanks, built to hold water
  temperature and aeration "over long distances", came in 2024, and 7 more were expected in 2025 (PFBC 2024
  Annual Report p. 8).
- **Tank size: not found.** Derived guess: ~2,000 lb at a comfortable 1.4–2 lb/gal points to a
  ~1,000–1,500 gal tank. Piper notes an empty truck with a 1,250-gal tank weighs 14,000 lb, which fits a
  "14-ton" loaded truck. *Unverified.*

**Tank volumes elsewhere**
- Piper (1982, p. 351): 300–700 gal, averaging 450 gal. 1,200-gal tanks are "occasionally" used for
  catchable trout.
- Michigan: 18 units of 300–3,200 gal. The "standard" unit is 1,200 gal in 4 × 300-gal compartments
  ([MI DNR](https://www.michigan.gov/dnr/managing-resources/fisheries/hatcheries/fish-transportation)).
- Wyoming: 300-, 650- and 2,400-gal units carrying 300–800 lb and 900–4,000 lb loads
  ([WGFD](https://wgfd.wyo.gov/Ask-Game-and-Fish/span-id-docs-internal-guid-d598e769-7fff-3d71-e959)).
- Idaho: 2,300–2,500-gal tanks
  ([IDFG HGMP 2002](https://www.fws.gov/sites/default/files/documents/Rainbow%20Trout%20Stocking%20HGMP.pdf)).

**Safe loading density** ([Piper et al. 1982](https://archive.org/details/fishhatcherymana00pipe), pp. 356–361)
- **Ceiling.** "Under ideal conditions, the maximum load of 8-11-inch rainbow trout is 2.5-3.5 pounds per
  gallon of water for 8 to 10 hours." Brook and brown trout load the same.
- **Size.** Allowable pounds rise in proportion to fish length.
- **Temperature.** Cut the load ~5.6% per 1 °F warmer, and raise it the same amount per 1 °F cooler. A load
  of 1,000 lb at 52 °F becomes 722 lb at 57 °F.
- **Duration.** The rates hold for 8–10 hours. (The 12-h and 16-h load cuts that
  [FAO](https://www.fao.org/4/af000e/AF000E05.htm) lists are catfish guidance. FAO's "3–3.1 kg/litre" for
  trout is a unit error for Piper's 2.5–3.5 lb/gal, which is ~0.3–0.4 kg/L.)
- **Agency practice is often lower.** Idaho's guideline is 0.5 lb/gal for ~16-fish/lb rainbows (IDFG
  HGMP).

**Multi-stop trips**
- Compartments exist partly so one trip can stock several sites (Piper p. 351).
- PFBC's Trout Plan 2020–24 (Issue 25) aims to "analyze … the percentage of trips made with distribution
  trucks at full capacity and reconfigure stocking assignments and schedules to maximize full capacity
  truck trips". So partial loads happen.
- For Class 5 lakes, the allocation "should not exceed the hauling capacity of one distribution unit"
  (Operational Guidelines p. 96). PFBC plans in truckloads.

**Choosing `fish_per_load`**
- The value is an effective average: 2,500 (1,500–3,500).
- **Calibration check (recommended, derived).** Once distances exist:
  `F_eff = Σ_s 2 · d_road(nearest h, s) · x_s / 300,000`, summed over all 3.14M adult trout. If only the
  2.60M stream fish are modelled, scale the 300,000 miles by 2.60/3.14.
  - Example: a fish-weighted mean haul of 80 road miles gives F_eff ≈ 1,700. A 120-mile mean gives ≈ 2,500.
  - The 300,000 miles may include other trips, and real assignments aren't always the nearest hatchery.
    Both push F_eff low, so treat it as a lower bound.
  - Adopt the calibrated value only if it falls within 1,500–3,500.

## 3. Mortality in transit

**Typical size: small**
- **Minnesota.** Catchable rainbows (160–310 mm) were held in net pens after hauling and stocking, with the
  truck at 11 °C and the lake at 9 °C and no tempering. Mortality was **1.6%** at 48 h and did not depend
  on fish size ([Cunningham & Anderson 1992](https://www.lrl.mn.gov/docs/pre2003/other/920576.pdf)).
  The authors call post-stocking mortality from "confinement, hauling, and handling stress" negligible.
- **Idaho.** "No significant mortality associated with this program has occurred" (IDFG HGMP §5.7).
- **PA-specific transit mortality: none found** (*unverified*).

**What drives it** (Piper et al. 1982, pp. 355–358)
- **Dissolved oxygen.** Keep it above 6–7 ppm. Give extra oxygen during loading and the first hour, when
  stress peaks. "The first hour of confinement in the unit is critical."
- **Ammonia.** Starve fish 8 inches and larger for 72 h before hauling. "If they are not, large losses may
  occur."
- **CO₂.** Trout are distressed near 25 ppm.
- **Temperature.** Pumps can warm 400 gal of water by 3–7 °F per hour, versus under 1 °F per hour for
  aerators. Insulated tanks limit the gain.
- **Loading density.** Stay under the ceiling in §2.
- **Temperature shock at release.** Temper the fish if truck and stream temperatures differ widely.
  - Some states set stocking temperature windows. California: no catchable trout in streams at 75 °F or
    higher, or below 45 °F ([CDFW](https://www.wildlife.ca.gov/Fishing/Hatcheries/Criteria)).
  - PFBC's temperature rules for adding and removing waters are in `docs/env_research.md` §4.

**Maximum haul time or distance**
- Piper's loading rates assume 8–10 hours.
- Long PA hauls take a few hours, well inside that window. For example, one Huntsdale load was stocked
  ~120 miles from the hatchery
  ([Inquirer 2025](https://www.inquirer.com/news/pennsylvania/trout-fishing-pennsylvania-stock-20250405.html)).
- No PA or PFBC rule of thumb for maximum distance was found.

## 4. Capital cost

- **Price: not found for PFBC or any recent state purchase.** This was searched in PFBC news, annual
  reports, the Trout Plans, LBFC audits, and other states' budgets and press releases.
  - **Michigan** (undated page, fleet mostly pre-2012): "nearly $1.7 million" across 18 stocking units, or
    **~$94k each**. As truck prices rose, Michigan began fitting refurbished tanks onto new chassis. Tanks
    outlive chassis ([MI DNR](https://www.michigan.gov/dnr/managing-resources/fisheries/hatcheries/fish-transportation)).
  - **Our assumption:** $200k for a new Class 7–8 chassis plus an insulated multi-compartment tank with
    aeration and oxygen, range $120–300k. *Unverified.*
- **Life**
  - The PFBC fleet averaged "approximately 20 years old". The Trout Plan 2020–24 (Issue 25) set a target to
    replace "two or three trucks per year".
  - Michigan retired a 4,000-gal semi unit "after 20 years of service".
  - Use 20 years (12–25).
- **Miles per truck (derived, *unverified*).** Fleet size isn't published.
  - Huntsdale produces ~20% of PFBC trout pounds (461,280 of ~2.25M lb in
    `data/raw/pa_hatchery_production.csv`). It stocked 305,000 fish in ~5 weeks of preseason
    (Inquirer 2025). That is ~12,000 fish per working day, or ~4 full loads.
  - At one load per truck per day, scaling that statewide gives ~20 trucks at the preseason peak. With
    spares, and the 2–3-per-year replacement pace, the fleet is probably **~20–40 trucks**. Use 30.
  - So ~10,000 miles per truck per year, and ~200,000 miles over a 20-year life.
- **Annualized (derived).** 30 × $200k ÷ 20 years ≈ $300k a year. The LBFC's FY2006–08 figure for "fixed
  assets" in the trout program ("vehicles, major equipment, and certain maintenance") was $571k a year
  (LBFC 2010, Table 20). That total covers more than trucks, but it is the right order of magnitude.

## 5. Overall program cost and cost per fish

**PFBC**
- **FY2006–08** ([LBFC 2010](https://www.legis.state.pa.us/WU01/LI/TR/Reports/2010_0083R.pdf), pp. S-7, 56–65):
  - The stocked-trout program cost **$12.4M a year**.
  - Producing an adult trout cost **$2.17** in direct costs, or **$2.73** all-in.
  - Hatchery-level direct costs were $1.27–2.92 per adult (Table 19).
  - Commercial farms charged $2.57 for a similar fish. A contract supplier charged $1.09–1.23 in 2004–09;
    the one 2009 bid was $3.38.
- **Inflated to 2025 dollars** (derived; [BLS CPI-U](https://www.bls.gov/regions/northeast/data/consumerpriceindex_us_table.htm)
  321.9 / 207.3 = 1.55): $3.37 direct, **$4.24 all-in** per trout, and **$19.2M** a year.
- **FY2023–24, the latest** (PFBC 2024 Annual Report, unaudited):
  - The Fish Fund spent $50.0M: personnel $31.0M, operating $15.5M, fixed assets $2.8M. Fish and Boat
    Funds together spent $73.8M.
  - PFBC stocked 3,143,145 adult trout and 1,556,362 fingerlings, and gave 1,135,658 fingerlings to
    co-ops.
  - There is no breakdown for hatcheries, stocking or distribution. **No published PFBC figure for annual
    distribution cost was found.**
  - The LBFC's June 2025 performance audit may have more, but its PDF returned 404 when we tried it.

**Other states (context only)**
- Wyoming, 1987–90: $0.68 per catchable trout for production plus distribution
  ([Wiley et al. 1993](https://academic.oup.com/najfm/article/13/1/160/7882432)).
- MassWildlife: a trout program of "about $3 million each year" for roughly half a million spring trout
  ([Boston Globe 2026](https://www.bostonglobe.com/2026/04/01/metro/stocked-trout-ponds-massachusetts/),
  citing MassWildlife's FY2024 report).

**Sanity check (derived)**
- Our transport estimate is $0.18 per adult trout in operating cost, or $0.28 with capital. That is **~4–7%**
  of the $4.24 all-in cost per trout, and ~3–5% of the inflated $19.2M program.
- Moving a fish an extra 100 miles costs ~$0.15, about 4% of what it cost to raise it.

## 6. Other things the transport element needs

- **Stockings per section per year.**
  - The Operational Guidelines (Table 44, pp. 69–70) give 1 preseason stocking plus 1–2 in-season:
    - High Yield: 2 in-season.
    - Optimum Yield II Suburban/Rural: 1 in-season.
    - Tailwaters: 2 or more.
    - Class 5 lakes: 1 in total.
  - Fall and winter stockings (from Oct 1,
    [PFBC 2025](https://www.pa.gov/agencies/fishandboat/newsroom/fall-and-winter-trout-stocking-to-begin-october-1-sept2025))
    are extra for some waters. Each stocking carries at least 300 trout.
  - In 2007 PFBC cut in-season frequencies partly "to reduce distribution costs through the elimination
    of some distribution (truck) trips and the amount of labor required for stocking" (p. 69). So visits
    do cost money, but mostly crew time.
  - Exact counts per section could come from the fbweb stocking schedule dates (upgrade; mind the
    1-request-per-second rule).
- **Multi-stop routes.** One truckload is shared across several sections (§2). The per-fish formula
  already spreads each round trip across the load. The miles driven between stops are ignored; state this
  in the report.
- **Hatchery assignment is a real PFBC decision.** The Trout Plan 2020–24 (Issue 26) aimed to "review
  trout hatchery assignments to optimize the timing of trout stocking". It also aimed to concentrate
  preseason and in-season stockings "to … reduce transportation costs". Both are good report hooks.
- **Season and temperature.**
  - Preseason stocking is concentrated in the ~3 weeks before opening day (Trout Plan Issue 26).
  - Cold March water allows bigger loads, while May and fall hauls must carry less (Piper, 5.6% per °F).
  - A seasonal `fish_per_load` is an upgrade. One annual value is fine for now.
- **Volunteers and float stocking.** Volunteers from local groups "traditionally assisted with float
  stocking and bucket carrying"
  ([PFBC 2021](https://www.pa.gov/agencies/fishandboat/newsroom/pfbc-announces-changes-to-2021-trout-season-and-stocking-operations-during-quarterly-meeting)).
  That cuts staff time at the stream but not truck miles. No effect on the model.
- **Is transport a meaningful share of cost?**
  - It is small: ~4–7% of cost per fish (§5).
  - Expect the cost objective to move tens of thousands of dollars, not millions.
  - The trade-off curves will likely show angler benefit gained cheaply in transport terms. That is a
    finding, not a flaw.

## 7. Recommendations for the model

**Include now**
- **Per-fish cost.** Use `cost[h,s] = cost_per_fish_road_mile × est_road_mi[h,s]`, with
  `cost_per_fish_road_mile = 2 × 1.90 / 2,500 = $0.00152`.
- **Sensitivity.** Run low ($0.00071) and high ($0.00413) in `03_sensitivities`, alongside the circuity
  factor.
- **Calibration check.** Once distances exist, run the `fish_per_load` check against 300,000 fleet miles
  (§2). Report it even if you keep 2,500.
- **Report the cost objective in plain units:** dollars per year, plus truck-miles per year
  (`Σ 2·d·x / fish_per_load`).

**Leave as upgrades**
- A per-stop cost × stockings per section (small: ~$0.02 per fish).
- Seasonal loads.
- A peak-day truck constraint per hatchery (fleet trips per day in preseason).
- Real multi-stop routing (a vehicle routing problem, out of scope).
- OSM road distances (already listed in `modeling_notes.md`).

**Mortality: keep it flat, not per mile**
- The evidence supports a small loss (~1–2%) driven by loading, handling, water quality and release
  shock. It does not support a loss that grows with distance at PA's few-hour hauls. Any per-mile rate
  would be an invented number.
- Either leave it out (1% is below the other uncertainties) or apply it as a flat factor: divide cost by
  (1 − m), and let the hatchery supply cover x / (1 − m).

**Capital: leave it out of the per-mile cost**
- The fleet is sized for the preseason peak and replaced by age (~20 years), not by mileage. Shifting fish
  between sections doesn't change how many trucks PFBC owns.
- A per-mile capital charge ($1.00/mi, range $0.40–2.50) would roughly add 50% to the marginal cost that
  the optimizer sees.
- Report capital as a fixed annual line on the scorecard (~$300k a year, *unverified*), identical across
  plans. Run "+$1.00/mi" as one sensitivity, to show conclusions don't hinge on it.
