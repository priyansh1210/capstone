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

- **Development on evaluation data (four disclosed instances).** (1) seasonal difficulty index and
  (2) ADWIN warm start - found in debugging runs on 2018-2019 before the dev harness existed;
  (3) deferring alarms raised during probation - a logic bug found in the first smoke run (2018);
  calibration was re-run after it (`reports/superseded/`); (4) the post-hoc variant - designed after
  the frozen benchmark, reported separately as exploratory. All numeric settings were chosen on dev
  data only, but the evaluation years are not untouched; a clean test needs new data.
- **Single real stream.** The real replay is one history; its variability is not sampled.
  Seeds vary only the generated scenarios.
- **Injected change family.** Abrupt/gradual changes are multiplicative demand changes in
  commute hours; detection results do not automatically transfer to other change types.
- **Seasonal-index assumption.** Estimated from 2017 calibration errors of the initial model;
  the pattern correlates 0.83-0.89 with 2018-2019 errors of other models, less in 2022-2023.
- **No refit after validation.** Deploying the validated artifact keeps the evaluation honest
  but leaves 14 days of the most recent data unused by each promoted model.

## Results (frozen protocol - the primary, pre-specified evaluation)

Executed on the big PC (Core Ultra 9 285, 24 cores, 64 GB) with `amm benchmark --workers 12`:
39 runs in 660 s. Raw inputs byte-identical to the laptop (106/106 SHA-256 match); the laptop
re-ran the adaptive real-data run and reproduced it exactly (MAE 114.67, 22 cycles), so the
engine is deterministic across machines. Files: `reports/benchmark/` (summary.md, results.csv/json,
daily series, figures). MAE/RMSE in trips per hour; generated scenarios: mean over 5 seeds (sd).

| Scenario | Policy | MAE | RMSE | Cycles | Fits | Train s | Promoted / rejected / rolled back |
|---|---|---|---|---|---|---|---|
| **Real replay, unmodified** (source observations) | static | 136.6 | 228.9 | 0 | 0 | 0 | - |
| | periodic 28 d | **81.5** | **136.7** | 91 | 546 | 361 | 65 / 26 / 10 |
| | adaptive | 114.7 | 186.3 | 22 | 132 | 70 | 19 / 3 / 3 |
| **Real + abrupt change** (modified) | static | 184.0 | 353.4 | 0 | 0 | 0 | - |
| | periodic | **101.2** | **181.6** | 91 | 546 | 356 | 77 / 14 / 7 |
| | adaptive | 123.4 | 213.7 | 29 | 174 | 89 | 27 / 2 / 3 |
| **Real + gradual change** (modified) | static | 181.3 | 349.1 | 0 | 0 | 0 | - |
| | periodic | **101.6** | **180.9** | 91 | 546 | 359 | 77 / 14 / 8 |
| | adaptive | 116.2 | 201.3 | 29 | 174 | 90 | 27 / 2 / 1 |
| **Synthetic stationary** (generated, 5 seeds) | static | 34.7 (1.5) | 59.4 | 0 | 0 | 0 | - |
| | periodic | 34.8 (1.6) | 60.2 | 26 | 156 | 207 | 3.4 / 22.6 / 0.2 |
| | adaptive | **34.7 (1.5)** | 59.5 | **0.6** | 4 | 4.7 | 0.2 / 0.4 / 0 |
| **Synthetic abrupt** (generated, 5 seeds) | static | 59.2 (2.7) | 124.5 | 0 | 0 | 0 | - |
| | periodic | **49.4 (2.6)** | **99.4** | 26 | 156 | 190 | 13 / 13 / 1.2 |
| | adaptive | 57.5 (2.0) | 118.4 | 1.8 | 11 | 12 | 1.2 / 0.6 / 0.2 |

**MAE per year, real unmodified replay**

| | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|---|
| static | 82.0 | **59.0** | 147.6 | 107.1 | 89.8 | 150.2 | 319.8 |
| periodic | **67.9** | 64.1 | **74.8** | **78.1** | **72.0** | **92.6** | **121.2** |
| adaptive | 72.5 | 72.4 | 113.3 | 126.2 | 180.6 | 100.2 | 137.5 |

**Detection and adaptation after injected changes** (hidden change start; 90-day detection horizon)

| Scenario | Adaptive: first alarm / confirmed / first promotion | Excess log-error vs no-change, first 120 d (static / periodic / adaptive) | Recovery days (periodic / adaptive) |
|---|---|---|---|
| bike_abrupt (x1.6 commute hours from 2019-04-01) | 13 / **15** / 15 days | 42 % / 31 % / 31 % | 101 / 237 |
| bike_gradual (ramp 2019-03-01 .. 09-01) | **not confirmed within 90 days** (missed by definition) | 39 % / 22 % / 22 % (from ramp end) | 94 / 190 |
| synthetic_abrupt, 5 seeds | confirmed after 14, 28, 37, 10, 20 days (mean 21.8; 5/5) | 35 % / 35 % / 34 % | periodic 5/5 (mean 299); adaptive 0/5 |

### What the evidence says

1. **Unnecessary retraining is almost eliminated under stable conditions.** On the truly
   stationary stream the adaptive policy started 0.6 cycles per run (0.2 promotions) and spent
   4.7 s training; the 28-day schedule started 26 cycles and spent 207 s, its gate rejected 22.6
   of them, and its error was not better (MAE 34.8 vs 34.7, RMSE 60.2 vs 59.5).
2. **Under persistent real drift, the frozen adaptive policy did *not* maintain quality.** On the
   2018-2024 replay it reduced static's MAE by 16 % (136.6 -> 114.7), i.e. recovered 40 % of the
   improvement that the 28-day schedule achieved (136.6 -> 81.5), using 24 % of the cycles and 19 %
   of the training time. In 2021 and 2022 it was *worse than never retraining*.
3. **Why (from the decision log; the run was re-executed on the laptop to read it):** on 2020-03-29, in the middle
   of the COVID-19 collapse, adaptive promoted a ridge model trained on 2019-03..2020-03. Its whole
   14-day probation fell inside the shock, so rebasing its reference to the median of validation and
   live probation error set it to 0.991 - about four times the normal level (~0.21-0.25). The
   deterioration threshold became 1.139; the next ~15 ADWIN alarms over 2.5 years were all
   dismissed ("error 0.31-1.04 < threshold 1.139") while the pre-COVID model under-predicted demand
   by up to 60 % (MAE 332 by Sep 2022, then a single retrain brought it to 84). The rolling-error
   chart (`fig_rolling_bike_unmodified.png`) shows this bulge.
4. **A deterioration trigger cannot see an attainable improvement.** After an abrupt change the
   first successful update is usually only a *partial* adaptation (365/730-day windows contain few
   post-change days). Its error is then compared with its own, already elevated reference, so no
   further update is requested; the schedule keeps offering fresher challengers. Hence synthetic
   abrupt: adaptive never met the recovery criterion (0/5), periodic did (5/5, after ~300 days).
5. **Detection.** Abrupt changes were confirmed in 15 days (real) and 10-37 days (synthetic, 5/5).
   The 6-month gradual ramp was not confirmed within 90 days of its start. In the demo rehearsal
   (`scripts/rehearse_demo.py`) a x1.6 change injected on 2019-03-11 raised the 14-day error above
   the threshold within ~3 weeks, but ADWIN (delta 0.002, hourly signal) did not alarm for 65 days;
   the deterioration test only runs after an ADWIN alarm. ADWIN gating is the bottleneck for moderate
   changes that affect a minority of hours.
6. **The validation gate and probation did their job.** Every promotion beat the current model on
   held-out days by >= 5 %; rejections kept the current model; organic rollbacks happened
   (periodic 10, adaptive 3 on the real replay) when a validated model then lost on paired live hours.
   With 365/730-day windows both policies adapt slowly in the first 120 days (excess error similar).
7. **Recovery time is fragile.** Under the counterfactual criterion, *static* met it on both real
   modified streams (269 and 116 days) without ever adapting: when a model's pre-existing bias has the
   opposite sign to the injected change, the change can temporarily cancel it. Recovery days are
   therefore reported but not used for conclusions.
8. **2019 is the exception that shows the cost of retraining:** the 2011-2016 static model was the
   best of all policies in 2019 (59.0); models retrained on 2017-2018 windows generalised worse.

**Answer to the research question (frozen protocol):** *partially.* Selective, validated retraining
reduced unnecessary retraining dramatically when nothing changed (26 -> 0.6 cycles at equal error),
but under the persistent, multi-year real drift of 2018-2024 the frozen evidence-based policy did not
maintain the quality of a fixed 28-day schedule; its failure is traceable to one specific mechanism
(reference rebasing during a shock) plus the structural blindness of deterioration triggers to
attainable improvement.

## Post-hoc analysis (exploratory - designed after seeing the results above)

`amm posthoc` (12.2 min on the big PC) adds two options to the adaptive policy, both off in the
frozen configuration: a cap on the reference at k x the initial model's calibration error level,
and a **bias trigger** (|total-demand bias| over 14 days >= b on 3 consecutive daily checks requests
an update, through the same gates). k and b were chosen on the **development** scenarios with the
calibration rule: the cap had *no effect at all on dev* (no shock of that kind in 2016-17), so the
rule selected **b = 15 %, no cap** (dev MAE ratio 0.796 vs 0.830 for frozen adaptive; stationary
cycles unchanged at 0.67). That variant was then run once on the evaluation scenarios:

| Scenario | periodic | adaptive (frozen) | **adaptive+ (post-hoc)** |
|---|---|---|---|
| Real unmodified: MAE / cycles / train s | 81.5 / 91 / 361 | 114.7 / 22 / 70 | **84.5 / 63 / 220** |
| Real abrupt | 101.2 / 91 | 123.4 / 29 | 106.4 / 67 |
| Real gradual | 101.6 / 91 | 116.2 / 29 | **101.1 / 68** |
| Synthetic abrupt (5 seeds) | 49.4 / 26 | 57.5 / 1.8 | **49.2 / 18.8** (first response 10 d) |
| Synthetic stationary (5 seeds) | 34.8 / 26 | 34.7 / 0.6 | **34.7 / 0.6** |

Per year on the real replay, adaptive+ stays close to periodic (2020: 82.6 vs 74.8, 2021: 74.1 vs
78.1, 2022: 77.8 vs 72.0) instead of stalling. It closes 95 % of the static-to-periodic gap with 31 %
fewer cycles and 39 % less training time, and still does not retrain on stationary data
(`reports/posthoc/fig_tradeoff_posthoc.png`, `fig_rolling_bike_unmodified_posthoc.png`).

**Status:** exploratory. The idea came from the evaluation data (the fourth evaluation-informed
change, see threats to validity), so these numbers are not a clean test. Confirmation requires a
pre-registered run with frozen code on untouched data, e.g. Capital Bikeshare 2025-01..2026-09 or
another city (memory/PUBLICATION_ROADMAP.md, gap 1).
