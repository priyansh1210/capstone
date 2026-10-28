# Presentation outline (15 minutes + live demo)

Figures: `reports/multicity/` (clean test) and `reports/benchmark/` (DC). All numbers come from
executed runs (docs/EVALUATION.md, docs/PAPER.md).

1. **Problem (1 min).**
   - Deployed models silently degrade when the world changes.
   - A fixed schedule retrains whether or not anything changed; never retraining fails when
     demand shifts.
   - Question: can *selective, validated* retraining keep quality while reducing unnecessary
     retraining?

2. **Data (1.5 min).**
   - 358 M real bike-share trips from four systems (DC 2011-25, Chicago, New York, SF Bay
     Area), aggregated to hourly demand with NOAA airport weather.
   - Real drift: growth (New York demand x2.5 since 2018), COVID-19, e-bikes.
   - The DC aggregation matches all 17,379 UCI hours (totals within 1.1 %).

3. **What "autonomous" means here (1.5 min).**
   - State machine: serve -> investigate -> wait -> retrain -> validate -> promote ->
     probation -> keep / roll back.
   - Every decision is logged with its measurements and thresholds. Diagram from
     ARCHITECTURE.md.

4. **Leakage boundaries (1 min).**
   - The simulator holds the truth; the controller only sees observed covariates and
     revealed labels (1-day delay).
   - Stored predictions are scored once; validation lies strictly after the current model's
     cutoff.
   - 55 tests.

5. **First experiment, DC 2018-24 (1.5 min).**
   - Results: periodic-28 MAE 81.5, ADWIN-adaptive 114.7, static 136.6.
   - On a stationary stream adaptive retrained 0.6x vs 26x, at equal error.
   - Chart: `reports/benchmark/fig_rolling_bike_unmodified.png`.

6. **Failure analysis (2 min) - the turning point.**
   - **Reference inflation:** a model accepted during the COVID collapse had a reference 4x
     normal; alarms were dismissed for 2.5 years.
   - **Blindness to attainable improvement:** a trigger that compares a model with *itself*
     never sees that a better model has become possible.

7. **Proposed method: probe (1.5 min).**
   - Every 14 days, fit one cheap challenger on the last 120 days and compare it with the
     current model on the newest held-out days.
   - Start a full validated cycle only if it is >= 5 % better and a paired t-test gives
     p <= 0.10.
   - No self-reference to inflate; drift detection only makes probing happen sooner.
     (docs/METHOD.md)

8. **Clean test protocol (1 min).**
   - All thresholds calibrated on DC development data; code frozen at git tag `clean-test-v1`.
   - Run once on Chicago, New York, SF and DC 2025, which no design decision has seen.
   - 230 runs, 58 min, 0 failures.

9. **Results (3 min).**
   - **Error vs compute:** `fig_pareto_clean.png`.
     - Detector triggers (ADWIN / Page-Hinkley / KSWIN): **25-30 % worse** than the 28-day
       schedule, and worse on every system. Chicago shows reference inflation (a COVID-era
       model with a 5x reference kept for 3 years). New York, SF and DC show missed
       improvement (fewer, later updates; 5-14 % worse).
     - Probe: **-0.1 %** against the schedule, with **40 % fewer full cycles**.
     - Probe never retrained on stationary streams (0 vs 26 cycles).
   - **Paired tests:** `fig_forest_clean.png`.
     - Probe vs schedule: no significant difference on any of 7 clean streams.
     - Probe vs ADWIN: better on all 7.
   - **Honest negative result:** a 14-day schedule is 4-5 % more accurate than any trigger, at
     1.7x compute. When retraining is cheap, retrain often; the trigger's value is fewer cycles.
   - **Surprise:** the change-timed oracle was *worse than static*. Three retrains at the
     injected change landed in COVID onset; the gains come from repeatedly retraining on fresh
     data, not from timing.

9a. **When does each policy pay off? (1 min)** `fig_cost_regret.png`:
    - the 14-day schedule while a retraining cycle costs less than about 1.4 days of forecast
      error;
    - probe from about 1.4 to 14 days;
    - rare retraining above that.

9b. **A bug we caught (1 min, good viva material).** New York's 2018 archive stores every
    month twice, so the first build counted 2.07x the trips. It showed up as an implausible
    calibration-year error. We fixed the parser (verified identical on all DC archives), added
    a yearly-jump check, and re-ran only New York with the same frozen code.

10. **Live demo (5 min).** docs/DEMO_SCRIPT.md.

11. **Limitations and future work (1 min).**
    - One task family; thresholds from one city.
    - The injected change coincides with COVID onset in two cities.
    - Retraining here costs seconds; a setting with expensive cycles or human sign-off is
      untested.
    - Next: survey the cost-aware retraining literature; confirm "probe without the
      significance test" (post-hoc best) on new data; station-level demand.
