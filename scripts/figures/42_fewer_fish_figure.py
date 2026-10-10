"""Report figure "How many fewer fish could PFBC produce?": most angler benefit possible against total stream fish
stocked (left), and fish per hatchery in PFBC's 2026 plan vs the fewest-fish plan (right).

The curve re-solves max benefit with total fish <= F (no change limit) for 12 values of F from 1.5M to 2.6M.
The fewest-fish plan and hatchery closures come from scripts/40_exploratory_fewer_fish.py (run it first).

Inputs : the same tables as optimization.py; outputs/tables/exploratory/fewer_fish_runs.csv
Outputs: outputs/tables/exploratory/fish_curve.csv, outputs/figures/exploratory_fewer_fish.png
Run    : .venv/bin/python scripts/figures/42_fewer_fish_figure.py   (12 solves, about 1 min)
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from gurobipy import GRB  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from optimization import StockingModel, load, score  # noqa: E402

TABLE_DIR = ROOT / "outputs" / "tables" / "exploratory"
FIG = ROOT / "outputs" / "figures" / "exploratory_fewer_fish.png"
NAVY, RED, GREEN = "#1f3b57", "#c0392b", "#2e7d5b"
MUST_STAY = {"Bellefonte", "Huntsdale"}   # the two hatcheries that cannot close alone (fewer_fish_runs.csv)


def fish_curve() -> pd.DataFrame:
    d = load("weighted")
    sm = StockingModel(d, "none")
    tot = sm.m.getConstrByName("total")
    tot.Sense = GRB.LESS_EQUAL
    rows = []
    for F in np.linspace(1.5e6, 2.6e6, 12):
        tot.RHS = F
        r = sm.solve(sm.B, GRB.MAXIMIZE)
        s = score(d, r["x"])
        rows.append(dict(F=F, B=s["B"], C=s["C"], fish=s["total_fish"]))
        print(f"{F:,.0f} fish: B {s['B']:,.0f}", flush=True)
    sm.m.dispose()
    return pd.DataFrame(rows)


def plot(c: pd.DataFrame, r: pd.DataFrame) -> None:
    b, p = r.loc["baseline"], r.loc["A1_min_fish_gap0.1pct"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 6.3), dpi=200, gridspec_kw=dict(width_ratios=[1.1, 1]))
    # left: benefit vs total fish
    a1.plot(c.fish / 1e6, c.B / 1e6, "-o", color=NAVY, lw=2.6, ms=5, zorder=3)
    a1.fill_between(c.fish / 1e6, c.B / 1e6, 2.3, color=NAVY, alpha=0.06)
    bx, by, px = b.total_fish / 1e6, b.B / 1e6, p.total_fish / 1e6
    a1.axhline(by, color=RED, lw=0.8, ls=":")
    a1.plot(bx, by, "X", color=RED, ms=16, mec="white", mew=1.5, zorder=5)
    a1.annotate("PFBC 2026", (bx, by), xytext=(0, 14), textcoords="offset points", color=RED, fontsize=12,
                weight="bold", ha="right")
    a1.plot(px, by, "o", color=GREEN, ms=11, mec="white", mew=1.5, zorder=5)
    a1.annotate("", (px, by), xytext=(bx, by),
                arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=2.2, shrinkA=10, shrinkB=8), zorder=4)
    a1.text(2.585, 2.95, f"Same benefit,\n{(b.total_fish - p.total_fish) / 1e3:,.0f}k fewer fish (−{p.fish_saved_pct:.0f}%)",
            ha="right", va="top", color=GREEN, fontsize=12.5, weight="bold")
    a1.set_xlabel("Total stream fish stocked (millions per year)", fontsize=13)
    a1.set_ylabel("Angler-days with a catch (millions per year)", fontsize=13)
    a1.set_title("Fewer fish, same benefit", fontsize=15, weight="bold", loc="left")
    a1.set_ylim(2.3, 3.75)
    # right: fish per hatchery
    hs = sorted([c_[5:] for c_ in r.columns if c_.startswith("fish_") and c_ != "fish_saved_pct"],
                key=lambda h: -b[f"fish_{h}"])
    y = np.arange(len(hs))
    a2.barh(y - 0.2, [b[f"fish_{h}"] / 1e3 for h in hs], 0.38, color="#bbb", label="PFBC 2026")
    a2.barh(y + 0.2, [p[f"fish_{h}"] / 1e3 for h in hs], 0.38, color=NAVY, label="Fewest-fish plan")
    a2.set_yticks(y, [h + ("" if h in MUST_STAY else "  ✓") for h in hs], fontsize=11.5)
    for t, h in zip(a2.get_yticklabels(), hs):
        t.set_color(NAVY if h in MUST_STAY else GREEN)
    a2.invert_yaxis()
    a2.set_xlabel("Fish per year (thousands)", fontsize=13)
    a2.set_title("Fish by hatchery", fontsize=15, weight="bold", loc="left")
    a2.legend(loc="lower right", bbox_to_anchor=(1, 0.22), frameon=False, fontsize=11.5)
    a2.text(0.98, 0.04, "✓ could close on its own\n   (up to 3 at once)", transform=a2.transAxes, ha="right",
            color=GREEN, fontsize=11.5)
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25)
        ax.tick_params(labelsize=11)
    fig.text(0.01, -0.02, f"Fewest-fish plan: PFBC's 2026 angler benefit with {p.total_fish / 1e6:.2f}M fish; transport "
             f"\\${p.C / 1e3:,.0f}k vs \\${b.C / 1e3:,.0f}k, wild-trout impact −{100 * (1 - p.I / b.I):.0f}%. Production "
             "savings ≈ \\$1.5M/yr at \\$3.37 per adult trout (LBFC 2010, 2025\\$). Stream fish only; lakes not modeled.",
             fontsize=10.5, color="#555")
    plt.tight_layout()
    fig.savefig(FIG, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    curve = fish_curve()
    curve.to_csv(TABLE_DIR / "fish_curve.csv", index=False)
    plot(curve, pd.read_csv(TABLE_DIR / "fewer_fish_runs.csv").set_index("run_id"))
