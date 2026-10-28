"""Rehearse the classroom demo headlessly with the same LiveDemo object the
dashboard uses, and print what the audience would see at each step.

    .venv\\Scripts\\python scripts\\rehearse_demo.py [--start 2019-03-01] [--policy adaptive]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from amm.ui.live import LiveDemo  # noqa: E402


def show(demo: LiveDemo, since: int, title: str) -> int:
    k = demo.kpis()
    print(f"\n== {title} | {k['date']} state={k['state']} active={k['active']} ({k['active_model']}) "
          f"rolling MAE={k['rolling_mae'] if k['rolling_mae'] is None else round(k['rolling_mae'], 1)} "
          f"cycles={k['cycles']} promo/rej/rb={k['promotions']}/{k['rejections']}/{k['rollbacks']}")
    for e in demo.main.controller.events[since:]:
        if e["action"] in ("PROBATION_CHECK", "CHANGE_IGNORED"):
            continue
        flag = " [TEST-ONLY]" if e["fault_injection"] else ""
        print(f"   {e['ts'][:10]} {e['action']:<26}{flag} {e['reason'][:150]}")
    return len(demo.main.controller.events)


def run_until(demo: LiveDemo, actions: set, max_days: int) -> int:
    n0 = len(demo.main.controller.events)
    for d in range(max_days):
        demo.step(1)
        if any(e["action"] in actions for e in demo.main.controller.events[n0:]):
            return d + 1
    return max_days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2019-03-01")
    ap.add_argument("--policy", default="adaptive")
    ap.add_argument("--factor", type=float, default=1.6)
    a = ap.parse_args()
    t0 = time.time()
    demo = LiveDemo("bike_unmodified", a.policy, 1, compare_static=True)
    print(f"[rehearse] run created in {time.time() - t0:.1f}s")
    t0 = time.time()
    demo.fast_forward(pd.Timestamp(a.start))
    print(f"[rehearse] fast-forward to {a.start} took {time.time() - t0:.1f}s")
    seen = show(demo, 0, "1. normal operation (history so far)")
    demo.step(10)
    seen = show(demo, seen, "1b. ten more normal days")

    rec = demo.inject_demand_change(a.factor, [7, 8, 9, 16, 17, 18, 19], True)
    print(f"\n[rehearse] 2. injected: {rec}")
    d = run_until(demo, {"DETERIORATION_CONFIRMED"}, 40)
    seen = show(demo, seen, f"3. detection ({d} days after injection)")
    d = run_until(demo, {"PROMOTED"}, 60)
    seen = show(demo, seen, f"4. update decision (+{d} days)")
    d = run_until(demo, {"KEPT", "ROLLED_BACK"}, 30)
    seen = show(demo, seen, f"5. probation outcome (+{d} days)")
    dd = demo.daily()
    after = dd[dd["day"] >= pd.Timestamp(rec["from_date"])]
    print("   MAE since injection by policy:", after.groupby("policy")["mae"].mean().round(1).to_dict())

    demo.main.inject_weak_candidates()
    ok = demo.main.operator_request()
    d = run_until(demo, {"CANDIDATES_REJECTED", "PROMOTED", "TRAINING_FAILED"}, 20)
    seen = show(demo, seen, f"6a. weak candidate + operator request (operator ok={ok}, +{d} days)")

    while demo.main.controller.state.value != "serving":
        demo.step(1)
    demo.main.force_activate_weak()
    d = run_until(demo, {"ROLLED_BACK", "KEPT"}, 30)
    seen = show(demo, seen, f"6b. forced weak activation -> probation (+{d} days)")
    demo.save()
    print(f"\n[rehearse] checkpoint saved; total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
