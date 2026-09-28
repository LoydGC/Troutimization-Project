"""Build the environment table: exclusions, wild brook presence and the wild-trout impact inputs.

Follows docs/model_design.md (Exclusions, Wild-trout impact) and docs/env_research.md. Overlaps are the ones
02_build_sections measured (rule 8); nothing is re-measured here. The density bound itself is cap_fish in
sections (04_river_cap.py).

Inputs : data/processed/sections.parquet (02, 03, 04)
Outputs: data/processed/environment.{parquet,csv}  one row per section
         logs/05_environment.log

    .venv/bin/python scripts/05_environment.py      (run after 04_river_cap.py)
"""
from __future__ import annotations

import logging

import pandas as pd

from common import PROCESSED_DIR, setup_logging

# Removals with a known reason beyond "not stocked in 2026". Blue Hole Creek: cadmium and lead (GoErie,
# 2026-01-31, reporting the Jan 30 Commission meeting; docs/model_design.md Candidate sections).
KNOWN_REMOVALS = {"3656_2": "health"}

log = logging.getLogger(__name__)


def exclusions(s: pd.DataFrame) -> pd.DataFrame:
    stocked = s.total_2026.fillna(0).gt(0)
    reasons = pd.DataFrame({
        "wilderness": s.wilderness_flag,
        "class_a_not_stocked": s.class_a_flag & ~stocked,
        "not_stocked_2026": ~stocked & ~s.class_a_flag,
        "health": s.section_id.map(KNOWN_REMOVALS).eq("health"),
    })
    for sid, reason in KNOWN_REMOVALS.items():
        assert reasons.loc[s.section_id.eq(sid), reason].all(), f"{sid} not found"
    s["exclude"] = reasons.any(axis=1)
    s["exclude_reason"] = reasons.apply(lambda r: "; ".join(r.index[r]) or None, axis=1)
    log.info("excluded: %d of %d sections; reasons %s", s.exclude.sum(), len(s),
             s.exclude_reason.value_counts().to_dict())
    ex = s[s.exclude]
    log.info("excluded sections were stocked in the baseline: 2024 %d fish in %d sections, 2025 %d fish in %d "
             "sections, 2026 %d", ex.total_2024.sum(), ex.total_2024.gt(0).sum(), ex.total_2025.sum(),
             ex.total_2025.gt(0).sum(), ex.total_2026.fillna(0).sum())
    return s


def wild_brook(s: pd.DataFrame) -> pd.DataFrame:
    """Wild brook trout present: parsed from the Class A Fishery text, the only layer with species.

    True if the text mentions brook (e.g. "Wild Brook Trout Fishery", "Mixed Brook/Brown"), False if it names
    other species only, NA where no overlapping Class A record has species text (no data, not "absent").
    """
    s["wild_brook_present"] = s.class_a_wild_brook.astype("boolean")
    parsed = s[s.class_a_fishery.notna()].groupby("class_a_fishery").wild_brook_present.first()
    log.info("wild_brook_present parsed from Class A Fishery text: %s", parsed.to_dict())
    log.info("wild_brook_present: %s", s.wild_brook_present.value_counts(dropna=False).to_dict())
    brook_on_wild = s.wild_brook_present.fillna(False) & s.brook_2026.fillna(0).gt(0)
    log.info("wild-brook sections stocked with brook trout in 2026: %d %s", brook_on_wild.sum(),
             s.loc[brook_on_wild, "section_id"].tolist())
    return s


def nat_repro_share(s: pd.DataFrame) -> pd.DataFrame:
    """Share of the section's river miles that overlap Natural Reproduction; 0 where not flagged (<= 100 m)."""
    rm = s.rm_length_mi.where(s.rm_length_mi > 0)
    share = (s.nat_repro_overlap_mi / rm).clip(upper=1).round(3)
    assert share[s.nat_repro_flag].notna().all(), "flagged section with no river-mile length"
    s["nat_repro_share"] = share.where(s.nat_repro_flag, 0.0)
    q = s.loc[s.nat_repro_flag, "nat_repro_share"]
    fish = s.total_2026.fillna(0)
    log.info("nat_repro_share, flagged sections (n=%d): >= 0.9 %d, 0.1-0.9 %d, < 0.1 %d. 2026 fish on natural "
             "reproduction water: %d by flag, %d weighted by share", len(q), (q >= 0.9).sum(),
             q.between(0.1, 0.9, inclusive="left").sum(), (q < 0.1).sum(), fish[s.nat_repro_flag].sum(),
             (fish * s.nat_repro_share).sum())
    return s


def validate(env: pd.DataFrame) -> None:
    e = env.set_index("section_id")
    assert not e.loc[["3197_2", "3197_3"], "exclude"].any()
    assert e.loc[["3197_2", "3197_3"], "nat_repro_flag"].all()
    log.info("Bear Creek (3197) checks passed: not excluded, natural reproduction")
    assert e.at["3190_2", "exclude_reason"] == "class_a_not_stocked"
    assert e.at["3656_2", "exclude_reason"] == "not_stocked_2026; health"
    assert env.section_id.is_unique


def main() -> None:
    setup_logging("05_environment")
    s = pd.read_parquet(PROCESSED_DIR / "sections.parquet")
    s = exclusions(s)
    s = wild_brook(s)
    s = nat_repro_share(s)
    log.info("nat_repro_flag as built in 02 (river miles only): %d sections", s.nat_repro_flag.sum())
    env = s[["section_id", "exclude", "exclude_reason", "wild_brook_present", "nat_repro_flag", "nat_repro_share",
             "biomass_class"]]
    validate(env)
    env.to_parquet(PROCESSED_DIR / "environment.parquet", index=False)
    env.to_csv(PROCESSED_DIR / "environment.csv", index=False)
    log.info("environment: %d rows, %d columns", len(env), env.shape[1])


if __name__ == "__main__":
    main()
