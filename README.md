# Trout Optimization Project

Optimization project (Python). Class: From Data to Action. Rules, model framing and conventions: `CLAUDE.md`.

## Layout
- `scripts/` – numbered data pipeline; run in numeric order
- `tests/` – pytest tests for the scripts
- `notebooks/` – run in order: `01_data_prep`, `02_optimization`, `03_sensitivities`
- `data/raw` → `interim` → `processed` – raw is git-ignored except `manifest.csv`; interim is git-ignored;
  processed is committed. Sources and outputs: `data/README.md`
- `outputs/` – figures and tables for the report

## Setup
```
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

## Run
```
python scripts/01_download_pfbc_layers.py   # then each later script in numeric order
pytest
```
