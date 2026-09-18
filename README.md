# Trout Optimization Project

Two-person optimization project (Python). Class: From Data to Action.

## Layout
- `notebooks/` – run in order: `01_data_prep`, `02_optimization`, `03_sensitivities`
- `src/` – reusable code (import in notebooks, e.g. `from src.paths import RAW`)
- `data/raw` → `interim` → `processed` – contents git-ignored; document sources in `data/README.md`
- `outputs/` – figures and tables for the report

## Setup
```
pip install -r requirements.txt
```
Run notebooks from the repo root or `notebooks/` (add repo root to `sys.path` if imports fail).

## Workflow
Pull before working, commit small, and avoid both editing the same notebook at once (notebook diffs merge badly).
