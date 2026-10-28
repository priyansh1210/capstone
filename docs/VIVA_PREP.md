# Viva preparation

Short, defensible answers. Numbers refer to executed runs in `reports/` (see EVALUATION.md).

## 1. What is the contribution?

1. **A complete, inspectable supervisor** around a deployed demand model (detect -> confirm ->
   gate -> train -> validate -> promote -> probation -> keep/rollback), with leakage-safe
   streaming evaluation on 377 M real trips from four bike-share systems.
2. **A diagnosis, from decision logs, of why drift-detector triggers fail** on long real
   streams: reference inflation under shocks, and blindness to attainable improvement. Both
   replicate on three held-out systems.
3. **A simple trigger that fixes both: probe.** It asks "can a better model be trained now?"
   instead of "has my error worsened?".
4. **A pre-registered clean test** (frozen git tag, new cities). Probe matches a 28-day
   schedule with 39 % fewer full cycles, and never retrains on stationary data. It does **not**
   beat a 14-day schedule on accuracy, and we report that.

Every building block is an established method (ADWIN, chronological validation,
champion/challenger, paired tests); the novelty is the trigger and the evidence.

## 2. Algorithms

**ADWIN** (Bifet & Gavalda 2007, River 0.26.1 `drift.ADWIN`). Keeps a variable-length window
of recent values in exponential buckets; whenever some split into "old" and "new" sub-windows
has means differing by more than a Hoeffding/Bernstein-style bound (confidence `delta`), the
old part is dropped and a change is reported. We check every 24 values (`clock=24`, one day).
It detects changes in the *mean* of whatever it is fed, in either direction.

**What we feed it.** One value per revealed hour: `min(|log1p(y) - log1p(yhat)|, 3) / s(month)`.
- log scale: a 20 % miss at 1,000 trips counts like a 20 % miss at 100 (demand tripled 2011->2024);
- cap 3: one closed-system hour cannot dominate;
- `s(month)`: monthly difficulty index estimated once on calibration data (Dec/Jan ~1.2-1.4x,
  summer ~0.8x) - without it the policy "detected" winter;
- outage hours (>= 6 zero-trip hours in revealed labels) are excluded.
ADWIN is warm-started with the active model's reference-window values, so it compares live
error with the evidence the model was accepted on.

**Why not act on ADWIN alone?** A detection is only "the mean changed". The controller
(1) ignores decreases, (2) checks *deterioration*: the 14-day median of daily mean signal must
exceed the model's reference by >= `rel_margin` (calibrated) and +0.02 absolute, (3) on three
consecutive daily checks. Otherwise the alarm is dismissed with the measurements logged.

**Explanations keep three things apart:** input shift (z-score of recent weather means vs
training rows from the same months - no labels needed), relationship/level evidence (residual
bias of revealed labels: over/under-prediction), and observed performance (error vs reference).
None proves a cause.

**Probe (proposed trigger, docs/METHOD.md).**
- *When:* every 14 days (calibrated on dev), or sooner after an ADWIN increase (probes at
  least 3 days apart).
- *What it fits:* one HGB challenger (80 iterations, lr 0.15) on the 120 days (calibrated)
  that end before the newest 14 eligible days, outage hours excluded.
- *How it decides:* it compares the challenger's and the current model's daily MAE on those 14
  days, and requests a full cycle if the gain is >= 5 % *and* a one-sided paired t-test over
  the 14 daily differences gives p <= 0.10.
- *Cost:* about 0.45 s per probe against about 5.3 s per full cycle.
- *Why it is robust:* both models are scored on the same recent days, so a shock hurts both
  sides and there is no reference to inflate.

**Candidates.** Ridge (one-hot hour x day-type, month, weekday, weathersit; scaled numerics),
RandomForest (80 trees, leaf 4, 60 % features, 2 jobs), HistGradientBoosting (250 iterations,
lr 0.06, 31 leaves, categorical hour/weekday/season). All predict log1p(count), are full
pipelines (imputation fitted on the training window), and are fitted on each of the
calibrated trailing windows -> 6 fits per cycle, seeded, 2 threads.

## 3. Leakage prevention (what, where, test)

| Risk | Control | Test |
|---|---|---|
| target in inputs | fixed feature list; `member`/`casual`/`electric`/`instant`/outage flag excluded | `test_leakage.py` |
| future weather | observation of hour H-1 for target hour H, forward fill <= 3 h | `test_weather_is_lagged_and_never_backfilled` |
| random split | chronological partitions; overlap raises | `test_partitions.py` |
| preprocessing on future rows | imputer/scaler inside each pipeline, fitted on its window | `test_preprocessing_is_fitted_on_training_rows_only` |
| unrevealed labels | simulator pushes labels into a view only at reveal step | `test_label_delay.py` |
| validating on fitted rows | validation = newest labels after the current model's fit **and selection** cutoff; candidates end before validation | `test_retraining_windows_precede_validation_and_follow_cutoff` |
| re-scoring with newer models | stored prediction + version scored once | `test_predictions_are_stored_with_original_version...` |
| scenario truth | no manifest/scenario reachable from the controller; altered manifest -> identical decisions | `test_truth_hidden.py` |
| tuning on test | thresholds, windows, interval calibrated on 2016-17 dev replay + dev seeds, frozen | `configs/frozen_policy.yaml` provenance |

Honest caveat: two *design* changes (seasonal index, ADWIN warm start) were made after looking
at 2018-19 debugging runs of the evaluation stream, before the dev harness existed. All numeric
values were then chosen on dev data only. This is disclosed in EVALUATION.md.

## 4. Retraining policy and gates

Trigger (only difference between policies): static never; periodic every N days (N calibrated);
adaptive = confirmed deterioration, or persistence after a rejected update; probe = a cheap
challenger significantly better on the newest held-out days. Shared gates:
budget (cycles/run), one job at a time, cooldown 14 days between cycle starts (restarted at
rollback), enough eligible labels (>= 240 validation hours after the cutoff, >= 720 training
hours) - otherwise WAIT with the reason. The periodic baseline uses the **same** validation
gate, probation and rollback.

## 5. Validation gate

Current and candidates are scored on the *same* newest 14 days of eligible labels. A candidate
passes if its MAE is >= 5 % lower than the current model's; the best passing candidate is
promoted; otherwise the current model stays and every score is logged. Cost of this honesty:
right after an abrupt change the validation window is post-change while the training windows
are mostly pre-change, so the first attempt is often rejected - the persistence re-check retries
after the cooldown.

## 6. Promotion, probation, rollback

Promotion saves the artifact first (temp file + `os.replace`), then swaps (active, previous) in
one assignment; any failure leaves the current model serving (`test_failures.py`). For 14 days
both models predict each arriving batch before labels exist. Every 84 paired hours the MAEs on
the *same* hours are compared; rollback if the new model is >= 5 % worse in 2 consecutive
windows, keep after 4 windows otherwise. Because it is paired, a demand shock that hurts both
models does not cause rollback (`test_shared_error_increase_does_not_cause_rollback`).
Rollback restores the previous model's original reference and restarts the cooldown. Error
increases detected *during* probation are deferred and investigated afterwards (cleared on rollback).

## 7. Baselines and fairness

Same initial model (trained once, deep-copied), same observations, label delay, history,
candidate procedure, gate, probation, budget. Each policy has its own simulator, view,
controller, monitor, registry and database rows; `test_isolation.py` checks object identity and
that running alongside other policies does not change a policy's predictions.

## 8. Limits of the evidence

- **One task family:** system-level hourly demand. Four systems are a small sample of real
  histories, and the thresholds were tuned on DC only (transfer is exactly what the clean test
  measured).
- **Injected-change confound:** the abrupt change starts 400 days into each replay. In Chicago
  and New York that is 2020-02-05, just before COVID-19, so those copies mix the injected and
  the real change. Only the paired cost of the change is interpreted there.
- **Cheap retraining:** a cycle costs about 5 s, so compute differences are small in absolute
  terms. A setting with expensive cycles or human sign-off is untested.
- **The seasonal index** assumes a stable difficulty pattern (checked pre-COVID: r = 0.83-0.89).
  The ablation shows it matters: without it, the ADWIN trigger is 23 % worse.
- **No refit:** the validated artifact is deployed without refitting on the validation window
  (simpler, auditable; costs 14 days of recency).
- **Observed weather:** airport observations, not forecasts.
- **DC 2018-24 is exploratory:** four design decisions saw those years (EVALUATION.md). The
  clean test is the confirmatory evidence.

## 9. Results you must be able to defend (clean test: `reports/multicity`, tag `clean-test-v1`)

- **Does your method win?**
  - Against drift-detector triggers, yes: probe beat ADWIN on all 7 clean streams (DM
    p <= 0.016), and ADWIN / Page-Hinkley / KSWIN were 39-45 % worse than a 28-day schedule.
  - Against the schedule, it ties: within 0.5 % on average, no significant difference on any
    stream (95 % CIs about -12 % to +10 %), with 39 % fewer full cycles and about 10 % less
    compute.
  - Against a 14-day schedule, it loses: 4-5 % worse, which periodic-14 buys with 1.8x compute.
- **So why use it?**
  - It is the only policy that both matches the schedule on drifting real data and does not
    retrain on stationary data (0 vs 26 cycles).
  - 95 % of the full cycles it requests are promoted (schedule: 73 %).
  - Its value grows with the cost of a cycle. With cycles as cheap as here, a short schedule is
    a fine choice, and we say so.
- **Why did the detectors fail on new cities?** The same two mechanisms as in DC:
  - New York kept its 2019 model until 2023-01-18 (22 of 34 alarms dismissed) while demand
    outgrew it (actual/predicted 1.34 -> 1.86);
  - Chicago kept a model promoted during COVID (2020-04-06) for three years.
- **Is the oracle an upper bound?** No. With three retrains timed at the injected change it was
  worse than static in all three cities (it locked in COVID-onset models). Even on generated
  streams it reached only 56.5, against 50.0 for 8 untimed retrains. The gains come from
  repeatedly retraining on fresh data.
- **What do the ablations say?** The seasonal index matters (+23 % error without it). Warm start
  and probe acceleration did not matter on real streams. Dropping the significance test gave
  2.5 % lower error at 22 % more cycles (post-hoc observation, not confirmed). Probation cost
  1.4 % accuracy here; its value is protection against faulty candidates (fault-injection tests).
- **Is the evaluation clean?** Thresholds were calibrated on DC dev data only, the code was
  frozen at a git tag, and the run on new cities happened once. Changes made after the run touch
  reporting only (charts, tables, export script) and reproduce every number exactly.
- **Is it reproducible?** Two machines (Python 3.11 / 3.12), identical raw SHA-256 checksums,
  an identical replay (MAE 114.67, 22 cycles), and the report regenerated bit-identically.

### Earlier DC results (exploratory; `reports/benchmark`)

- **Did adaptive win?** No, not on real data: periodic-28d MAE 81.5, adaptive 114.7, static 136.6
  (2018-2024). It did win on *effort*: 22 vs 91 cycles, 70 s vs 361 s of training - and on the
  stationary stream it retrained 0.6x vs 26x at equal error (34.7 vs 34.8).
- **Why did it lose?** Decision log: v007 was promoted on 2020-03-29 during the COVID collapse;
  probation (also inside the shock) rebased its reference to 0.991 (~4x normal); threshold 1.139;
  ~15 alarms dismissed over 2.5 years; MAE 332 by Sep 2022. Plus: a deterioration trigger compares a
  model with *itself*, so it cannot notice that a better model is now attainable (partial adaptation).
- **Is the periodic baseline fair?** Same initial model, data, delays, candidate procedure, gate,
  probation, budget; interval calibrated on dev (28 d chosen over 14 d inside a 1 % tie band).
- **Detection delay?** Real abrupt change 15 days; synthetic abrupt 10-37 days (5/5); the 6-month
  ramp was not confirmed within 90 days; in the demo rehearsal ADWIN needed 65 days for a x1.6 change
  although the error was above the threshold after ~3 weeks - ADWIN gating is the bottleneck.
- **Recovery?** Reported with a counterfactual criterion, but not used for conclusions: static met it
  on real modified streams by coincidence (the change cancelled its existing bias).
- **What about the post-hoc variant?** Bias trigger b = 15 % chosen on dev data only (the cap had no
  effect on dev). Real replay MAE 84.5 with 63 cycles (vs 81.5 / 91 for periodic), stationary still
  0.6 cycles. It is exploratory because the idea came from evaluation data; the confirmatory test is a
  frozen run on 2025-26 Capital Bikeshare data or another city.
- **Is it reproducible?** Two machines (Python 3.11 / 3.12), identical raw SHA-256 (106/106), the
  laptop reproduced the big PC's adaptive run exactly (MAE 114.67, 22 cycles).
