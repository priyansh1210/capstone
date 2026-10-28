# BUILD_STATUS — Autonomous Model Maintenance under Concept Drift

Last updated: 2026-10-28, session 1b (clean multi-city test done and written up). Resume from "Next steps".

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
| D17 | **Probe trigger** (docs/METHOD.md) plus Page-Hinkley/KSWIN triggers. Probe interval 14 d / window 120 d and the PH/KSWIN thresholds are chosen by `amm calibrate-extra` on dev scenarios only; code frozen at tag `clean-test-v1` (6b63a9b) before the single clean run. | Fixes both diagnosed failure modes without a self-reference; detectors added as stronger baselines. |
| D18 | City abrupt copies: change at replay start + 400 days (x1.6 commute hours). | Fixed before the run. **Disclosure:** for Chicago/NYC this is 2020-02-05, just before COVID-19, so those copies are confounded; only the paired cost of the change is interpreted there. |
| D20 | **NYC 2018 double count** (fixed; NYC re-run), found after the clean run from an anomalous calibration-year reference (MAE 2,451 vs 668 in 2019; reference 0.902 vs Chicago 0.213). Build log: 2018 zip 36,404,221 rows. `inspect_archive.py`: whole-month CSVs (quoted) + the same months as 1M-row parts in month folders (unquoted) + an extra April copy = 2 x 17,548,339 + 1,307,543. | The parser now drops trips repeated across files of one archive, matched on ride id or (start, end, bike); verified byte-identical on all 91 DC archives. Rebuild NYC, re-run the NYC jobs from a tag whose only change vs `clean-test-v1` is the data fix; first NYC results go to `reports/superseded/`. Policy code and thresholds unchanged. The build checks (unparsed rows, peak hours) could not catch duplication, so a yearly-total check is added. |
| D21 | `build-city` summary printed rows *read* as `trips=`; it now prints counted trips, rows read and repeats removed. | The misleading label hid the dedupe effect in the first rebuild log. |
| D19 | Reporting changes made after the clean run: Pareto chart label placement and off-scale markers, forest plot, scenario counts (n) in mean tables, matched ablation means, `scripts/export_decisions.py`. | The first summary averaged ablation variants over 4 scenarios and main policies over 7, which made e.g. no-warmstart look better than ADWIN. Reporting only: regenerated `results.csv` and `significance.csv` are identical. |

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
- [x] Tests: 55 passed (59 after the trip-parser tests).
- [x] Big PC: `calibrate-extra` (dev only, 7.1 min): probe (14 d, 120 d), Page-Hinkley 20, KSWIN alpha 1e-4 -> tag `clean-test-v1`.
- [x] Big PC: clean multi-city test, 230 runs in 58 min, 0 failures; `environment.json` = tag `clean-test-v1`.
- [x] Report regenerated on the laptop with the D19 reporting fixes (44 s, results identical); figures checked visually.
- [x] Docs from executed results: EVALUATION (clean-test section, final answer), PAPER (v0.2, all results filled), METHOD, README, PRESENTATION_OUTLINE, VIVA_PREP.
- [x] Big PC: decision logs exported (`reports/multicity/decisions/`); Chicago mechanism quantified (reference 1.074 = 5x).
- [x] NYC 2018 double count diagnosed (`memory/logs/inspect_nyc_2018.txt`) and fixed in the parser; DC regression identical; 59 tests.
- [x] Big PC step E: NYC rebuilt (18,855,882 repeats removed, no yearly-jump warning), 26 NYC jobs re-run from `clean-test-v1.1` (12.9 min, 0 failures); first NYC results in `reports/superseded/`; all docs updated.
- [x] Big PC step F: Chicago, SF and DC rebuilt with the fixed parser: 0 repeats, identical trip totals, no yearly-jump warning (0.8 min).
- [x] Related work surveyed and positioned (PAPER section 2: Cara, Regol et al. ICML 2025, Casimiro et al. TAAS 2024, Zliobaite et al. 2015, MAPE-K); references checked online (Cara volume/DOI and KSWIN volume/pages still to confirm).
- [x] Cost model (`amm cost-model`, reporting only): probe cheapest for a cycle price of 1.4-14 days of forecast error on the clean streams; test added (60 tests).
- [ ] Slides; dashboard visual check.

## Key results

**Clean test (confirmatory; docs/EVALUATION.md)**
- Drift-detector triggers (ADWIN / Page-Hinkley / KSWIN) were 25-30 % worse than periodic-28 on
  average, and worse on every system.
  - Chicago (65-95 %): reference inflation, a COVID-onset model with a 5x reference and 17
    alarms dismissed over 3 years.
  - New York, SF, DC 2025 (5-14 %): missed improvement, i.e. fewer and later updates.
- Probe: -0.1 % vs periodic-28 (no significant difference on any of 7 clean streams), 40 % fewer
  full cycles, 15-18 % less compute, and 0 cycles on stationary streams. ADWIN+bias: +0.5 %, 19 %
  fewer cycles.
- Periodic-14 was the most accurate on every stream: -4.5 % vs periodic-28 at 1.71x compute.
- New York numbers come from the re-run after the 2018 dedupe fix (D20).
- The oracle (3 retrains timed at the change) was worse than static in all cities.

**DC 2018-2024 (exploratory)**
- Periodic-28 81.5 (91 cycles), adaptive 114.7 (22), probe 82.2 (50), static 136.6.

## Next steps (resume here)

All experiments are complete and verified; no big-PC run is pending.

1. Slides from docs/PRESENTATION_OUTLINE.md with `reports/multicity/fig_pareto_clean.png`,
   `fig_forest_clean.png`, `fig_cost_regret.png` and the rolling charts.
2. Journal-version items (PAPER section 8): Cara / Regol et al. baselines adapted to regression,
   online learners, a non-bike domain, an expensive-retraining setting, sensitivity runs.
3. Optional: visual dashboard check (big PC, or the laptop with other apps closed).
