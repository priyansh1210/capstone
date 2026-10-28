# STATE (read first)

Updated: 2026-10-28 by the laptop (Claude Code).

## Done

- Big PC (DESKTOP-RTIKELL) ran prepare-data, tests (43 passed), calibration v2 (13.1 min), smoke, full
  benchmark (11 min). Raw checksums identical to the laptop (106/106). Frozen values unchanged from v1.
- Laptop reproduced the frozen adaptive bike_unmodified run exactly (MAE 114.67) -> deterministic across machines.
- **Frozen result (primary):** periodic-28d best on real data (MAE 81.5 vs adaptive 114.7 vs static 136.6),
  adaptive avoids unnecessary retraining on stationary streams (0.6 vs 26 cycles, equal MAE).
- **Diagnosis:** adaptive got stuck 2020-04 .. 2022-09 because a model accepted during the COVID collapse
  had its reference rebased to ~4x normal, so all later alarms were dismissed.
- Post-hoc variant implemented (reference cap + bias trigger, OFF by default), 46 tests pass.

## Next action - BIG PC

```
git pull
powershell -ExecutionPolicy Bypass -File scripts\bigpc_run.ps1 -Workers 12 -OnlyPosthoc
git add memory reports
git commit -m "Big PC: post-hoc variant"
git push
```

## Then - LAPTOP

Write `docs/EVALUATION.md` results (frozen) + post-hoc section, README runtimes, presentation, rehearse demo.
