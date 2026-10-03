# Repo audit: findings for human triage and Claude implementation

Audited 2026-10-01 on branch `tionesta-hatchery` at commit `95df9d6` (clean tree). Reviewer: a fresh Claude session with no
memory of the two authoring sessions. It read every script, test, notebook cell and doc, ran `pytest` (31 passed), and
re-derived about 25 documented numbers from the committed tables. **Nothing in the repo was changed except this file.**

How to use this file
- **Humans:** read §0, then the triage table (§1) and the decisions list (§2). Tick `Status` in §1 as you go. Each finding in §3
  is written so you can judge it without opening the code: *Where / What / Evidence / Fix / Done when*.
- **Claude agents:** read §5 first. Do not start an item marked **Decision needed** until a human has recorded the answer in §2.

Severity: **High** = blocks the model, blocks a clean rebuild, or could give a wrong result. **Med** = misleads a reader or will
bite soon. **Low** = cleanup. Effort: **S** < 30 min, **M** 1–3 h, **L** > 3 h.

---

## 0. Executive summary

The pipeline code that exists (scripts 00–10) is careful and I found **no outright calculation bug in the committed tables** (within the limits in §4):
every number I re-derived (section counts, species totals, cap logic, demand sums, figure_ideas statistics, cluster tables)
matched its doc. The risks are elsewhere:

1. **The optimization model does not exist yet** (B1). `scripts/optimization.py` and `scripts/sensitivities.py` are empty scaffolds,
   and the three tables they need (`hatcheries`, `cost_matrix`, `model_input`) have not been built. Prompts 7–9 are all still open.
   This is the biggest project risk, and the repo's own status text (`PROMPTS.md`) is out of date about it.
2. **A fresh clone cannot rebuild the data** (A1, A2). Scripts 02, 03, 09 and 11 read partner files that were untracked on 2026-09-29
   (`data/raw/pa_hatcheries.gpkg`, `Coop_nurseries.geojson`, `pa_hatchery_production.csv`), and scripts 03, 06 and 08 need downloads
   that no script performs. "manifest.csv is enough to re-fetch" is only true by hand.
3. **The cluster work (scripts 12–16, over a quarter of the script lines, plus the largest committed data file) has no consumer in the model**
   (B2). Its stated purpose is a "representative cost per hatchery for a group of sections", but the model already has an exact
   `cost[h,s]` for all 9 × 1,022 pairs, and the other cluster design (the schedule clusters) exists for a different purpose (a detour or trip
   charge). Someone must decide what clusters are *for* before more effort goes in.
4. **Small modeling traps to fix before the solver is written:** hatchery supply sums to 3 fish fewer than the baseline total (B3), and
   golden and brood fish are silently in every "fish" total while the doc lists that as an open question (B4).
5. **Documentation drift:** CLAUDE.md still points at notebooks that were replaced by scripts, never mentions scripts 11–16, and its
   rule 3 is contradicted by committed code (the OSRM waiver lives only in `known_gaps.md`). `PROMPTS.md` status is two days stale.
6. **Two code styles in one repo:** scripts 01–10 are structured (`main()`, importable); 00 and 11–16 are notebook-style top-level
   code with 130+ column lines, so they cannot be unit tested and script 12 fires network calls on import (E1).
7. `requirements.txt` omits `scikit-learn`, which scripts 13–16 import (A6).

---

## 1. Triage table

| ID | Sev | Finding | Effort | Decision needed? | Status |
|---|---|---|---|---|---|
| **A. Reproducibility and pipeline integrity** | | | | | |
| A1 | High | Fresh clone fails: scripts 02/03/09/11 need untracked partner raw files | M | partly (D-7) | Open |
| A2 | High | Sources with a manifest URL but no download code (03, 06, 08) | M | no | Open |
| A3 | Med | No orchestrator; run order documented only in stale text; 02→03→04 read-modify-write one file | M | no | Open |
| A4 | Med | Script 12 overwrites the committed table and re-hits the OSRM demo server on a clean clone | S | no | Open |
| A5 | Med | OSRM rule-3 waiver not reflected in CLAUDE.md; script 11 has no backoff | S | yes (D-6) | Open |
| A6 | Med | `requirements.txt` missing scikit-learn; lists unused packages; no pins | S | no | Open |
| A7 | Low | Local git remote still points at the old repo name (GitHub redirects); `USER_AGENT` URL is correct | S | no | Open |
| A8 | Low | Committed logs were produced from uncommitted code | S | no | Open |
| **B. Model readiness and design consistency** | | | | | |
| B1 | High | Model, `hatcheries`, `cost_matrix`, `model_input` not built (Prompts 7–9 open) | L | partly (D-5) | Open |
| B2 | High | Cluster work has no consumer in the model; two incompatible cluster purposes | S to decide | **yes (D-1)** | Open |
| B3 | Med | Hatchery supply is 3 fish short of the baseline total | S | no | Open |
| B4 | Med | Golden and brood are inside every fish total; doc says undecided | S | **yes (D-2)** | Open |
| B5 | Med | Transit mortality in/out of the cost formula is inconsistent across docs | S | **yes (D-3)** | Open |
| B6 | Low | 300-fish minimum is per section-year; PFBC's rule is per stocking | S | **yes (D-4)** | Open |
| B7 | Med | "3.06× baseline" cap statistic includes the 23 non-candidate sections | S | no | Open |
| **C. Code and data details** | | | | | |
| C1 | Low | Script 13's silhouette table reports only the last seed's cost and cluster count | S | no | Open |
| C2 | Low | Hard-coded `1022` and two different "2026-stocked" definitions | S | no | Open |
| C3 | Low | Script 11: CRS 5070 and distance-to-line vs midpoint; stale comment | S | no | Open |
| C4 | Low | Notebooks: corrupted dash characters and stale statements | S | no | Open |
| C5 | Low | Class A flag and Class A attributes use two overlap routines (latent) | S | no | Open |
| **D. Stale or contradictory documentation** | | | | | |
| D1 | Med | CLAUDE.md: stale notebook references, missing scripts/docs, undefined "Nate", imprecise supply rule | S | partly | Open |
| D2 | Med | PROMPTS.md status block and script-order line are stale | S | no | Open |
| D3 | Low | `data/README.md` table lists 7 of ~21 processed outputs | S | no | Open |
| D4 | Low | `known_gaps.md` "Gavin's stocked-streams layer" gap is obsolete | S | no | Open |
| D5 | Low | `.gitignore` comment says partner files "stay tracked" (they were untracked) | S | no | Open |
| D6 | Low | `figure_ideas.md` / `scenarios_and_extensions.md` statuses and dates stale | S | no | Open |
| D7 | Low | Misc wrong cross-references (model_design, transport_research, source_inventory) | S | no | Open |
| D8 | Low | README: POSIX-only commands; no pointer to docs | S | no | Open |
| **E. Code quality** | | | | | |
| E1 | Med | Two code styles; scripts 11–16 not importable; same loader/plot code copied 4× | L | no | Open |
| E2 | Low | Scrapped script 14 still sits in the numbered run sequence | S | no | Open |
| E3 | Low | Numbers hard-coded into figure text and docstrings | S | no | Open |
| E4 | Low | Personal names ("Nate's", "Gavin's") in code, figures and docs | S | yes (D-8) | Open |
| E5 | Low | Table-format convention ("parquet plus csv") not followed by 8 tables | S | no | Open |
| **F. Tests** | | | | | |
| F1 | Med | No unit tests for the logic in scripts 02–10 and 13–15 | L | no | Open |
| F2 | Low | No cross-table consistency tests | S | no | Open |
| F3 | Low | No CI | S | no | Open |
| **G. Repo hygiene** | | | | | |
| G1 | Med | Work branch is 13 commits / 68 files ahead of `main`; stale branches | S | yes (D-10) | Open |

---

## 2. Decisions needed from the team

Record the answer in the last column. Agents: an item with a blank answer is **not** yours to decide.

| # | Question | Options | Reviewer's lean | Answer |
|---|---|---|---|---|
| D-1 | **What are clusters for?** (B2) | (a) Drop clusters from the model path; archive scripts 12–16 and the 10.6 MB section-to-section table. (b) Keep them for a per-trip or per-stop fixed charge (binary `y_c`, `x_s ≤ cap_s·y_c`): then the schedule clusters are the right family, and truck-run width/size limits matter again. (c) Keep as report-only exploration (a methods slide), clearly labelled as not feeding the model. | (a) or (c). With 9 hatcheries × 1,022 sections the model is ~9k continuous variables, so aggregating cost buys no speed and only adds 2–3% distance error. Choose (b) only if the team wants a trip charge. | |
| D-2 | Do golden and brood fish count in the baseline, caps and supply? (B4) | Include (current data), or restrict to brook + brown + rainbow like PFBC's `TotalAdultStocked_minusBrood`. | Include, but add explicit `adult_2026` columns so either can be run. Brood is 2.4% and golden 0.6% of 2026 fish. | |
| D-3 | Is transit mortality in the base cost formula? (B5) | Leave out (sensitivity), or divide cost by (1−m) and let supply cover x/(1−m). | Leave out of base, run 1% as a sensitivity. | |
| D-4 | Per-stocking minimum? (B6) | Keep `x_s ≥ 300·y_s`, or also run `x_s ≥ 300·n_events_s·y_s`. | Keep as base; add the second as a sensitivity. | |
| D-5 | Confirm the baseline cost uses each section's **scheduled** hatchery (nearest hatchery = sensitivity)? | CLAUDE.md still says "Proposed, to confirm with Gavin". | Confirm; it is already how `section_schedule` is built. | |
| D-6 | Put the OSRM waiver into CLAUDE.md rule 3 (and the rule-2 deviation)? (A5) | Add an exception paragraph, or stop using OSRM. | Add the exception; the tables are already built and checked. | |
| D-7 | Where do the two partner inputs with no public source live? (A1) | `Coop_nurseries.geojson` (65 KB) and `pa_hatchery_production.csv` (2 KB, has a per-row `source_url`): re-track under a new `data/inputs/` with a provenance README, or re-source. | Re-track under `data/inputs/` now; they are tiny. | **Answered 2026-10-03 (Gavin):** neither file matters to the model any more, so no `data/inputs/` folder. Sources are now recorded: co-ops are PASDA dataset 970 (PFBC), the production figures were scraped with Claude from PFBC's official hatchery pages (links in `source_inventory.md` and `data/raw/manifest.csv`). Scripts 03 and 11 still read the co-op file, so a fresh clone still needs it downloaded from PASDA. |
| D-8 | Replace personal names in code, figures and docs with roles? (E4) | "schedule clusters", "geography clusters", etc. | Yes, before the final report. | |
| D-9 | Review files still waiting on people: `logs/07_survey_crosswalk_review.csv` (22 rows, 6.4% of survey mentions) and `logs/03_coop_review.csv`. | These feed demand (07) and the optional co-op extension. | Decide or explicitly defer; undecided names are spread like proximity demand. | |
| D-10 | Merge strategy for `tionesta-hatchery`. (G1) | PR into `main` as-is, or split. Rename the branch? | One PR; branch name no longer describes the contents. | |

---

## 3. Findings in detail

### A. Reproducibility and pipeline integrity

#### A1 — Fresh clone fails: scripts need untracked partner raw files  (High, M)
- **Where:** [02_build_sections.py:408](../scripts/02_build_sections.py) (`pa_hatcheries.gpkg`),
  [03_coop_stockings.py:101](../scripts/03_coop_stockings.py) and [11_road_distances.py:67](../scripts/11_road_distances.py)
  (`Coop_nurseries.geojson`), [09_stocking_schedule.py:280-281](../scripts/09_stocking_schedule.py)
  (`pa_hatchery_production.csv`, `pa_hatcheries.gpkg`), [11_road_distances.py:64](../scripts/11_road_distances.py).
- **What:** commit `8e5151c` untracked these under `data/raw/`. `git ls-files data/raw` now shows only `manifest.csv`. The manifest rows
  for `Coop_nurseries.geojson` and `pa_hatchery_production.csv` have no source URL, so they cannot be re-fetched at all
  (`pa_hatcheries.gpkg` does have an ArcGIS Online URL, and `pa_hatchery_production.csv` has a per-row `source_url` column).
- **Failure mode:** script 02 reaches `write_outputs` after already writing `sections`, `stocking_section_year` and the `sections`
  layer of `pa_trout.gpkg`, then raises `FileNotFoundError` on the hatchery layer, leaving a half-built gpkg. Scripts 03, 09 and 11–16 all
  depend on that gpkg.
- **Evidence:** `git ls-files data/raw` ; the seven `source = partner_loydgc` rows in `data/raw/manifest.csv`.
- **Fix:**
  1. Script 01 already downloads PFBC's official State Fish Hatcheries layer to `data/interim/pfbc_gis/hatcheries.parquet`. Build the
     `hatcheries` map layer in 02, the name check in 09 and the node list in 11 from it (this is also Prompt 7 step 1, see B1). Check first
     that it matches `pa_hatcheries.gpkg` (names have trailing spaces; flags `TROUT`, `WARM_COOL`, `STEEL_SALM`; `Lat`, `Long_`).
  2. For the two files with no public source, see D-7 (suggested: `data/inputs/`, tracked, with a README stating provenance).
- **Done when:** in a fresh clone with no `data/raw` or `data/interim`, scripts 01 → 10 run (network allowed) and `pytest` passes.
  Do not run the full schedule download (68 requests) without a human OK; use `git worktree` in the scratchpad and run only the stages
  you changed.

#### A2 — Manifest has URLs, but no code downloads them  (High, M)
- **Where:** [03:40](../scripts/03_coop_stockings.py) (`sorted(glob)[-1]` raises `IndexError` if the xlsx is absent),
  [06:53-56](../scripts/06_county_anglers.py) (`assert found, "see data/raw/manifest.csv for its URL"`),
  [06:113,122](../scripts/06_county_anglers.py) and [08:78](../scripts/08_demand.py) (Census files).
  Scripts 00 and 04 already do it right (download if missing).
- **What:** CLAUDE.md says "manifest.csv is enough to re-fetch". It is, but only by hand.
- **Fix:** add `common.ensure_raw(source, filename, url, date=None) -> Path` (latest `data/raw/<source>/*/<filename>`, else download with
  `PoliteSession` + `save_raw`). Use it in 03 (cnu xlsx), 06 (license PDF, Census txt + zip), 08 (Census txt), and refactor 00 and 04 onto it.
  URLs are in `data/raw/manifest.csv` and `docs/source_inventory.md`.
- **Done when:** a mocked-session unit test (pattern in `tests/test_common.py`) proves "present → no request; absent → one request + one
  manifest row", and 03/06/08 no longer assert on a missing file.

#### A3 — No orchestrator; run order lives in stale prose  (Med, M)
- **Where:** [PROMPTS.md:34-35](../PROMPTS.md) ("Script order … 00 → … → 10"), README "Run".
- **What:** scripts 02 → 03 → 04 each read-modify-write the same committed file `data/processed/sections.parquet` (03 and 04 drop and re-add
  their own columns, so reruns are idempotent, but 02 overwrites everything). Running 02 alone silently leaves a `sections.parquet` without
  cap or co-op columns, which `tests/test_processed.py` and 05–10 expect. The order for 11–16 is documented nowhere (see Appendix A).
- **Fix:** add `scripts/run_all.py` (or a `Makefile`) with the DAG in Appendix A: `--from N --to M`, a `--dry-run` that prints inputs and outputs,
  and **no OSRM calls unless `--refresh-osrm`**. Replace the PROMPTS.md order line with a pointer to it.
- **Done when:** `python scripts/run_all.py --dry-run` prints all stages in dependency order and exits 0.

#### A4 — Script 12 overwrites the committed table and re-queries OSRM on a clean clone  (Med, S)
- **Where:** [12_section_road_distances.py:92-128](../scripts/12_section_road_distances.py) vs the guard in
  [11:148](../scripts/11_road_distances.py).
- **What:** script 11 skips the network when its output exists unless `--refresh`; script 12 has no such guard. Its per-block cache is in
  gitignored `data/interim/`, so on a clean clone it sends 121 requests to the public demo server and rewrites
  `section_to_section_road_distance.parquet`, which `known_gaps.md` calls "the reference" because rebuilds can differ slightly.
- **Fix:** after `OUT` is defined, `if OUT.exists() and not args.refresh and not args.limit: log it and exit(0)`.
- **Done when:** running the script on this checkout with the cache deleted makes zero requests.

#### A5 — Rule 3 contradicted by committed code; script 11 lacks backoff  (Med, S) — Decision D-6
- **Where:** [CLAUDE.md:130](../CLAUDE.md) ("Never bulk-query public demo services (e.g. the OSRM demo server)");
  [11_road_distances.py:132](../scripts/11_road_distances.py) (bare `requests.get`, `raise_for_status`, no retry).
- **What:** the waiver and the rule-2 deviation are recorded only in `docs/known_gaps.md` (end of file). A future Claude session reading
  CLAUDE.md will see committed scripts that break a hard rule and may "fix" them. Script 12 uses `PoliteSession` (retry/backoff);
  script 11 does not.
- **Fix:** after D-6, add one exception paragraph to rule 3 pointing at `known_gaps.md` § OSRM. Switch 11 to
  `PoliteSession(min_interval=PAUSE_S, cache_path=None)` like script 12.

#### A6 — `requirements.txt`  (Med, S)
- **Where:** [requirements.txt](../requirements.txt).
- **What:** `scikit-learn` is imported by scripts 13, 14, 15 and 16 but not listed (a `pip install -r` environment fails there).
  Listed but never imported in `scripts/`, `tests/` or notebooks: `duckdb`, `seaborn`, `folium`, `tqdm`, `pynhd` (the last is an optional
  upgrade). `ipywidgets` is imported by `travel_arcs.ipynb`. Nothing is pinned. On this machine `pdfplumber` and `pynhd` are not installed
  (scripts 00, 04, 06 would fail here), while Anaconda has scikit-learn 1.6.1.
- **Fix:** add `scikit-learn`, `ipywidgets`; move unused packages to a commented "optional" block or delete; add lower bounds from the
  working environment (pandas 2.3.3, numpy 2.1.3, geopandas 1.1.1, shapely 2.0.7, scipy 1.15.3, scikit-learn 1.6.1, matplotlib 3.10.0,
  requests-cache 1.3.3, gurobipy 13.0.3, pytest 8.3.4) or commit a `requirements-lock.txt`. CLAUDE.md says "Python 3.11+"; the working
  interpreter is 3.13.5, so say which one is tested.
- **Done when:** `pip install -r requirements.txt` into a clean venv, then `pytest` and `python -c "import sklearn, pdfplumber, bs4"` pass.

#### A7 — Local git remote uses the old repo name  (Low, S)
*Corrected 2026-10-01: the first version of this finding had it backwards.* The repo was renamed on GitHub; a push printed "This repository moved. Please use the new location:
`https://github.com/LoydGC/Troutimization-Project.git`". So the `USER_AGENT` in [common.py:29](../scripts/common.py) (`github.com/LoydGC/Troutimization-Project`) is **correct**.
What is stale is the `origin` URL in the local clone (`.../Trout-Optimization-Project.git`) and any mention of the old name in docs. GitHub redirects it, so pushes work today, but the redirect can break
if the old name is ever reused.
- **Fix:** `git remote set-url origin https://github.com/LoydGC/Troutimization-Project.git` in each collaborator's clone; grep docs for the old name (`grep -rn "Trout-Optimization-Project" .`; none in tracked files as of this audit).

#### A8 — Committed logs came from uncommitted code  (Low, S)
`logs/02…10`, `12…16` start with "run from commit X + uncommitted changes to scripts/…". `logs/04_river_cap.log` is dated 2026-09-28 00:01
and `logs/02_build_sections.log` 2026-09-27; both predate later script commits. After the fixes above, rerun the stages that are cheap and
offline (02–08, 10, 13, 15, 16 on committed inputs) once on a clean tree and commit the logs, so each log names a real commit.

---

### B. Model readiness and design consistency

#### B1 — The model and its three input tables are not built  (High, L)
- **Where:** [optimization.py](../scripts/optimization.py) (56 lines, all `# TODO`), [sensitivities.py](../scripts/sensitivities.py) (47 lines, all
  `# TODO`); [PROMPTS.md:259-282, 333-352](../PROMPTS.md) (Prompts 7, 8, 9 not marked done).
- **What is missing**, in dependency order (specs are already in the docs; this is the checklist):
  1. **`data/processed/hatcheries.parquet`** (Prompt 7 step 1): the 13 hatcheries from PFBC's official layer: stripped `name`, `hatchery_id`,
     county, lat/lon, `in_2026_schedule` (9 true), `supply` = `stream_fish_2026` from `hatchery_schedule_supply.csv` (see B3), the lbs-split
     sensitivity, and the raw `TROUT`/`WARM_COOL`/`STEEL_SALM` flags as reference. Retire the placeholder layers built from the old `TROUT`
     flag (`pa_trout.gpkg` layer `hatcheries`, `data/processed/trout_hatcheries.gpkg`), or label them.
  2. **Transport rows in `parameters.csv`** (rule 7), from `docs/transport_research.md` § Proposed parameters: `cost_per_truck_mile`
     1.90 (1.25–3.10), `fish_per_load` 2,500 (1,500–3,500), `transport_mortality_pct` (per D-3), `capital_cost_per_truck_mile` 1.00 (sensitivity),
     `fleet_miles_per_year` 300,000, derived `cost_per_fish_road_mile` 0.00152.
  3. **`cost_matrix.parquet`** (long): `node_id, section_id, road_mi, cost_per_fish = 2 × road_mi × cost_per_truck_mile / fish_per_load`, from
     `hatchery_to_section_road_distance.parquet`. Keep all 13 × 1,045 rows with an `in_base_model` flag (9 nodes × 1,022 sections).
  4. **Baseline node and implied baseline cost** (Prompt 7 step 4, D-5), plus the fleet-mile calibration check. Prototype numbers I got from
     the committed tables are in Appendix B so you can sanity-check yours.
  5. **`model_input.parquet`** (Prompt 8), one row per candidate section: baseline counts by species and total (see B4), species mix
     (**specify which**: `model_design.md` says "shares from 2024–26", the simplest consistent choice is 2026 only), `cap_fish`,
     `cap_fish_mid`, `cap_fish_river`, `cap_fish_class_a_grow`, `max_trout_per_acre`, `program_rate`, exclusion flags and reason,
     Class A / natural reproduction / biomass / wild-brook (NA = unknown), the three impact-weight versions from `model_design.md`
     § Wild-trout impact, `prox_days`, `pref_days`, `prox_days_pooled`, `prox_days_pop`, `coop_stocked`, `length_mi`, plus a completeness
     flag per component. Cast pandas nullable `Int64`/`Float64`/`boolean` columns to plain numpy types before they reach Gurobi.
  6. **`optimization.py`**: `x[h,s] ≥ 0`, `y[s]` binary; supply `Σ_s x[h,s] ≤ supply_h`; `x[h,s]` only for the base-model hatcheries; `Σ x = baseline total`;
     `300·y_s ≤ Σ_h x[h,s] ≤ cap_s·y_s`; exclusions; the concave benefit as a piecewise-linear curve with breakpoints r = 0, .25, .5, 1, 2, 4, 8 (× D_s);
     ε-constraint sweeps on cost and impact; score the PFBC baseline on the same three objectives.
  7. **Model checks to ship with it:** the baseline plan must be feasible under `cap_fish` (it is: `cap_fish ≥ total_2026` for all 1,022); the
     "max benefit only" solve must score ≥ baseline; with no cost or impact limit the solution should approach equal fish per angler-day
     across uncapped sections (this is `model_design.md`'s own predicted behaviour, so it doubles as a test).
- **Note:** because `Σ supply ≈ baseline total` (B3), the supply constraints are effectively equalities: each hatchery's output is fixed and the
  model chooses *where* it goes. Say so in the report.
- **Done when:** the baseline and the three single-objective extremes are scored and written to `outputs/tables/optimization/`.

#### B2 — The clusters have no consumer in the model  (High, decide first) — Decision D-1
- **Where:** [docs/clustering_options.md](clustering_options.md) § Objective (lines 5–23) and § Plan of record (27–36);
  [model_design.md:461-472](model_design.md) (detour charge); scripts 12–16.
- **What:** two incompatible purposes are in the repo.
  - *Schedule clusters* (scripts 09–10, in `model_design.md` § Open questions): a **detour or trip charge** per cluster (`y_c`). Here
    truck-run width and sections-per-run matter.
  - *Geography clusters* (scripts 13, 15): "hand the model one representative cost per hatchery for the whole group", with
    width, hop and size explicitly declared irrelevant. But the model's decision is still `x[h,s]` with an exact per-section
    `cost[h,s]` from OSRM for every one of the 9 × 1,022 pairs. Replacing it with a cluster mean makes the cost *less* accurate (mean error
    1.7–3.0% of distance; 2.4–4.1 mi mean) and saves nothing: the LP has about 9.2k continuous variables and 1,022 binaries.
  - `clustering_options.md:33-35` itself says "the repo does not yet say that Nate's clusters become a representative cost".
  - Cost of the status quo: scripts 12–16 (~1,240 lines), the 10.6 MB `section_to_section_road_distance.parquet`, 121 demo-server requests,
    two cluster docs and four figure/table sets all exist to serve a use that has not been defined.
- **Fix:** answer D-1. If (a) or (c): move 12–16 to `scripts/archive/` (see E2), mark the docs "exploration, not in the model", and
  consider dropping the 10.6 MB parquet from tracking. If (b): write the `y_c` formulation into `model_design.md` first, then re-score the
  cluster options against *that* (width/size limits become relevant again), and decide which clustering feeds it.
- **Done when:** `model_design.md` contains one sentence naming where clusters enter the model, or says they do not.

#### B3 — Hatchery supply is 3 fish short of the baseline total  (Med, S)
- **Where:** [09_stocking_schedule.py:292-306](../scripts/09_stocking_schedule.py) (per-species allocations are rounded to 0.01, summed per
  hatchery, **each species rounded to an integer**, then summed).
- **Evidence:** Σ `stream_fish_2026` in `hatchery_schedule_supply.csv` = **2,606,465**; Σ `sections.total_2026` = **2,606,468**. Per species the supply
  is short by 1 brown, 1 rainbow and 1 golden. `tests/test_hatchery_schedule_supply` allows a gap < 10, so it does not catch this.
- **Why it matters:** with "total fish fixed at the baseline total" and `Σ_s x[h,s] ≤ supply_h`, the solver's equality is infeasible by 3 fish.
- **Fix:** allocate with largest-remainder rounding so that Σ over hatcheries equals `total_2026.sum()` exactly (or compute supply from
  unrounded allocations and round once); tighten the test to `== 0`. Alternatively state the total constraint as `Σ x = Σ supply`.
- **Done when:** `hatchery_schedule_supply.stream_fish_2026.sum() == sections.total_2026.sum()` and the test asserts it.

#### B4 — Golden and brood fish are inside every total; the doc calls it open  (Med, S) — Decision D-2
- **Where:** `total_20xx` = sum of all five species ([02:333](../scripts/02_build_sections.py)); [model_design.md:457-458](model_design.md)
  ("Include golden and brood in the model's fish total?" listed as an **open question**); CLAUDE.md Known facts quote Bear Creek as
  "150 brown + 1,750 rainbow".
- **Evidence:** Bear Creek `3197_2` has `total_2026 = 1,030` (150 + 850 + 30 brood) and `3197_3` has 920, so the tables say 1,950, not 1,900
  (script 09's assert uses 1,950). Brood is 2.4% and golden 0.6% of 2026 fish. Baseline, `cap_source` ("today's stocking"), hatchery supply and the
  demand `r = fish / angler-days` all use the inclusive total. PFBC's own `TotalAdultStocked_minusBrood` excludes them.
- **Fix:** after D-2, add `adult_2026` (brook+brown+rainbow) next to `total_2026` in `sections`, document both in `data_dictionary.md`,
  state the chosen one in `model_design.md`, and fix the Bear Creek sentence in CLAUDE.md to show both numbers.

#### B5 — Transit mortality: in or out?  (Med, S) — Decision D-3
`model_design.md:317` and CLAUDE.md give `cost = 2 × road_mi × $/mi ÷ fish_per_load` (no mortality). `model_design.md:321` and :441 call a flat 1% an
"assumption" that "no scenario tests". `transport_research.md` (worked example, § 7) divides cost by (1 − m) and lets supply cover x/(1 − m).
An implementer cannot tell which is meant. Pick one and make all three places agree; if mortality is in, add the parameter row (B1 item 2).

#### B6 — 300-fish minimum is per section-year; PFBC's is per stocking  (Low, S) — Decision D-4
- **Where:** [parameters.csv:8](../data/processed/parameters.csv) (the note admits it); `model_design.md:144`.
- **Evidence:** 847 of the 1,022 candidate sections have two or more scheduled events (`section_schedule.n_events`), and PFBC's own 2026 baseline
  never falls below 300 fish **per event** (0 sections have `total_2026 < 300 × n_events`). So `x_s ≥ 300·y_s` lets the model give a two-event section
  300–599 fish, below PFBC's floor, in a plan that is supposed to be "realistic".
- **Fix:** keep as base (it is labelled), and add the sensitivity `x_s ≥ 300·n_events_s·y_s` to `scenarios_and_extensions.md` § Constraint scenarios.

#### B7 — "Cap is 3.06× baseline" includes non-candidate sections  (Med, S)
- **Where:** [model_design.md:145-146](model_design.md) and [04_river_cap.py:231-234](../scripts/04_river_cap.py) (log line); `logs/04_river_cap.log`.
- **Evidence:** the ratio sums `cap_fish` over all 1,045 sections but divides by 2026 fish (which only the 1,022 candidates have).
  Over the candidates: `cap_fish` **3.00×**, `cap_fish_mid` **2.19×**, `cap_fish_river` **3.39×** (docs: 3.06 / 2.23 / 3.45).
- **Fix:** compute the log and the doc over `fish > 0` rows; update the three numbers in `model_design.md`; add the figure to `test_density_cap`.

---

### C. Code and data details

#### C1 — Script 13 silhouette table reports the last seed only  (Low, S)
[13_medoid_clusters.py:155-163](../scripts/13_medoid_clusters.py): `silhouette` is the mean of two seeds, but `clusters` and
`total_distance_to_medoid_mi` come from whichever seed ran last (and with `restarts // 3` starts, not the 30 used for the final tables).
Result: `silhouette_by_k.csv` says 4,181.9 for k = 310 while `comparison.csv` says 4,160. Record the min cost over seeds and the number of clusters of
the seed that was kept, or label the column "second run".

#### C2 — Hard-coded `1022` and two definitions of "2026-stocked"  (Low, S)
`assert len(s) == 1022` in [08:101](../scripts/08_demand.py) and [10:175](../scripts/10_runs_clusters.py); script 12 selects
`latest_year == 2026` ([12:54-57](../scripts/12_section_road_distances.py)), scripts 08 and 10 select `total_2026 > 0`. They agree today (both 1,022)
but nothing enforces it. Add `common.candidate_sections()`, use it everywhere, and keep the literal only in `tests/test_processed.py`.

#### C3 — Script 11 distance conventions  (Low, S)
[11:33](../scripts/11_road_distances.py) uses EPSG:5070 and distance-to-nearest-point-on-line for the straight-line table, while the road table routes to the
section *midpoint* and CLAUDE.md says EPSG:26918 for distances. The notebook's validation recomputes midpoint distances itself, so nothing is wrong
in the road table, but the two "straight-line" files mean different things. Switch to 26918, name the definition in the filename or header,
and fix the stale comment at line 37 ("10 hatcheries + 100 points" is now 13 + 100).

#### C4 — Notebook text problems  (Low, S)
- `notebooks/travel_arcs.ipynb` cells 17, 18, 21 contain corrupted characters ("�" where an en or em dash was; the saved UTF-8 got mangled once).
- Cell 20 comment says "his baseline assigns each section to its nearest one"; the proposed baseline is the **scheduled** hatchery (D-5).
- `notebooks/01_data_prep.ipynb` cell 21 says "the 10 trout hatcheries" but the table has 11 rows after the Tionesta correction.
- Both notebooks read untracked raw files (A1) and cannot run on a fresh clone.

#### C5 — Class A flag and Class A attributes use different overlap routines (latent)  (Low, S)
[02:224-233](../scripts/02_build_sections.py) merges Class A intervals before applying the 100 m rule; [02:254-270](../scripts/02_build_sections.py) applies it per
record. A section overlapping two adjacent Class A records of < 100 m each would be flagged but have no species text. **No current section is affected**
(`class_a_flag` and `class_a_gis_keys.notna()` agree on all 18). Add that equality as an assertion in `validate()`.

---

### D. Stale or contradictory documentation

#### D1 — CLAUDE.md  (Med, S)
CLAUDE.md is the file every new Claude session trusts first, and it was last touched 2026-09-29. Fix:
- Lines 11 and 159 name `notebooks/02_optimization.ipynb` and `03_sensitivities`; commit `13e0842` replaced them with `scripts/optimization.py` and
  `scripts/sensitivities.py`. (Also `docs/transport_research.md:322`.)
- Lines 5, 30, 51 (and `model_design.md:325`, `PROMPTS.md:262, 324`) say road distances are built in `notebooks/travel_arcs.ipynb`; they are built by
  `scripts/11_road_distances.py` (and 12); the notebook only loads and validates.
- Layout (lines 148–165) omits scripts 11–16, `tests/test_clusters.py`, `docs/clustering_options.md`, `docs/cluster_tracker.md`, `section_*clusters`,
  `*_road_distance` tables.
- "Nate" or "Gavin" appears on 45 lines of `scripts/` and "Nate" on 27 lines of `docs/`, but CLAUDE.md never says who is who. Add one line mapping names to roles (see D-8).
- Agreed simplifications say each section's 2026 count "is split equally over its scheduled events"; the code splits **per species over the events marked
  with that species** (brood over all events) — see the 09 docstring. Use the precise wording.
- Rule 3 / OSRM: see A5. The "tables are parquet plus a csv copy" convention: see E5.

#### D2 — PROMPTS.md status block  (Med, S)
Lines 9–35 (dated 2026-09-28) say: `sections-pull` is "not merged into main … PR drafted" (merged as PR #2, and PR #4 followed); Gavin's distances "need Tionesta added"
(done 2026-09-29); the "Script order" line stops at script 10; Prompt 0 step 1 says untracking the partner files is "ON HOLD" (done in `8e5151c`). Replace the
block with the real state: scripts 00–16 exist; Prompts 7 (not started), 8 (not started), 9 (not started); the open decisions in §2 above.

#### D3 — `data/README.md` table  (Low, S)
Lines 12–22 list 7 entries (of about 21 outputs). Missing: `demand`, `coop_stockings`, `county_anglers`, `survey_water_crosswalk`, `stocking_events`, `section_schedule`, `clusters`,
`hatchery_schedule_supply`, `hatchery_to_section_road_distance`, `section_to_section_road_distance`, `section_medoid_clusters`, `section_hierarchical_clusters`,
`pfbc_stocking_rates`, `trout_hatcheries.gpkg`. Line 22 says later phases will add "demand, cost_matrix"; demand exists, cost_matrix does not (B1). Either generate this
table from `docs/data_dictionary.md` or replace it with a link.

#### D4 — `known_gaps.md` § "Gavin's stocked-streams layer vs our sections"  (Low, S)
Lines 80–85 say 8 candidate sections "would have no distance". The road tables are now built on `sections.parquet` midpoints for all 1,045 sections
(`tests/test_clusters.py::test_hatchery_to_section_distance_table`). Mark the gap resolved. `pa_stocked_trout_streams.gpkg` is now only read by
`notebooks/01_data_prep.ipynb`.

#### D5 — `.gitignore` comment  (Low, S)
[.gitignore:9](../.gitignore) says partner files "stay tracked until we agree to untrack them". They were untracked in `8e5151c`.

#### D6 — `figure_ideas.md` and `scenarios_and_extensions.md`  (Low, S)
`figure_ideas.md` ("Last updated 2026-09-27") still marks the demand figures "Prompt 6" although `demand` is built; the numbers it quotes are correct (verified),
so flip them to **ready**, and add the cluster figures that exist. `scenarios_and_extensions.md` says "Last updated: 2026-09-28" but has a 2026-09-30 row.

#### D7 — Small wrong or stale statements  (Low, S)
- `model_design.md:145-146` — see B7. `model_design.md:457-458` — see B4.
- `data_dictionary.md` § `pa_trout.gpkg`: `hatcheries` layer has 10 features (TROUT == "y"); the base model uses 9 supply nodes and the official layer has 13; mark clearly "placeholder".
- `docs/source_inventory.md` says the Operational Guidelines were saved under `data/raw/pfbc_docs/`; no code reads that PDF (Table 14/18/45/46 are hand-transcribed
  into scripts 02 and 04 and `parameters.csv`). Say so, and list the page numbers each table came from in one place.

#### D8 — README  (Low, S)
`python3 -m venv .venv && source .venv/bin/activate` and `.venv/bin/python …` (12 occurrences in docstrings and docs) are POSIX-only, but both collaborators work on Windows
(`.venv\Scripts\python.exe`). Give both forms. Add a one-line map of `docs/` and a link to this audit.

---

### E. Code quality

#### E1 — Two styles; scripts 11–16 cannot be imported or tested  (Med, L)
- **Evidence:** `main()` exists in 01–10 but not in 00, 11, 12, 13, 14, 15, 16. Lines over 130 columns: 13 → 38, 16 → 30, 15 → 21, 14 → 18, 12 → 8. Semicolon-chained statements: 13 → 35.
  Importing 12 runs `argparse.parse_args()` and starts querying OSRM. The following is copied across scripts 13, 14, 15, 16: the road-matrix loader (4×),
  the colour palette and `rcParams` block (4×), `poly()` (4×), `state_map()` (3 variants), `describe()` (3 variants), hull-building.
- **Fix (in this order, each its own commit):**
  1. `scripts/cluster_common.py` with `load_road_matrix()`, `load_clusterings()`, palette/`apply_style()`, `hulls_of()`, `poly()`, `describe_clusters()`.
  2. Wrap 12, 13, 15, 16 in `main()` + `if __name__ == "__main__":`; move constants to module level. Keep `# %%` cell markers if Gavin uses them.
  3. Match the surrounding style (see 01–10): ≤ 120 columns, one statement per line, docstring with Inputs/Outputs.
  4. **Gate:** after each step, re-run the script on committed inputs and confirm `git diff --stat data/processed outputs/tables` is empty (figures may differ at the pixel level).
- **Skip this item** if D-1 resolves to (a).

#### E2 — Scrapped script 14 is still in the numbered sequence  (Low, S)
[14_dbscan_clusters.py](../scripts/14_dbscan_clusters.py) says "SCRAPPED" in its first line, but README says to run scripts "in numeric order", and script 16
re-implements DBSCAN inline. Move it to `scripts/archive/`, update the paths mentioned in `docs/clustering_options.md`, `docs/cluster_tracker.md` and README, and leave
its outputs where they are.

#### E3 — Numbers typed into text  (Low, S)
[16:125-178](../scripts/16_compare_methods_map.py) hard-codes "1,015 truck runs", "632 runs", "19.9 mi", "234 clusters", "74 clusters", "5.7%"; [13:282](../scripts/13_medoid_clusters.py) says
"in a similar number of clusters"; [15:222](../scripts/15_hierarchical_clusters.py) hard-codes "4 sections, 20 mi"; the 13 docstring says "407 with the fixed seeds". They match today and
will drift silently. Build the strings from the computed tables and `parameters.csv`.

#### E4 — Personal names in code and figures  (Low, S) — Decision D-8
45 lines mentioning "Nate" or "Gavin" in `scripts/`, plus figure titles ("Nate's schedule clusters") and `docs/cluster_tracker.md`. Fine for a working repo; not for a final report or a repo a grader reads.

#### E5 — Format convention  (Low, S)
CLAUDE.md: "Tables are parquet plus a csv copy." CSV only: `clusters`, `county_anglers`, `county_region`, `hatchery_schedule_supply`, `parameters`, `pfbc_stocking_rates`, `survey_water_crosswalk`.
Parquet only: `section_to_section_road_distance` (documented). Either add parquet siblings (cheap) or reword the convention. Note that `demand.csv` is rounded to 3 decimals while
the parquet is not; say that the parquet is authoritative.

---

### F. Tests

#### F1 — No unit tests for pipeline logic  (Med, L)
`tests/test_common.py` covers `common.py`; `tests/test_processed.py` and `tests/test_clusters.py` only freeze output counts. A logic bug that happens to preserve the counts would pass.
Add `tests/test_logic.py` (scripts 02–10 are importable; load by path with `importlib` as I did, or add `scripts/__init__`/`conftest.py` that puts `scripts/` on `sys.path`):
- `02.table18()` regenerates `pfbc_stocking_rates.csv` exactly (I verified it does today: 234 rows).
- `02.merge_intervals` and `river_mile_overlap`: touching intervals merge; reversed limits handled; overlap ≤ 100 m not flagged.
- `04.table18_caps`: after the cummax step, for every (biomass, width), `access_rate` is non-decreasing in access (L ≤ G ≤ H) and ≤ `cap_rate_river`.
- `08.per_mile_rates`: Σ_s rate[i,s]·length[s] = 1 for every block group, including a case where a whole band has no section.
- `07.name_key`: "Twenty Mile" = "Twentymile"; "(Warrensville)" and "- hillsgrove" suffixes dropped.
- `10.components` / `detours`: two sections with share exactly 0.5 link under the default and not under the strict rule.
- `13/15` (after E1): `limited_cut` never returns a cluster above either limit; `kmedoids` is deterministic for a fixed seed.

#### F2 — Cross-table consistency tests  (Low, S)
Add: Σ `hatchery_schedule_supply.stream_fish_2026` == Σ `total_2026` (B3); `demand`, `section_schedule`, `section_*clusters` ids == the 1,022 candidates; every candidate id has all 13 rows in the hatchery
road table; hatchery names equal across `stocking_events`, `hatchery_schedule_supply` and the road table; `class_a_flag == class_a_gis_keys.notna()` (C5); CSV and parquet copies have equal shape and columns (verified today for 10 tables).

#### F3 — No CI  (Low, S)
Add `.github/workflows/test.yml` that installs `requirements.txt` and runs `pytest`. All tests use committed data only; none needs the network.

---

### G. Repo hygiene

#### G1 — Branch state  (Med, S) — Decision D-10
`git rev-list --left-right --count origin/main...tionesta-hatchery` → `0  13`: the work branch contains all of `main` plus 13 commits, 68 files, +9,685 / −1,545 lines (OSRM tables, clusters, scripts 11–16,
the optimization scaffolds, tests). `main` has none of it, and the name `tionesta-hatchery` no longer describes it. Stale branches: `road-distances`, `schedule-rebuild`, `origin/sections-pull`, `origin/prompt7_nate`.
Open one PR into `main`, then delete the merged branches. I cannot see unpushed local work in the other collaborator's checkout; confirm they have nothing outstanding before merging.

---

## 4. Checked and found correct (so nobody repeats it)

Re-derived from committed tables or by re-running pure functions:
- `pytest`: 31 passed in 3.4 s.
- `table18()` regenerates `pfbc_stocking_rates.csv` exactly (all columns except the free-text `source`; 234 rows); biomass-B/High at widths 2–3 = 147, Good up to 323; the cummax "better access never lowers the cap" rule is implemented as documented.
- 1,045 sections, 1,022 stocked in 2026, 23 dropped; 2026 species totals (68,305 / 659,290 / 1,800,505 / 15,123 / 63,245 = 2,606,468) match `model_design.md`.
- `cap_source` counts (access 1,012 / class A 17 / program 9 / baseline 7 over all 1,045), Class A "grow" scenario 84.7k vs 34.5k fish (2.46×), Youghiogheny needs a 67 m width at 266/acre, no candidate has `cap_fish < total_2026`.
- Backing the width out of stocking (fish ÷ rate ÷ length) gives class medians 6.2 / 12.3 / 24.8 m, as the doc states (class 1L is 42.9 m against the assumed top of 60 m, so the 1L caps are generous).
- `figure_ideas.md` statistics: fish per acre by population class (216/125/111/66), High vs Good medians (163 vs 73) and counts (216/800/6), fish per angler-day by region (0.21 SE/SW, 0.45 NC), 3.3 angler-days per stream trout.
- Demand: total 8,717,541 angler-days in every column; p93 table row order vs `statewide_all` mapping is correct (0–10 miles = 37%); `destination_index` median 1.42.
- Cluster docs: 310 / 407 / 375 / 309 clusters, silhouettes (0.39 / 0.35 / 0.38 / 0.44), hatchery-distance errors (2.2 / 1.7 / 1.9 / 2.2%), real-run coverage (42–65%) all match the saved comparison tables
  (the hierarchical "within 0.01" k-range differs slightly only because the saved CSV is rounded to 3 decimals).
- Hatchery attribute coordinates (`Lat`, `Long_`) equal the geometry to < 1e-5°; hatchery names agree across the schedule, the supply table and the road table; the road table has no missing route (13,585 rows); 121 OSRM block files are cached locally.
- Wild-trout layers have no missing river miles; 14 natural-reproduction records have zero river-mile length and 1 is reversed (not investigated further; the documented 18-section gap is the known consequence of short river miles).
- No credentials, API keys or absolute user paths in tracked files.

**Not verified (limits of this audit):** scripts 01–10 were not re-run end to end (this checkout has no `data/raw/pfbc_*` downloads or `data/interim/pfbc_gis`; `pdfplumber`/`pynhd` are not installed here);
hand-transcribed PDF values (Table 14/18/45/46, survey chart percentages, the license-PDF column x-positions) were not re-checked against the PDFs (not stored locally); only one figure PNG was viewed;
notebooks were read, not executed; the other collaborator's unpushed work is invisible from here.

---

## 5. Instructions for a Claude agent implementing this file

**Ground rules (all from CLAUDE.md; repeated because they matter here)**
1. Read `CLAUDE.md`, then this file's §2. **Do not decide a "Decision needed" item yourself.** If its answer cell is empty, skip it and say so.
2. One phase at a time, commit small, stop for review at each phase end. Do not push, open PRs, or merge without the user's OK.
3. When you change a documented fact, update the checkpoint file CLAUDE.md names for it (`data_dictionary.md`, `data_methods.md`, `known_gaps.md`, `model_design.md`, `parameters.csv`, `source_inventory.md`, `PROMPTS.md`, `tests/test_processed.py`).
   A failing assert in `tests/test_processed.py` names the doc to fix.
4. Never touch `data/raw/` contents. Do not call fbweb.pa.gov, PASDA or the OSRM server except where an item says so and the user has OK'd it (rules 2–3; ≤ 1 request/s; the schedule download is 68 requests).
5. Never "fix" a processed table by hand. Change the script, re-run it on committed inputs, and show `git diff --stat data/processed`.
6. Match the code around you: scripts 01–10 are the house style (`from __future__ import annotations`, `main()`, `setup_logging`, counts logged before/after, docstring with Inputs/Outputs).

**Environment (this machine)**
- Python: `C:\Users\loydg\anaconda3\python.exe` (3.13.5). Bare `python`/`python3` fail. Installed: numpy, pandas, scipy, geopandas, shapely, pyproj, scikit-learn, matplotlib, gurobipy 13.0.3, pytest, requests-cache, bs4, lxml, pyarrow.
  Not installed: `pdfplumber`, `pynhd` (install with `python.exe -m pip install pdfplumber` before touching 00/04/06).
- Shell is Git Bash or PowerShell on Windows; pass `PYTHONIOENCODING=utf-8` when printing notebook text.
- Run tests with `C:\Users\loydg\anaconda3\python.exe -m pytest -q` from the repo root.

**Suggested order (each bullet = one commit; verification in parentheses)**
- *Phase 0, docs only, no risk:* D1, D2, D3, D4, D5, D6, D7, D8, B7 (doc part) (`pytest` unchanged; `git diff` touches only `*.md`, `.gitignore`).
- *Phase 1, repo and environment:* A6, A7, F3, G1 once D-10 is answered (`pip install -r requirements.txt` in a clean venv; CI green).
- *Phase 2, reproducibility:* A2 → A1 (needs D-7) → A4 → A5 (needs D-6) → A3 → A8 (a clean-clone dry run per A3; `pytest`).
- *Phase 3, model inputs (B1 items 1–5):* B3 first (so `hatcheries.supply` is right), then D-2/D-3/D-4 → B4/B5/B6, then `hatcheries`, `parameters.csv` rows, `cost_matrix`, baseline cost, `model_input`
  (extend `tests/test_processed.py` with the new counts; compare against Appendix B).
- *Phase 4, model (B1 items 6–7):* `optimization.py`, then `sensitivities.py` (checks listed under B1 item 7).
- *Phase 5, only after D-1:* B2 and, if cluster code is kept, E1 → E2 → E3 → C1; otherwise archive 12–16 and skip E1/E3/C1.
- *Phase 6, polish:* C2–C5, E4 (after D-8), E5, F1, F2.

**Per-item "done" gates** are in each finding. Generic gates: `pytest -q` passes; `git status` shows only intended files; every new column is in `docs/data_dictionary.md`; every new parameter is in `data/processed/parameters.csv` with source or "assumption" plus range;
every changed number in prose matches the table it came from.

---

## Appendix A — Pipeline dependency map (as the code actually behaves)

```
00  PDF (downloads if missing) ........................ -> angler_survey/*.csv
01  fbweb + PASDA (downloads) ......................... -> data/interim/pfbc_gis/*.parquet   (7 layers incl. hatcheries)
02  <- 01, [raw/pa_hatcheries.gpkg  *untracked*] ...... -> sections, stocking_section_year, pfbc_stocking_rates, pa_trout.gpkg
03  <- 02 (sections + gpkg), 01 (nat_repro, class_a),
       [raw/pfbc_coop xlsx *manual*], [raw/Coop_nurseries.geojson *untracked*]
                                                         -> coop_stockings; ADDS coop_* cols to sections
04  <- sections, parameters, pfbc_stocking_rates,
       raw summarybook.pdf (downloads if missing) ...... -> county_region; ADDS river/area/cap cols to sections
05  <- sections ...................................... -> environment
06  <- county_region (04), [raw census *manual*], [raw license PDF *manual*]  -> county_anglers
07  <- angler_survey (00), sections, county_anglers, parameters               -> survey_water_crosswalk
08  <- sections, county_anglers, crosswalk, angler_survey, parameters, [raw census] -> demand
09  <- sections, pa_trout.gpkg, fbweb schedule (downloads, 68 POSTs),
       [raw/pa_hatchery_production.csv], [raw/pa_hatcheries.gpkg]            -> stocking_events, hatchery_schedule_supply
10  <- stocking_events, sections, parameters ........... -> section_schedule, clusters
11  <- [raw/pa_hatcheries.gpkg], [raw/Coop_nurseries.geojson], sections, pa_trout.gpkg, (stocking_events), OSRM
                                                         -> hatchery_to_section_road_distance (skips OSRM if output exists)
12  <- sections, hatchery_to_section_road_distance (check), OSRM (re-queries; overwrites output!  see A4)
                                                         -> section_to_section_road_distance
13  <- 12, 10, 11, 09 (supply), parameters, pa_trout.gpkg  -> section_medoid_clusters
14  SCRAPPED <- 12, 10, 13 .............................. -> outputs/*dbscan*
15  <- 12, 11, 09, 10, 13, parameters .................... -> section_hierarchical_clusters
16  <- 12, 10, 13, 15 .................................... -> outputs/figures/method_comparison/*
```
`[ ]` = file that is not tracked and not downloaded by any script. 02 → 03 → 04 all rewrite `sections.parquet`; rerun 03 and 04 after 02.

## Appendix B — Prototype numbers for sanity-checking Prompt 7

Quick calculation from committed tables only (road miles to section midpoints; 9 base hatcheries; `total_2026` including brood and golden; central cost $1.90/truck-mile, 2,500 fish/load, no mortality).
These are **not** results; they are a reasonableness check for whoever builds `cost_matrix` and the baseline cost.

| Quantity | Scheduled hatchery | Nearest of the 9 |
|---|---|---|
| Fish-weighted mean one-way haul | 88.5 mi | 68.0 mi |
| Σ fish × one-way miles | 230.6 M | 177.3 M |
| Baseline transport cost, `2 × mi × 1.90 / 2500` | ≈ $350k / yr | ≈ $270k / yr |
| Implied fleet miles at 2,500 fish/load (`2·Σ fish·mi / 2500`) | ≈ 184k | ≈ 142k |

Reference for the calibration check: 300,000 fleet miles × (2.606 M / 3.143 M stream share) ≈ 249k. The scheduled-hatchery figure implies an effective load of about 1,850 fish, inside the 1,500–3,500 range in `transport_research.md`.
The scheduled baseline is about 30% more fish-miles than "nearest", which supports keeping nearest as a sensitivity (D-5).
