# Big PC runbook

Everything runs on the CPU (small scikit-learn models by design). Always start with:

```powershell
cd C:\Users\FITT\capstoneproject
git pull
```

## Done already

setup, prepare-data, calibrate, smoke, benchmark, posthoc, download-city, build-city,
calibrate-extra (step A), multicity (step B) (see `memory/RUNLOG.md`).

## Part 2 - step A: calibrate the new method on DEVELOPMENT data only (~5-10 min)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bigpc_run.ps1 -Only calibrate-extra -Workers 12
git add memory reports configs/frozen_policy.yaml
git commit -m "Big PC: calibrate-extra (dev only)"
git push
```

## Part 2 - step B: clean multi-city test from the FROZEN tag (~1 h, 230 runs)

Only after the laptop has reviewed step A and pushed the tag `clean-test-v1`:

```powershell
git fetch --tags
git checkout clean-test-v1
powershell -ExecutionPolicy Bypass -File scripts\bigpc_run.ps1 -Only multicity -Workers 12
git checkout main
git add memory reports
git commit -m "Big PC: multi-city clean test (tag clean-test-v1)"
git push
```

`reports/multicity/environment.json` records the commit/tag used. The laptop does not push to
`main` while step B runs, so `git checkout main` keeps the new result files.

## Part 2 - step C: export the decision logs of the clean runs (~1 min)

The per-run SQLite stores (`reports/multicity/runs/`) are gitignored. This writes small CSVs
(decisions + model-version references) to `reports/multicity/decisions/`, read-only on the stores:

```powershell
git pull
.venv\Scripts\python scripts\export_decisions.py reports\multicity
git add reports/multicity/decisions
git commit -m "Big PC: decision logs of the clean multi-city runs"
git pull --no-edit
git push
```

## Part 2 - step D: inspect the NYC 2018 archive (counted about twice; ~2-5 min, read-only)

```powershell
git pull
.venv\Scripts\python scripts\inspect_archive.py data\raw\nyc\trips\2018-citibike-tripdata.zip --out memory\logs\inspect_nyc_2018.txt
git add memory/logs/inspect_nyc_2018.txt
git commit -m "Big PC: inspect NYC 2018 archive"
git pull --no-edit
git push
```

## Part 2 - step E: rebuild NYC with the dedupe fix and re-run only the NYC jobs (~25-40 min)

Tag `clean-test-v1.1` = `clean-test-v1` + the trip-parser fix, the build check and the re-run
plumbing (reporting/scripts/tests/docs too). Policy, config, scenario and runner code are
byte-identical to `clean-test-v1`.

```powershell
git pull
git fetch --tags
git checkout clean-test-v1.1
powershell -ExecutionPolicy Bypass -File scripts\bigpc_run.ps1 -OnlyBuild -Cities nyc -Workers 12
powershell -ExecutionPolicy Bypass -File scripts\bigpc_run.ps1 -Only multicity -Scenarios city_nyc_unmodified,city_nyc_abrupt -Workers 12
.venv\Scripts\python scripts\export_decisions.py reports\multicity
git checkout main
git add memory reports
git commit -m "Big PC: NYC rebuilt with 2018 dedupe, NYC jobs re-run (tag clean-test-v1.1)"
git pull --no-edit
git push
```

**Expected from the build** (`memory/logs/build_nyc.log`):
- the line `2018-citibike-tripdata.zip: 36,404,221 rows ..., 18,855,882 repeated across members
  removed`;
- no `WARNING ... trips per active day` line;
- total trips 242,270,970, i.e. 261,126,852 - 18,855,882.

If any of these differ, stop and push the logs.

The re-run moves the earlier NYC results to `reports/superseded/multicity-city_nyc_*/`.

## Other one-off commands

`-Only <amm command>` runs any single command with `--workers`, e.g. `-Only multicity-report`.
Earlier switches still work: `-OnlyDownload`, `-OnlyBuild`, `-OnlyPosthoc`.
