# Evaluation

Research question: *Can selective, validated retraining maintain prediction quality while
reducing unnecessary retraining compared with a fixed schedule?*

## Protocol

1. **Initial model** (identical for all policies): HGB on all 2011-2016 training rows (outage
   hours removed), chosen by calibration-year MAE among Ridge/RF/HGB x {365, 730, all} days
   (`reports/model_selection.json`: HGB-all 82.7 trips/h vs best RF 90.0, best Ridge 96.2).
2. **Frozen policy settings** from development scenarios only (`python -m amm calibrate`,
   `configs/frozen_policy.yaml`, `reports/calibration/`): candidate windows, ADWIN delta,
   deterioration margin, periodic interval. Fixed a priori (not tuned): validation 14 days,
   5 % MAE gate, probation 4 x 84 h with a 5 % / 2-consecutive-window rollback rule,
   cooldown 14 days, budget 200 cycles (never binding for a calibrated schedule), 3 confirmations, label delay 1 day.
3. **Evaluation replay** 2018-01-01..2024-12-31, 2,557 daily batches, 61,361 hourly
   predictions per run, on five scenarios (generated ones with 5 seeds each). Every policy
   predicts every hour; all metrics are computed from the *stored* predictions after their
   labels arrived, so all policies are scored on exactly the same observations.

## Metrics and definitions

| Metric | Definition |
|---|---|
| Stream MAE / RMSE | over all 61,361 scored replay hours (generated: over the replay) |
| Post-change MAE | over hours at/after the hidden change start; also within the first 120 days |
| Retraining cycles | number of RETRAIN_START events (each = up to 6 candidate fits) |
| Candidate fits | individual pipeline fits, including failed ones |
| Training time | measured wall time of candidate fits (`time.perf_counter`), excludes replay overhead |
| Promotions / rejections / rollbacks | PROMOTED / CANDIDATES_REJECTED / ROLLED_BACK events |
| Detection delay | days from the hidden change start to the first DETERIORATION_CONFIRMED (adaptive); a change is **missed** if none occurs within 90 days. For periodic we report days to the first retraining attempt / promotion instead. |
| Unnecessary retraining | cycles on `synthetic_stationary`, where nothing changes by construction |
| Recovery time | first day after the change from which the 14-day rolling seasonally adjusted error stays within +10 % of its 28-day pre-change level for 14 consecutive days; reported as "not met" otherwise |

Alarms on the **unmodified real replay** are not counted as false positives: real demand did
change (growth, COVID-19, e-bikes). They are reported as alarms and judged by whether the
validated update improved error.

## Threats to validity

- **Development on early evaluation years.** Before the dev harness existed, debugging runs on
  2018-2019 of the evaluation stream revealed two design flaws (seasonal false alarms; ADWIN
  blind to a model that is degraded from day one). The fixes (seasonal difficulty index, ADWIN
  warm start) are design decisions, not tuned numbers; all numeric settings were then chosen
  on dev data only. Still, 2018-2019 results are not fully untouched.
- **Single real stream.** The real replay is one history; its variability is not sampled.
  Seeds vary only the generated scenarios.
- **Injected change family.** Abrupt/gradual changes are multiplicative demand changes in
  commute hours; detection results do not automatically transfer to other change types.
- **Seasonal-index assumption.** Estimated from 2017 calibration errors of the initial model;
  the pattern correlates 0.83-0.89 with 2018-2019 errors of other models, less in 2022-2023.
- **No refit after validation.** Deploying the validated artifact keeps the evaluation honest
  but leaves 14 days of the most recent data unused by each promoted model.

## Results

See the generated `reports/benchmark/summary.md`, `results.csv` and charts; the narrative
interpretation is below.

(RESULTS_PLACEHOLDER)
