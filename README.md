# Autonomous Model Maintenance under Concept Drift

A supervisor for a deployed **hourly bike-demand model**. It:
- observes prediction outcomes as labels arrive;
- notices when a better model has become attainable, or when error has deteriorated;
- trains and validates replacement candidates, and promotes an acceptable one;
- monitors the new model on paired predictions, keeping it or rolling it back.

**Research question:** can selective, validated retraining maintain prediction quality while
reducing unnecessary retraining compared with a fixed schedule?

- **Data:** 377 M real bike-share trips from four systems, aggregated to hourly demand with NOAA
  airport weather: Washington DC (Capital Bikeshare 2011-2025), Chicago (Divvy), New York
  (Citi Bike) and SF Bay Area (Bay Wheels). See [docs/DATASET.md](docs/DATASET.md).
- **Policies.** All share candidate training, the validation gate, probation/rollback and the
  budget; only the trigger differs:
  - static;
  - periodic, every 14/28/56/91 days;
  - drift-detector triggers (ADWIN, Page-Hinkley, KSWIN, ADWIN+bias);
  - the proposed **probe** trigger, which fits one cheap challenger and retrains only if it is
    significantly better on the newest held-out days ([docs/METHOD.md](docs/METHOD.md)).
- **Results, clean test** (frozen tag `clean-test-v1`, cities never used for design;
  [docs/EVALUATION.md](docs/EVALUATION.md), `reports/multicity/`):
  - Drift-detector triggers were 39-45 % less accurate than a 28-day schedule.
  - Probe matched the schedule (+0.5 %, no significant difference on any of 7 streams) with
    39 % fewer full cycles, and never retrained on stationary streams.
  - A 14-day schedule was 4-5 % more accurate than every trigger, at 1.8x compute.
  - *Correction pending:* the NYC 2018 archive was counted about twice in the built data, so
    the NYC rows (and the means that include them) are superseded until the deduplicated re-run
    (BUILD_STATUS D20).
- **Paper-style report:** [docs/PAPER.md](docs/PAPER.md).

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

| Step | Command | Laptop (i5-11300H, 4C, 8 GB) | Big PC (Core Ultra 9 285, 24C, 64 GB) |
|---|---|---|---|
| Download + validate + build data | `prepare-data` (`--offline` = cache only) | ~10 min download + 1.7 min build; offline rebuild 3.0 min | 3.3 min (incl. 1.3 GB download) |
| Initial model selection | `select-model` | 0.7 min | - |
| Calibrate on dev scenarios | `calibrate --workers N` | 36.8 min (N=4) | 13.1 min (N=12) |
| Fast smoke experiment | `smoke --workers N` | 3.2 min (N=4) | 1.5 min (N=12) |
| Full benchmark (39 runs) | `benchmark --workers N` | not run: use N<=2 on 8 GB | 11.0 min (N=12) |
| Post-hoc variant (exploratory) | `posthoc --workers N` | - | 12.2 min (N=12) |
| Download / build three more cities | `download-city`, `build-city` | - | 12.6 min + 1.5 min |
| Calibrate probe + detectors (dev only) | `calibrate-extra --workers N` | - | 7.1 min (N=12) |
| Clean multi-city test (230 runs) | `multicity --workers N` (from tag `clean-test-v1`) | - | 58 min (N=12) |
| Re-draw multi-city report | `multicity-report` | 44 s | - |
| Re-draw charts | `report --name benchmark` | seconds | seconds |
| Tests (55) | `test` (or `python -m pytest tests -q`) | 24 s | 13 s (43 at the time) |
| Dashboard | `python -m streamlit run app/dashboard.py` | | |

On 8 GB RAM run heavy steps with `--workers 2` and without the dashboard open (4 workers + the
dashboard exhausted memory). Two-machine workflow: [memory/README.md](memory/README.md).

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
scripts/        setup.ps1, setup.sh, bigpc_run.ps1, rehearse_demo.py, export_decisions.py
data/           raw/ (downloads, unchanged), processed/, scenarios/
reports/        model_selection.json, calibration*/, smoke/, benchmark/, posthoc/, multicity/
docs/           DATASET, ARCHITECTURE, METHOD, EVALUATION, PAPER, DEMO_SCRIPT, PRESENTATION_OUTLINE, VIVA_PREP
BUILD_STATUS.md implemented features, test status, decisions, how to resume
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - components, information boundary, state machine diagram
- [docs/DATASET.md](docs/DATASET.md) - sources, licences, checksums, transformations, feature availability
- [docs/METHOD.md](docs/METHOD.md) - the proposed probe trigger
- [docs/EVALUATION.md](docs/EVALUATION.md) - protocol, metric definitions, results, threats to validity
- [docs/PAPER.md](docs/PAPER.md) - paper-style report of the whole study
- [docs/VIVA_PREP.md](docs/VIVA_PREP.md) - algorithms, leakage prevention, policy, rollback, limits
- [docs/PRESENTATION_OUTLINE.md](docs/PRESENTATION_OUTLINE.md) and [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)

Data attribution: Capital Bikeshare system data (Capital Bikeshare Data License Agreement);
NOAA NCEI ISD-Lite; Fanaee-T, H. (2013) Bike Sharing, UCI ML Repository,
https://doi.org/10.24432/C5W894 (CC BY 4.0, used for a cross-check only).
