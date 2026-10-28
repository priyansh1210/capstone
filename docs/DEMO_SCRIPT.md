# Classroom demo script (about 8 minutes)

Start: `.venv\Scripts\python -m streamlit run app/dashboard.py` -> http://localhost:8501
Everything shown is computed live by the engine; nothing on screen is pre-recorded.

**0. Setup (sidebar)** - Scenario *Source observations: 2018-2024 replay, unmodified*,
policy **adaptive**, keep *Also run static baseline* ticked -> **Create new run**
(about 8 s: builds the scenario and trains the initial HGB model on 2011-2016).

**1. Normal operation.** Set *Fast-forward to* 2019-03-01 -> **Fast-forward** (runs every
day for real, about 25 s). Point at: replay date, controller state `serving`, active model,
rolling MAE, and the timeline tab - the controller already handled real 2018 drift
(alarms, a promotion, a rejection), each with its logged reason. Press **Start**
(speed 3 days/tick) for a few seconds of normal operation, then **Pause**.

**2. Introduce a labelled experimental change.** In *Experiment controls* keep factor 1.6,
hours 7-9 and 16-19, working days only -> **Inject labelled demand change**. Say: this changes
the simulated world for both policies from today; the controller is not told - it only sees
predictions and the labels that arrive one day later.

**3. Let it detect independently.** **Start**. Watch the actual-vs-predicted chart: actual
commute peaks now exceed predictions. Within days the timeline shows `ALARM` (ADWIN), then
`DETERIORATION_CONFIRMED` with the explanation (error vs reference, under-prediction bias,
input shift z-scores - the inputs did not change, the relationship did).

**4. Update decision and candidate evaluation.** Open the latest `RETRAIN_START` /
`CANDIDATES_REJECTED` or `PROMOTED` row in the timeline: six candidates, their validation
MAE on the same 14 held-out days, the 5 % threshold. Often the first attempt is rejected
(the validation days are post-change but the training window is still mostly pre-change);
after the 14-day cooldown `DETERIORATION_PERSISTS` triggers a retry that is promoted. Show the
*Model versions* tab: new active version, previous kept as fallback.

**5. Subsequent measured results.** Probation: `PROBATION_CHECK` rows compare new vs previous
on the same hours, then `KEPT`. The rolling-error chart shows adaptive vs the static baseline
after the change.

**6a. Rejected update (TEST-ONLY, disclosed).** **Pause**. Click *Next cycle trains only a
weak candidate*, then *Operator: request retraining attempt*, then **Step** once or twice.
Timeline: `FAULT_INJECTION`, `OPERATOR_REQUEST`, `RETRAIN_START [TEST-ONLY ...]`,
`CANDIDATES_REJECTED` - the real gate rejected the weak model; the current model stays.

**6b. Verified rollback (TEST-ONLY, disclosed).** Click *Force-activate weak model (bypass
gate)*. The weak model now serves (orange `FAULT_INJECTION_ACTIVATION`), the old model
shadow-predicts. **Start**: after two 3.5-day paired windows the timeline shows
`PROBATION_CHECK ... new worse` twice and `ROLLED_BACK`; the old model is active again and
the rolling MAE recovers. Model versions: weak version `rolled_back`, flagged test-only.

**Close** with the *Experiments* tab: the benchmark over the full 2018-2024 replay, separated
into source observations, modified observations and generated data.

Fallbacks: if a step takes a moment, a retraining cycle is running (measured times are shown
in Model versions). **Save checkpoint** / **Resume saved** reload the exact run state.
