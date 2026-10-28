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
   controller. 41 tests cover each boundary.

5. **Detection that is not fooled by seasons (1.5 min).** ADWIN on a log-scale error divided
   by a calibration-estimated monthly difficulty index; warm start; confirmation of sustained
   deterioration (14-day daily median, 3 checks). Show one DETERIORATION_CONFIRMED explanation.

6. **Experiments (1.5 min).** Static vs periodic vs adaptive with identical initial model,
   data, delays, candidate procedure, gate, probation and budget; only the trigger differs.
   Scenarios: unmodified replay, abrupt and gradual injected changes, stationary synthetic
   (5 seeds), synthetic abrupt (5 seeds). Thresholds frozen from 2016-17 dev scenarios.

7. **Results (3 min).** Table from `reports/benchmark/summary.md` + `fig_tradeoff.png` +
   rolling-error charts. Talk through: quality vs training effort, detection delay, rollbacks,
   stationary streams - including where adaptive loses. (Fill from EVALUATION.md "Results".)

8. **Live demo (5 min).** docs/DEMO_SCRIPT.md.

9. **Limitations (1 min).** One real stream (no repeated real trials); injected change family;
   seasonal-index assumption; design fixes found on early evaluation years (disclosed);
   validation lag after abrupt changes.

10. **Future work (0.5 min).** Refit-after-validation variant; forecast weather; station-level
    demand; cost-aware trigger (expected benefit vs training cost); conformal error bounds for
    the gate; shadow-deploying candidates before promotion.
