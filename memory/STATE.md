# STATE (read first)

Updated: 2026-10-28 by the laptop (Claude Code).

## Done

- Engine, scenarios, dashboard, CLI, 43 passing tests (`python -m amm test`).
- Data built on the laptop: 44,967,423 trips -> 122,722 hourly rows (2011-2024) + NOAA DCA weather.
- Smoke benchmark verified end to end (3 min 11 s) - but with settings that are now superseded.

## Not done (why the big PC is needed)

- **Calibration v2 never finished**: Claude Code stopped it at 14/~90 runs because the 8 GB laptop
  ran low on memory. `configs/frozen_policy.yaml` does **not exist** yet (v1 is archived in
  `reports/superseded/`, calibrated before the probation alarm-deferral bug fix; not to be used).
- Full benchmark not run yet.

## Next action - BIG PC

Follow `BIG_PC_RUNBOOK.md`: setup -> `scripts\bigpc_run.ps1` (prepare-data, tests, calibrate,
smoke, benchmark) -> commit + push the listed paths.

## Then - LAPTOP

`git pull`; check `memory/RUNLOG.md`, compare `data/raw/SOURCES.json` checksums reported in
`memory/logs/` with `memory/laptop_SOURCES.json`; write results into `docs/EVALUATION.md`, README
runtimes, presentation; rehearse the demo (`scripts/rehearse_demo.py`) with the frozen values.
