# Trout Optimization Project

Optimization project (Python). Class: From Data to Action. Rules, model framing and conventions: `CLAUDE.md`.

## Layout
- `scripts/` – numbered data pipeline (run in numeric order), plus the model scripts `optimization.py` and `sensitivities.py`
  (`11`, `12` and `19` build road distances; `13`, `15` and `16` explore section clusters, see `docs/clustering_options.md`)
- `tests/` – pytest tests for the scripts
- `notebooks/` – exploration and maps only: `01_data_prep`, `travel_arcs`. Data building and the model are scripts
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
