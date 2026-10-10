"""Report figure and table: share of angler demand and of stocked fish by PFBC population class (Rural, Suburban,
Urban, Metro: 3rd character of AllocationCode), PFBC's 2026 plan vs the model's "more benefit" plan
(none|dominance in runs.csv). Demand uses the base blend w = 0.5.

Inputs : outputs/tables/optimization/sections.parquet (run scripts/optimization.py first),
         data/processed/sections.parquet, data/processed/demand.parquet
Outputs: outputs/tables/optimization/fish_by_area_type.csv, outputs/figures/optimization/class_shares.png
Run    : .venv/bin/python scripts/figures/43_fish_by_area_type.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OPT = ROOT / "outputs" / "tables" / "optimization"
FIG = ROOT / "outputs" / "figures" / "optimization" / "class_shares.png"
W = 0.5   # demand blend weight, as in parameters.csv (blend_weight_w)
ORDER = ["Rural", "Suburban", "Urban", "Metro"]
COLS = {"Angler demand": "#c9ced6", "PFBC 2026": "#e07b39", "Model": "#1f3b57"}


def shares() -> pd.DataFrame:
    s = pd.read_parquet(OPT / "sections.parquet").pivot(index="section_id", columns="run_id", values="x")
    sec = pd.read_parquet(PROCESSED / "sections.parquet").drop_duplicates("section_id").set_index("section_id")
    dm = pd.read_parquet(PROCESSED / "demand.parquet").set_index("section_id")
    d = (pd.DataFrame({"PFBC 2026": s["baseline"], "Model": s["none|dominance"]})
         .join(sec.allocation_code).join(dm[["prox_days", "pref_days"]]))
    d["Angler demand"] = (1 - W) * d.prox_days + W * d.pref_days
    d["area"] = d.allocation_code.str[2].map({"M": "Metro", "U": "Urban", "S": "Suburban", "R": "Rural"})
    cols = list(COLS)
    out = (d.groupby("area")[cols].sum() / d[cols].sum() * 100).reindex(ORDER)
    out["sections"] = d.groupby("area").size().reindex(ORDER)
    out["fish_change_pct"] = (out["Model"] / out["PFBC 2026"] - 1) * 100
    return out


def plot(sh: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    x, wd = np.arange(len(ORDER)), 0.26
    for i, c in enumerate(COLS):
        b = ax.bar(x + (i - 1) * wd, sh[c], wd, color=COLS[c], label=c)
        ax.bar_label(b, fmt="%.0f%%", fontsize=8, padding=2)
    ax.set_xticks(x, ORDER)
    ax.set_ylabel("Share of statewide total")
    ax.set_yticks([])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    ax.set_ylim(0, sh[list(COLS)].values.max() * 1.15)
    fig.tight_layout()
    fig.savefig(FIG, dpi=200, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    sh = shares()
    sh.round(2).to_csv(OPT / "fish_by_area_type.csv", index_label="area")
    print(sh.round(1).to_string())
    plot(sh)
