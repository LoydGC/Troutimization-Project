"""Sensitivity: truck capacity (fish per truck trip) on the angler-benefit-maximizing plans, next to PFBC's 2026 plan.

For each capacity (1,000 / 2,500 / 3,500 current / 5,000 / 10,000) the model is rebuilt with that capacity in the trip-count
constraint (trips = ceil(round fish in a cluster / capacity), model_formulation.md) and two benefit-maximizing plans are solved
(no change limit, same model as scripts/optimization.py; everything else unchanged, including the $1.90 per truck-mile):
  max_benefit   max B with no limit on cost or impact; ties broken by lower cost, then lower impact (the payoff-table plan)
  more_benefit  max B with cost no higher and wild-trout impact no higher than PFBC's 2026 plan scored at the SAME capacity
                (the "more benefit" way to beat PFBC; ties broken by lower cost, then lower impact)
PFBC's 2026 plan (baseline_flows) is re-scored at each capacity with the same scoring function, so each comparison is
like for like. Plans are scored exactly (whole trips, exact benefit curve), as in runs.csv.

Inputs : data/processed/ (via scripts/optimization.py load)
Outputs: outputs/tables/sensitivity_truck_capacity/{truck_capacity_runs.csv,flows_<mode>.parquet}
         outputs/figures/sensitivity_truck_capacity/truck_capacity_sensitivity.png      logs/37_truck_capacity_sensitivity.log

    python scripts/37_truck_capacity_sensitivity.py [--trip-mode fractional|integer]      (default fractional, as the team's runs)
"""
# %% Setup
from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd
from gurobipy import GRB

import optimization as opt
from common import ROOT, setup_logging

CAPACITIES = [1000, 2500, 3500, 5000, 10000]
CURRENT = 3500
OUT_T = ROOT / "outputs" / "tables" / "sensitivity_truck_capacity"
OUT_F = ROOT / "outputs" / "figures" / "sensitivity_truck_capacity"
log = logging.getLogger("37_truck_capacity_sensitivity")


def lex(sm, order: list[tuple[str, int]], **eps) -> dict:
    """Optimize in order, holding each optimum (1e-6) before the next; eps = fixed epsilon rows (eps_C, eps_I)."""
    rhs = dict(eps)
    r = None
    for name, sense in order:
        r = sm.solve(getattr(sm, name), sense, **rhs)
        if "x" not in r:
            return r
        val = {"B": r["B_pwl"], "C": float(sm.C.getValue()), "I": float(sm.I.getValue())}[name]
        rhs[f"eps_{name}"] = val * (1 - 1e-6) if sense == GRB.MAXIMIZE else val * (1 + 1e-6) + 1e-6
    return r


def main(trip_mode: str) -> None:
    setup_logging(f"37_truck_capacity_sensitivity_{trip_mode}")
    OUT_T.mkdir(parents=True, exist_ok=True)
    d = opt.load()
    x0 = d["x0_hs"]
    rows, flows = [], {}
    for cap in CAPACITIES:
        d["truck_cap"] = float(cap)
        base = opt.score(d, x0)
        rows.append(dict(capacity=cap, plan="pfbc_2026", trip_mode="-", runtime_s=0.0, status=np.nan, gap=np.nan, **base))
        flows[(cap, "pfbc_2026")] = x0
        log.info("cap %5d  PFBC 2026: B %s  C $%s  I %s  trips %d", cap, f"{base['B']:,.0f}", f"{base['C']:,.0f}", f"{base['I']:,.0f}", base["trips"])
        sm = opt.StockingModel(d, "none", trip_mode=trip_mode)
        plans = {"max_benefit": dict(order=[("B", GRB.MAXIMIZE), ("C", GRB.MINIMIZE), ("I", GRB.MINIMIZE)], eps={}),
                 "more_benefit": dict(order=[("B", GRB.MAXIMIZE), ("C", GRB.MINIMIZE), ("I", GRB.MINIMIZE)],
                                      eps=dict(eps_C=base["C"], eps_I=base["I"]))}
        for name, p in plans.items():
            r = lex(sm, p["order"], **p["eps"])
            if "x" not in r:
                log.warning("cap %d %s: no solution (status %s)", cap, name, r["status"])
                continue
            sc = opt.score(d, r["x"])
            rows.append(dict(capacity=cap, plan=name, trip_mode=trip_mode, runtime_s=round(r["runtime"], 1), status=r["status"], gap=r["gap"],
                             model_cost=float(sm.C.getValue()), **sc))
            flows[(cap, name)] = r["x"]
            log.info("cap %5d  %-12s B %s  C $%s (model $%s)  I %s  trips %d  closed %d  moved %.0f%%  %.1fs", cap, name, f"{sc['B']:,.0f}",
                     f"{sc['C']:,.0f}", f"{rows[-1]['model_cost']:,.0f}", f"{sc['I']:,.0f}", sc["trips"], sc["n_closed"], 100 * sc["share_moved"], r["runtime"])
        sm.m.dispose()
    res = pd.DataFrame(rows)
    res.to_csv(OUT_T / f"truck_capacity_runs_{trip_mode}.csv", index=False)
    ids = d["mi"].section_id.to_numpy()
    hid = d["h"].hatchery_id.to_numpy()
    long = [pd.DataFrame(x, index=hid, columns=ids).rename_axis("hatchery_id").reset_index().melt("hatchery_id", var_name="section_id", value_name="fish")
            .assign(capacity=cap, plan=name) for (cap, name), x in flows.items()]
    long = pd.concat(long)
    long[long.fish > 0.5].to_parquet(OUT_T / f"flows_{trip_mode}.parquet", index=False)
    log.info("wrote %d rows to %s", len(res), OUT_T)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trip-mode", default="fractional", choices=["fractional", "integer"])
    main(ap.parse_args().trip_mode)
