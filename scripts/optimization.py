"""Stocking optimization (Gurobi): how should each hatchery's trout be spread across the stocked sections?

Model (docs/model_formulation.md, docs/model_design.md):
  sets         h = the 9 hatcheries with 2026 stream fish; s = the 1,022 sections stocked in 2026
  variables    x[h, s] >= 0 fish/yr; y[s] binary (section stocked); zz[s] binary (more than 600 fish, so a second stocking);
               a[h, s] round-1 fish; tau[r, h, g] truck trips by round, hatchery and cluster (continuous by default);
               z[s, j] >= 0 piecewise-linear benefit segments
  objectives   kept separate, never weighted together:
               benefit B = sum_s D_s (1 - exp(-x_s / (k D_s)))   angler-days with a catch       (max)
               cost    C = sum_rhg 2 t_cost miles[h, g] tau[r, h, g]   $/yr, truck trips at k-medoids cluster miles (min)
               impact  I = sum_s omega_s x_s   wild-trout impact (min): omega = impact_weighted (main: biomass weight
                       x share on wild-trout water, class D = 1), or impact_simple / impact_overlap (--impact)
  constraints  supply: sum_s x[h, s] <= supply_h; total: sum_s x_s = T = sum_h supply_h
               minimum: 300 y_s <= x_s; density cap: x_s <= cap_fish_s y_s
               stockings: one up to 600 fish, n_s above (zz); trips: round fish in a cluster <= 3,500 tau (docs/model_formulation.md, Transit)
               change limit (option): none | band (L x0 <= x_s <= U x0) | close_or_band (the band, or 0)
  solve        payoff table (each objective alone, ties broken lexicographically), PFBC's 2026 baseline scored on
               the same three objectives, the dominance run (max B with C <= C0 and I <= I0), PFBC's benefit for
               less (min C with B >= B0 and I <= I0; min I with B >= B0 and C <= C0), then 1-D epsilon
               curves: max B with C <= eps (I free) and with I <= eps (C free). AUGMECON: the epsilon runs maximize
               B - eta R_B (C / R_C + I / R_I), so every point is efficient.
  benefit      piecewise linear in Gurobi (concave, so no SOS); reported from the exact formula.

Inputs : data/processed/model_input.parquet (21), hatcheries.parquet, cost_matrix.parquet, baseline_flows.parquet (20),
         parameters.csv
Outputs: outputs/tables/optimization/runs.csv              one row per solve: the three objectives and plan stats
         outputs/tables/optimization/sections.parquet      x_s per run and section
         outputs/tables/optimization/flows.parquet         non-zero x[h, s] per run
         outputs/figures/optimization/tradeoff_curves.png  benefit vs cost and vs impact, PFBC's plan marked
         logs/optimization.log

    .venv/bin/python scripts/optimization.py                       (all change-limit variants, 8 points per curve)
    .venv/bin/python scripts/optimization.py --variants none --points 4
    .venv/bin/python scripts/optimization.py --impact simple            (impact version: weighted | simple | overlap)

Run it with VS Code's "Run Python File", or cell by cell with the "Run Cell" links above each # %%.
"""
# %% Setup
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import gurobipy as gp
import numpy as np
import pandas as pd
import scipy.sparse as sp
from gurobipy import GRB

try:
    ROOT = Path(__file__).resolve().parents[1]
except NameError:     # running cell by cell in VS Code's interactive window: find the repo root
    ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / ".git").exists())
sys.path.insert(0, str(ROOT / "scripts"))
from common import setup_logging  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
TABLE_DIR = ROOT / "outputs" / "tables" / "optimization"
FIG_DIR = ROOT / "outputs" / "figures" / "optimization"
# piecewise-linear breakpoints for the benefit curve, in units of k (fish per angler-day / k). Every 0.05 from 0.5 to
# 1.5, where today's statewide 0.37 fish per angler-day (0.73 k) and the plans sit: within one straight segment every
# section is worth the same per fish, so coarse segments leave the split to tie-breaking. Flat within 0.03% past 8
BREAKS = np.concatenate([[0, .05, .1, .15, .2, .3, .4], np.arange(.5, 1.5001, .05), [1.75, 2, 2.5, 3, 4, 6, 8]])
ETA = 1e-3            # AUGMECON weight on the slack terms
MIP_GAP = 1e-2
TIME_LIMIT = 120      # seconds per solve
TRIP_MODE = "fractional"   # "integer" keeps whole trips inside the model (about 2 min per constrained solve)

log = logging.getLogger("optimization")


def param(name: str) -> float:
    p = pd.read_csv(PROCESSED / "parameters.csv").set_index("parameter")
    return float(p.loc[name, "value"])


# %% Load inputs
IMPACT_COLS = {"weighted": "impact_weighted", "simple": "impact_simple", "overlap": "impact_overlap"}


def load(impact: str = "weighted") -> dict:
    mi = pd.read_parquet(PROCESSED / "model_input.parquet")
    assert mi.complete.all() and not mi.exclude.any()
    h = pd.read_parquet(PROCESSED / "hatcheries.parquet")
    h = h[h.in_2026_schedule].reset_index(drop=True)
    cm = pd.read_parquet(PROCESSED / "cost_matrix.parquet")
    cost = (cm.pivot(index="hatchery_id", columns="section_id", values="cost_per_fish")
            .reindex(index=h.hatchery_id, columns=mi.section_id).to_numpy(dtype=float))
    miles = (cm.pivot(index="hatchery_id", columns="section_id", values="cluster_road_mi")
             .reindex(index=h.hatchery_id, columns=mi.section_id).to_numpy(dtype=float))
    assert not np.isnan(cost).any()
    bf = pd.read_parquet(PROCESSED / "baseline_flows.parquet")
    x0_hs = (bf.pivot_table(index="hatchery_id", columns="section_id", values="fish", aggfunc="sum")
             .reindex(index=h.hatchery_id, columns=mi.section_id).fillna(0).to_numpy(dtype=float))
    w, k = param("blend_weight_w"), param("benefit_saturation_k")
    D = ((1 - w) * mi.prox_days + w * mi.pref_days).to_numpy(dtype=float)
    d = dict(mi=mi, h=h, cost=cost, miles=miles, x0_hs=x0_hs, x0=mi.x0.to_numpy(dtype=float), D=D, k=k, w=w,
             cap=mi.cap_fish.to_numpy(dtype=float), omega=mi[IMPACT_COLS[impact]].to_numpy(dtype=float), impact=impact,
             supply=h.supply.to_numpy(dtype=float), min_fish=param("min_fish_per_section"),
             L=param("change_limit_lower"), U=param("change_limit_upper"),
             fish_per_load=param("fish_per_load"), n_stock=mi.n_stockings.to_numpy(dtype=float),
             truck_cap=param("truck_capacity"), t_cost=param("cost_per_truck_mile"), p_pre=param("preseason_share"), one_max=param("stocking_one_max_fish"))
    # clusters: section -> cluster index; miles_g[h, g] = the cluster's average road miles (same for every member)
    gid = pd.factorize(cm.drop_duplicates("section_id").set_index("section_id").cluster_id.reindex(mi.section_id))[0]
    first = np.array([np.flatnonzero(gid == g)[0] for g in range(gid.max() + 1)])
    d.update(gid=gid, miles_g=miles[:, first], G=sp.csr_matrix((np.ones(len(gid)), (np.arange(len(gid)), gid))))
    log.info("inputs: %d hatcheries (supply %s), %d sections, demand %s angler-days (w = %g), k = %g, impact %s (%s)",
             len(h), f"{d['supply'].sum():,.0f}", len(mi), f"{D.sum():,.0f}", w, k, impact, IMPACT_COLS[impact])
    return d


def stockings(x_s, n_stock, one_max=600.0):
    """Stockings per section: 0 if closed, 1 up to one_max fish (600), n_s above it (decision 2026-10-04)."""
    return np.where(x_s > 0.5, np.where(x_s > one_max + 1e-6, n_stock, 1.0), 0.0)


def round_shares(d: dict, xs: np.ndarray):
    """Fish share of each section in rounds 1-3 (rows), model_formulation.md Transit table."""
    two, p, n = xs > d["one_max"] + 1e-6, d["p_pre"], d["n_stock"]
    r1 = np.where(two, p, 1.0)
    r2 = np.where(two, (1 - p) / (n - 1), 0.0)
    r3 = np.where(two & (n >= 3), (1 - p) / (n - 1), 0.0)
    return np.array([r1, r2, r3])


def trips(d: dict, x_hs: np.ndarray) -> np.ndarray:
    """Whole truck trips per (round, hatchery, cluster) for any plan: ceil(round fish in the cluster / capacity)."""
    sh = round_shares(d, x_hs.sum(axis=0))
    return np.array([np.ceil((x_hs * s[None, :]) @ d["G"] / d["truck_cap"] - 1e-9) for s in sh])


# %% Scoring (exact benefit, same for the baseline and every plan)
def score(d: dict, x_hs: np.ndarray) -> dict:
    xs = x_hs.sum(axis=0)
    B = float((d["D"] * (1 - np.exp(-xs / (d["k"] * d["D"])))).sum())
    tr = trips(d, x_hs)
    C = float(2 * (tr * d["miles_g"][None]).sum() * d["t_cost"])
    C_linear = float((d["cost"] * x_hs).sum())
    I = float((d["omega"] * xs).sum())
    truck_mi = float(2 * (tr * d["miles_g"][None]).sum())
    x0 = d["x0"]
    stocked = xs > 0.5
    ratio = np.divide(xs, x0, out=np.zeros_like(xs), where=x0 > 0)
    high = d["mi"].use_potential.eq("High").to_numpy()
    return dict(B=B, C=C, C_linear=C_linear, I=I, trips=int(tr.sum()), truck_miles=truck_mi, stockings=float(stockings(xs, d["n_stock"], d["one_max"]).sum()),
                n_550_600=int(((xs >= 550) & (xs <= 600 + 1e-6)).sum()), total_fish=float(xs.sum()), n_stocked=int(stocked.sum()),
                n_closed=int((~stocked & (x0 > 0)).sum()), n_doubled=int((ratio >= 2 - 1e-6).sum()),
                n_halved_or_less=int((stocked & (ratio <= 0.5 + 1e-6)).sum()),
                share_moved=float(np.abs(xs - x0).sum() / 2 / x0.sum()),
                high_access_fish_vs_2026=float(xs[high].sum() / x0[high].sum()),
                fish_per_angler_day_p10=float(np.quantile(xs / d["D"], 0.1)),
                fish_per_angler_day_p90=float(np.quantile(xs / d["D"], 0.9)))


# %% Build the model
class StockingModel:
    """One Gurobi model per change-limit variant; runs only change objective and epsilon right-hand sides."""

    def __init__(self, d: dict, change_limit: str = "none", trip_cost: bool = True, trip_mode: str = TRIP_MODE):
        self.d, self.change_limit = d, change_limit
        nh, ns = d["cost"].shape
        m = self.m = gp.Model(f"stocking_{change_limit}")
        m.Params.OutputFlag = 0
        m.Params.MIPGap = MIP_GAP
        m.Params.TimeLimit = TIME_LIMIT
        self.x = x = m.addMVar((nh, ns), lb=0.0, name="x")
        xs = x.sum(axis=0)
        # benefit segments: width k D_s (beta_j - beta_j-1) fish, slope (e^-b_j-1 - e^-b_j) / (k (b_j - b_j-1))
        db = np.diff(BREAKS)
        slope = (np.exp(-BREAKS[:-1]) - np.exp(-BREAKS[1:])) / (d["k"] * db)
        width = d["k"] * d["D"][:, None] * db[None, :]
        self.z = z = m.addMVar(width.shape, lb=0.0, ub=width, name="z")
        m.addConstr(z.sum(axis=1) <= xs, name="benefit_link")   # <=, not ==: fish past the last breakpoint add nothing
        self.B = (z @ slope).sum()
        self.C = (x * d["cost"]).sum()   # linear per-fish cost; replaced by trip cost below when trip_cost
        self.I = (x * d["omega"][None, :]).sum()
        m.addConstr(x.sum(axis=1) <= d["supply"], name="supply")
        m.addConstr(xs.sum() == d["supply"].sum(), name="total")
        x0, cap, lo_min = d["x0"], d["cap"].copy(), d["min_fish"]
        if change_limit == "band":         # every section stays within [L, U] x today: y = 1, an LP
            m.addConstr(xs >= np.maximum(d["L"] * x0, lo_min), name="band_lo")
            m.addConstr(xs <= np.minimum(cap, d["U"] * x0), name="band_hi")
        else:
            self.y = y = m.addMVar(ns, vtype=GRB.BINARY, name="y")
            lo = np.full(ns, lo_min)
            if change_limit == "close_or_band":   # 0 fish, or within [L, U] x today
                lo, cap = np.maximum(d["L"] * x0, lo_min), np.minimum(cap, d["U"] * x0)
            else:
                assert change_limit == "none", change_limit
            m.addConstr(xs >= lo * y, name="min_fish")
            m.addConstr(xs <= cap * y, name="cap")
        if trip_cost:
            self._add_trips(d, ns, x, xs, cap, trip_mode)
        # epsilon rows, inactive until a run sets them
        self.cB = m.addConstr(self.B >= -GRB.INFINITY, name="eps_B")
        self.cC = m.addConstr(self.C <= GRB.INFINITY, name="eps_C")
        self.cI = m.addConstr(self.I <= GRB.INFINITY, name="eps_I")
        m.update()
        log.info("model %s: %d vars (%d binary), %d constraints", change_limit, m.NumVars, m.NumBinVars, m.NumConstrs)

    def _add_trips(self, d: dict, ns: int, x, xs, cap, trip_mode: str = "integer") -> None:
        """C3b + Transit (model_formulation.md): zz_s = 1 if s gets > 600 fish (n_s stockings); a[h,s] = round-1 fish
        (x if zz = 0, p x if zz = 1; big-M with cap_s); later rounds split x - a over n_s - 1; whole trips per
        (round, hatchery, cluster). trip_mode "integer" = whole trips in the model (exact, slow); "fractional" =
        continuous trips, rounded up only when scoring (fast; the model cost is a lower bound on the scored cost)."""
        m, nh, p, T = self.m, d["cost"].shape[0], d["p_pre"], d["truck_cap"]
        self.zz = zz = m.addMVar(ns, vtype=GRB.BINARY, name="two")
        if hasattr(self, "y"):
            m.addConstr(zz <= self.y, name="two_if_stocked")
        big = np.maximum(cap, d["one_max"])
        m.addConstr(xs <= d["one_max"] + (big - d["one_max"]) * zz, name="one_stocking")
        m.addConstr(xs >= (d["one_max"] + 0.01) * zz, name="two_means_over_600")   # else z = 1 could split small loads to dodge trips
        self.a = a = m.addMVar((nh, ns), lb=0.0, name="round1")
        zb, M = zz[None, :], big[None, :]
        m.addConstr(a >= p * x, name="a_lo")
        m.addConstr(a >= x - (1 - p) * M * zb, name="a_lo_one")
        m.addConstr(a <= p * x + (1 - p) * M * (1 - zb), name="a_hi")
        n = d["n_stock"]
        later = x - a
        cost = 0
        self.tau = []
        for r, w in enumerate([None, (n >= 2) / (n - 1), (n >= 3) / (n - 1)]):
            Gr = d["G"] if w is None else sp.diags(w) @ d["G"]
            members = np.flatnonzero(np.asarray((Gr != 0).sum(axis=0)).ravel())
            Gr = Gr[:, members].tocsr()
            tau = m.addMVar((nh, len(members)), vtype=GRB.INTEGER if trip_mode == "integer" else GRB.CONTINUOUS, lb=0.0, name=f"trips{r + 1}")
            m.addConstr(((a if w is None else later) @ Gr) <= T * tau, name=f"load{r + 1}")
            cost = cost + (2 * d["t_cost"] * d["miles_g"][:, members] * tau).sum()
            self.tau.append(tau)
        self.C = cost

    def solve(self, objective, sense, eps_B=None, eps_C=None, eps_I=None) -> dict:
        self.cB.RHS = -GRB.INFINITY if eps_B is None else eps_B
        self.cC.RHS = GRB.INFINITY if eps_C is None else eps_C
        self.cI.RHS = GRB.INFINITY if eps_I is None else eps_I
        self.m.setObjective(objective, sense)
        t = time.time()
        self.m.optimize()
        st = self.m.Status
        if st not in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL) or self.m.SolCount == 0:
            return dict(status=st, runtime=time.time() - t)
        x = self.x.X
        out = dict(status=st, runtime=time.time() - t, B_pwl=float(self.B.getValue()), x=x,
                   gap=float(self.m.MIPGap) if self.m.IsMIP else 0.0)
        return out

    def lexicographic(self, order: list[tuple[str, int]]) -> dict:
        """Optimize objectives in order, holding each optimum (1e-6 relative) before the next."""
        rhs = {}
        for name, sense in order:
            r = self.solve(getattr(self, name), sense, **{f"eps_{k}": v for k, v in rhs.items()})
            if "x" not in r:
                return r
            val = {"B": r["B_pwl"], "C": float(self.C.getValue()), "I": float(self.I.getValue())}[name]
            rhs[name] = val * (1 - 1e-6) if sense == GRB.MAXIMIZE else val * (1 + 1e-6) + 1e-6
        return r

    def augmecon(self, R: dict, eps_C=None, eps_I=None) -> dict:
        """Max B with C <= eps_C and I <= eps_I, plus a small reward for slack in both (efficient points only)."""
        obj = self.B - (ETA * R["B"] / R["C"]) * self.C - (ETA * R["B"] / R["I"]) * self.I
        return self.solve(obj, GRB.MAXIMIZE, eps_C=eps_C, eps_I=eps_I)


# %% Solve and save
def run_variant(d: dict, variant: str, points: int, base_row: dict, trip_mode: str = TRIP_MODE) -> tuple[list, list]:
    sm = StockingModel(d, variant, trip_mode=trip_mode)
    rows, plans = [], []

    def record(run_id: str, kind: str, r: dict, eps_C=None, eps_I=None):
        row = dict(run_id=run_id, variant=variant, kind=kind, eps_C=eps_C, eps_I=eps_I, status=r["status"],
                   runtime_s=round(r["runtime"], 1))
        if "x" in r:
            row.update(score(d, r["x"]), B_pwl=r["B_pwl"], gap=r["gap"])
            plans.append((run_id, r["x"]))
        rows.append(row)
        log.info("%-34s status %d  B %s  C $%s  I %s  stocked %s  %.1fs", run_id, r["status"],
                 f"{row.get('B', float('nan')):,.0f}", f"{row.get('C', float('nan')):,.0f}",
                 f"{row.get('I', float('nan')):,.0f}", row.get("n_stocked"), r["runtime"])
        return row

    # payoff table: each objective first, ties broken by the other two
    pay = {}
    for name, order in [("max_B", [("B", GRB.MAXIMIZE), ("C", GRB.MINIMIZE), ("I", GRB.MINIMIZE)]),
                        ("min_C", [("C", GRB.MINIMIZE), ("B", GRB.MAXIMIZE), ("I", GRB.MINIMIZE)]),
                        ("min_I", [("I", GRB.MINIMIZE), ("B", GRB.MAXIMIZE), ("C", GRB.MINIMIZE)])]:
        r = sm.lexicographic(order)
        pay[name] = record(f"{variant}|payoff|{name}", "payoff", r)
        if "x" in r:
            pay[name]["C_model"] = float(sm.C.getValue())   # the model's own cost (fractional trips), what eps_C limits
    if any("B" not in p for p in pay.values()):
        log.warning("%s: a payoff run failed, skipping its curves", variant)
        return rows, plans
    R = {"B": pay["max_B"]["B_pwl"] - min(pay["min_C"]["B_pwl"], pay["min_I"]["B_pwl"]),
         "C": max(pay["max_B"]["C_model"], pay["min_I"]["C_model"]) - pay["min_C"]["C_model"],
         "I": max(pay["max_B"]["I"], pay["min_C"]["I"]) - pay["min_I"]["I"]}
    R = {k: max(v, 1e-6) for k, v in R.items()}
    log.info("%s ranges (payoff table): B %s, C $%s, I %s", variant, f"{R['B']:,.0f}", f"{R['C']:,.0f}", f"{R['I']:,.0f}")

    # dominance: at least as good as PFBC's plan on cost and impact
    record(f"{variant}|dominance", "dominance", sm.augmecon(R, eps_C=base_row["C"], eps_I=base_row["I"]),
           eps_C=base_row["C"], eps_I=base_row["I"])
    # PFBC's benefit for less: min cost (impact no worse), and min impact (cost no worse), each with B >= B0
    for name, obj, kw in [("same_benefit_min_C", sm.C + ETA * R["C"] / R["I"] * sm.I, dict(eps_I=base_row["I"])),
                          ("same_benefit_min_I", sm.I + ETA * R["I"] / R["C"] * sm.C, dict(eps_C=base_row["C"]))]:   # small weight on the other goal breaks ties
        record(f"{variant}|{name}", "same_benefit", sm.solve(obj, GRB.MINIMIZE, eps_B=base_row["B"], **kw), **kw)
    # 1-D curves from each objective's best to its value at max B. Cost limits are in model units (fractional
    # trips), which run below the whole-trip cost every plan is scored with: a range in scored units would put
    # most points past max B, where they all repeat it
    for obj, lo, hi in [("C", pay["min_C"]["C_model"], pay["max_B"]["C_model"]), ("I", pay["min_I"]["I"], pay["max_B"]["I"])]:
        for i, eps in enumerate(np.linspace(lo, hi, points)):
            kw = {f"eps_{obj}": eps}
            record(f"{variant}|curve_{obj}|{i}", f"curve_{obj}", sm.augmecon(R, **kw), **kw)
    sm.m.dispose()
    return rows, plans


IMPACT_CAPS = [0.25, 0.5, 0.75, 1.0, None]   # wild-trout impact limits as a share of PFBC's 2026 impact; None = no limit


def goal_sweeps(d: dict, base: dict, points: int = 8, impact: str = "weighted", trip_mode: str = TRIP_MODE) -> pd.DataFrame:
    """Benefit vs transport cost, one curve per wild-trout impact limit (no change limit). Everything scored exactly."""
    sm = StockingModel(d, "none", trip_mode=trip_mode)
    pay = {n: sm.lexicographic(o) for n, o in [("max_B", [("B", GRB.MAXIMIZE), ("C", GRB.MINIMIZE), ("I", GRB.MINIMIZE)]),
                                               ("min_C", [("C", GRB.MINIMIZE), ("B", GRB.MAXIMIZE), ("I", GRB.MINIMIZE)]),
                                               ("min_I", [("I", GRB.MINIMIZE), ("B", GRB.MAXIMIZE), ("C", GRB.MINIMIZE)])]}
    sc = {n: score(d, r["x"]) for n, r in pay.items()}
    R = {"B": sc["max_B"]["B"] - min(sc["min_C"]["B"], sc["min_I"]["B"]),
         "C": max(sc["max_B"]["C"], sc["min_I"]["C"]) - sc["min_C"]["C"],
         "I": max(sc["max_B"]["I"], sc["min_C"]["I"]) - sc["min_I"]["I"]}
    rows = []
    for share in IMPACT_CAPS:
        cap = None if share is None else share * base["I"]
        r0 = sm.solve(sm.C, GRB.MINIMIZE, eps_I=cap)
        lo = float(sm.C.getValue())
        for eps in np.linspace(lo, sc["max_B"]["C"] * 1.01, points):
            r = sm.augmecon(R, eps_C=eps, eps_I=cap)
            if "x" in r:
                rows.append(dict(impact_cap_share=share, eps_C=eps, **score(d, r["x"]), gap=r["gap"], runtime_s=r["runtime"]))
        log.info("goal sweep impact cap %s: %d points", share, sum(r_["impact_cap_share"] == share for r_ in rows))
    # three ways to beat PFBC's 2026 plan, each improving one goal and holding the other two at PFBC's level
    ways = []
    wC, wI = ETA * R["B"] / R["C"], ETA * R["B"] / R["I"]
    for name, obj, sense, kw in [("More benefit", sm.B - wC * sm.C - wI * sm.I, GRB.MAXIMIZE, dict(eps_C=base["C"], eps_I=base["I"])),
                                 ("Less cost", sm.C + (R["C"] / R["I"]) * ETA * sm.I, GRB.MINIMIZE, dict(eps_B=base["B"], eps_I=base["I"])),
                                 ("Less wild-trout impact", sm.I + (R["I"] / R["C"]) * ETA * sm.C, GRB.MINIMIZE, dict(eps_B=base["B"], eps_C=base["C"]))]:
        r = sm.solve(obj, sense, **kw)
        ways.append(dict(plan=name, **score(d, r["x"]), gap=r["gap"]))
    ways = pd.DataFrame(ways)
    # grid of cost and impact limits, best benefit at each (for the cost-vs-impact map)
    grid = []
    for cs in np.linspace(sc["min_C"]["C"], sc["max_B"]["C"] * 1.01, 6):
        for share in np.linspace(0.2, 1.2, 6):
            r = sm.augmecon(R, eps_C=cs, eps_I=share * base["I"])
            if "x" in r:
                grid.append(dict(eps_C=cs, impact_cap_share=share, **score(d, r["x"])))
    grid = pd.DataFrame(grid)
    sm.m.dispose()
    out = pd.DataFrame(rows)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLE_DIR / "goal_sweeps.csv", index=False)
    ways.to_csv(TABLE_DIR / "ways_to_beat_pfbc.csv", index=False)
    grid.to_csv(TABLE_DIR / "cost_impact_grid.csv", index=False)
    plot_goal_sweeps(out, base, impact)
    plot_ways(ways, base)
    plot_cost_impact_map(grid, base)
    return out


def plot_goal_sweeps(out: pd.DataFrame, base: dict, impact: str = "weighted") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    cmap = plt.get_cmap("viridis")
    xmax = max(out.C.max(), base["C"]) * 1.04
    for k, share in enumerate(IMPACT_CAPS):
        g = out[out.impact_cap_share.isna() if share is None else np.isclose(out.impact_cap_share, share)].sort_values("C")
        label = "no limit" if share is None else f"{share:.0%} of PFBC 2026"
        col = cmap(k / (len(IMPACT_CAPS) - 1))
        ax.plot(g.C / 1e3, g.B / 1e6, marker="o", ms=4, color=col, label=label)
        ax.plot([g.C.iloc[-1] / 1e3, xmax / 1e3], [g.B.iloc[-1] / 1e6] * 2, color=col, lw=1.2, ls=":")   # more money adds nothing
        if share == 1.0:
            top, g100 = g.B.max(), g
    ax.scatter([base["C"] / 1e3], [base["B"] / 1e6], marker="X", s=110, color="crimson", zorder=6, label="PFBC 2026 plan")
    # guides: same cost, more benefit (up to the 100% line); same benefit, less cost (left to it)
    ax.annotate("", xy=(base["C"] / 1e3, top / 1e6), xytext=(base["C"] / 1e3, base["B"] / 1e6),
                arrowprops=dict(arrowstyle="->", color="crimson"))
    ax.text(base["C"] / 1e3 - 3, (top + base["B"]) / 2e6 + 0.12, f"same cost:\n+{top / base['B'] - 1:.0%} benefit", ha="right", color="crimson", fontsize=8)
    c_same = np.interp(base["B"], g100.B, g100.C)
    ax.annotate("", xy=(c_same / 1e3, base["B"] / 1e6), xytext=(base["C"] / 1e3, base["B"] / 1e6),
                arrowprops=dict(arrowstyle="->", color="crimson"))
    ax.text((c_same + base["C"]) / 2e3, base["B"] / 1e6 + 0.05, f"same benefit:\n{c_same / base['C'] - 1:.0%} cost", ha="center", color="crimson", fontsize=8, va="bottom")
    ax.set_xlabel("Transport cost ($ thousand / yr)")
    ax.set_ylabel("Angler benefit (million angler-days with a catch)")
    ax.set_title("Benefit vs transport cost, by wild-trout impact limit")
    ax.grid(alpha=0.3)
    ax.legend(title="Wild-trout impact limit", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "goal_sweeps.png", dpi=150)
    plt.close(fig)


def plot_ways(ways: pd.DataFrame, base: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.2), sharey=True)
    names = {"B": "Angler benefit", "C": "Transport cost", "I": "Wild-trout impact"}
    good = {"B": 1, "C": -1, "I": -1}   # sign of an improvement
    for ax, (_, w) in zip(axes, ways.iterrows()):
        vals = [100 * (w[k] / base[k] - 1) for k in "BCI"]
        cols = ["tab:green" if v * good[k] > 0.5 else "lightgray" for k, v in zip("BCI", vals)]
        bars = ax.bar([names[k] for k in "BCI"], vals, color=cols)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + (1 if v >= 0 else -1), f"{v:+.0f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_title(w.plan, fontsize=11)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("Change vs PFBC 2026 plan (%)")
    fig.suptitle("Three ways to beat PFBC's 2026 plan (the other two goals held at PFBC's level)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ways_to_beat_pfbc.png", dpi=150)
    plt.close(fig)


def plot_cost_impact_map(grid: pd.DataFrame, base: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pv = grid.pivot_table(index="impact_cap_share", columns="eps_C", values="B")
    fig, ax = plt.subplots(figsize=(8, 5.2))
    im = ax.imshow(pv.to_numpy() / 1e6, origin="lower", aspect="auto", cmap="viridis")
    for (i, j), v in np.ndenumerate(pv.to_numpy() / 1e6):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", color="w" if v < 3.1 else "k", fontsize=9)
    ax.set_xticks(range(pv.shape[1]), [f"{c / 1e3:.0f}" for c in pv.columns])
    ax.set_yticks(range(pv.shape[0]), [f"{s_:.0%}" for s_ in pv.index])
    ax.set_xlabel("Transport cost budget ($ thousand / yr; PFBC 2026 plan = $%.0fk)" % (base["C"] / 1e3))
    ax.set_ylabel("Wild-trout impact limit (% of PFBC 2026)")
    ax.set_title("Best angler benefit (million angler-days) at each budget and limit\n"
                 "PFBC 2026 plan: %.2fM at 100%% impact; blank = no plan fits" % (base["B"] / 1e6), fontsize=10)
    fig.colorbar(im, label="Angler benefit (million angler-days with a catch)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "cost_impact_map.png", dpi=150)
    plt.close(fig)


def main(variants: list[str], points: int, impact: str = "weighted", trip_mode: str = TRIP_MODE) -> None:
    setup_logging("optimization")
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    d = load(impact)
    base = dict(run_id="baseline", variant="-", kind="baseline", **score(d, d["x0_hs"]))
    log.info("baseline (PFBC 2026): B %s angler-days with a catch, C $%s/yr, I %s (impact, %s), "
             "%s truck-miles", f"{base['B']:,.0f}", f"{base['C']:,.0f}", f"{base['I']:,.0f}",
             impact, f"{base['truck_miles']:,.0f}")
    rows, plans = [base], [("baseline", d["x0_hs"])]
    for v in variants:
        r, p = run_variant(d, v, points, base, trip_mode)
        rows += r
        plans += p
    runs = pd.DataFrame(rows)
    runs.to_csv(TABLE_DIR / "runs.csv", index=False)
    sid, hid = d["mi"].section_id.to_numpy(), d["h"].hatchery.to_numpy()
    sec = pd.concat([pd.DataFrame({"run_id": rid, "section_id": sid, "x": x.sum(axis=0)}) for rid, x in plans])
    sec.to_parquet(TABLE_DIR / "sections.parquet", index=False)
    fl = []
    for rid, x in plans:
        i, j = np.nonzero(x > 0.5)
        fl.append(pd.DataFrame({"run_id": rid, "hatchery": hid[i], "section_id": sid[j], "x": x[i, j]}))
    pd.concat(fl).to_parquet(TABLE_DIR / "flows.parquet", index=False)
    plot(runs, impact)
    cols = ["run_id", "B", "C", "I", "truck_miles", "n_stocked", "n_closed", "share_moved", "high_access_fish_vs_2026",
            "gap", "runtime_s"]
    log.info("runs:\n%s", runs[[c for c in cols if c in runs]].round(3).to_string(index=False))


def frontier(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Efficient points only: sorted by col, each keeps more benefit than every cheaper point (drops gap ties)."""
    df = df.sort_values([col, "B"], ascending=[True, False])
    return df[df.B > df.B.cummax().shift(fill_value=-np.inf) + 1]


def plot(runs: pd.DataFrame, impact: str = "weighted") -> None:
    """Main figure: benefit vs cost and benefit vs impact (as % of PFBC 2026), frontier per change-limit variant."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    base = runs[runs.kind == "baseline"].iloc[0]
    style = {"none": ("No change limit", "#1f3b57"), "close_or_band": ("Close, or stay within ½–2× today", "#e07b39"),
             "band": ("Stay within ½–2× today", "#7b6fb0")}
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.3), dpi=200, sharey=True)
    for ax, col, scale, xlabel, title in [
            (axes[0], "C", 1e-3, "Transport cost (\\$ thousand per year)", "Benefit vs transport cost"),
            (axes[1], "I", 100 / base.I, "Wild-trout impact (% of PFBC 2026)", "Benefit vs wild-trout impact")]:
        pts = runs[runs.kind.isin([f"curve_{col}", "payoff"])]
        lines = {v: frontier(g, col) for v, g in pts.groupby("variant", sort=False)}
        bx, by = base[col] * scale, base.B / 1e6
        xmax = 1.05 * max(bx, max(q[col].max() * scale for q in lines.values()))
        xmin = min(q[col].min() * scale for q in lines.values())
        xmin -= 0.05 * (xmax - xmin)
        for v, q in lines.items():
            lab, c = style.get(v, (v, None))
            ax.plot(q[col] * scale, q.B / 1e6, "-o", color=c, lw=2.6, ms=5, label=lab, zorder=3)
            ax.plot([q[col].iloc[-1] * scale, xmax], [q.B.iloc[-1] / 1e6] * 2, "--", color=c, lw=1.8, zorder=2)  # past max B
            if v == "none":
                ax.fill_between(q[col] * scale, q.B / 1e6, 0, color=c, alpha=0.06, zorder=1)
        ytop = 1.04 * runs.B.max() / 1e6
        ax.fill_between([xmin, bx], by, ytop, color="#2e7d5b", alpha=0.10, lw=0, zorder=0)
        ax.text(xmin + 0.02 * (xmax - xmin), 0.995 * ytop, "Better than PFBC", color="#2e7d5b", fontsize=11,
                weight="bold", va="top")
        ax.axhline(by, color="#c0392b", lw=0.8, ls=":", zorder=1)
        ax.axvline(bx, color="#c0392b", lw=0.8, ls=":", zorder=1)
        ax.plot(bx, by, "X", color="#c0392b", ms=16, mec="white", mew=1.5, zorder=5)
        ax.annotate("PFBC 2026", (bx, by), xytext=(10, -22), textcoords="offset points", color="#c0392b",
                    fontsize=12, weight="bold")
        ax.set_xlim(xmin, xmax)
        ax.set_xlabel(xlabel, fontsize=13)
        ax.set_title(title, fontsize=15, weight="bold", loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25)
        ax.tick_params(labelsize=11)
    lo = runs[runs.kind.str.startswith("curve") | (runs.kind == "baseline")].B.min() / 1e6
    axes[0].set_ylim(0.95 * lo, 1.04 * runs.B.max() / 1e6)
    axes[0].set_ylabel("Angler-days with a catch (millions per year)", fontsize=13)
    axes[1].legend(loc="lower right", fontsize=11.5, frameon=False)
    fig.text(0.01, -0.02, "Each line: the most benefit possible at each cost (left) or impact (right) limit. Same 2.6M fish "
             f"in every plan; costs counted in whole truck trips. Impact: {impact} version.", fontsize=10.5, color="#555")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "tradeoff_curves.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=["none", "close_or_band"],
                    choices=["none", "band", "close_or_band"])
    ap.add_argument("--points", type=int, default=16)
    ap.add_argument("--impact", default="weighted", choices=list(IMPACT_COLS))
    ap.add_argument("--trip-mode", default=TRIP_MODE, choices=["fractional", "integer"],
                    help="trips in the model: continuous and rounded up when scored (fast), or whole trips (slow)")
    ap.add_argument("--goal-sweeps", action="store_true", help="only the three one-goal-at-a-time sweeps and their figure")
    a = ap.parse_args()
    if a.goal_sweeps:
        setup_logging("optimization")
        _d = load(a.impact)
        goal_sweeps(_d, dict(score(_d, _d["x0_hs"])), a.points, a.impact, a.trip_mode)
        raise SystemExit
    main(a.variants, a.points, a.impact, a.trip_mode)
