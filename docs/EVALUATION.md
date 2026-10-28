# Evaluation

Research question: *Can selective, validated retraining maintain prediction quality while
reducing unnecessary retraining compared with a fixed schedule?*

The evaluation ran in three stages. Only the last one is a clean test:

1. **DC 2018-2024, first frozen protocol** (static / periodic / ADWIN-adaptive). Four design
   decisions were later informed by these years, so this stage is now **exploratory**.
2. **Post-hoc analysis** of stage 1 (bias trigger): exploratory by construction.
3. **Clean multi-city test** (confirmatory, primary): code and thresholds frozen at git tag
   `clean-test-v1`, run once on Chicago, New York, SF Bay Area and DC 2025 (New York re-run
   once after a data correction, with the same frozen code). See
   [Clean multi-city test](#clean-multi-city-test-confirmatory-primary) and the
   [final answer](#answer-to-the-research-question-after-the-clean-test).

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
- **Clean test, injected change date (found after the run).** The injected abrupt change starts
  400 days after each replay start (fixed before the run, without checking the calendar). For
  Chicago and New York that is 2020-02-05, a few weeks before the COVID-19 collapse, so their
  "abrupt" copies mix the injected change with the real shock. Detection-delay and recovery metrics
  are therefore not reported for the city abrupt streams; the paired cost of the change
  (MAE of the abrupt copy minus MAE of its unmodified twin, same policy) is still valid.
- **Clean test, reporting changes after the run.** After the frozen run, only reporting code
  changed: the Pareto chart layout, a new forest plot, scenario counts in the mean tables,
  matched means for the ablations, and a decision-log export script. Regenerating the report
  reproduced every run result and every CI exactly (`results.csv` and `significance.csv` are
  bit-identical, apart from about 1e-15 in the DM statistic).
- **Clean test, data correction.** The NYC 2018 archive was counted 2.07x in the first build.
  This was found from an implausible calibration-year reference in the results. NYC was
  rebuilt and its 26 jobs re-run with the frozen policy code; details are in the clean-test
  section, and the first NYC results are in `reports/superseded/`.
- **Cheap retraining.** A full cycle costs about 5 s here, and one probe about 0.45 s (9 % of a
  cycle), so compute differences between policies are seconds to minutes over six years. The
  number of full cycles (and promotions to review) is reported separately because it, not
  CPU time, dominates when retraining is expensive.

## Results on DC 2018-2024 (first frozen protocol; exploratory, see stage 1 above)

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
change, see threats to validity), so these numbers are not a clean test. It was then frozen
and tested on new data in the clean multi-city test below.

## Clean multi-city test (confirmatory, primary)

**Protocol.**
- **Frozen code:** every threshold was fixed at git tag `clean-test-v1` (commit 6b63a9b,
  recorded in `reports/multicity/environment.json`). The probe interval and window and the
  Page-Hinkley/KSWIN thresholds were chosen on the DC development scenarios only
  (`amm calibrate-extra`: probe every 14 days on a 120-day window; Page-Hinkley threshold 20;
  KSWIN alpha 0.0001).
- **New data, never used for any design decision:**
  - Chicago (Divvy), replay 2019-2024;
  - New York (Citi Bike), replay 2019-2024;
  - SF Bay Area (Bay Wheels), replay 2020-2024;
  - DC 2025-01-01..2025-08-26.
- **Injected changes:** each city replay also ran as a copy with an injected abrupt change
  (x1.6 in commute hours on working days, starting 400 days into the replay).
- **Initial model:** HGB on each city's training years, fitted with the same rule as for DC.
- **Execution:** 230 runs (including the DC exploratory and generated groups) in 58 min on the
  big PC, 0 failed jobs. The 26 New York runs were then repeated after a data correction (box
  below).
- **Outputs:** `reports/multicity/` (summary.md, cities.csv, significance.csv,
  ablations.csv, daily series, decision logs, figures).

> **Data correction: New York re-run (2026-10-28).**
> - **The problem:** after the run, the NYC initial model showed an implausible
>   calibration-year reference (MAE 2,451 trips/h against 668 when replayed on 2019; reference
>   error 0.90 against Chicago's 0.21).
> - **The cause:** the Citi Bike 2018 archive holds every month as a whole-month CSV *and* as
>   split parts in month folders, plus an extra copy of April. The parser counted 36,404,221
>   rows for 17,548,339 unique trips (docs/DATASET.md). 2018 is NYC's calibration year, so the
>   doubled data also entered the NYC seasonal index and the 2019-20 retraining windows.
> - **The fix:** the parser now drops trips repeated across files of one archive. It is
>   verified byte-identical on all 91 DC archives, and a new build check flags such jumps.
> - **The re-run:** NYC was rebuilt and its 26 jobs re-run from tag `clean-test-v1.1`, whose
>   policy, config, scenario and runner code is byte-identical to `clean-test-v1`.
>   `environment.json` records the re-run, and the first NYC results are kept in
>   `reports/superseded/multicity-city_nyc_*`.
> - **Effect:** the NYC reference became 0.246. The NYC detector-trigger MAEs fell by 34-40 %,
>   and every other NYC policy changed by 1-5 %. Chicago, SF and DC 2025 are untouched.
> - **Compute:** NYC compute times were measured in the re-run, so ratios are compared within a
>   city.

**Table C1 - unmodified clean streams: MAE in trips/h (full retraining cycles).** "vs p28" is
the mean over the four systems of each policy's MAE relative to the calibrated 28-day schedule.

| Policy | Chicago 2019-24 | New York 2019-24 | SF Bay Area 2020-24 | DC 2025 (Jan-Aug) | mean MAE vs p28 | mean compute vs p28 | full cycles (sum) |
|---|---|---|---|---|---|---|---|
| static | 211.0 (0) | 1629.1 (0) | 132.2 (0) | 339.1 (0) | +122.9% | 0.00x | 0 |
| periodic 14 d | **112.3** (140) | **578.0** (136) | **66.4** (112) | **128.3** (14) | **-4.5%** | 1.71x | 402 |
| periodic 28 d (calibrated) | 117.5 (78) | 602.1 (78) | 69.6 (65) | 134.9 (8) | +0.0% | 1.00x | 229 |
| periodic 56 d | 126.6 (39) | 656.3 (39) | 80.8 (32) | 162.5 (4) | +13.4% | 0.55x | 114 |
| periodic 91 d | 150.5 (24) | 743.2 (24) | 82.8 (20) | 207.9 (2) | +31.2% | 0.33x | 70 |
| ADWIN trigger | 194.3 (12) | 670.6 (30) | 78.1 (21) | 147.6 (4) | +24.6% | 0.38x | 67 |
| Page-Hinkley trigger | 227.6 (12) | 683.3 (36) | 75.1 (33) | 142.2 (4) | +30.2% | 0.46x | 85 |
| KSWIN trigger | 228.7 (9) | 632.9 (56) | 76.3 (26) | 147.4 (5) | +29.7% | 0.49x | 96 |
| ADWIN+bias trigger | 117.2 (60) | 614.5 (65) | 67.1 (55) | 140.0 (6) | +0.5% | 0.88x | 186 |
| **probe (proposed)** | 118.0 (35) | 607.7 (46) | 70.5 (51) | 130.7 (5) | **-0.1%** | **0.85x** | 137 |

**Table C2 - paired tests on all 7 clean streams** (daily MAE, A - B, as % of B;
moving-block bootstrap 95 % CI, 28-day blocks; Diebold-Mariano with Newey-West lag 7).

| A vs B | A lower | CI excludes 0 | DM p < 0.05 | range of differences |
|---|---|---|---|---|
| probe vs periodic-28 | 2 / 7 | **0 / 7** | 0 / 7 (smallest p 0.371) | -3.1 % .. +1.3 % |
| probe vs ADWIN | **7 / 7** | 5 / 7 (SF: upper ends +0.7 %, +0.2 %) | **7 / 7** | -42.9 % .. -7.6 % |
| probe vs periodic-14 | 0 / 7 | 4 / 7, all worse | 6 / 7, all worse | +1.8 % .. +7.1 % |
| ADWIN+bias vs periodic-28 | 4 / 7 | 0 / 7 | 0 / 7 (smallest p 0.074) | -3.6 % .. +3.8 % |

Figures: `fig_pareto_clean.png` (error vs compute), `fig_forest_clean.png` (the CIs above),
`fig_rolling_city_*.png` (28-day rolling MAE).

**Table C3 - injected abrupt copies: MAE, and cost of the change** (MAE of the abrupt copy
minus MAE of its unmodified twin under the same policy).

| Policy | Chicago MAE | cost | New York MAE | cost | SF MAE | cost | mean vs p28 |
|---|---|---|---|---|---|---|---|
| static | 297.5 | +86.5 | 2225.3 | +596.2 | 171.7 | +39.5 | +141.3% |
| periodic 14 d | **132.1** | +19.8 | **721.5** | +143.5 | **76.4** | +10.0 | **-4.8%** |
| periodic 28 d | 140.2 | +22.7 | 744.0 | +142.0 | 80.8 | +11.2 | +0.0% |
| periodic 56 d | 149.3 | +22.7 | 817.2 | +161.0 | 93.6 | +12.8 | +10.7% |
| periodic 91 d | 165.3 | +14.8 | 885.5 | +142.4 | 94.1 | +11.3 | +17.8% |
| ADWIN trigger | 247.7 | +53.4 | 902.8 | +232.1 | 86.0 | +7.9 | +34.8% |
| Page-Hinkley trigger | 152.2 | -75.5 | 815.7 | +132.4 | 87.8 | +12.6 | +8.9% |
| KSWIN trigger | 237.7 | +9.0 | 822.6 | +189.7 | 89.0 | +12.6 | +30.1% |
| ADWIN+bias trigger | 136.0 | +18.7 | 761.2 | +146.7 | 78.0 | +11.0 | -1.4% |
| **probe (proposed)** | 141.4 | +23.4 | 745.0 | +137.4 | 79.4 | +9.0 | -0.2% |
| oracle (3 retrains timed at the change) | 411.2 | - | 2400.0 | - | 188.6 | - | +183.1% |

The Page-Hinkley cost in Chicago is negative: the injected change set off more retraining
(27 vs 12 cycles), which also reduced the error from the real changes. The detector-triggered
costs vary in sign and size for this reason.

**Table C4 - ablations on the four unmodified clean streams** (each variant against its parent
on the same streams; `reports/multicity/summary.md`, "Matched means").

| Variant | vs parent | vs periodic-28 | cycles (mean) | compute vs p28 |
|---|---|---|---|---|
| probe without drift acceleration | +0.3 % | +0.2 % | 35.0 | 0.80x |
| probe without the significance test (gain >= 5 % only) | **-1.9 %** | -2.0 % | 42.5 | 1.02x |
| probe without probation/rollback | +0.1 % | -0.1 % | 37.0 | 0.98x |
| ADWIN without the seasonal index | **+26.9 %** | +58.4 % | 14.0 | 0.25x |
| ADWIN without warm start | +3.3 % | +28.3 % | 14.8 | 0.41x |

**Generated streams (5 seeds; Table C5).**
- **Stationary:** probe started **0 cycles in 5/5 seeds**. Its probes cost 33.8 s, against
  154.9 s for periodic-28 (26 cycles) and 5-7 s for the detector triggers (0.6-0.8 cycles),
  all at equal MAE (34.6-34.8).
- **Abrupt:** probe reached 49.2 with 18.6 cycles, against 49.4 for periodic-28 (26 cycles),
  49.1 for periodic-14 (48.4 cycles), 57.5 for ADWIN and 59.2 for static. Its first retraining
  came 26.4 days after the change, on average, against 12 days for periodic-28.
- **Oracle:** with three retrains timed exactly at the change it reached only 56.5. Periodic-91,
  with 8 untimed retrains, reached 50.0.

### What the clean test says

1. **Deterioration triggers lose to the schedule on every held-out system.**
   - **Size of the gap:** ADWIN, Page-Hinkley and KSWIN triggers were worse than the 28-day
     schedule in all four systems, by 25-30 % on average (Table C1).
   - **Two patterns, one per failure mode.**
     - **New York, SF and DC 2025 (5-14 % worse):** the detectors kept retraining, but less
       often (NYC: 30-56 cycles vs 78; SF: 21-33 vs 65). Each update was triggered only by
       error rising above the model's own reference, never by an improvement that had become
       possible. This is failure mode 2.
     - **Chicago (65-95 % worse):** the reference inflation seen in DC recurred (decision log in
       `reports/multicity/decisions/`). Model v006 (ridge) was validated on 2020-03-23..04-05,
       the COVID-19 onset, and promoted on 2020-04-06. Its reference was rebased to **1.074, 5x
       the initial model's 0.213**, which put the deterioration threshold at 1.235. All 17 ADWIN
       alarms of the next three years were dismissed (recent errors 0.26-1.15) until 2023-04-29,
       while the model's daily log error rose from 0.47 to 0.96. This is failure mode 1, the DC
       mechanism (0.991, about 4x), on data never used for design.
2. **The fix derived from the DC diagnosis transfers, and so does the post-hoc bias trigger.**
   - **Accuracy:** probe (-0.1 %) and ADWIN+bias (+0.5 %) were within 1 % of the 28-day schedule
     on average. Neither differed significantly from it on any of the 7 clean streams (Table C2,
     Figure `fig_forest_clean.png`).
   - **Against the detectors:** probe beat the ADWIN trigger on all 7 streams (DM p <= 0.016).
   - **Cycles and compute:** probe needed **40 % fewer full retraining cycles** than
     periodic-28 (271 vs 450 across the 7 streams) and 15-18 % less compute (0.85x on the
     unmodified streams, 0.82x over all 7). ADWIN+bias needed 19 %
     fewer cycles.
   - **Gate outcomes:** **96 % of probe-requested cycles were promoted** and 83 % survived
     probation. For periodic-28 the figures were 72 % and 60 %, and for the ADWIN trigger 83 %
     and 73 %. The cheap challenger is a good predictor of whether a full cycle will pass the
     gate.
3. **Neither triggered policy beats the schedule.**
   - A 14-day schedule was the most accurate policy on every clean stream: 4-5 % lower MAE than
     periodic-28 at 1.7x its compute.
   - Probe was significantly worse than periodic-14 on 4 of 7 streams by bootstrap CI, and on
     6 of 7 by DM test.
   - On the error-compute plane (unmodified streams) the triggered policies sit *on* the
     schedule's curve, not below it. Probe dominates periodic-28 in DC 2025 and ADWIN+bias in
     New York, is dominated in SF (by periodic-28 and ADWIN+bias), and is non-dominated in
     Chicago.
4. **What a trigger is for.** The probe matches a schedule when the world keeps changing, and
   it does not retrain when the world is stable (0 vs 26 cycles). No trigger in this study
   beats a frequent schedule on accuracy.
   - When retraining is as cheap as here, the practical recommendation is a short schedule.
   - When each cycle is expensive (large models, human sign-off per promotion), the probe's
     40 % fewer cycles at equal error is the relevant saving.
5. **Change-timed retraining is not an upper bound.** The oracle (three retrains at the
   injected change + 15/45/90 days) was worse than static on all three clean abrupt streams.
   - In Chicago and New York its three retrains fell in February-May 2020, so it then served a
     COVID-onset model until 2024 (Chicago MAE 530 vs static 384 in 2022).
   - On the generated streams, where there is no real shock, it still reached only 56.5 against
     50.0 for periodic-91. The value of retraining comes from repeatedly folding in post-change
     data. Reacting at the moment of change is not enough.
6. **Ablations.**
   - **Seasonal index:** removing it makes the ADWIN trigger 27 % worse, and worse on all four
     systems.
   - **ADWIN warm start:** without it, error was 14 % higher in New York, with no difference
     elsewhere (+3.3 % on average).
   - **Probe acceleration:** no measurable effect (+0.3 %).
   - **Significance test:** without it, probe was 1.9 % more accurate, and better than
     periodic-28 on all four systems, but needed 24 % more cycles. This is a post-hoc
     observation, not a confirmed result.
   - **Probation/rollback:** no net effect on accuracy (+0.1 %; between -4 % and +4 % per
     system). Its value is the protection against faulty candidates shown in the fault-injection
     tests, which did not occur in these replays.

## Answer to the research question (after the clean test)

*Yes for the probe policy, with a qualification.*
- **Quality maintained:** on four held-out bike-share systems, selective validated retraining
  with the probe trigger kept prediction quality at the level of the calibrated 28-day schedule
  (-0.1 %). The difference was not significant on any of 7 clean streams, and probe used 40 %
  fewer full retraining cycles.
- **No unnecessary retraining:** it never retrained when nothing changed.
- **Detectors do not do this:** the classical drift-detector triggers did not maintain quality
  (25-30 % worse on average, worse on every system).
- **The qualification:** no trigger was more accurate than retraining more often. A 14-day
  schedule was 4-5 % better at 1.7x compute.
