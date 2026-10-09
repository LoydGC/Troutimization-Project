"""Slide visual: PFBC's current way of allocating trout to a stream section, and its basic components.

    trout per section per year  ~  stocking rate (trout per acre per year)  x  area (acres)

The rate is a maximum from the Operational Guidelines' Table 18, looked up from four things: wild trout biomass class (A-E), recreational use
potential / access (High, Good, Low), population density (Metro, Urban, Suburban, Rural) and width class (1L, 1S, 2, 3, 4). Area = length x width.
Docs: docs/env_research.md section 2, docs/data_methods.md (allocation category, area), data/processed/pfbc_stocking_rates.csv (Table 18).

The worked example (Bear Creek section 3197_2) is read from data/processed/sections.parquet: its Table 18 rate, area (length x 10 m, the top of width
class 3, an assumption of this repo because no layer gives real widths) and the trout PFBC actually stocked in 2026. No title on purpose: it is
added in PowerPoint.

Inputs : data/processed/sections.parquet
Outputs: outputs/figures/allocation_problem/pfbc_formula.png   (16:9, 300 dpi)
         logs/22_pfbc_formula_visual.log

    python scripts/figures/22_pfbc_formula_visual.py
"""
# %% Setup
from __future__ import annotations

import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/, where common.py lives
from common import PROCESSED_DIR, ROOT, setup_logging, register_open_sans

FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2, PANEL = "#ffffff", "#0b0b0b", "#52514e", "#ffffff"
BLUE, BLUE_LIGHT, AMBER, AMBER_LIGHT, BERRY = "#2a78d6", "#e3eefb", "#f5ae00", "#fdf0cc", "#a6192e"   # BERRY = the deck's dark red
setup_logging("22_pfbc_formula_visual")
log = logging.getLogger("22_pfbc_formula_visual")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Open Sans (the deck's font; SIL Open Font License), local only: see common.register_open_sans. Falls back to DejaVu Sans if absent.
register_open_sans()

# %% Worked example from the data
SID = "3197_2"
r = pd.read_parquet(PROCESSED_DIR / "sections.parquet").set_index("section_id").loc[SID]
rate, acres, miles, actual = float(r.max_trout_per_acre), float(r.area_acres), float(r.length_mi), int(r.total_2026)
formula = rate * acres
assert abs(acres - miles * r.width_top_m * 1609.344 / 4046.856) < 0.01, "area = length x width"
log.info("%s %s %s: rate %.0f/acre x %.2f acres (%.2f mi x %.0f m) = %.0f; PFBC stocked %d in 2026 (%.0f%% of the formula)",
         SID, r.water_name, r.allocation_code, rate, acres, miles, r.width_top_m, formula, actual, 100 * actual / formula)

# %% Draw (coordinates in inches on a 13.333 x 7.5 slide)
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})
fig = plt.figure(figsize=(13.333, 7.5))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 13.333)
ax.set_ylim(0, 7.5)
ax.set_axis_off()


def box(x, y, w, h, fc, ec=None, lw=0, rad=0.12):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rad}", fc=fc, ec=ec or fc, lw=lw))


# column centres shared by the formula, its components and the example
CX = {"rate": 2.75, "area": 7.1, "result": 11.2}
W = {"rate": 4.3, "area": 3.4, "result": 3.2}
Y1, H1 = 4.85, 1.35                                                       # the formula boxes
for key, fc, ec, head, sub, tc in (("rate", BLUE_LIGHT, BLUE, "Stocking rate", "trout per acre per year", BLUE),
                                   ("area", AMBER_LIGHT, AMBER, "Area", "acres of stream", "#8a5d00"),
                                   ("result", BERRY, BERRY, "Trout stocked", "per section per year", "white")):
    box(CX[key] - W[key] / 2, Y1, W[key], H1, fc, ec, lw=2.2 if key != "result" else 0)
    ax.text(CX[key], Y1 + 0.85, head, fontsize=26, fontweight="bold", color=tc, ha="center", va="center")
    ax.text(CX[key], Y1 + 0.38, sub, fontsize=14, color=tc if key == "result" else INK2, ha="center", va="center")
ax.text((CX["rate"] + W["rate"] / 2 + CX["area"] - W["area"] / 2) / 2, Y1 + H1 / 2, "×", fontsize=44, ha="center", va="center", color=INK2)
ax.text((CX["area"] + W["area"] / 2 + CX["result"] - W["result"] / 2) / 2, Y1 + H1 / 2, "=", fontsize=44, ha="center", va="center", color=INK2)

# components under each box
ax.text(CX["rate"], 4.52, "A maximum from PFBC's rate table, set by four things", fontsize=12, color=INK2, ha="center", va="center")
for i, (name, vals) in enumerate((("Wild trout biomass", "class A to E"), ("Access to the water", "High, Good or Low"),
                                  ("Population nearby", "Metro to Rural"), ("Stream width", "class 1L to 4"))):
    y = 4.05 - i * 0.4
    ax.scatter([0.8], [y], s=70, c=BLUE, zorder=3)
    ax.text(1.0, y, name, fontsize=13.5, fontweight="bold", va="center")
    ax.text(4.9, y, vals, fontsize=12.5, color=INK2, va="center", ha="right")
ax.text(CX["area"], 4.52, "The size of the section", fontsize=12, color=INK2, ha="center", va="center")
for i, (name, desc) in enumerate((("Length", "miles of the section"), ("Width", "from its width class"))):
    y = 4.05 - i * 0.4
    ax.scatter([5.55], [y], s=70, c=AMBER, zorder=3)
    ax.text(5.75, y, name, fontsize=13.5, fontweight="bold", va="center")
    ax.text(8.65, y, desc, fontsize=12.5, color=INK2, va="center", ha="right")
for yy, line in ((4.52, "The rate is a maximum,"), (4.2, "not a target. Managers"), (3.88, "can stock less.")):
    ax.text(CX["result"], yy, line, fontsize=12, color=INK2, ha="center", va="center")

# worked example, aligned under the same three columns
box(0.55, 0.6, 12.2, 1.9, PANEL, ec="#d9d8d2", lw=1.5, rad=0.15)
ax.text(0.85, 2.22, f"Example: {r.water_name}, section 2", fontsize=14, fontweight="bold", va="center")
ax.text(0.85 + 3.55, 2.22, f"category {r.allocation_code}  ·  {miles:.1f} miles long, up to 10 m wide (width class 3)", fontsize=12, color=INK2, va="center")
ax.text(CX["rate"], 1.5, f"{rate:.0f}", fontsize=34, fontweight="bold", color=BLUE, ha="center", va="center")
ax.text(CX["rate"], 1.02, "trout per acre per year", fontsize=12, color=INK2, ha="center", va="center")
ax.text(CX["area"], 1.5, f"{acres:.1f}", fontsize=34, fontweight="bold", color="#8a5d00", ha="center", va="center")
ax.text(CX["area"], 1.02, f"acres ({miles:.1f} mi × 10 m)", fontsize=12, color=INK2, ha="center", va="center")
ax.text(CX["result"], 1.5, f"≈ {round(formula, -1):,.0f}", fontsize=34, fontweight="bold", color=BERRY, ha="center", va="center")
ax.text(CX["result"], 1.02, "trout at most", fontsize=12, color=INK2, ha="center", va="center")
ax.text(CX["result"], 0.74, f"PFBC stocked {actual:,} in 2026", fontsize=11, color=INK2, ha="center", va="center")
ax.text((CX["rate"] + W["rate"] / 2 + CX["area"] - W["area"] / 2) / 2, 1.5, "×", fontsize=30, ha="center", va="center", color=INK2)
ax.text((CX["area"] + W["area"] / 2 + CX["result"] - W["result"] / 2) / 2, 1.5, "=", fontsize=30, ha="center", va="center", color=INK2)

ax.text(6.667, 0.25, "Source: PFBC, Operational Guidelines for the Management of Trout Fisheries in Pennsylvania Waters, 5th ed. (rate table: Table 18).",
        fontsize=9, color=INK2, ha="center", va="center")

out = FIG_DIR / "pfbc_formula.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
