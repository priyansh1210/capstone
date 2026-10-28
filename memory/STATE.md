# STATE (read first)

Updated: 2026-10-28 by the laptop (Claude Code), after the clean multi-city test.

## Done

- Big PC heavy runs (see RUNLOG.md): data for 4 cities, tests, calibration v2, smoke, the
  benchmark, post-hoc, calibrate-extra (dev only), and the **clean multi-city test**: 230 runs
  from tag `clean-test-v1`, 58 min, 0 failures.
- Decision logs of the clean runs were exported (step C) to `reports/multicity/decisions/`.
- The laptop regenerated `reports/multicity/` with reporting-only fixes (BUILD_STATUS D19).
  Results are identical; figures were checked visually.
- Docs written from executed results: EVALUATION, PAPER v0.2, METHOD, README,
  PRESENTATION_OUTLINE, VIVA_PREP, BUILD_STATUS.

## Headline (clean test; NYC superseded, see Open)

- Drift-detector triggers were 39-45 % worse than the 28-day schedule. Chicago replicates the DC
  mechanism: a COVID-onset model with a 5x reference, 17 alarms dismissed over 3 years.
- **Probe** matched the schedule (+0.5 %, no significant difference on any of 7 streams), with
  39 % fewer full cycles and 0 cycles on stationary data.
- Periodic-14 was 4-5 % better than every trigger, at 1.8x compute.

## Open

- **NYC 2018 was counted 2.07x** (BUILD_STATUS D20; docs/DATASET.md). The archive holds every
  month as a whole file *and* as split parts, plus an extra April copy.
  - Done: inspection (step D); parser fix (trips repeated across files of one archive are
    dropped) verified byte-identical on all 91 DC archives; yearly-jump build check; NYC
    re-run plumbing; 59 tests pass; tag `clean-test-v1.1`.
  - **Next: big PC step E** (memory/BIG_PC_RUNBOOK.md): rebuild NYC, re-run only the NYC jobs,
    export the decision logs, push. Then the laptop replaces the NYC numbers and the means in
    every doc.
- Slides; related-work survey + citation check (PAPER TODOs); dashboard visual check.
