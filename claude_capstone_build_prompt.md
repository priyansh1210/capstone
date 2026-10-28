# Claude Code build prompt: Autonomous Model Maintenance under Concept Drift

You are my senior AI/ML engineer and software engineer. Build this project in the current workspace, including implementation, tests, experiments, dashboard, and presentation documentation.

I have approximately 24 hours before presenting this as an AI-engineering capstone. I will use Claude Code throughout. Start implementing immediately after a brief repository inspection and concise plan. Continue through running and debugging the system; an outline or scaffold is not the deliverable. Preserve existing work, follow applicable repository instructions, and make reasonable reversible implementation decisions without repeatedly asking for approval.

The goal is a substantial, working, locally runnable software system. Keep the application focused while completing the entire autonomous decision loop.

## 1. Project and research question

Title: Autonomous Model Maintenance under Concept Drift.

Build a supervisor for a deployed demand-prediction model. It observes prediction outcomes, notices sustained deterioration, decides whether retraining is justified, trains replacement candidates, evaluates them, activates an acceptable replacement, and monitors whether to keep it or revert.

Research question: Can selective, validated retraining maintain prediction quality while reducing unnecessary retraining compared with a fixed schedule?

Use bike-rental demand as the concrete application. All input is historical or generated data; no physical equipment is involved.

Treat this as an engineering and evaluation contribution using established ML methods. Do not claim to invent drift detection or guarantee that our policy outperforms the baselines. Explain actual findings, including unsuccessful cases.

## 2. Runtime and architecture

Use Python with compatible, tested dependency versions. Preferred stack:

- pandas and NumPy for data handling.
- scikit-learn pipelines and small CPU-based regression models.
- River ADWIN for monitoring changes in prediction error.
- Streamlit and Plotly for the dashboard.
- SQLite for run metadata, predictions, decisions, and model-version records.
- joblib for locally created model artifacts.
- pytest for meaningful correctness and integration tests.

Use a modular Python engine shared by the dashboard and command-line experiments. Keep policy decisions independent of UI rendering. A separate API service is optional only if it serves a demonstrated need.

Run locally on an ordinary laptop. After the dataset is downloaded, normal operation and demonstrations must work offline. No paid API, GPU, external LLM, cloud account, Kubernetes, or external database should be required. The autonomous supervisor can use statistical detection and explicit decision policies.

Inspect the OS, Python environment, and existing repository first. Use an isolated environment and provide tested setup commands. Record the versions actually used.

## 3. All required datasets and their roles

Only ONE external dataset is required: the UCI Bike Sharing dataset.

Official dataset page:
https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset

Official archive linked from that page:
https://archive.ics.uci.edu/static/public/275/bike%2Bsharing%2Bdataset.zip

Dataset citation:
Fanaee-T, H. (2013). Bike Sharing [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5W894

The source lists a CC BY 4.0 license. Retain attribution and identify modifications to derived data.

Required archive contents:

- hour.csv: primary modelling and chronological replay data.
- Readme.txt: source variable definitions; preserve it with attribution.
- day.csv: included in the archive but NOT needed for the core build. Do not merge it with hourly observations or treat it as independent evaluation data.

Create a download-and-validation command with timeouts, useful errors, local caching, and a manual-file fallback. If downloading is blocked, continue using clearly labelled generated development data and explain how to place the official hour.csv locally. Never silently present generated data as the UCI dataset.

Report the actual downloaded row count, columns, date range, missingness, timestamp gaps, and source-file checksum. Preserve raw files unchanged.

Target:
- cnt, the total hourly rental count.

Time and input fields:
- Build the chronological timestamp from dteday and hr.
- Calendar inputs can include hr, weekday, workingday, holiday, mnth, season, and yr.
- Weather fields include temp, atemp, hum, windspeed, and weathersit.
- For a forecasting interpretation, use weather observations available BEFORE the prediction timestamp. Handle time gaps explicitly; do not substitute future observed weather.
- Start without demand-derived lag features unless label-availability checks are implemented.

Exclude from prediction inputs:
- casual and registered: their sum equals cnt, so using them leaks the target.
- cnt itself and any feature derived from an unrevealed target.
- instant as a predictive feature; an identifier may still be retained for traceability.

Generate the following additional datasets LOCALLY from code; no further downloads are required:

A. Unmodified chronological replay:
Use held-out chronological UCI records without injected changes. Call this "unmodified replay", not "guaranteed stationary", because real historical data can naturally change.

B. Abrupt-change replay:
Derive a copy of the held-out stream with an explicitly documented change to demand conditional on available features, such as a demand increase during selected hours after a chosen point. Preserve nonnegative targets.

C. Gradual-change replay:
Derive another copy with a smoothly increasing change to the demand relationship over a defined interval.

D. Stationary synthetic regression stream:
Generate a seeded stream with a fixed input distribution, fixed target relationship, and fixed noise process. Use it to study unnecessary alarms and retraining under known stable conditions.

E. Small deterministic test fixtures:
Generate tiny streams and deliberately weak candidate models for unit and integration tests, including label delays, candidate rejection, and rollback.

Store seeds, transformation definitions, and hidden change timestamps in scenario manifests. The evaluator may inspect these manifests; the detector and controller must never receive the true change point, scenario identifier as a predictive input, or an instruction to retrain when a scenario changes.

Clearly distinguish source observations, modified observations, and fully generated data in the UI and reports. Do not interpret every alarm in unmodified real data as a false positive.

## 4. Prevent data leakage throughout

Use chronological initial training, calibration/development, and final replay partitions; do not randomly split time-series observations.

Fit preprocessing only on each model's allowed training data. Select initial model settings, detection thresholds, policy thresholds, and scheduled-update intervals using training/calibration data or separate development scenarios, then freeze them for reported evaluation.

At stream time, a policy may access only covariates already observed and labels already revealed. Later-arriving labels can become training history after their reveal time.

Implement configurable label delay, initially one replay batch. Save each prediction, original model version, prediction time, and label-reveal time. Score the prediction that was actually made; never recompute historical predictions using a newer model.

The controller must not access future targets or scenario manifests, even if the simulator holds a full dataframe internally. Create explicit interfaces that enforce this separation.

Within each retraining cycle, separate the training window from a later validation window. Validation labels must already be available, and neither compared model may have been fitted on that validation window. Track training cutoffs. If there are not enough eligible examples, wait.

Evaluate the overall policies on subsequent stream predictions, independently of candidate selection. Document these boundaries and test them.

## 5. Implement the autonomous supervisor

Represent the controller as an explicit state machine or similarly inspectable policy. It must be able to keep serving, investigate, wait, retrain, reject a candidate, promote a candidate, and roll back.

Monitoring:
- Track rolling MAE, RMSE, and sample counts after labels arrive.
- Feed a documented, consistently scaled error signal to ADWIN.
- A statistical change signal alone is not proof of deterioration or its cause. Check whether error has actually worsened.
- Distinguish data-distribution changes, changes in the target relationship, and observed performance deterioration in explanations.

Retraining decision:
- Require sustained evidence of deterioration and sufficient recent labelled data.
- Enforce a configurable cooldown and per-run retraining budget.
- Avoid simultaneous duplicate training jobs.
- Record reasons for acting and for declining or postponing action.
- Reset or rebase monitoring appropriately after a model change so improvement does not cause repeated retraining.

Candidate training:
- Use a modest set of CPU-based models, such as Ridge, RandomForestRegressor, and HistGradientBoostingRegressor.
- Use small, documented configurations with reproducible seeds and bounded parallelism.
- Fit a complete preprocessing-plus-model pipeline for every candidate.
- Use configurable recent-data windows and a bounded candidate search.

Validation and promotion:
- Compare the current model and candidates on the same eligible validation observations.
- Require a configurable minimum sample count and meaningful MAE improvement.
- Keep the existing model if no candidate passes.
- Log candidate scores, thresholds, training duration, and the decision.
- Preserve the previous model and activate a replacement atomically.

Post-update monitoring and rollback:
- During a defined observation period, record predictions from both the active and previous model on the same arriving inputs, before their labels are revealed.
- Compare their paired errors only after enough subsequent labels arrive.
- Roll back if the replacement is consistently worse by a configured margin.
- Do not roll back solely because absolute error increased; both models may be affected by a changed environment.
- Avoid immediate promotion/rollback loops and retain the reason and relevant measurements.

Failures in training, validation, or saving a candidate must leave a usable current model available.

## 6. Dashboard and live demonstration

Build a polished, readable dashboard with four areas:

Overview:
- Scenario, data source, replay progress, active model, controller state.
- Actual versus originally predicted demand.
- Rolling prediction error.
- Update counts and measured training time.
- Honest empty states while labels or evaluation samples are unavailable.

Decision timeline:
- Timestamped actions and reasons.
- Relevant measurements and thresholds.
- Waiting, retraining, rejection, promotion, and rollback events.

Model versions:
- Current, previous, rejected, and retired versions.
- Training ranges, validation ranges, metrics, model configuration, and activation times.

Experiments:
- Comparable baseline results, charts, and CSV/JSON exports.
- Clear separation of real-data replay and generated scenarios.

Provide start, pause, step, speed, and reset controls with fixed-seed reproducibility. Streamlit reruns must not duplicate events, train twice, or silently reset experiments.

Include an understandable classroom demo:
1. Establish normal operation.
2. Introduce a labelled experimental demand change through the simulator.
3. Let the controller detect evidence independently.
4. Show its update decision and candidate evaluation.
5. Show subsequent measured results.
6. Demonstrate a rejected update and a verified rollback.

Use an explicit, visibly labelled fault-injection test for rejection or rollback if necessary. A test-only activation of an intentionally weak model must be disclosed. The validation, monitoring, and recovery logic must still execute for real. Never fake dashboard values, results, or recovery events.

## 7. Baseline experiments and metrics

Implement at least these policies:

- Static: keep the initial model.
- Periodic: attempt retraining on a fixed, calibrated schedule.
- Adaptive: our evidence-based supervisor.

For fair comparisons, give every policy the same initial model, incoming observations, label delays, and available history. Periodic and adaptive policies should share the candidate-training procedure, validation gate, rollback rules, and per-run training budget; isolate the retraining trigger as the main difference. State explicitly that the periodic baseline also uses the validation gate.

Keep each policy's model, controller, detectors, and history independent.

Run comparisons on unmodified, abrupt-change, gradual-change, and stationary synthetic streams. Use reproducible configurations; add repeated seeds for generated experiments when runtime permits.

Report:
- Stream MAE and RMSE over matching scored observations.
- Rolling error and post-change error.
- Retraining cycles, individual candidate fits, and actual training wall time.
- Promotions, rejections, and rollbacks.
- Detection delay relative to injected changes, with its definition and missed detections.
- Unnecessary alarms/retraining on the truly stationary synthetic stream.
- Recovery time only when a clearly defined recovery criterion is actually met.

Compare prediction quality and training effort together. Never insert predetermined improvement percentages or hide scenarios where adaptation is worse. If an update or recovery never occurs, show that honestly.

## 8. Verification and acceptance criteria

Write meaningful tests for:
- Excluding target-leaking columns.
- Chronological partitions and preprocessing boundaries.
- Delayed-label availability and stored original predictions.
- Insufficient-data, cooldown, and budget decisions.
- Honest rejection of an inferior candidate.
- Promotion using held-out measurements.
- Rollback using paired, subsequent predictions.
- Isolation of benchmark policies.
- Persistence/reload and absence of duplicate processing.
- Scenario truth remaining inaccessible to the controller.

Run the tests, a complete small experiment, and the actual app. Inspect the dashboard with browser tooling if available. Fix integration failures; do not report unexecuted checks as passed.

Provide a fast smoke configuration and a fuller benchmark configuration. Measure their runtime on the available machine. Check fresh setup and cached-data offline operation.

## 9. Deliverables

Produce:
- Complete modular source code, dashboard, configuration files, and dependency specifications.
- CLI commands for dataset preparation, a smoke run, full experiments, and tests.
- A dataset/source README with attribution, transformations, and feature-availability assumptions.
- README with exact setup and demo commands.
- Architecture and evaluation documentation with an appropriate diagram.
- Machine-readable experiment results and charts generated from executed runs.
- A short demo script and presentation outline covering problem, autonomy, architecture, data, experiments, results, limitations, and future work.
- A viva preparation document explaining the algorithms, leakage prevention, retraining policy, rollback, baselines, and limits of the evidence.
- BUILD_STATUS.md recording implemented features, actual test status, decisions, commands, and remaining work so a later session can resume.

Use sensible folders such as src/, tests/, configs/, scripts/, data/, artifacts/, reports/, and docs/. Keep UI code thin and secrets out of the repository.

## 10. Execution order and completion behavior

Work in this order:
1. Inspect the environment; create a short implementation plan and status file.
2. Build a working slice: dataset to chronological predictions to recorded error.
3. Implement detection, autonomous decisions, retraining, validation, promotion, and rollback.
4. Add baseline experiments and meaningful tests.
5. Build and verify the dashboard.
6. Run experiments, fix failures, and write presentation documentation from actual results.

Allocate the latter part of the sprint to verification and rehearsal materials. Avoid unrelated features such as authentication, billing, arbitrary dataset support, or a complex distributed deployment.

Make reasonable assumptions and document them. Ask a question only when a genuine blocker prevents progress. Do not stop after planning, creating files, or obtaining one passing test. Continue until the core acceptance criteria are demonstrated or a concrete environmental blocker is documented.

At completion, report what works, exact run commands, measured results, tests actually run, limitations, and anything incomplete.

Start now by inspecting this workspace and implementing the first working slice.
