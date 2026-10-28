# STATE (read first)

Updated: 2026-10-28 by the laptop (Claude Code).

## Done

- All heavy runs finished on the big PC (see RUNLOG.md): data, tests, calibration v2, smoke, full
  benchmark, post-hoc variant. Raw checksums identical on both machines; runs reproduce exactly.
- Results written into docs/EVALUATION.md, README, DEMO_SCRIPT, PRESENTATION_OUTLINE, VIVA_PREP.
- Demo rehearsed headlessly (`scripts/rehearse_demo.py`, 42 s).

## Headline

Frozen protocol: periodic-28d best on real 2018-2024 data (MAE 81.5 vs adaptive 114.7 vs static
136.6); adaptive retrains 0.6x vs 26x on stationary data at equal error. Adaptive stalled after a
COVID-era promotion inflated its reference. Post-hoc bias-trigger variant (exploratory): 84.5 with
31 % fewer cycles than the schedule.

## Open

- Visual dashboard check in a browser (Chrome extension was not connected).
- Slides from docs/PRESENTATION_OUTLINE.md.
- Publication path: PUBLICATION_ROADMAP.md (gap 1 = confirmatory run on untouched 2025-26 data).
