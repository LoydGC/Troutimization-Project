# Sets       
h ∈ H   9 hatcheries on the 2026 schedule
s ∈ S   1,022 sections stocked in 2026 (excluded waters simply aren't in S)

Exclusions are handled by the sets and data, not extra constraints: Wilderness waters and Buffalo Creek 3190_2 (Class A since 2026) aren't in S, and each section keeps its 2026 species mix, so no brook trout go over wild brook trout.

# Decision Variables (kinda)
### 1. Fish per year from h to s 
$$
x[h,s] ≥ 0
$$,  

Continuous (fractional fish allowed); plans are rounded to whole fish for reporting.

### 2. Fish per year to s
$$
x_s = \sum_h x[h,s]
$$, 

### 3. Section is stocked or not
$$
y_s ∈ \{0,1\}
$$  

### 4. Section gets a second stocking
$$
z_s ∈ {0,1},\qquad z_s \le y_s
$$
$z_s = 1$ means section $s$ gets more than 600 fish and so is stocked $n_s$ times; $z_s = 0$ means one stocking (at most 600 fish). Written as $x_s \ge 600.01\,z_s$ so a section can't claim a second stocking on a small load

# Objectives

### 1) Angler Benefit: Maximize number of days with an angler catch 

$$
\max B = \Sigma_s D_s·(1 − e^{(−x_s / (k·D_s))})$$

In Gurobi the curve is approximated by straight-line pieces (it is concave, so no extra binaries are needed); the approximation is within 0.13% of the exact curve, and all reported benefits use the exact formula.

### 2) Transportation Cost: Minimize the cost of the truck trips that deliver the fish

$$
\min C = \sum_h \sum_g \sum_r 2 \times miles_{h,g} \times t_{cost} \times \tau_{h,g,r}
$$

- $\tau_{h,g,r} \ge 0$: truck trips from hatchery $h$ to cluster $g$ in stocking round $r$ (1 = preseason, 2 and 3 = in-season). Sections in the same cluster and round share trucks (a costing convention, not a real route). Trips are set under Transit below
- **Fractional (default) vs whole trips:** in the default run $\tau$ is continuous, so the model's cost is a lower bound that is fast to solve (seconds per point). Every reported plan is then scored with whole trips: $\lceil \text{round fish in the cluster from } h \,/\, t_{max} \rceil$ for each hatchery, cluster and round, so reported costs are real whole-trip costs. Option `--trip-mode integer` makes $\tau$ an integer inside the model (about 2 minutes per constrained solve), which is the only mode where the model can plan around part-loads and the second-stocking switch changes cost
- $miles_{h,g} = \frac{1}{|g|} \sum_{s' \in g} \text{road mi}_{h,s'}$: the cluster's average one-way road miles from $h$ (Gavin's `cluster_hatchery_distance.avg_road_mi`)
- $\text{road mi}_{h,s'}$: one-way OSRM road miles from hatchery $h$ to section $s'$ (Gavin, `hatchery_to_section_road_distance`, all 13 hatcheries)
- First run: Gavin's k-medoids clusters on road miles (`kmedoids_best_silhouette`, 310). Sensitivities: Nate's schedule clusters (351), Gavin's hierarchical clusters (309), no clustering ($g$ = one section), and the old per-fish cost without trip counting ($2 \, miles \, t_{cost} / 2500$ per fish)

### 3) Overlap with Wild Fish: Minimize stocked fish on wild-trout water, weighted by how many wild trout live there

$$
\min I = \sum_s \omega_s \, x_s,
\qquad
\omega_s = a_{b(s)} \cdot p_s
$$

- $p_s$: share of section $s$'s length on natural-reproduction water (river miles). Sections PFBC rates biomass B–D but that aren't on the natural-reproduction list count whole ($p_s = 1$): the rating covers the section
- $a_b$: wild-trout density weight of biomass class $b$, the class midpoint relative to D (Operational Guidelines Table 2, p. 16): A 8 (≥ 40 kg/ha), B 6 (20–40), C 3 (10–20), D 1 (0–10), E 0. E sections on the natural-reproduction list get 1 (assumption)
- Unit: stocked fish weighted by wild-trout density, class D = 1. PFBC's 2026 plan scores 2.27M
- Sensitivities: binary ($\omega_s$ = 1 if natural reproduction or biomass B–D) and overlap only ($\omega_s = p_s$)

# Constraints

### C1) No hatchery ships more than its 2026 stream fish
$$
\sum_s x_{h,s} \le supply_h
$$  

### C2) Every fish must be allocated
$$
\sum_s x_s = Σ_h supply_h = T
$$

$supply_h$ is hatchery $h$'s 2026 stream fish from PFBC's 2026 stocking schedule, T = 2,606,465. Because T is the sum of all supplies, C1 and C2 together make every hatchery ship exactly its 2026 supply: the model decides where each hatchery's fish go, not how many it raises.

### C3) If stocked, section receives at least 300 fish
$$
300·y_s ≤ x_s
$$ 

### C3b) Stockings: one up to 600 fish, $n_s$ above
$$
x_s \le 600 + (cap_s - 600)^+ \, z_s
$$

- $n_s$: stockings for a section above 600 fish: 3 if $D_s \ge 15{,}000$ angler-days (about the top 10%) or High-Yield-like (High access, width 2–3, biomass C–E), else 2. Restates Operational Guidelines Table 44 with demand in place of population. 253 sections get 3, 769 get 2
- Matches 2026: every section under 600 fish is stocked once, 94% above it get two or more. The model can sit just under 600 to avoid a second round; we report how many sections do
- Preseason share of a section's fish $p = 0.55$ (Guidelines category tables; sensitivity 0.50–0.60), the rest split equally over the in-season stockings

### C4) If stocked, maximum number of fish per section
$x_s ≤ cap_s·y_s$    

$$
cap_s = \max\left(300,\; rate_s \times L_s \times W_s\right)
$$

- $rate_s$: trout per acre, the highest Operational Guidelines Table 18 rate for the section's wild biomass class and width class at its own recreational use potential (access) or any worse one. Delayed Harvest and tailwater sections use their program rate (Tables 45–46) where it's higher
- $L_s \times W_s$: section area, length times the top of its PFBC width class (4, 10, 20, 30 m; 60 m for 1L)
- Exceptions capped at today's count ($cap_s = x0_s$, keep or cut, never add): the 17 Class A sections and the 7 sections PFBC already stocks above the cap
- A policy/crowding bound, not carrying capacity. 

### C5) Change limit (option): how far a section can move from today's stocking in one step
$x0_s$ = PFBC's 2026 count for section $s$; $L = 0.5$, $U = 2$ (assumptions, sensitivity 0.75 / 1.25). C3's 300-fish minimum still applies inside the band

- **None** (main run): no extra constraint, $0 \le x_s \le cap_s$
- **Band**: every section stays stocked, between half and double today ($y_s = 1$, so the model is an LP)
$$
L \cdot x0_s \le x_s \le \min(U \cdot x0_s,\; cap_s)
$$
- **Close or band**: a section either closes or stays within the band
$$
L \cdot x0_s \cdot y_s \le x_s \le \min(U \cdot x0_s,\; cap_s) \cdot y_s
$$

# Variables

## Demand $D_s$: stream angler-days per year
Computed once before the model (`scripts/08_demand.py`); the model only reads it.

$$
D_s = (1-w)\,\text{prox}_s + w\,\text{pref}_s
$$
Weight applied to preference/proximity 
$$
w = 0.5
$$, weight 

### 1. Stream angler-days per county subdivision $i$

$$
E_i = \text{pop}_i \cdot a_{c(i)} \cdot d_{r(i)} \cdot \left(1 - \ell_{r(i)}\right),
\qquad E = \sum_i E_i = 7{,}121{,}847
$$

$$
\ell_r = \%\text{primarily lakes}_r + 0.5 \times \%\text{both equally}_r
$$

- $i$: county subdivision (2,567 townships, boroughs and cities). PFBC sets each section's population-density class from the same municipal units (Operational Guidelines p. 52, Table 17)
- $\text{pop}_i$: 2020 Census population (PL 94-171) of subdivision $i$, on 2026 boundaries (7 subdivisions renamed or merged since 2020 are moved to their 2026 successor; `subdivision_anglers`)
- $a_c$: anglers per resident in county $c$ (2024 trout + combo permits − non-resident licenses + online permits by population share)
- $d_r$: mean days fished for stocked trout by anglers from home region $r$ (survey p115; 19.1–26.7)
- $\ell_r$: share of region $r$'s days spent on lakes (survey p88), removed because lakes aren't in $S$: 13.1% (NW, SE) to 29.0% (NE), 18.3% statewide

### 2. Proximity: days go out by trip distance, split by length

$$
\text{prox}_s = \sum_i E_i \; \tilde q_{i,\,j(i,s)} \; \frac{L_s}{\displaystyle\sum_{s' :\, j(i,s') = j(i,s)} L_{s'}}
$$

$$
j(i,s) = \text{distance band of road miles}(i, s),
\qquad
\tilde q_{i,j} = \sum_{j' :\, t(i,j') = j} q_{r(i),j'}
$$

$$
t(i,j') = \begin{cases} \min\{\, j \ge j' : \text{band } j \text{ holds a section for } i \,\} & \text{if one exists} \\ \max\{\, j < j' : \text{band } j \text{ holds a section for } i \,\} & \text{otherwise} \end{cases}
$$

- road miles$(i,s)$: OSRM driving distance from subdivision $i$'s centroid to section $s$'s midpoint (Gavin, `subdivision_to_section_road_distance`, script 19). No circuity factor: the survey's trip distances are driving miles
- $q_{r,j}$: share of trips in band $j$ (0–10, 11–20, …, 150+ mi) for home region $r$ (survey p93)
- $t(i,j')$: the band that band $j'$'s trips land in: itself if it holds a section for $i$, else the next band out that does (an angler with no stocked water at their usual distance drives a little farther), else the nearest band in (never needed in the build)
- $\tilde q_{i,j}$: band $j$'s own share plus the shares of the empty bands that roll into it
- $L_s$: section length (mi). Within a band, days are split by length

### 3. Preference: favorite waters get their survey share, the rest is spread like proximity

$$
\text{pref}_s = E \; m_{v(s)} \, \frac{L_s}{L_{v(s)}} \; + \; u \; \text{prox}_s,
\qquad u = 1 - \sum_v m_v = 0.305
$$

$$
m_v = \frac{\displaystyle\sum_{n \to v} \mu_n \, \text{pct}_n}{\displaystyle\sum_{n \,\notin\, \text{lakes}} \text{pct}_n},
\qquad \sum_{n \,\notin\, \text{lakes}} \text{pct}_n = 199.25
$$

- $v(s)$: the river section $s$ is on; $L_v$: that river's stocked miles in 2026
- $\text{pct}_n$: % of anglers naming water $n$ as a favorite (survey p76–77, up to three each; "<0.5%" = 0.25)
- $\mu_n$: split of an ambiguous name across rivers (e.g. French Creek: 75% Chester's, 25% Erie's)
- $m_v$: river $v$'s share of stream mentions (lake mentions leave with the lake days)
- $u$: share no stocked river claims ("Other", "Don't know", unmatched names)

### Check

$$
\sum_s \text{prox}_s = \sum_s \text{pref}_s = \sum_s D_s = E
$$

Demand only decides *where* the angler-days go; the total is fixed.

### Benefit 

$$k = 0.5$$

## Supply
Total amount of trout stocked to streams is fixed at 2026 total. Amount available to each hatchery based on 2026 allocation
$$
supply_h = \text{2026 hatchery allocation for streams}
​$$

## Transit
Mostly comes from transport_research.md

Cost per truck mile and truck capacity (a full load; the 2,500 average already includes part-full trucks, so it isn't used inside a round-up)
$$
t_{cost} = \$1.90, \qquad t_{max} = 3500
$$

Fish of section $s$ in each round, by its stocking count (a section with $z_s = 0$ puts everything in round 1):

| | round 1 | round 2 | round 3 |
|---|---|---|---|
| $z_s = 0$ | $x_s$ | 0 | 0 |
| $z_s = 1$, $n_s = 2$ | $p\,x_s$ | $(1-p)\,x_s$ | 0 |
| $z_s = 1$, $n_s = 3$ | $p\,x_s$ | $\tfrac{1-p}{2}\,x_s$ | $\tfrac{1-p}{2}\,x_s$ |

Trips carry the round's fish for the cluster, so trips are fish over capacity, rounded up:
$$
\sum_{s \in g} f_{r}(h,s) \le t_{max} \, \tau_{h,g,r}
$$
where $f_r(h,s)$ is $x_{h,s}$ times the share in the table. The $z_s$ switch is linearized with big-M constraints in the code ($M_s = \max(cap_s, 600)$). $\tau$ exists only for rounds with members. $\tau$ is continuous by default and integer with `--trip-mode integer`; in either case scoring rounds each (hatchery, cluster, round) up to whole trips. With continuous $\tau$ the round shares add back to $x_s$, so the model's cost does not depend on $z_s$ or $p$, and the 600-fish rule only shows up in scoring and the stocking-count report
