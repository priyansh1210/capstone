# Autonomous Model Maintenance under Concept Drift

A supervisor for a deployed **hourly bike-demand model** (Washington DC, Capital Bikeshare).
It observes prediction outcomes as labels arrive, notices sustained deterioration, decides
whether retraining is justified, trains and validates replacement candidates, promotes an
acceptable one, and monitors it on paired predictions to keep it or roll back.

**Research question:** can selective, validated retraining maintain prediction quality while
reducing unnecessary retraining compared with a fixed schedule?

- Data: 44,967,423 Capital Bikeshare trips (2011-2024) aggregated to 122,722 hourly rows, plus
  NOAA hourly weather observations at DCA; evaluation replay 2018-2024 (incl. COVID-19).
  See [docs/DATASET.md](docs/DATASET.md).
- Policies: **static** (never retrain), **periodic** (calibrated schedule), **adaptive**
  (ADWIN + confirmed deterioration). Periodic and adaptive share candidate training, the
  validation gate, probation/rollback and the budget; only the trigger differs.
- Results: [docs/EVALUATION.md](docs/EVALUATION.md) and `reports/benchmark/`.

## Setup (Windows PowerShell; tested)

```powershell
cd D:\capstoneproject
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # creates .venv, installs requirements.txt
# if PyPI is slow/blocked but the system Python already has the packages:
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -SystemSitePackages
```

Linux/macOS/Git Bash: `bash scripts/setup.sh`. Python 3.11; versions in `requirements.txt`.
No GPU, cloud account, paid API or external database is needed.

## Commands

All commands: `.venv\Scripts\python -m amm <command>` (run from the project root).

| Step | Command | Measured on i5-11300H / 8 GB |
|---|---|---|
| Download + validate + build data | `prepare-data` (`--offline` to use the cache only) | RUNTIME_PREPARE |
| Initial model selection | `select-model` | ~45 s |
| Calibrate thresholds on dev scenarios | `calibrate --workers 4` | RUNTIME_CALIBRATE |
| Fast smoke experiment | `smoke --workers 4` | RUNTIME_SMOKE |
| Full benchmark | `benchmark --workers 4` | RUNTIME_BENCH |
| Re-draw charts | `report --name benchmark` | seconds |
| Tests | `test` (or `python -m pytest tests -q`) | RUNTIME_TESTS |
| Dashboard | `python -m streamlit run app/dashboard.py` | |

Outputs: `data/processed/` (hourly table + `dataset_report.json`), `data/scenarios/`
(scenario replays + manifests), `configs/frozen_policy.yaml` (calibrated values with
provenance), `reports/<name>/` (results.csv/json, summary.md, per-run SQLite, daily series,
`fig_*.png`), `artifacts/` (dashboard database, model artifacts, checkpoints).

## Dashboard and live demo

`python -m streamlit run app/dashboard.py`, then follow [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).
Tabs: **Overview** (scenario and data-source label, replay progress, active model, controller
state, actual vs originally predicted demand, rolling error, update counts and measured
training time), **Decision timeline** (every action with reason, measurements and thresholds),
**Model versions** (active/previous/rejected/retired/rolled-back with training and validation
ranges), **Experiments** (benchmark tables split by source/modified/generated data, charts,
CSV/JSON downloads). Controls: create run, start, pause, step, speed, fast-forward, save and
resume checkpoint, inject a labelled demand change, operator retraining request, and
visibly labelled TEST-ONLY fault injections (weak candidate pool, forced weak activation).

## Repository layout

```
src/amm/        engine (data, stream, monitoring, policy, models, storage, experiments, ui)
app/            Streamlit dashboard (thin)
configs/        base.yaml, smoke.yaml, full.yaml, demo.yaml, frozen_policy.yaml
tests/          pytest suite (fixtures = small generated streams)
scripts/        setup.ps1, setup.sh
data/           raw/ (downloads, unchanged), processed/, scenarios/
reports/        model_selection.json, calibration/, smoke/, benchmark/
docs/           DATASET, ARCHITECTURE, EVALUATION, DEMO_SCRIPT, PRESENTATION_OUTLINE, VIVA_PREP
BUILD_STATUS.md implemented features, test status, decisions, how to resume
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - components, information boundary, state machine diagram
- [docs/DATASET.md](docs/DATASET.md) - sources, licences, checksums, transformations, feature availability
- [docs/EVALUATION.md](docs/EVALUATION.md) - protocol, metric definitions, results, threats to validity
- [docs/VIVA_PREP.md](docs/VIVA_PREP.md) - algorithms, leakage prevention, policy, rollback, limits
- [docs/PRESENTATION_OUTLINE.md](docs/PRESENTATION_OUTLINE.md) and [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)

Data attribution: Capital Bikeshare system data (Capital Bikeshare Data License Agreement);
NOAA NCEI ISD-Lite; Fanaee-T, H. (2013) Bike Sharing, UCI ML Repository,
https://doi.org/10.24432/C5W894 (CC BY 4.0, used for a cross-check only).
