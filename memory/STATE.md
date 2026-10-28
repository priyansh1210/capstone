# STATE (read first)

Updated: 2026-10-28 23:05 by the laptop (Claude Code), end of session 1. Latest pushed commit
before this update: `4b9f51f`. Tags: `clean-test-v1` (6b63a9b, frozen policy code),
`clean-test-v1.1` (7ed1f0a, + NYC data fix and rerun plumbing; policy code byte-identical).

## Resume here

All experiments are complete and verified. **No big-PC run is pending.** The project is in the
writing / presentation stage.

1. Pull, then read this file, `RUNLOG.md` and `BUILD_STATUS.md` ("Next steps").
2. Offered to the user but not started (wait for them to ask):
   - a slide deck from `docs/PRESENTATION_OUTLINE.md` with the real figures
     (`reports/multicity/fig_pareto_clean.png`, `fig_forest_clean.png`, `fig_cost_regret.png`,
     rolling charts);
   - a visual check of the dashboard (`amm dashboard`; big PC, or the laptop with other apps
     closed);
   - journal-version items (PAPER section 8): Cara / Regol et al. baselines adapted to
     regression, online learners (River), a non-bike domain, an expensive-retraining setting,
     sensitivity to label delay and gate margin, a confirmatory test of probe without the
     significance test on new data.
3. Two references still to confirm in `docs/PAPER.md`: the Cara volume/DOI (KBS 2024,
   arXiv 2310.04216) and the KSWIN (Raab et al., Neurocomputing 2020) volume/pages.

## Publishability verdict given to the user

Workshop / applied-track ready (empirical study + negative result + probe). Not main-track
without the journal-version items above.

## Done

- Big PC heavy runs (see RUNLOG.md): data for 4 cities, tests, calibration v2, smoke, the
  benchmark, post-hoc, calibrate-extra (dev only), and the **clean multi-city test**: 230 runs
  from tag `clean-test-v1`, 58 min, 0 failures.
- **NYC data correction (BUILD_STATUS D20).** The 2018 Citi Bike archive stores every month twice.
  - Parser fixed; verified identical on all 91 DC archives; yearly-jump check added.
  - NYC rebuilt (18,855,882 repeats removed) and its 26 jobs re-run from tag
    `clean-test-v1.1` (12.9 min).
  - The first NYC results are in `reports/superseded/`.
- Step F: Chicago, SF and DC rebuilt with the fixed parser: 0 repeats and identical totals, so
  their results stand.
- Decision logs of all clean runs are in `reports/multicity/decisions/`.
- **Related work and positioning** (PAPER v0.4 section 2; references checked online): Cara,
  Regol et al. ICML 2025, Casimiro et al. TAAS 2024, Zliobaite/Budka/Stahl 2015, MAPE-K
  (Kephart & Chess 2003). Positioning: they watch or forecast degradation of the current model;
  probe *measures* the attainable gain with a cheap challenger.
- **Cost model** (`amm cost-model`, reporting only; PAPER 7.7, EVALUATION, BUILD_STATUS D21):
  J = MAE/MAE_p28 + kappa x effective cycles per day; probes counted at ~8 % of a cycle.
- **Explainer page** (how it works, framework diagrams, results, interactive cost explorer,
  36 autonomous-systems viva questions): private Claude artifact
  https://claude.ai/artifact/3oss3vmvpt3f4kwbmHETp2 ; backup copy in `docs/explainer/`.
- Docs current: EVALUATION, PAPER v0.4, METHOD, DATASET, README, PRESENTATION_OUTLINE,
  VIVA_PREP, BUILD_STATUS (D17-D21), PUBLICATION_ROADMAP. **60 tests pass.**

## Headline (clean test, held-out cities, corrected)

- Drift-detector triggers were 25-30 % worse than the 28-day schedule, and worse on every
  system: Chicago 65-95 % (reference inflation, COVID-onset model with a 5x reference),
  elsewhere 5-14 % (missed improvement).
- **Probe** matched the schedule (-0.1 %, no significant difference on any of 7 streams), with
  40 % fewer full cycles (271 vs 450) and 0 cycles on stationary data; it beat ADWIN on 7/7.
- Periodic-14 was 4-5 % better than every trigger, at 1.7x compute.
- Cost model, clean streams: periodic-14 cheapest below kappa ~1.4 days; **probe cheapest for
  ~1.4-14 days** (1.1-25 with free probes); periodic-56/91 above; static beyond 100. On
  stationary data static/KSWIN win; on short synthetic abrupt streams periodic-91 is hard to beat.

## Working notes for the next session

- Laptop: `--workers 2` at most. Heavy jobs: give the user `scripts/bigpc_run.ps1` commands for
  the big PC (Core Ultra 9 285, 24 cores, 64 GB) and wait for "pushed".
- If a push fails with "You are not currently on a branch": `git push origin HEAD:main`,
  `git checkout main`, `git pull`.
- Commit messages carry no AI-attribution lines (CLAUDE.md).
