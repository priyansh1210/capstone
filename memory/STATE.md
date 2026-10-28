# STATE (read first)

Updated: 2026-10-28 by the laptop (Claude Code), after the corrected New York re-run.

## Done

- Big PC heavy runs (see RUNLOG.md): data for 4 cities, tests, calibration v2, smoke, the
  benchmark, post-hoc, calibrate-extra (dev only), and the **clean multi-city test**: 230 runs
  from tag `clean-test-v1`, 58 min, 0 failures.
- **NYC data correction (BUILD_STATUS D20).** The 2018 Citi Bike archive stores every month twice.
  - Parser fixed; verified identical on all 91 DC archives; yearly-jump check added.
  - NYC rebuilt (18,855,882 repeats removed) and its 26 jobs re-run from tag
    `clean-test-v1.1` (12.9 min; policy code byte-identical to `clean-test-v1`).
  - The first NYC results are in `reports/superseded/`.
- Decision logs of all clean runs are in `reports/multicity/decisions/`.
- All docs updated from the corrected results: EVALUATION, PAPER v0.3, METHOD, DATASET, README,
  PRESENTATION_OUTLINE, VIVA_PREP, BUILD_STATUS, PUBLICATION_ROADMAP. 59 tests pass.

## Headline (clean test, held-out cities, corrected)

- Drift-detector triggers were 25-30 % worse than the 28-day schedule, and worse on every
  system: Chicago 65-95 % (reference inflation, COVID-onset model with a 5x reference),
  elsewhere 5-14 % (missed improvement).
- **Probe** matched the schedule (-0.1 %, no significant difference on any of 7 streams), with
  40 % fewer full cycles and 0 cycles on stationary data.
- Periodic-14 was 4-5 % better than every trigger, at 1.7x compute.

## Open

- **Big PC step F** (memory/BIG_PC_RUNBOOK.md): rebuild Chicago, SF and DC with the fixed parser
  and confirm 0 repeats and unchanged totals.
- Slides; related-work survey + citation check (PAPER TODOs); dashboard visual check.
