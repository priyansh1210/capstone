# Project instructions (shared by every machine and session)

- Read `memory/STATE.md` first, then `memory/RUNLOG.md`; long-form history is in `BUILD_STATUS.md`.
- This repo is worked on from two machines: the laptop (Claude Code, 8 GB RAM - use
  `--workers 2` at most) and a bigger PC (heavy compute via `scripts/bigpc_run.ps1`). Sync is
  git: pull before working, push after.
- Write anything the other machine needs to know into `memory/` (state, run results, decisions),
  never only into a chat.
- Policy thresholds come only from `configs/frozen_policy.yaml` produced by `amm calibrate` on
  development scenarios; never tune on the 2018-2024 evaluation replay. Disclose any design change
  informed by evaluation data in `BUILD_STATUS.md`.
- Do not commit `*.sqlite`, model artifacts or raw downloads (see `.gitignore`).
- Commit messages and PR bodies carry no AI-attribution lines.
