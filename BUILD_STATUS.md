# BUILD_STATUS — Autonomous Model Maintenance under Concept Drift

Last updated: 2026-10-28, session 1 (in progress). Resume from "Next steps".

## Environment (actually used)

- Windows 11, i5-11300H (4C/8T), 8 GB RAM; GPU not used (CPU-only by design).
- `.venv` = Python 3.11.9 venv created with `--system-site-packages` because PyPI's file CDN
  (files.pythonhosted.org) delivered ~17-25 kB/s from this network while S3/NOAA were fast.
  Installed into the venv: river 0.26.1, numpy 2.4.6, pytest 9.2.0. Inherited from the system
  Python: pandas 3.0.2, scikit-learn 1.7.2, scipy 1.15.3, streamlit 1.56.0, plotly 6.3.1,
  pyarrow 21.0.0, joblib 1.5.2, PyYAML 6.0.1, matplotlib 3.10.8, threadpoolctl 3.6.0.
- Package importable via `.venv/Lib/site-packages/amm-src.pth` (editable install needs `wheel`,
  which could not be fetched). `scripts/setup.ps1` tries `pip install -e .` first.

## Decisions

| # | Decision | Why |
|---|----------|-----|
| D1 | Dataset changed by user request to the **raw Capital Bikeshare trip archive 2011-2024** (44,967,423 trips -> 122,722 hourly rows) + **NOAA ISD-Lite DCA hourly weather**. | "Bigger and better". Same upstream source as UCI Bike Sharing (cross-check: all 17,379 UCI hours matched, totals within 1.1 %), 14 years of real drift (growth, COVID-19, e-bikes). Gas Sensor Array Drift rejected (13,910 rows, no intra-batch time order, classification). |
| D2 | Weather features = DCA observation from the hour *before* the target hour; forward fill <= 3 h from past values only. | Forecasting interpretation, no future weather. |
| D3 | Outage hours (>= 6 consecutive zero-trip hours in revealed labels) excluded from *fitting* and from the *monitor signal*; still predicted and scored. | Jan-2016 blizzard taught models "January ~ 0" (Jan-2017 log error 0.87 -> 0.32 after the rule; calibration MAE 87.9 -> 82.7). |
| D4 | Initial model = HGB on all 2011-2016 training rows (best calibration MAE among ridge/rf/hgb x {365, 730, all} days). | `reports/model_selection.json`. |
| D5 | Detector signal = scaled error `|log1p(y)-log1p(yhat)|` (cap 3) / monthly difficulty index estimated on calibration data. | Raw scaled error is ~2x higher in Dec/Jan than summer; without the index the adaptive policy retrained on seasons. Profile correlation across years 0.83-0.89 (pre-COVID), weaker later (documented assumption). |
| D6 | ADWIN warm-started with the active model's reference-window signal. | Otherwise a model already worse than its reference on day 1 looks stable to ADWIN. |
| D7 | Deterioration statistic = median of daily mean signal over 14 days vs reference (daily median); confirmed on 3 consecutive daily checks. | Robust to single outage/blizzard days. A rollback during the 2016 blizzard had inflated the reference and masked later deterioration (found on dev data). |
| D8 | After a rejected deterioration-triggered update, adaptive re-checks after the cooldown and retries if deterioration persists. | Otherwise ADWIN has already adapted to the higher error and no new alarm comes (dev abrupt: MAE 118.6 -> 103.6). |
| D9 | Validation gate: candidate MAE >= 5 % better than current on the newest eligible 14 days; deploy the validated artifact (no refit). Probation: 4 paired windows of 84 h; rollback if new MAE >= 1.05 x previous in 2 consecutive windows. | Spec 5. |
| D10 | Thresholds/intervals/windows calibrated ONLY on dev scenarios (train 2011-14, cal 2015, replay 2016-17; synthetic seeds 101-103), frozen in `configs/frozen_policy.yaml`. | Spec 4. **Disclosure:** D5/D6 were motivated by debugging runs on 2018-2019 of the evaluation stream before the dev harness existed. |
| D11 | Dev changes are increases (x1.5); a first dev change (x0.65 midday) *reduced* error because the dev model under-predicted 2016 - uninformative. | Honest note for the report. |
| D12 | Error increases detected by ADWIN *during probation* are deferred and investigated when probation ends (cleared on rollback). | Bug found in the first smoke run (2018 eval stream): a change starting during probation was absorbed by ADWIN and detection took 53 days. **Calibration was re-run after this fix**; the earlier calibration/smoke are kept in `reports/superseded/` and not used. Third evaluation-informed design fix (disclosed). |
| D13 | Recovery time is measured against a counterfactual: same policy, same stream without the injected change (bike: unmodified replay; synthetic: same-seed stationary stream, identical noise), on the log-scale error, from the end of the ramp; criterion: 14-day rolling excess <= 10 % for 14 consecutive days. | The first definition (return to the pre-change error level) let *static* "recover" because error levels move seasonally - invalid. |
| D14 | Budget 200 cycles per run. | 7-year replay with a 14-day schedule needs 183 cycles; 120 would have truncated periodic arbitrarily. Budget enforcement is still tested. |
| D15 | Operator retraining request (logged) in the dashboard. | Deterministic classroom demo of a rejected update; it uses the same gates, gate and probation. |

## Status

- [x] Download + validation (`python -m amm prepare-data`): 105 files cached, sizes/MD5 ETags checked, SHA-256 in `data/raw/SOURCES.json`; UCI zip via manual fallback (Python SSL error "certificate has expired" for archive.ics.uci.edu; curl worked).
- [x] Hourly dataset + report (`data/processed/hourly.parquet`, `dataset_report.json`).
- [x] Engine: simulator/view (label delay), monitor (ADWIN), state machine, retraining, gate, promotion, probation, rollback, fault injection, SQLite store, checkpoint/resume.
- [x] Scenarios A-D (+ synthetic_abrupt) and fixtures E; manifests.
- [x] Tests: **43 passed** (`python -m pytest tests -q`, ~15-25 s).
- [x] Calibration v1 (36.8 min) superseded by D12.
- [ ] **Calibration v2 was stopped by Claude Code at 14/~90 runs because the laptop ran low on memory** (4 workers + Streamlit; 1.9 GB of 8 GB free afterwards). `configs/frozen_policy.yaml` is currently ABSENT (v1 copy in `reports/superseded/`). Re-run with `--workers 2` here (~60-70 min) or on the larger PC.
- [x] Smoke benchmark ran end-to-end in 3 min 11 s (v1 settings; superseded).
- [x] Dashboard (`app/dashboard.py`): verified headless with Streamlit AppTest (create, step, fast-forward, inject, operator, weak pool); server health 200. Chrome extension was not connected, so no visual browser check yet.
- [ ] Smoke + full benchmark, charts, docs.

## Next steps (resume here)

1. `configs/frozen_policy.yaml` is missing: `.venv\Scripts\python -m amm calibrate --workers 2` (memory-safe on 8 GB; 4 workers + dashboard exhausted RAM).
2. `.venv\Scripts\python -m amm smoke` then `.venv\Scripts\python -m amm benchmark --workers 4`.
3. Dashboard: `.venv\Scripts\python -m streamlit run app/dashboard.py`.
4. Docs in `docs/` from `reports/benchmark/summary.md`.
