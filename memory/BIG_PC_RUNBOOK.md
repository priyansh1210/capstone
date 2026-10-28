# Big PC runbook

Everything runs on the CPU (small scikit-learn models by design); the GPU is not used.
Expected time on a desktop with >= 8 cores / 32 GB: roughly 1-1.5 h in total, mostly unattended.

## 0. One-time prerequisites

- Python **3.11** (3.12 also works) on PATH: `python --version`
- Git: `git --version`; signed in to GitHub (`gh auth login` or a credential helper)
- ~4 GB free disk (1.3 GB raw downloads + outputs)

## 1. Get the code

```powershell
cd D:\            # or any folder
git clone https://github.com/priyansh1210/capstone.git capstoneproject
cd capstoneproject
```

(later runs: `cd capstoneproject; git pull`)

## 2. Set up the environment (fresh-setup check)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

It must end with `ok: amm 0.1.0 | river 0.26.1 | sklearn 1.7.2`. If it fails, copy the last 30
lines of output into `memory\logs\setup_failure.log`, commit, push.

## 3. Run all heavy steps

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bigpc_run.ps1
```

This does, in order, logging each to `memory\logs\<step>.log` and `memory\RUNLOG.md`:

| Step | Command | Notes |
|---|---|---|
| prepare_data | `amm prepare-data` | downloads ~1.3 GB from S3/NOAA, builds `data/processed/hourly.parquet` |
| tests | `amm test` | must report `43 passed` |
| calibrate | `amm calibrate --workers N` | writes `configs/frozen_policy.yaml` + `reports/calibration/` |
| smoke | `amm smoke --workers N` | ~3 min sanity run |
| benchmark | `amm benchmark --workers N` | full 2018-2024 comparison -> `reports/benchmark/` |

`N` is chosen automatically from cores and RAM (override: `-Workers 6`). Resume after an
interruption with `-SkipPrepare -SkipTests` (and `-SkipCalibrate` once
`configs/frozen_policy.yaml` exists). It also compares raw-file checksums with the laptop
(`memory\logs\checksum_compare.log`).

If the UCI cross-check download fails with a TLS/certificate error, that is expected and
harmless: the repo already contains `data/raw/manual/bike_sharing_dataset.zip`.

## 4. Share the results

```powershell
git add memory reports configs/frozen_policy.yaml
git commit -m "Big PC: calibration + benchmark results"
git push
```

Databases (`*.sqlite`) and model artifacts are git-ignored on purpose (hundreds of MB); the
CSV/JSON results, daily series, summaries and figures are enough for the docs and dashboard.

## 5. Optional: view the dashboard on the big PC

```powershell
.venv\Scripts\python -m streamlit run app/dashboard.py
```
