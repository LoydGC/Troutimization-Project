"""Stocking optimization (Gurobi): how should each hatchery's trout be spread across the stocked sections?

STATUS: scaffold. The structure and inputs are laid out below; the model itself isn't written yet.

Model (docs/model_design.md, CLAUDE.md):
  decision     x[h, s] = adult trout per year trucked from hatchery h to section s, and a binary y[s] = section
               stocked (for the 300-fish minimum)
  objectives   kept separate: maximize angler benefit, minimize transport cost, minimize wild-trout impact
  solve        epsilon-constraint sweeps: maximize benefit subject to cost <= C and impact <= E, then vary C and E
               to trace the trade-off curves
  constraints  hatchery supply, per-section density cap (cap_fish), environmental exclusions, total fish fixed at
               the baseline, optionally stability vs the baseline
  baseline     PFBC's actual 2026 stocking, scored on the same three objectives, is the point we compare against

Inputs (data/processed/). Files marked TODO are Nate's Prompts 7-8 and don't exist yet:
  hatchery_to_section_road_distance.parquet   road miles and drive time, hatchery -> section  (11_road_distances.py)
  sections.parquet                            1,045 sections: density cap (cap_fish), baseline stocking counts
  environment.parquet                         exclusions and wild-trout impact inputs         (05_environment.py)
  demand.parquet                              angler-days per section                         (08_demand.py)
  hatchery_schedule_supply.csv                fish supply per hatchery from the 2026 schedule (09_stocking_schedule.py)
  hatcheries.parquet, cost_matrix.parquet     TODO (Prompt 7)
  model_input.parquet                         TODO (Prompt 8): one row per destination, everything above joined
Outputs (planned): data/processed/optimization_results.parquet, outputs/tables/optimization/,
                   outputs/figures/optimization/

Run it with VS Code's "Run Python File", or cell by cell with the "Run Cell" links above each # %%.
"""
# %% Setup
from pathlib import Path

import pandas as pd

# import gurobipy as gp        # needs the Gurobi academic license on this machine
# from gurobipy import GRB

try:
    ROOT = Path(__file__).resolve().parents[1]
except NameError:     # running cell by cell in VS Code's interactive window: find the repo root
    ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / ".git").exists())
PROCESSED = ROOT / "data" / "processed"
FIG_DIR = ROOT / "outputs" / "figures" / "optimization"
TABLE_DIR = ROOT / "outputs" / "tables" / "optimization"


# %% Load inputs
# TODO: read model_input.parquet (Prompt 8) and the hatchery -> section cost matrix (Prompt 7)


# %% Build the model
# TODO: variables x[h, s] and y[s]; supply, density-cap, exclusion and total-fish constraints; the three objectives


# %% Solve and save
# TODO: epsilon-constraint sweeps over cost and wild-trout impact; write results to data/processed and outputs/

print("optimization.py is a scaffold: the model isn't written yet.")
