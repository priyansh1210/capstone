# Viva preparation

Short, defensible answers. Numbers refer to executed runs in `reports/` (see EVALUATION.md).

## 1. What is the contribution?

An engineering and evaluation contribution: a complete, inspectable supervisor around a
deployed demand model (detect -> confirm -> gate -> train -> validate -> promote -> probation ->
keep/rollback), with leakage-safe streaming evaluation on 14 years of real data. Every
building block is an established method (ADWIN, chronological validation, champion/challenger,
paired comparison). We do **not** claim a new drift detector or that our policy beats the
baselines everywhere; we report where it loses.

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
adaptive = confirmed deterioration, or persistence after a rejected update. Shared gates:
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
Rollback restores the previous model's original reference and restarts the cooldown.

## 7. Baselines and fairness

Same initial model (trained once, deep-copied), same observations, label delay, history,
candidate procedure, gate, probation, budget. Each policy has its own simulator, view,
controller, monitor, registry and database rows; `test_isolation.py` checks object identity and
that running alongside other policies does not change a policy's predictions.

## 8. Limits of the evidence

- One city, one operator; 7 replay years; one source of real drift per period, so no
  repeated real-world trials - variance only for generated scenarios (5 seeds).
- Injected changes are multiplicative demand shifts in fixed hours; other change types
  (new stations, pricing) are only present implicitly in the unmodified replay.
- The seasonal index assumes a stable difficulty pattern (checked pre-COVID: r = 0.83-0.89).
- Detection delay is measured only for injected changes; alarms on unmodified real data are not
  automatically false positives (real demand changed).
- The validated artifact is deployed without refitting on the validation window (simpler,
  auditable; costs 14 days of recency).
- Weather is airport observation, not a forecast; a production system would use forecasts.
- Development choices made while looking at early evaluation years (section 3 caveat).
