# STATE (read first)

Updated: 2026-10-28 by the laptop (Claude Code), after the clean multi-city test.

## Done

- Big PC heavy runs (see RUNLOG.md): data for 4 cities, tests, calibration v2, smoke, the
  benchmark, post-hoc, calibrate-extra (dev only), and the **clean multi-city test**: 230 runs
  from tag `clean-test-v1`, 58 min, 0 failures.
- The laptop regenerated `reports/multicity/` with reporting-only fixes (BUILD_STATUS D19).
  Results and CIs are identical; figures were checked visually.
- Docs written from executed results: EVALUATION (clean-test section + final answer), PAPER
  v0.2, METHOD, README, PRESENTATION_OUTLINE, VIVA_PREP, BUILD_STATUS.

## Headline (clean test, held-out cities)

- Drift-detector triggers were 39-45 % worse than the 28-day schedule, by the same failure
  mechanisms as in DC.
- **Probe** matched the schedule (+0.5 %, no significant difference on any of 7 streams), with
  39 % fewer full cycles and 0 cycles on stationary data.
- Periodic-14 was 4-5 % better than every trigger, at 1.8x compute.

## Open

- **Big PC step C** (memory/BIG_PC_RUNBOOK.md): export the decision logs of the clean runs and
  push. The laptop then fills the PAPER 7.2 TODO (references behind the dismissed alarms).
- Slides; related-work survey + citation check (PAPER TODOs); dashboard visual check.
