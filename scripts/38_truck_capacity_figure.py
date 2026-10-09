"""Figure for the truck-capacity sensitivity (scripts/37_truck_capacity_sensitivity.py): benefit, transport cost and wild-trout impact
of the benefit-maximizing plans at each truck capacity, with PFBC's 2026 plan re-scored at the same capacity as the reference.

Reads : outputs/tables/sensitivity_truck_capacity/truck_capacity_runs_<mode>.csv
Writes: outputs/figures/sensitivity_truck_capacity/truck_capacity_sensitivity_<mode>.png      logs/38_truck_capacity_figure.log

    python scripts/38_truck_capacity_figure.py [fractional|integer]      (default fractional)
"""
# %% Setup
from __future__ import annotations

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import ROOT, setup_logging

MODE = sys.argv[1] if len(sys.argv) > 1 else "fractional"
T = ROOT / "outputs" / "tables" / "sensitivity_truck_capacity"
OUT = ROOT / "outputs" / "figures" / "sensitivity_truck_capacity"
import logging
setup_logging("38_truck_capacity_figure")
log = logging.getLogger("38_truck_capacity_figure")
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
GREY, BLUE, ORANGE = "#8d8c86", "#2a78d6", "#e8890c"
FONT_DIR = ROOT / "data" / "references" / "fonts"
if (FONT_DIR / "OpenSans.ttf").exists():
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    from matplotlib import font_manager
    for style, wght in [("Regular", 400), ("SemiBold", 600)]:
        cut = FONT_DIR / f"OpenSans-{style}.ttf"
        if not cut.exists():
            instancer.instantiateVariableFont(TTFont(FONT_DIR / "OpenSans.ttf"), {"wght": wght, "wdth": 100}, updateFontNames=True).save(cut)
        font_manager.fontManager.addfont(str(cut))
    plt.rcParams["font.family"] = "Open Sans"
plt.rcParams.update({"text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white"})

# %% Data
res = pd.read_csv(T / f"truck_capacity_runs_{MODE}.csv")
caps = sorted(res.capacity.unique())
pos = {c: i for i, c in enumerate(caps)}
get = lambda plan, col: np.array([res[(res.capacity == c) & (res.plan == plan)][col].iloc[0] for c in caps])
labels = [f"{c:,}" + ("\n(current)" if c == 3500 else "") for c in caps]
x = np.arange(len(caps))
PLANS = [("pfbc_2026", "PFBC 2026 plan", GREY), ("max_benefit", "Max benefit (no limits)", BLUE), ("more_benefit", "Max benefit, cost and impact no worse than PFBC", ORANGE)]

# %% Figure
fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2))

ax = axes[0]
for plan, name, col in PLANS:
    ax.plot(x, get(plan, "B") / 1e6, marker="o", ms=6, lw=2.2, color=col, label=name)
ax.set_ylim(3.0, 3.85)
ax.set_title("Angler benefit", loc="left", fontsize=13, fontweight="semibold")
ax.set_ylabel("Million angler-days with a catch")
gain = get("more_benefit", "B") / get("pfbc_2026", "B") - 1
for i in x:
    ax.text(i, get("more_benefit", "B")[i] / 1e6 + 0.03, f"+{gain[i]:.0%}", ha="center", fontsize=9, color=ORANGE)

ax = axes[1]
w = 0.27
for j, (plan, name, col) in enumerate(PLANS):
    v = get(plan, "C") / 1e3
    ax.bar(x + (j - 1) * w, v, w, color=col, label=name)
    if plan != "pfbc_2026":
        pct = get(plan, "C") / get("pfbc_2026", "C") - 1
        for i in x:
            ax.text(i + (j - 1) * w, v[i] + 14, f"{pct[i] * 100:.0f}%".replace("-", "−"), ha="center", va="bottom", fontsize=8, color=col, rotation=90)
ax.set_title("Transport cost", loc="left", fontsize=13, fontweight="semibold")
ax.set_ylabel("$ thousand per year (labels: change vs PFBC)")
ax.set_ylim(0, get("pfbc_2026", "C").max() / 1e3 * 1.15)

ax = axes[2]
for plan, name, col in PLANS:
    ax.plot(x, (get(plan, "I") / get("pfbc_2026", "I") - 1) * 100, marker="o", ms=6, lw=2.2, color=col, label=name)
ax.set_title("Wild-trout impact", loc="left", fontsize=13, fontweight="semibold")
ax.set_ylabel("Change vs PFBC 2026 plan (%, lower is better)")
ax.set_ylim(-10, 10)
ax.axhline(0, color=INK2, lw=0.8)

for ax in axes:
    ax.set_xticks(x, labels)
    ax.set_xlabel("Truck capacity (fish per trip)")
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=11, bbox_to_anchor=(0.5, -0.01))
fig.suptitle("Truck capacity sensitivity: benefit-maximizing plans vs PFBC's 2026 plan, scored at each capacity", x=0.01, ha="left", fontsize=14, fontweight="semibold")
fig.tight_layout(rect=(0, 0.07, 1, 0.95))
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / f"truck_capacity_sensitivity_{MODE}.png", dpi=170)
log.info("wrote %s", OUT / f"truck_capacity_sensitivity_{MODE}.png")
