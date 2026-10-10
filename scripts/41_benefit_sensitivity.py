"""Angler-benefit sensitivity: re-solve the three ways to beat PFBC's 2026 plan under other values of the demand
blend weight w and the benefit saturation scale k (ranges in data/processed/parameters.csv), and compare.

Settings: base (w 0.5, k 0.5), w 0 (proximity only), w 1 (preference only), k 0.3, k 1. For each, PFBC's plan is
rescored and the "more benefit", "less cost" and "less wild-trout impact" plans are solved (no change limit).
Tie-break weights scale each goal by PFBC's value (no payoff runs), so the base row differs slightly from
optimization.py's runs.csv on the non-improved goals.

Inputs : the same tables as optimization.py
Outputs: outputs/tables/sensitivities/benefit_assumptions.csv, outputs/figures/sensitivities/benefit_assumptions.png,
         logs/41_benefit_sensitivity.log
Run    : .venv/bin/python scripts/41_benefit_sensitivity.py   (15 solves, about 1.5 min)
"""
# %% Setup
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gurobipy import GRB

try:
    ROOT = Path(__file__).resolve().parents[1]
except NameError:     # running cell by cell in VS Code's interactive window: find the repo root
    ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / ".git").exists())
sys.path.insert(0, str(ROOT / "scripts"))
import optimization as o  # noqa: E402

FIG_DIR = ROOT / "outputs" / "figures" / "sensitivities"
TABLE_DIR = ROOT / "outputs" / "tables" / "sensitivities"
log = o.log


# %% Angler-benefit assumptions: demand blend w and saturation k (ranges in parameters.csv)
SETTINGS = [("base (w 0.5, k 0.5)", 0.5, 0.5), ("w 0 (proximity only)", 0.0, 0.5), ("w 1 (preference only)", 1.0, 0.5),
            ("k 0.3", 0.5, 0.3), ("k 1", 0.5, 1.0)]


def benefit_runs(d0: dict) -> pd.DataFrame:
    """For each (w, k): rescore PFBC's plan, then the three ways to beat it (no change limit). Tie-break weights
    scale each goal by PFBC's value instead of the payoff-table ranges optimization.py uses (no payoff runs here)."""
    mi, rows = d0["mi"], []
    for label, w, k in SETTINGS:
        d = dict(d0, w=w, k=k, D=((1 - w) * mi.prox_days + w * mi.pref_days).to_numpy(dtype=float))
        base = o.score(d, d["x0_hs"])
        B0, C0, I0 = base["B"], base["C"], base["I"]
        sm = o.StockingModel(d, "none")
        e = o.ETA
        for plan, obj, sense, kw in [
                ("More benefit", sm.B - e * B0 * (sm.C / C0 + sm.I / I0), GRB.MAXIMIZE, dict(eps_C=C0, eps_I=I0)),
                ("Less cost", sm.C + e * C0 * sm.I / I0, GRB.MINIMIZE, dict(eps_B=B0, eps_I=I0)),
                ("Less wild-trout impact", sm.I + e * I0 * sm.C / C0, GRB.MINIMIZE, dict(eps_B=B0, eps_C=C0))]:
            r = sm.solve(obj, sense, **kw)
            row = dict(setting=label, w=w, k=k, plan=plan, status=r["status"], B0=B0, C0=C0, I0=I0)
            if "x" in r:
                sc = o.score(d, r["x"])
                row.update({c: sc[c] for c in ["B", "C", "I", "n_closed"]},
                           **{f"{c}_pct": 100 * (sc[c] / base[c] - 1) for c in "BCI"})
            rows.append(row)
            log.info("%-24s %-24s B %+.1f%%  C %+.1f%%  I %+.1f%%", label, plan,
                     row.get("B_pct", np.nan), row.get("C_pct", np.nan), row.get("I_pct", np.nan))
        sm.m.dispose()
    return pd.DataFrame(rows)


def plot_benefit_runs(df: pd.DataFrame) -> None:
    """One panel per way to beat PFBC: the improved goal's % change under each (w, k) setting."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    panels = [("More benefit", "B_pct", "% more benefit"),
              ("Less cost", "C_pct", "% less cost"),
              ("Less wild-trout impact", "I_pct", "% less impact")]
    labels = [s[0] for s in SETTINGS]
    short = ["Base (w 0.5, k 0.5)", "w = 0 (proximity)", "w = 1 (preference)", "k = 0.3", "k = 1"]
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 3.0), sharey=True)
    for ax, (plan, col, title) in zip(axes, panels):
        v = df[df.plan == plan].set_index("setting")[col].reindex(labels).abs()
        colors = ["#1f3b57" if lab.startswith("base") else "#e07b39" for lab in labels]
        ax.barh(range(len(labels)), v, color=colors)
        for i, val in enumerate(v):
            ax.text(val, i, f" {val:.0f}%", va="center", fontsize=8)
        ax.set_title(f"{plan}\n{title} than PFBC", fontsize=9)
        ax.tick_params(labelsize=8)
        ax.set_xlim(0, v.max() * 1.3)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(range(len(labels)), short)
    axes[0].invert_yaxis()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "benefit_assumptions.png", dpi=200, facecolor="white")
    plt.close(fig)


# %% Run and save
if __name__ == "__main__":
    o.setup_logging("41_benefit_sensitivity")
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out = benefit_runs(o.load())
    out.to_csv(TABLE_DIR / "benefit_assumptions.csv", index=False)
    plot_benefit_runs(out)
    log.info("benefit assumptions:\n%s", out.drop(columns=["B0", "C0", "I0"]).round(1).to_string(index=False))
