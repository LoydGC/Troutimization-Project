"""Sensitivity and scenario runs: re-solve the stocking model under different assumptions and compare.

STATUS: scaffold. The runs are listed below; nothing is implemented yet. It needs optimization.py first.

What to vary (docs/scenarios_and_extensions.md lists the full set; ranges are in data/processed/parameters.csv):
  angler benefit    saturation scale k (0.5 / 1 / 2) and the demand blend weight w (0 / 0.5 / 1)
  transport cost    cost per truck-mile and fish per load, low and high; circuity factor
  density cap       cap_fish (default), cap_fish_mid (midpoint widths), cap_fish_river (looser),
                    cap_fish_class_a_grow (Class A sections may grow)
  hatchery set      the 9 on the 2026 schedule (base) vs all 13 (the "more hatcheries" extension)
  baseline          each section served by its scheduled hatchery (base) vs its nearest hatchery
  constraints       stability vs the baseline (delta), wild-trout lever (rho), sections PFBC dropped by 2026
Report the sections that gain or lose fish in every scenario (robust changes) separately from those that move
only under some assumptions.

Inputs : the same tables as optimization.py, plus data/processed/parameters.csv for the ranges
Outputs (planned): data/processed/sensitivity_results.parquet, outputs/tables/sensitivities/,
                   outputs/figures/sensitivities/

Run it with VS Code's "Run Python File", or cell by cell with the "Run Cell" links above each # %%.
"""
# %% Setup
from pathlib import Path

import pandas as pd

try:
    ROOT = Path(__file__).resolve().parents[1]
except NameError:     # running cell by cell in VS Code's interactive window: find the repo root
    ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / ".git").exists())
PROCESSED = ROOT / "data" / "processed"
FIG_DIR = ROOT / "outputs" / "figures" / "sensitivities"
TABLE_DIR = ROOT / "outputs" / "tables" / "sensitivities"


# %% Load the base model and the parameter ranges
# TODO: import the model builder from optimization.py; read the low/high ranges from parameters.csv


# %% Run the scenarios
# TODO: one solve (or one epsilon sweep) per scenario above; keep every result in one long table


# %% Compare and save
# TODO: robust vs scenario-specific changes per section; write tables and figures to outputs/

print("sensitivities.py is a scaffold: nothing is implemented yet.")
