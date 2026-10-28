# Presentation outline (12-15 minutes + live demo)

1. **Problem (1 min).** Deployed models silently degrade when the world changes. Retraining on
   a fixed schedule wastes compute and can even make things worse; never retraining fails
   when demand shifts. Question: can *selective, validated* retraining keep quality while
   reducing unnecessary retraining?

2. **Application and data (2 min).** Hourly demand for Capital Bikeshare (Washington DC).
   44.97 M trips -> 122,722 hourly rows, 2011-2024, + NOAA hourly weather at DCA.
   Real drift: growth, COVID-19 (2020: mean 252 trips/h vs 388 in 2019), e-bike era
   (2024: 696 trips/h). Same upstream source as UCI Bike Sharing; our aggregation matches all
   17,379 UCI hours (totals within 1.1 %). Chart: yearly demand / `fig_yearly_bike_unmodified.png`.

3. **What "autonomous" means here (2 min).** State machine: serve -> investigate -> wait ->
   retrain -> validate -> promote -> probation -> keep / roll back. Every decision logged with
   measurements and thresholds. Diagram from ARCHITECTURE.md.

4. **Architecture and leakage boundaries (2 min).** Simulator holds the truth; the controller
   only sees a view of observed covariates and revealed labels (1-day delay). Stored predictions
   scored once; validation strictly after the current model's cutoff; manifests never reach the
   controller. 46 tests cover each boundary.

5. **Detection that is not fooled by seasons (1.5 min).** ADWIN on a log-scale error divided
   by a calibration-estimated monthly difficulty index; warm start; confirmation of sustained
   deterioration (14-day daily median, 3 checks). Show one DETERIORATION_CONFIRMED explanation.

6. **Experiments (1.5 min).** Static vs periodic vs adaptive with identical initial model,
   data, delays, candidate procedure, gate, probation and budget; only the trigger differs.
   Scenarios: unmodified replay, abrupt and gradual injected changes, stationary synthetic
   (5 seeds), synthetic abrupt (5 seeds). Thresholds frozen from 2016-17 dev scenarios.

7. **Results (3 min)** - `fig_tradeoff.png`, `fig_rolling_bike_unmodified.png`, EVALUATION.md tables.
   - Stationary stream: adaptive 0.6 cycles/run vs periodic 26 at equal MAE (34.7 vs 34.8) -
     unnecessary retraining essentially eliminated.
   - Real 2018-2024: periodic-28d MAE **81.5**, adaptive 114.7, static 136.6. Adaptive recovered 40 %
     of the schedule's gain with 24 % of the cycles - and was worse than static in 2021-22.
   - Abrupt change detected in 15 days (real) / 10-37 days (synthetic, 5/5); 6-month ramp not
     confirmed within 90 days. Gate and probation worked: organic rollbacks (10 periodic, 3 adaptive).

7b. **Failure analysis (2 min) - the most interesting slide.** Decision log: a model promoted on
   2020-03-29 passed probation *during* the COVID collapse, its reference was rebased to ~4x normal,
   and 15 alarms over 2.5 years were dismissed while it under-predicted demand by 60 % (MAE 332).
   Second lesson: a deterioration trigger cannot see that a *better* model has become attainable.
   Post-hoc, exploratory bias trigger (chosen on dev data): MAE 84.5 with 31 % fewer cycles than the
   schedule, still 0.6 cycles on stationary data (`reports/posthoc/fig_tradeoff_posthoc.png`) - to be
   confirmed on untouched 2025-26 data.

8. **Live demo (5 min).** docs/DEMO_SCRIPT.md.

9. **Limitations (1 min).** One real stream (no repeated real trials); injected change family;
   seasonal-index assumption; four design changes informed by evaluation data (disclosed);
   validation lag after abrupt changes; ADWIN gating slow for moderate partial-hour changes.

10. **Future work (0.5 min).** Confirm the post-hoc variant on untouched 2025-26 data / other cities;
    a daily control-chart deterioration check alongside ADWIN; cost-aware trigger (expected benefit
    vs training cost); refit-after-validation; forecast weather; station-level demand.
