# Shared project memory (both machines)

This folder is the shared memory between the two machines that work on this project.
It travels with the git repository, so whatever one machine writes here the other sees
after `git pull`.

| Machine | Role |
|---|---|
| **Laptop** (i5-11300H, 4C/8T, 8 GB RAM) | Claude Code session (code, docs, decisions); accessed over Remote Desktop |
| **Big PC** (RTX 4000-class GPU, more RAM/cores) | heavy compute: data preparation, calibration, full benchmark |

## Protocol

1. **Before working** on either machine: `git pull`.
2. **Big PC** runs what `BIG_PC_RUNBOOK.md` says; `scripts\bigpc_run.ps1` appends every run to
   `RUNLOG.md`, writes logs to `memory/logs/` and a machine profile to `memory/machines/`.
3. **After working**: commit `memory/`, `reports/` (CSV/JSON/PNG/MD only - databases and model
   artifacts are git-ignored) and `configs/frozen_policy.yaml`, then `git push`.
4. **Laptop / Claude** pulls, reads `STATE.md` + `RUNLOG.md` + logs, writes docs from the results,
   and updates `STATE.md`.

## Files

| File | What it holds |
|---|---|
| `STATE.md` | current status and the next action - read this first |
| `BIG_PC_RUNBOOK.md` | exact commands for the big PC |
| `RUNLOG.md` | append-only log: when, which machine, which command, runtime, outcome |
| `machines/` | hardware/software profile of each machine (written by the run script) |
| `logs/` | console output of each heavy step |
| `laptop_SOURCES.json` | the laptop's raw-file checksums; the big PC's `data/raw/SOURCES.json` must match |
| `PUBLICATION_ROADMAP.md` | what is still needed to turn the capstone into a paper |

Long-form history and design decisions stay in `../BUILD_STATUS.md`.
