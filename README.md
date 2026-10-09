# PA Trout Stocking Optimization

Class project for *From Data to Action*. The Pennsylvania Fish and Boat Commission (PFBC) raises adult trout at
state hatcheries and trucks them to stream sections across the state. This project asks: **given the same fish
from the same hatcheries, could they be spread over the same stream sections in a way that is better for anglers,
cheaper to haul, or gentler on wild trout?**

It builds the data for that question from public PFBC, PASDA, Census and survey sources, and solves a
multi-objective model in Gurobi.

## The model in brief
Full formulation: [`docs/model_formulation.md`](docs/model_formulation.md). The code, `scripts/optimization.py`, is
the final word if a doc disagrees with it.

- **Decision:** `x[h, s]`, the adult trout per year trucked from hatchery `h` to stream section `s`.
- **Sets:** the 9 hatcheries with stream fish on PFBC's 2026 schedule (13 exist; the model ships from 9), and the
  1,022 stream sections PFBC stocks in 2026. Each hatchery ships exactly its 2026 stream supply (2,606,465 fish in
  total), so the model decides *where* fish go, not how many are raised.
- **Three objectives, kept separate and never pre-weighted:**
  1. maximize angler benefit, the angler-days with a catch (diminishing returns per section, built from the 2023
     PFBC angler survey, license sales and Census population);
  2. minimize transport cost, in truck trips costed at k-medoids cluster-average road miles;
  3. minimize wild-trout impact, stocked fish weighted by wild-trout density on natural-reproduction water.
- **Constraints:** hatchery supply, every fish allocated, a 300-fish minimum per stocked section, a per-section
  density bound, and an optional limit on how far a section may move from today's stocking.
- **Solve:** epsilon-constraint sweeps trace the trade-off curves, with PFBC's actual 2026 plan scored on the same
  three objectives as the baseline.

## Layout
```
scripts/      numbered pipeline scripts (re-runnable end to end), plus optimization.py
scripts/figures/  scripts that only draw figures (they keep their original numbers)
tests/        pytest tests; test_processed.py pins the documented counts in data/processed
notebooks/    01_data_prep (EDA) and travel_arcs (maps). They read data/processed and build nothing
data/raw/         untouched downloads. Gitignored except manifest.csv (enough to re-fetch) and 4 small partner files
data/interim/     scratch tables, gitignored
data/processed/   model-ready tables (parquet + csv), committed. Overview: data/README.md
docs/         methods, model design, data dictionary, source inventory, known gaps (see below)
docs/archive/ working notes kept for the record, not maintained (phase plan, old audit, cluster tracker, figure ideas)
outputs/      figures and tables for the report; outputs/tables/optimization holds the model runs
logs/         run logs and QA reports
CLAUDE.md     project rules, agreed simplifications and verified facts
```

## Setup
Python 3.11+ and a Gurobi license (an academic one is free; `gurobipy` is in `requirements.txt`).

macOS / Linux:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Windows (PowerShell):
```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

## Run
The processed tables are committed, so to reproduce the model results you only need the last step:
```bash
python scripts/optimization.py                      # all change-limit variants, 8 points per curve
python scripts/optimization.py --variants none --points 4
python scripts/optimization.py --impact simple      # impact version: weighted | simple | overlap
pytest
```
It writes `outputs/tables/optimization/` (`runs.csv`, `sections.parquet`, `flows.parquet`) and
`outputs/figures/optimization/tradeoff_curves.png`.

### Rebuilding the data
Each script reads the tables its predecessors wrote, so order matters. It is **not** plain numeric order: the
distance scripts (11, 12, 19) sit between the section build and the demand build.

| Step | Scripts | What they build |
|---|---|---|
| 1. Sections and baseline | `00`, `01`, `02`, `03`, `04`, `05` | angler-survey tables; PFBC layers downloaded; `sections` and `stocking_section_year` (the 2024-26 baseline); co-op flag; river key, density cap; `environment` |
| 2. Schedule | `09`, `10` | PFBC's 2026 stocking schedule, hatchery supply, truck runs and the schedule clusters |
| 3. Road distances | `11`, `12`, `19` | hatchery to section, section to section, and county subdivision to section road miles (public OSRM server, so slow and rate-limited) |
| 4. Clusters | `13`, `15`, `18` | k-medoids and hierarchical section clusters; cluster-average road miles from each hatchery |
| 5. Demand | `06`, `07`, `08` | resident anglers by county and subdivision; favorite-water crosswalk; angler-days per section |
| 6. Model inputs | `20_transport_cost`, `21_model_input` | `hatcheries`, `cost_matrix`, `baseline_flows`; one row per section with everything the model reads |
| 7. Model | `optimization` | the Gurobi runs above |

`scripts/37_truck_capacity_sensitivity.py` re-solves the model at other truck capacities (fractional or integer
trips) and writes `outputs/tables/sensitivity_truck_capacity/`. Other scenarios are listed, not run, in
`docs/scenarios_and_extensions.md`.

The scripts in `scripts/figures/` make figures, not data, each logging to `logs/`. They kept their original
numbers, so 20 and 21 exist in both folders:
- `16`, `17`: cluster-method comparison and wild-trout overlap maps
- `20_allocation_map`, `21_hatchery_heat_maps`, `22`-`33`: slide and appendix visuals (hatchery maps, the PFBC
  allocation formula, stocking-season timeline, k-medoids clusters, one-truck example, road-distance appendix)
- `34`-`36`, `39`: maps of the model's plans against PFBC's 2026 plan
- `38`: the truck-capacity sensitivity figure

Scripts 06 and 09 also read PFBC documents saved under `data/raw/` (license sales PDF, stocking schedule); where each
comes from is in `docs/source_inventory.md` and `data/raw/manifest.csv`.

## Docs
| File | Read it for |
|---|---|
| `docs/model_formulation.md` | the model as built (kept in sync with the code) |
| `docs/model_design.md` | why each modelling choice was made, and open questions |
| `docs/data_dictionary.md` | every column in `data/processed/` |
| `docs/data_methods.md` | how source data was changed (PFBC license: describe every change) |
| `docs/source_inventory.md` | endpoints, fields, join keys, where each reference document came from |
| `docs/known_gaps.md` | missing data and source problems |
| `docs/scenarios_and_extensions.md` | sensitivities and extensions (additional analysis) |
| `docs/clustering_options.md` | how section clusters set the haul cost |

`CLAUDE.md` holds the agreed simplifications and verified facts. Where a doc and the code differ, the code
(`scripts/optimization.py`) and `docs/model_formulation.md` win.

## Data and credits
Official public sources only: PFBC (fbweb.pa.gov ArcGIS services, stocking schedule, Operational Guidelines),
PASDA (PAFishBoat map service), the US Census (TIGERweb), and the 2023 PFBC trout angler survey by Responsive
Management. Road distances come from OSRM. All changes to PFBC data are described in `docs/data_methods.md`.
Nothing is taken from trout.app; saved pages of it in `data/references/` are used only to validate output and stay
local.

Division of work (details in `CLAUDE.md`): Gavin Loyd ([LoydGC](https://github.com/LoydGC)) owns the hatchery and
co-op data, the hatchery-to-section road distances (`scripts/11`, `notebooks/travel_arcs.ipynb`) and the county
subdivision-to-section distances (`scripts/19`). The sections, stocking baseline, environment and demand pipeline
is the other partner's (Nate).
