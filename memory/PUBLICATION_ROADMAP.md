# From capstone to paper: what is missing

Honest assessment as of 2026-10-28, before the final benchmark exists. The project is a strong,
reproducible **engineering + evaluation** artefact; a paper additionally needs a clear claim,
breadth, stronger baselines and statistics. Venue tier changes how much is needed.

## What we already have (counts toward a paper)

- Real, large, long-horizon drift data (122,722 hourly rows, 14 years, COVID-19, e-bikes), built
  reproducibly from raw sources with checksums; cross-checked against UCI Bike Sharing.
- A leakage-safe streaming protocol (delayed labels, stored-prediction scoring, validation after
  the model's fit *and* selection cutoff, hidden scenario truth) with 43 tests.
- A complete supervisor (detect, confirm, gate, validate, promote, probation, rollback), fair
  baselines that differ only in the trigger, dev-only calibration, a counterfactual recovery metric.

## Gaps, in priority order

| # | Gap | Why reviewers care | Effort |
|---|---|---|---|
| 1 | **Clean confirmatory test.** Three design fixes were informed by 2018-19 evaluation data. Freeze the code (git tag) and evaluate once on data nobody has looked at: Capital Bikeshare **2025-01 to 2026-09** (already in the S3 bucket, not downloaded) and/or another city. Weather for 2025-26 needs NOAA global-hourly (ISD-Lite stops in 2025) or Open-Meteo. | Removes the test-set contamination objection | 1-2 days |
| 2 | **More real datasets / domains.** Same pipeline on Citi Bike (NYC), Divvy (Chicago), Bay Wheels; ideally one non-bike stream (taxi demand, electricity load, traffic). | One stream = one anecdote; no variance over real histories | 1 day per bike system; 2-4 days per new domain |
| 3 | **Stronger baselines.** Other detectors as triggers (Page-Hinkley, KSWIN, HDDM from River), a plain error-threshold trigger, retrain-every-batch (compute upper bound), an **oracle trigger** at the true change point (injected scenarios), continuously updated online learners (e.g. River adaptive random forest / Hoeffding adaptive tree regressors), and the cost-aware retraining literature (search needed). | "Static vs periodic" alone is a weak comparison | 3-5 days |
| 4 | **Statistics.** Rolling-origin replays (start at every quarter 2018-2023) and multiple cities for confidence intervals; paired tests on hourly losses (Diebold-Mariano with HAC errors, or block bootstrap); effect sizes. | Single runs on real data cannot show significance | 2-3 days |
| 5 | **Quality-cost trade-off curves.** Sweep trigger sensitivity and schedule intervals (reporting only, not selection) and plot MAE vs training cost per policy; state where each policy is Pareto-optimal. | The research question is a trade-off; single points do not answer it | 1-2 days (compute-heavy: big PC) |
| 6 | **Ablations.** Remove one at a time: seasonal index, ADWIN warm start, probation deferral, persistence retry, validation gate, probation/rollback. | Shows which design choice matters | 1-2 days (compute) |
| 7 | **Sensitivity.** Label delay 1/3/7/14 days, validation length, gate margin, cooldown, budget. | Robustness of conclusions | 1-2 days (compute) |
| 8 | **Problem formulation + related work.** Formalise retraining as a sequential decision (loss + lambda x cost under delayed labels); position against concept-drift adaptation surveys and MLOps retraining work. | Needed for any venue | 3-5 days writing |
| 9 | **Paper draft + artefact.** 8-12 pages, figures, archived code/data-processing (e.g. Zenodo DOI; raw data stays at the source because of its licence). | | 1-2 weeks |

## How far are we?

- **Workshop / short paper** (MLOps or drift workshops, applied tracks): gaps **1, 3 (oracle +
  2-3 detectors), 4 (rolling origins), 5, 8, 9** - roughly **2-3 weeks** of focused work after the
  capstone.
- **Main-track conference or journal:** all nine, plus at least 3 real datasets - roughly
  **2-3 months**.
- The outcome is not known yet: if adaptive matches periodic quality at a fraction of the
  retraining cost, the paper is an efficiency result; if periodic wins on quality, it can still be
  a rigorous *empirical* paper on when triggered retraining does and does not pay off - such
  results are publishable only with gaps 1-5 closed.
