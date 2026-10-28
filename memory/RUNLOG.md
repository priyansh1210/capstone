# Run log (append-only)

Laptop rows before this log existed are reconstructed from the session (in order; only the date
is recorded because exact clock times were not logged; runtimes are measured). Rows written by
`scripts/bigpc_run.ps1` are appended automatically with real timestamps.

| when | machine | step | command | runtime | outcome |
|---|---|---|---|---|---|
| 2026-10-28 (1) | laptop | download | `amm.data.download.download_all(2011, 2024)` | ~10 min | 105 files OK; UCI zip via manual fallback (Python TLS "certificate has expired") |
| 2026-10-28 (2) | laptop | build | `amm.data.build.build(2011, 2024)` | 1.7 min | 122,722 rows, 44,967,423 trips, 0 unparsed |
| 2026-10-28 (3) | laptop | select-model | `amm.experiments.model_selection` | 0.7 min | HGB on all training rows, calibration MAE 82.7 |
| 2026-10-28 (4) | laptop | calibrate v1 | `amm calibrate --workers 4` | 36.8 min | completed; superseded by the alarm-deferral fix |
| 2026-10-28 (5) | laptop | prepare (offline) | `amm prepare-data --offline` | 3.0 min | identical rebuild from cache, 5 scenario manifests |
| 2026-10-28 (6) | laptop | smoke v1 | `amm smoke --workers 4` | 3.2 min | completed; superseded |
| 2026-10-28 (7) | laptop | tests | `amm test` | 0.5 min | 43 passed |
| 2026-10-28 (8) | laptop | calibrate v2 | `amm calibrate --workers 4` | stopped | stopped by Claude Code at 14/~90 runs: laptop low on memory |
| 2026-10-28 13:32 | DESKTOP-RTIKELL | prepare_data | `amm prepare-data` | 3.3 min | ok |
| 2026-10-28 13:32 | DESKTOP-RTIKELL | tests | `amm test` | 0.3 min | ok |
| 2026-10-28 13:45 | DESKTOP-RTIKELL | calibrate | `amm calibrate --workers 12` | 13.1 min | ok |
| 2026-10-28 13:47 | DESKTOP-RTIKELL | smoke | `amm smoke --workers 12` | 1.5 min | ok |
| 2026-10-28 13:58 | DESKTOP-RTIKELL | benchmark | `amm benchmark --workers 12` | 11 min | ok |
| 2026-10-28 14:25 | DESKTOP-RTIKELL | posthoc | `amm posthoc --workers 12` | 12.2 min | ok |
| 2026-10-28 15:10 | DESKTOP-RTIKELL | download_cities | `amm download-city --workers 8 --city chicago sf nyc dc` | 12.6 min | ok |
| 2026-10-28 15:17 | DESKTOP-RTIKELL | build_cities | `amm build-city --workers 12 --city chicago sf nyc dc` | 1.5 min | ok |
| 2026-10-28 16:23 | DESKTOP-RTIKELL | calibrate_extra | `amm calibrate-extra --workers 12` | 7.1 min | ok |
| 2026-10-28 17:25 | DESKTOP-RTIKELL | multicity | `amm multicity --workers 12` | 58.1 min | ok |
| 2026-10-28 (9) | laptop | multicity-report | `amm multicity-report --workers 2` (reporting fixes, BUILD_STATUS D19) | 44 s | results.csv identical; significance.csv identical up to 1e-15 in DM; new fig_forest_clean.png |
| 2026-10-28 (10) | laptop | tests | `pytest -q` | 24 s | 55 passed |
| 2026-10-28 (11) | laptop | regression | new trip parser on all 91 local DC archives vs the old hourly table | 103 s | identical: 44,967,423 trips, 0 hours differ, 0 rows removed |
| 2026-10-28 (12) | laptop | rerun test | `amm multicity --config configs/multicity_smoke.yaml --only-scenarios synthetic_stationary` on a copy of the smoke results | 2.0 min | 21 runs before/after, identical MAE, old files moved to superseded (test output deleted) |
| 2026-10-28 (13) | laptop | tests | `pytest -q` | 25 s | 59 passed |
| 2026-10-28 18:24 | DESKTOP-RTIKELL | build_nyc | `amm build-city --workers 12 --city nyc` | 2.2 min | ok |
