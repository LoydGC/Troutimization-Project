"""Three slide maps: how each of the model's "beat PFBC" plans changes the trout stocked in every stream section, as a percent of PFBC's 2026 count.

Each map compares one model run with PFBC's 2026 plan (baseline_flows) section by section: change = (model fish - PFBC fish) / PFBC fish, all
hatcheries summed. The three runs improve one goal and hold the other two at PFBC's level (no change limit), as in outputs/tables/optimization/runs.csv:
  1 benefit    none|dominance            max benefit, cost and wild-trout impact no worse than PFBC
  2 cost       none|same_benefit_min_C   min transport cost, benefit and impact no worse than PFBC
  3 impact     none|same_benefit_min_I   min wild-trout impact, benefit and cost no worse than PFBC
Sections are drawn in 7 classes of percent change (closed = -100%; within +-10% counts as unchanged), same colours on all three maps.

Checks asserted: every run and the baseline place the same total fish on the 1,022 candidate sections as the model's supply (within rounding).

Inputs : outputs/tables/optimization/{flows.parquet,runs.csv}, data/processed/{sections.parquet,pa_trout.gpkg}, data/raw/pa_boundary.gpkg
Outputs: outputs/figures/statewide_results/{1_more_benefit,2_less_cost,3_less_impact}_pct_change_map.png      logs/39_pct_change_maps.log
"""
# %% Setup
from __future__ import annotations

import logging

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/, where common.py lives
from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging, register_open_sans

OPT = ROOT / "outputs" / "tables" / "optimization"
FIG_DIR = ROOT / "outputs" / "figures" / "statewide_results"
SURFACE, INK, INK2 = "#ffffff", "#0b0b0b", "#52514e"
setup_logging("39_pct_change_maps")
log = logging.getLogger("39_pct_change_maps")
FIG_DIR.mkdir(parents=True, exist_ok=True)

register_open_sans()
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})

MINUS = "−"
# (label, lower edge, upper edge, colour, line width); edges in % change, lower inclusive except the closed class
CLASSES = [("Closed (−100%)", -100.0, -100.0, "#8e1b1f", 2.6), (f"{MINUS}99% to {MINUS}50%", -99.999, -50, "#d1434a", 2.4),
           (f"{MINUS}50% to {MINUS}10%", -50, -10, "#f0a3a0", 2.2), ("Within ±10% (unchanged)", -10, 10, "#d6d5cf", 1.0),
           ("+10% to +50%", 10, 50, "#9cc3f0", 2.2), ("+50% to +100%", 50, 100, "#4b8fe0", 2.4), ("More than doubled (over +100%)", 100, np.inf, "#1b4f9c", 2.6)]
RUNS = [("1_more_benefit", "none|dominance", "Benefit-Maximizing Plan vs. PFBC 2026",
         "Percent change in trout per stream section. Benefit raised; transport cost and wild-trout impact no worse than PFBC's 2026 level.", "B"),
        ("2_less_cost", "none|same_benefit_min_C", "Cost-Minimizing Plan vs. PFBC 2026",
         "Percent change in trout per stream section. Transport cost cut; benefit and wild-trout impact no worse than PFBC's 2026 level.", "C"),
        ("3_less_impact", "none|same_benefit_min_I", "Impact-Minimizing Plan vs. PFBC 2026",
         "Percent change in trout per stream section. Wild-trout impact cut; benefit and transport cost no worse than PFBC's 2026 level.", "I")]

# %% Load
flows = pd.read_parquet(OPT / "flows.parquet")
runs = pd.read_csv(OPT / "runs.csv").set_index("run_id")
base_row = runs.loc["baseline"]
tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
stocked = set(tab.loc[tab.total_2026.fillna(0) > 0, "section_id"])
sec = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
sec = sec[sec.section_id.isin(stocked)].set_index("section_id")
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg")


def by_section(run: str) -> pd.Series:
    s = flows[flows.run_id == run].groupby("section_id").x.sum().astype(float).reindex(sec.index).fillna(0)
    assert abs(s.sum() - 2_606_465) < 10, f"{run}: total fish {s.sum():,.0f}"
    return s


old = by_section("baseline")
assert (old > 0.5).all(), "every candidate section is stocked in PFBC's 2026 plan"


def klass(p: float) -> int:
    if p <= -99.9:
        return 0
    return 1 + int(np.searchsorted([-50, -10, 10, 50, 100], p, side="right"))


# %% Draw
for key, run, title, sub, moved in RUNS:
    new = by_section(run)
    pct = (new - old) / old * 100
    cls = pct.map(klass)
    counts = cls.value_counts().reindex(range(len(CLASSES))).fillna(0).astype(int)
    log.info("%s: classes %s; sections up %d, down %d, closed %d; fish moved %.0f%%", run, counts.tolist(), (pct > 10).sum(), (pct < -10).sum(),
             counts[0], 100 * np.abs(new - old).sum() / 2 / old.sum())

    fig = plt.figure(figsize=(13.333, 7.5))
    ax = fig.add_axes([0.02, 0.04, 0.62, 0.78])
    fig.suptitle(title, x=0.012, y=0.985, ha="left", fontsize=30, color="#a6192e")
    fig.text(0.014, 0.875, sub, fontsize=12.5, color=INK2, va="center")
    pa.plot(ax=ax, facecolor="#ffffff", edgecolor=INK2, lw=1.2, zorder=0)
    for i in (3, 4, 2, 5, 1, 6, 0):          # unchanged underneath, the largest changes on top
        ids = cls.index[cls == i]
        if len(ids):
            sec.loc[ids].plot(ax=ax, color=CLASSES[i][3], lw=CLASSES[i][4], zorder=1 + (0 if i == 3 else 1 + abs(i - 3)), capstyle="round")
    ax.set_xlim(-80.7, -74.6)
    ax.set_ylim(39.6, 42.4)
    ax.set_aspect(1 / np.cos(np.radians(41)))
    ax.set_axis_off()

    pan = fig.add_axes([0.665, 0.04, 0.315, 0.78])
    pan.set_axis_off()
    pan.set_xlim(0, 1)
    pan.set_ylim(0, 1)
    pan.text(0, 1.0, "Plan vs. PFBC 2026", fontsize=12, color=INK2, va="top")
    for j, (code, name) in enumerate([("B", "Angler benefit"), ("C", "Transport cost"), ("I", "Wild-trout impact")]):
        chg = (runs.loc[run, code] / base_row[code] - 1) * 100
        held = code != moved
        y = 0.925 - j * 0.085
        pan.text(0, y, name, fontsize=13, color=INK2 if held else INK, va="center", fontweight="normal" if held else "bold")
        label = "held" if held and abs(chg) < 0.5 else f"{chg:+.0f}%".replace("-", MINUS)
        if held and abs(chg) >= 0.5:
            label += " (no worse)"
        pan.text(1.0, y, label, fontsize=16 if not held else 12.5, color=INK2 if held else "#1b4f9c", ha="right", va="center", fontweight="bold" if not held else "normal")
    pan.plot([0, 1], [0.665, 0.665], color="#d6d5cf", lw=1)
    pan.text(0, 0.635, "Stream sections by change in trout", fontsize=12, color=INK2, va="top")
    for i in (6, 5, 4, 3, 2, 1, 0):
        y = 0.55 - (6 - i) * 0.068
        pan.plot([0.0, 0.1], [y, y], color=CLASSES[i][3], lw=CLASSES[i][4] + 1.5, solid_capstyle="butt")
        pan.text(0.14, y, CLASSES[i][0], fontsize=11.5, color=INK, va="center")
        pan.text(1.0, y, f"{counts[i]:,}", fontsize=11.5, color=INK2, va="center", ha="right")
    pan.text(0, 0.02, f"{len(sec):,} stocked stream sections", fontsize=11, color=INK2, va="bottom")
    out = FIG_DIR / f"{key}_pct_change_map.png"
    fig.savefig(out, dpi=300, facecolor=SURFACE)
    plt.close(fig)
    log.info("wrote %s", out)
