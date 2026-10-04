"""Model input (Prompt 8): one row per 2026-stocked section, everything the optimization reads per section.

Joins, never recomputes: sections (02-04: baseline counts, density caps, wild-trout flags), environment (05),
demand (08). Hatchery supply and haul costs stay in their own tables (hatcheries, cost_matrix, script 20).
- x0 = PFBC's 2026 count (total_2026, all five species), the baseline.
- impact_weighted (main, decision 2026-10-04) = biomass weight x share of the section on wild-trout water
  (model_design.md § Wild-trout impact). Weights are class biomass midpoints relative to D (Guidelines Table 2,
  parameters.csv impact_weight): A 8, B 6, C 3, D 1, E 0. The share is nat_repro_share, except sections rated B-D but
  not on the natural-reproduction list count whole (the rating covers the section), and E sections on the list get
  impact_weight_e_nat_repro (1).
- impact_simple = 1 if natural reproduction or wild biomass B-D, else 0 (sensitivity, version 1).
- impact_overlap = nat_repro_share, the share of the section on natural-reproduction water (sensitivity).
- complete = every component the base model needs is present.

Inputs : data/processed/sections.parquet, environment.parquet, demand.parquet, cost_matrix.parquet
Outputs: data/processed/model_input.{parquet,csv}, logs/21_model_input.log

    .venv/bin/python scripts/21_model_input.py      (run after 08 and 20)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from common import PROCESSED_DIR, setup_logging

SPECIES = ["brook", "brown", "rainbow", "golden", "brood"]
SECTION_COLS = ["section_id", "river_id", "water_name", "county", "region", "length_mi", "area_acres", "width_class",
                "use_potential", "biomass_class", "allocation_code", "class_a_flag", "nat_repro_flag",
                "coop_stocked", "cap_fish", "cap_source", "cap_fish_mid", "cap_fish_river", "cap_fish_class_a_grow"]
DEMAND_COLS = ["prox_days", "pref_days", "prox_days_pooled", "prox_days_pop", "destination_index", "dhalo",
               "catch_release", "keystone_select", "open_year_round"]

log = logging.getLogger(__name__)


def main() -> None:
    setup_logging("21_model_input")
    s = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    n = len(s)
    s = s[s.total_2026.fillna(0).gt(0)].reset_index(drop=True)
    log.info("sections: %d stocked 2024-26, %d stocked in 2026 (the candidates)", n, len(s))
    m = s[SECTION_COLS].copy()
    m.insert(1, "x0", s.total_2026.astype(int))
    for sp in SPECIES:
        m[f"share_{sp}"] = (s[f"{sp}_2026"].fillna(0) / s.total_2026).astype(float)

    env = pd.read_parquet(PROCESSED_DIR / "environment.parquet")[["section_id", "exclude", "exclude_reason",
                                                                  "nat_repro_share", "wild_brook_present"]]
    dem = pd.read_parquet(PROCESSED_DIR / "demand.parquet")[["section_id"] + DEMAND_COLS]
    for name, t in [("environment", env), ("demand", dem)]:
        before = len(m)
        m = m.merge(t, on="section_id", how="left", validate="1:1", indicator=True)
        log.info("join %s: %d rows, %d matched, %d missing", name, before, m._merge.eq("both").sum(),
                 m._merge.ne("both").sum())
        m = m.drop(columns="_merge")

    m["impact_simple"] = (m.nat_repro_flag.fillna(False) | m.biomass_class.isin(["B", "C", "D"])).astype(int)
    m["impact_overlap"] = m.nat_repro_share.fillna(0).astype(float)
    par = pd.read_csv(PROCESSED_DIR / "parameters.csv")
    wt = par[par.parameter.eq("impact_weight")].set_index("applies_to").value.astype(float)
    wt.index = wt.index.str.removeprefix("biomass ")
    on_nr = m.impact_overlap.gt(0)
    weight = m.biomass_class.map(wt).astype(float)
    weight = weight.mask(m.biomass_class.eq("E") & on_nr,
                         float(par.set_index("parameter").loc["impact_weight_e_nat_repro", "value"]))
    rated_only = m.biomass_class.isin(["B", "C", "D"]) & ~on_nr
    m["impact_weighted"] = weight * m.impact_overlap.mask(rated_only, 1.0)
    log.info("impact_weighted: weights %s; %d sections rated B-D but not on the natural-reproduction list count whole; "
             "%d E sections on the list get weight %g; %d sections > 0; 2026 total %s (class D = 1)", wt.to_dict(),
             rated_only.sum(), (m.biomass_class.eq("E") & on_nr).sum(), weight[m.biomass_class.eq("E") & on_nr].max(),
             m.impact_weighted.gt(0).sum(), f"{(m.impact_weighted * m.x0).sum():,.0f}")
    # stocking count rule (decision 2026-10-04; Guidelines Table 44 restated): 3 if demand D >= threshold or
    # High-Yield-like (High access, width 2-3, biomass C-E), else 2. The model phases stockings in by fish (300 each)
    pp = par.set_index("parameter").value
    D = (1 - float(pp["blend_weight_w"])) * m.prox_days + float(pp["blend_weight_w"]) * m.pref_days
    hy = m.use_potential.eq("High") & m.width_class.astype(str).isin(["2", "3"]) & m.biomass_class.isin(["C", "D", "E"])
    m["n_stockings"] = np.where(D.ge(float(pp["stockings_3_demand_threshold"])) | hy, 3, 2)
    log.info("n_stockings: %s (3 from demand %d, High-Yield-like %d)", m.n_stockings.value_counts().to_dict(),
             D.ge(float(pp["stockings_3_demand_threshold"])).sum(), hy.sum())
    cost = pd.read_parquet(PROCESSED_DIR / "cost_matrix.parquet")
    n_cost = cost[cost.in_2026_schedule].groupby("section_id").cost_per_fish.count()
    m["n_supply_costs"] = m.section_id.map(n_cost).fillna(0).astype(int)
    m["complete"] = (m[["x0", "cap_fish", "prox_days", "pref_days", "impact_weighted"]].notna().all(axis=1)
                     & m.n_supply_costs.eq(9) & ~m.exclude.fillna(True).astype(bool))
    log.info("complete for the base model: %d of %d; excluded %d; impact_simple = 1 on %d sections (%s fish, %.1f%%)",
             m.complete.sum(), len(m), m.exclude.sum(), m.impact_simple.sum(), f"{m.x0[m.impact_simple == 1].sum():,}",
             100 * m.x0[m.impact_simple == 1].sum() / m.x0.sum())
    log.info("x0 total %s; cap_fish total %s (%.2fx); cap = today's count on %d sections (%s)", f"{m.x0.sum():,}",
             f"{m.cap_fish.sum():,}", m.cap_fish.sum() / m.x0.sum(), m.cap_source.eq("baseline").sum() if
             "baseline" in set(m.cap_source) else 0, m.cap_source.value_counts().to_dict())
    nulls = m.isna().mean().round(3)
    log.info("null shares (non-zero): %s", nulls[nulls > 0].to_dict())
    assert m.section_id.is_unique and len(m) == 1022 and m.complete.all()
    m.to_parquet(PROCESSED_DIR / "model_input.parquet", index=False)
    m.round(4).to_csv(PROCESSED_DIR / "model_input.csv", index=False)
    log.info("model_input: %d rows, columns %s", len(m), list(m.columns))


if __name__ == "__main__":
    main()
