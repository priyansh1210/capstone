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

## Other one-off commands

`-Only <amm command>` runs any single command with `--workers`, e.g. `-Only multicity-report`.
Earlier switches still work: `-OnlyDownload`, `-OnlyBuild`, `-OnlyPosthoc`.
