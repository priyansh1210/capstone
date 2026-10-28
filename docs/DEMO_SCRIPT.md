# Classroom demo script (about 8 minutes)

Start: `.venv\Scripts\python -m streamlit run app/dashboard.py` -> http://localhost:8501
(on the 8 GB laptop, close other heavy programs first). Everything is computed live by the
engine; nothing is pre-recorded. Rehearse headlessly with `python scripts/rehearse_demo.py`
(42 s); the numbers below are from that rehearsal (frozen settings, 2026-10-28) and will match
if you inject on the same day.

**0. Setup (sidebar).** Scenario *Source observations: 2018-2024 replay, unmodified*, policy
**adaptive**, keep *Also run static baseline* ticked -> **Create new run** (a few seconds: builds the
scenario and trains the initial HGB model on 2011-2016).

**1. Normal operation.** *Fast-forward to* 2019-03-01 -> **Fast-forward** (runs all ~425 days
for real, ~30 s). Point at the timeline: the controller already handled real 2018 drift on its own
- `DETERIORATION_CONFIRMED` -> `PROMOTED` (May 2018, +28 % on held-out days) -> `KEPT`, several
`ALARM_DISMISSED` ("statistical change without sustained deterioration") and one
`CANDIDATES_REJECTED` (Dec 2018, best candidate -4.1 %). **Step** 10 days.

**2. Introduce a labelled experimental change.** *Experiment controls*: factor 1.6, hours 7-9 and
16-19, working days only -> **Inject labelled demand change** (from 2019-03-11, 10,143 future rows).
It changes the simulated world for both policies; the controller is not told and only sees
predictions and the labels that arrive one day later.

**3. Let it detect independently.** Speed 5 -> **Start**. The actual-vs-predicted chart shows
commute peaks far above the predictions and the rolling MAE climbs from ~46 to ~160 trips/h.
*Say:* detection is deliberately conservative - ADWIN must flag a change, then the 14-day error must
stay above the reference on 3 consecutive days. In the rehearsal ADWIN alarmed on 2019-05-15 (65
simulated days, ~20 s at speed 5), deterioration was confirmed two days later (+43 % vs reference,
"model under-predicts total demand"). This delay is a real finding (EVALUATION.md, finding 5).

**4. Update decision and candidate evaluation.** Open `RETRAIN_START` / `PROMOTED` in the timeline:
6 candidates scored on the same 14 held-out days; v005 (HGB, 365-day window) 114.8 vs current 166.1
(+30.9 %) passes the 5 % gate. *Model versions*: v005 active, v003 kept as fallback.

**5. Subsequent measured results.** `PROBATION_CHECK` rows compare new vs previous on the same
hours, then `KEPT` (paired MAE 124.5 vs 172.1). Overview: MAE since the injection 161.8 (adaptive)
vs 173.6 (static baseline). **Pause.**

**6a. Rejected update (TEST-ONLY, disclosed).** Click *Next cycle trains only a weak candidate*, then
*Operator: request retraining attempt*, then **Step**. Timeline: `FAULT_INJECTION`,
`OPERATOR_REQUEST`, `RETRAIN_START [TEST-ONLY ...]`, `CANDIDATES_REJECTED` (weak model MAE 337.5 vs
122.4, -176 %): the real gate rejected it and the current model stays.

**6b. Verified rollback (TEST-ONLY, disclosed).** Click *Force-activate weak model (bypass gate)* ->
**Start**. The weak model serves, the old one shadow-predicts; after two 3.5-day paired windows the
timeline shows `ROLLED_BACK` (8 days) and the old model is active again. *Model versions*: weak
version `rolled_back`, flagged test-only.

**Close** with the *Experiments* tab (benchmark): the schedule wins on real drift, adaptive avoids
retraining when nothing changes, and the decision-log diagnosis of the COVID-19 stall
(EVALUATION.md, findings 2-4); mention the post-hoc variant as exploratory.

Fallbacks: a pause during a step is a retraining cycle (times shown in *Model versions*).
**Save checkpoint** / **Resume saved** reload the exact run state; the static baseline can be
unticked to halve memory.
