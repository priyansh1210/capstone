# Proposed method: opportunity-aware retraining ("probe")

## Motivation (from the decision logs of the frozen DC benchmark)

A deterioration trigger asks *"has my error become worse than my own reference?"*. On the
2018-2024 DC replay this failed in two ways:

1. **Reference inflation under shocks.** A model accepted during the COVID-19 collapse had its
   reference rebased to ~4x the normal error level; for 2.5 years every alarm was dismissed
   while it under-predicted demand by up to 60 %.
2. **Blindness to attainable improvement.** After a change, the first accepted model is usually
   only a partial adaptation. Its error is compared with its own (already elevated) reference,
   so no further update is requested even though fresher data would allow a much better model.

Both failures come from the self-referential question. The probe policy asks a different one.

## The question: *can a better model be trained right now?*

Every `interval_batches` days (7 or 14, calibrated) - and earlier when the drift detector reports
an increase in error (`accelerate`, at least `min_gap_batches` = 3 days apart) - the supervisor:

1. takes the **newest eligible labelled days** (the same 14-day validation window as the full
   retraining gate: strictly after everything the current model was fitted or selected on);
2. fits **one cheap challenger** (HistGradientBoosting, 80 iterations, learning rate 0.15) on a
   trailing window of `window_days` (120 or 365, calibrated) that ends **before** those days
   (outage hours excluded);
3. computes the challenger's and the current model's **daily MAE** on the held-out days;
4. requests a full retraining cycle only if the challenger is better by at least `min_gain`
   (5 %) **and** a one-sided paired t-test over the daily MAE differences gives p <= `alpha` (0.10).

The full cycle is unchanged from the other policies: 6 candidates (Ridge, RF, HGB x 365/730-day
windows), the 5 % validation gate on the same held-out days, atomic promotion, 14-day paired
probation with rollback. Cooldown (14 days) and the budget apply as before.

## Why this fixes both failure modes

* There is **no self-reference** to inflate: each decision compares two models on the same
  recent days, so a shock affects both sides of the comparison.
* An attainable improvement is visible **whether or not error has risen**: if fresher data
  allows a better model, the cheap challenger already shows it.
* Drift detection is kept, but only to **probe sooner**, never as the gate to action.

## Cost

A probe is one small fit (fractions of a second) plus two predictions on 336 hours. The cost of
the policy is measured as *training + probe seconds* and reported next to error in every table
and in the Pareto charts.

## Relation to the other policies

| Policy | Asks | Acts when |
|---|---|---|
| static | never | - |
| periodic-N | every N days | always attempts (gate decides) |
| adaptive (ADWIN / Page-Hinkley / KSWIN) | after a detected error increase | deterioration vs own reference confirmed |
| adaptive+bias | also on persistent total-demand bias | as above, or bias >= 15 % confirmed |
| **probe** | every 7-14 days, sooner on drift | a cheap challenger is significantly better on held-out days |
| oracle (reference only) | at the known change + 15/45/90 days | always attempts |

All share the same candidate training, validation gate, probation/rollback and budget.

## Ablations

`probe-no-accel` (no drift acceleration), `probe-no-test` (gain threshold only, no significance
test), `probe-no-probation` (promote without the paired observation period), plus
`adaptive-no-seasonal` and `adaptive-no-warmstart` for the detector-side design choices.

## Calibration and clean test

Probe interval/window and the Page-Hinkley/KSWIN thresholds are chosen by `amm calibrate-extra`
on the development scenarios only (DC 2016-17 replay + synthetic dev seeds), with the same rule as
all other settings. The code is then frozen with a git tag and evaluated once on Chicago, San
Francisco, New York and DC 2025 - data that no design decision has seen.
