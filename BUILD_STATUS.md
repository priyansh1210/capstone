# BUILD_STATUS — Autonomous Model Maintenance under Concept Drift

Last updated: 2026-10-28, session 1 (core deliverables complete). Resume from "Next steps".

## Environment (actually used)

- Big PC (DESKTOP-RTIKELL): Core Ultra 9 285 (24 cores), 64 GB, Windows 11 Pro, Python 3.12.10, fresh `scripts/setup.ps1` install from requirements.txt (verified).

- Windows 11, i5-11300H (4C/8T), 8 GB RAM; GPU not used (CPU-only by design).
- Laptop `.venv` = Python 3.11.9 venv created with `--system-site-packages` because PyPI's file CDN
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
| D16 | **Post-hoc variant "adaptive+"** (reference cap at k x calibration anchor, total-demand bias trigger), both OFF in the frozen config; `amm posthoc` selects k and the bias threshold on dev scenarios, then runs once on evaluation. | Diagnosed from the frozen benchmark: a model accepted during the COVID collapse got a ~4x reference and every later alarm was dismissed for 2.5 years. Fourth evaluation-informed change -> reported as exploratory only. |
| D15 | Operator retraining request (logged) in the dashboard. | Deterministic classroom demo of a rejected update; it uses the same gates, gate and probation. |

## Status

- [x] Download + validation (`amm prepare-data`): 106 files, sizes/MD5 ETags checked, SHA-256 in `data/raw/SOURCES.json`; UCI zip via manual fallback on the laptop (Python TLS "certificate has expired"), committed under `data/raw/manual/` (CC BY 4.0).
- [x] Hourly dataset + report (`data/processed/hourly.parquet`, `dataset_report.json`): 122,722 rows, 44,967,423 trips; identical on both machines (106/106 checksums).
- [x] Engine: simulator/view (label delay), monitor (ADWIN), state machine, retraining, gate, promotion, probation (with alarm deferral), rollback, operator request, fault injection, SQLite store, checkpoint/resume.
- [x] Scenarios A-D (+ synthetic_abrupt) and fixtures E; manifests in `data/scenarios/`.
- [x] Tests: **46 passed** (laptop, `python -m pytest tests -q`, ~16 s); 43 passed on the big PC (before the post-hoc tests were added).
- [x] Calibration v2 on the big PC (13.1 min, 12 workers) -> `configs/frozen_policy.yaml`: windows [365, 730], ADWIN delta 0.002, rel_margin 0.15, periodic 28 d (same values as v1; v1 + partial v2 log in `reports/superseded/`).
- [x] Smoke (big PC 1.5 min) and **full benchmark** (big PC 11 min, 39 runs) -> `reports/smoke/`, `reports/benchmark/`.
- [x] Cross-machine determinism: laptop re-ran adaptive/bike_unmodified -> identical (MAE 114.67, 22 cycles).
- [x] Post-hoc exploratory variant (`amm posthoc`, big PC 12.2 min) -> `reports/posthoc/` (bias trigger 15 %, chosen on dev).
- [x] Demo rehearsal (`scripts/rehearse_demo.py`, 42 s): detection, promotion, keep, test-only rejection and rollback all executed.
- [x] Docs written from executed results: README, docs/EVALUATION.md (results, failure analysis, post-hoc), DATASET, ARCHITECTURE, DEMO_SCRIPT, PRESENTATION_OUTLINE, VIVA_PREP; memory/PUBLICATION_ROADMAP.md.
- [ ] Visual browser check of the dashboard: the Chrome extension was not connected; AppTest (headless) passed and the server returned health 200. The dashboard server was later stopped by Claude Code during a low-memory event and has not been restarted.

## Session 1b - upgrade to a paper-grade study (in progress)

- [x] Multi-city data: `amm download-city` (big PC 12.6 min, 0 failures) + `amm build-city` (1.5 min):
      Chicago 46,868,464 trips / 96,421 h; San Francisco 17,507,791 / 65,849 h; New York 261,126,852 / 96,421 h;
      DC 2011-2025 51,630,070 / 131,481 h (weather to 2025-08-27). 0 unparsed rows; working-day peaks 8/17 every city-year.
- [x] Schema-agnostic trip parser (5 header styles, US/ISO timestamp formats, nested zips, station CSVs skipped), archive-gap handling.
- [x] Proposed method `probe` (docs/METHOD.md): cheap challenger + paired daily-MAE test, drift only accelerates probing.
- [x] Baselines: periodic 14/28/56/91 d, Page-Hinkley and KSWIN triggers, ADWIN+bias, oracle (injected changes only).
- [x] Statistics: moving-block bootstrap CI + Diebold-Mariano (stats.py); ablations; Pareto + rolling charts.
- [x] Tests: 55 passed.
- [ ] Big PC: `-Only calibrate-extra` (dev only) -> review -> tag `clean-test-v1` -> `-Only multicity` (230 runs).
- [ ] Paper-style report, slides, dashboard visual check.

## Key results (frozen protocol; details in docs/EVALUATION.md)

- Real 2018-2024 replay MAE: periodic-28d **81.5** (91 cycles), adaptive 114.7 (22), static 136.6.
- Stationary synthetic: adaptive 0.6 cycles vs periodic 26 at equal MAE (34.7 vs 34.8).
- Detection: real abrupt 15 d; synthetic abrupt 10-37 d (5/5); 6-month ramp not confirmed in 90 d.
- Failure diagnosed: reference rebased during the COVID-19 collapse (~4x), alarms dismissed for 2.5 years.
- Post-hoc (exploratory): adaptive+ bias trigger 84.5 with 63 cycles; still 0.6 cycles on stationary data.

## Next steps (resume here)

1. Presentation slides from docs/PRESENTATION_OUTLINE.md + figures in `reports/benchmark/` and `reports/posthoc/`.
2. Optional: visual check of the dashboard (`.venv\Scripts\python -m streamlit run app/dashboard.py`, close other apps on the 8 GB laptop).
3. Publication path: memory/PUBLICATION_ROADMAP.md (first: frozen-code confirmatory run on 2025-01..2026-09 data).
