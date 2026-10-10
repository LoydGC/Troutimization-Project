"""Exploratory: could PFBC give anglers its 2026 benefit with fewer fish, or fewer hatcheries?

Reuses scripts/optimization.py unchanged (load, score, StockingModel, no change limit). The total-fish equality
(C2, sum x = T) is relaxed to <=, so total fish can fall; each hatchery still ships at most its 2026 supply.

  A1  min total fish  s.t. B >= B_PFBC, C <= C_PFBC, I <= I_PFBC
  A2  min total fish  s.t. B >= B_PFBC only (cost and impact free): the lower bound
  B_h for each hatchery h: ship nothing from h, min total fish s.t. B >= B_PFBC, C <= C_PFBC, I <= I_PFBC
  C1  binary open_h, x[h, s] <= supply_h open_h: fewest hatcheries open (model cost), then every closure set of that
      size and every pair, each min total fish s.t. B, C, I no worse than PFBC (skipped when supply is short)

B in the model is the piecewise-linear B_pwl, an inner approximation of the concave exact benefit, so B_pwl >= B_PFBC
implies the exact B does too. C in the model uses fractional trips (a lower bound on the whole-trip scored C), so
"C <= C_PFBC" holds in model units and the scored C can come out higher: solve_scored() then tightens the model's
cost limit until the scored cost is no worse than PFBC's. Every plan is scored with score().
Small tie-breakers: total fish carries a tiny weight on model cost so equal-fish plans prefer cheaper ones.

Outputs: outputs/tables/exploratory/fewer_fish_runs.csv       one row per run (scored objectives, fish per hatchery)
         outputs/tables/exploratory/fewer_fish_sections.parquet x_s per run and section
         logs/40_exploratory_fewer_fish.log

    .venv/bin/python scripts/40_exploratory_fewer_fish.py
"""
from __future__ import annotations

import itertools
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from gurobipy import GRB

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import setup_logging  # noqa: E402
from optimization import MIP_GAP, StockingModel, load, score  # noqa: E402

OUT = ROOT / "outputs" / "tables" / "exploratory"
log = logging.getLogger("40_exploratory_fewer_fish")


def build(d: dict) -> StockingModel:
    sm = StockingModel(d, "none")
    sm.m.getConstrByName("total").Sense = GRB.LESS_EQUAL   # C2 relaxed: total fish may fall below T
    sm.F = sm.x.sum()
    sm.m.update()
    return sm


def main() -> None:
    setup_logging("40_exploratory_fewer_fish")
    OUT.mkdir(parents=True, exist_ok=True)
    d = load("weighted")
    hid = d["h"].hatchery.to_numpy()
    base = score(d, d["x0_hs"])
    B0, C0, I0 = base["B"], base["C"], base["I"]
    T0 = float(d["supply"].sum())   # the model's T (2,606,465); the 2026 count is 3 fish more (supply-table rounding)
    log.info("PFBC 2026: B %s, C $%s, I %s, fish %s", f"{B0:,.0f}", f"{C0:,.0f}", f"{I0:,.0f}", f"{T0:,.0f}")
    rows, plans = [], []

    def record(run_id: str, desc: str, sm: StockingModel, r: dict, closed: list[str]):
        row = dict(run_id=run_id, description=desc, status=r["status"], runtime_s=round(r["runtime"], 1),
                   eps_C_model=r.get("eps_C", np.nan),
                   hatcheries_closed=";".join(closed))
        if "x" in r:
            x = r["x"]
            sc = score(d, x)
            row.update(sc, B_pwl=r["B_pwl"], C_model=float(sm.C.getValue()), gap=r["gap"],
                       fish_lower_bound=float(sm.m.ObjBound) if sm.m.IsMIP else np.nan,
                       fish_saved=T0 - sc["total_fish"], fish_saved_pct=100 * (T0 - sc["total_fish"]) / T0,
                       C_saved=C0 - sc["C"], B_meets_pfbc=sc["B"] >= B0 - 1e-6, C_meets_pfbc=sc["C"] <= C0 + 1e-6,
                       I_meets_pfbc=sc["I"] <= I0 + 1e-6,
                       n_hatcheries_used=int((x.sum(axis=1) > 0.5).sum()))
            row.update({f"fish_{h}": float(v) for h, v in zip(hid, x.sum(axis=1))})
            plans.append((run_id, x))
            log.info("%-22s fish lower bound %s", run_id, f"{row['fish_lower_bound']:,.0f}")
            log.info("%-22s fish %s (saved %s, %.1f%%)  B %s  C $%s (model $%s)  I %s  gap %.3f  %.0fs",
                     run_id, f"{sc['total_fish']:,.0f}", f"{row['fish_saved']:,.0f}", row["fish_saved_pct"],
                     f"{sc['B']:,.0f}", f"{sc['C']:,.0f}", f"{row['C_model']:,.0f}", f"{sc['I']:,.0f}",
                     r["gap"], r["runtime"])
        else:
            log.info("%-22s status %d (infeasible / no solution)  %.0fs", run_id, r["status"], r["runtime"])
        rows.append(row)

    rows.append(dict(run_id="baseline", description="PFBC 2026 plan", hatcheries_closed="", **base,
                     fish_saved=T0 - base["total_fish"], fish_saved_pct=0.0, C_saved=0.0, n_hatcheries_used=len(hid),
                     **{f"fish_{h}": float(v) for h, v in zip(hid, d["x0_hs"].sum(axis=1))}))
    plans.append(("baseline", d["x0_hs"]))

    def solve_scored(sm: StockingModel, obj, cost=True) -> dict:
        """Min fish with B >= B0 (and, if cost, I <= I0 and C <= C0). The model's C uses fractional trips, so a plan
        can meet C <= C0 in the model but not when scored with whole trips: then eps_C is tightened by
        C0 / scored C and the solve repeated (up to 8 times) until the scored cost is no worse than PFBC's."""
        if not cost:
            r = sm.solve(obj, GRB.MINIMIZE, eps_B=B0)
            r["eps_C"] = np.nan
            return r
        eps = C0
        for _ in range(8):
            r = sm.solve(obj, GRB.MINIMIZE, eps_B=B0, eps_C=eps, eps_I=I0)
            r["eps_C"] = eps
            if "x" not in r:
                return r
            c = score(d, r["x"])["C"]
            if c <= C0:
                return r
            eps *= C0 / c * 0.99
        log.warning("scored cost still above PFBC's after 8 tightenings")
        return r

    sm = build(d)
    obj = sm.F + 1e-3 * (T0 / C0) * sm.C    # min fish; tiny cost tie-break (1e-3 fish per $ x scale)
    record("A1_min_fish", "min fish, B >= PFBC, C <= PFBC, I <= PFBC", sm, solve_scored(sm, obj), [])
    sm.m.Params.MIPGap = 1e-3      # same run at a 0.1% gap: the 1% gap leaves up to ~20k fish on the table
    record("A1_min_fish_gap0.1pct", "A1 at MIPGap 0.1% instead of 1%", sm, solve_scored(sm, obj), [])
    sm.m.Params.MIPGap = MIP_GAP
    record("A2_min_fish_B_only", "min fish, B >= PFBC only (cost, impact free)", sm, solve_scored(sm, obj, False), [])
    fish_lb = float(sm.m.ObjBound)

    # one hatchery off at a time
    for i, h in enumerate(hid):
        sm.x[i, :].UB = 0.0
        record(f"B_close_{h.replace(' ', '_')}", f"{h} ships nothing; min fish, B, C, I no worse than PFBC", sm,
               solve_scored(sm, obj), [h])
        sm.x[i, :].UB = GRB.INFINITY

    # most hatcheries closed at once: binary open_h on a fresh model
    sm2 = build(d)
    u = sm2.m.addMVar(len(hid), vtype=GRB.BINARY, name="open")
    sm2.m.addConstr(sm2.x.sum(axis=1) <= d["supply"] * u, name="open_link")
    r = sm2.solve(u.sum() + 1e-9 * sm2.F, GRB.MINIMIZE, eps_B=B0, eps_C=C0, eps_I=I0)
    n_open = int(round(u.X.sum())) if "x" in r else len(hid)
    log.info("C1: fewest hatcheries open (model cost) = %d (%s)", n_open, ", ".join(hid[u.X > 0.5]) if "x" in r else "-")
    sm2.m.dispose()

    # every closure set of that size (and pairs) whose remaining supply covers the fewest fish found (A2's bound)
    for size in sorted({2, len(hid) - n_open}):
        for combo in itertools.combinations(range(len(hid)), size):
            left = d["supply"].sum() - d["supply"][list(combo)].sum()
            names = list(hid[list(combo)])
            if left < fish_lb:
                log.info("closure %-40s remaining supply %s < %s fish needed: infeasible", "+".join(names),
                         f"{left:,.0f}", f"{fish_lb:,.0f}")
                continue
            for i in combo:
                sm.x[i, :].UB = 0.0
            record("C_close_" + "+".join(n.replace(" ", "_") for n in names),
                   f"close {', '.join(names)}; min fish, B, C, I no worse than PFBC", sm, solve_scored(sm, obj), names)
            for i in combo:
                sm.x[i, :].UB = GRB.INFINITY
    sm.m.dispose()

    runs = pd.DataFrame(rows)
    runs.to_csv(OUT / "fewer_fish_runs.csv", index=False)
    sid = d["mi"].section_id.to_numpy()
    pd.concat([pd.DataFrame({"run_id": rid, "section_id": sid, "x": x.sum(axis=0)}) for rid, x in plans]).to_parquet(
        OUT / "fewer_fish_sections.parquet", index=False)
    cols = ["run_id", "total_fish", "fish_saved", "fish_saved_pct", "B", "B_pwl", "C", "C_model", "I", "gap",
            "hatcheries_closed"]
    log.info("runs:\n%s", runs[[c for c in cols if c in runs]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
