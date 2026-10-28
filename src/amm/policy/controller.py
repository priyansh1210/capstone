"""The autonomous supervisor: an explicit, inspectable state machine.

States
------
SERVING        normal operation; the trigger is polled every step
INVESTIGATING  (adaptive) ADWIN reported an *increase* in error; collect
               evidence that error has really worsened before acting
WAITING        a retraining request exists but a gate blocks it (cooldown,
               insufficient eligible labels, job running); re-checked each step
RETRAINING     fitting candidates and running the validation gate (synchronous)
OBSERVING      probation after a promotion: paired active/previous predictions,
               then KEEP or ROLLBACK

The *only* difference between policies is the trigger (``_poll_trigger``):
static never asks, periodic asks on a fixed schedule, adaptive asks when a
detected error increase is confirmed as sustained deterioration, probe
(opportunity-aware) asks when a cheap challenger trained on recent labels
beats the current model significantly on the newest held-out days, and
oracle (evaluation baseline only) asks at evaluator-supplied steps. Everything
after the trigger - gates, budget, candidate training, validation gate,
promotion, probation and rollback - is shared code.

The controller sees the world only through a ControllerView (observed
covariates, revealed labels). It never receives the scenario name, the
scenario manifest or the hidden change point.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from amm.data.quality import outage_mask
from amm.metrics import SeasonalIndex, daily_median, months_of, scaled_error
from amm.models.candidates import make_model
from amm.models.registry import ArtifactSaveError, ModelVersion, Registry
from amm.monitoring import diagnostics
from amm.monitoring.monitor import Monitor
from amm.policy import evidence
from amm.policy.probation import Probation
from amm.policy.retrain import evaluate, fit_candidates, plan_cycle
from amm.storage.store import Store
from amm.stream.simulator import CovariateBatch, LabelBatch
from amm.stream.view import ControllerView

POLICIES = ("static", "periodic", "adaptive", "probe", "oracle")


class State(str, Enum):
    SERVING = "serving"
    INVESTIGATING = "investigating"
    WAITING = "waiting"
    RETRAINING = "retraining"
    OBSERVING = "observing"


@dataclass
class Pending:
    batch: int
    seq: np.ndarray
    yhat: np.ndarray
    version: str
    shadow_yhat: np.ndarray | None = None
    shadow_version: str | None = None


def _r(x, nd=4):
    return None if x is None else round(float(x), nd)


class Controller:
    def __init__(
        self,
        policy: str,
        cfg: dict,
        view: ControllerView,
        registry: Registry,
        store: Store,
        run_id: str,
        seed: int,
        profiles: dict | None = None,
        warm: dict | None = None,
        index: SeasonalIndex | None = None,
        request_steps: list[int] | None = None,
    ):
        if policy not in POLICIES:
            raise ValueError(f"unknown policy {policy}")
        self.policy, self.cfg, self.view, self.registry = policy, cfg, view, registry
        self.store, self.run_id, self.seed = store, run_id, seed
        mc = cfg["monitor"]
        self.index = index or SeasonalIndex()
        self.monitor = Monitor(mc["adwin_delta"], mc["adwin_clock"], mc["rolling_hours"], warm_hours=mc.get("warm_start_hours", 672),
                               detector=mc.get("detector", "adwin"),
                               detector_params=mc.get("detector_params") or (cfg.get("detectors") or {}).get(mc.get("detector", "adwin")) or {})
        self.monitor.reset(0, warm=(warm or {}).get(registry.active_id))
        self.state = State.SERVING
        self.pending: dict[int, Pending] = {}
        self.events: list[dict] = []
        self.cycle = 0
        self.fits = 0
        self.train_seconds = 0.0
        self.last_cycle_step: int | None = None
        self.interval = int(cfg["policy"]["periodic_interval_batches"])
        self.next_periodic_step = self.interval
        self.request: dict | None = None
        self.investigation: dict | None = None
        self.probation: Probation | None = None
        self.wait_reason: str | None = None
        self.new_detections = []
        self.persist_check = False  # adaptive: re-check deterioration after a rejected update
        self.deferred = None  # adaptive: increase detected during probation, investigated afterwards
        # Post-hoc options (both off in the frozen evaluation; see docs/EVALUATION.md "Post-hoc analysis"):
        pc = cfg["policy"]
        self.ref_cap = pc.get("reference_cap_factor")  # cap reference at k x calibration anchor
        self.bias_trigger = pc.get("bias_trigger")  # |total-demand bias| that requests an update
        self.anchor = float(registry.active.reference_signal)  # initial model's calibration error level
        self.bias_count = 0
        # Probe policy (opportunity-aware) state and cost accounting
        self.pcfg = cfg.get("probe", {})
        self.next_probe_step = int(self.pcfg.get("interval_batches", 7))
        self.last_probe_step = -10**9
        self.probes = 0
        self.probe_seconds = 0.0
        # Oracle baseline: retraining requests at evaluator-supplied steps (breaks the
        # information boundary on purpose; it is an upper-bound reference, never a policy).
        self.request_steps = sorted(set(request_steps or []))
        self.probation_enabled = cfg["probation"].get("enabled", True)
        self.fault = {"weak_candidates": False, "fail_training": set(), "fail_save": False}
        self.profiles = profiles or {}  # version -> training input profile (diagnostics)
        self.warm = dict(warm or {})  # version -> reference-window detector signal (ADWIN warm start)
        self._y_tail = np.array([])  # last revealed labels, to detect outage runs across batch edges
        self.now_ts = None

    # ================================================================ logging
    def _log(self, step, action, reason, meas=None, thr=None, to: State | None = None, fault=False):
        s_from = self.state.value
        if to is not None:
            self.state = to
        ev = {
            "event_id": len(self.events) + 1,
            "step": step,
            "ts": str(self.now_ts),
            "state_from": s_from,
            "state_to": self.state.value,
            "action": action,
            "reason": reason,
            "measurements": meas or {},
            "thresholds": thr or {},
            "fault_injection": fault,
        }
        self.events.append(ev)
        self.store.add_decision(
            self.run_id, ev["event_id"], step, ev["ts"], s_from, ev["state_to"], action, reason, ev["measurements"], ev["thresholds"], fault
        )
        return ev

    def _save_version(self, v: ModelVersion):
        self.store.upsert_version(self.run_id, v.record())

    # ============================================================ label phase
    def on_labels(self, step: int, lb: LabelBatch) -> None:
        p = self.pending.pop(lb.batch, None)
        if p is None:
            return
        if not np.array_equal(p.seq, lb.seq):
            raise RuntimeError("revealed labels do not match stored predictions")
        y = lb.y
        abs_e, sc = np.abs(y - p.yhat), scaled_error(y, p.yhat)
        rows = [(float(y[i]), float(abs_e[i]), float(sc[i]), self.run_id, int(p.seq[i]), "active") for i in range(len(y))]
        if p.shadow_yhat is not None:
            ae2, sc2 = np.abs(y - p.shadow_yhat), scaled_error(y, p.shadow_yhat)
            rows += [(float(y[i]), float(ae2[i]), float(sc2[i]), self.run_id, int(p.seq[i]), "shadow") for i in range(len(y))]
        self.store.score_predictions(rows)
        # Monitor only the errors of the model that is active *now*; outcomes
        # of a replaced model's predictions are scored but not held against it.
        months = months_of(lb.ts)
        # Outage hours (>= 6 consecutive zero-trip hours in *revealed* labels) are
        # system closures, not model errors: scored above, but not monitored.
        tail = self._y_tail
        ok = ~outage_mask(np.concatenate([tail, y]))[len(tail):]
        self._y_tail = np.concatenate([tail, y])[-12:]
        if p.version == self.registry.active_id:
            sig = self.index.signal(sc, months)
            self.new_detections += self.monitor.update(step, p.seq[ok], y[ok], p.yhat[ok], sig[ok])
        pb = self.probation
        if pb and p.version == pb.new and p.shadow_version == pb.prev and ok.any():
            for w in pb.add(y[ok], p.yhat[ok], p.shadow_yhat[ok], months[ok], lb.ts[ok]):
                self._log(
                    step,
                    "PROBATION_CHECK",
                    f"window {w['window']}: new MAE {w['mae_new']:.1f} vs previous {w['mae_prev']:.1f} "
                    f"on the same {w['n']} hours ({'new worse' if w['new_worse'] else 'not worse'} by margin)",
                    {k: _r(v) if isinstance(v, float) else v for k, v in w.items()},
                    {"rollback_rel_margin": pb.margin, "consecutive_windows": pb.need, "max_windows": pb.max_windows},
                )

    # =========================================================== decide phase
    def decide(self, step: int) -> None:
        if self.state == State.OBSERVING:
            self._note_trigger_while_busy(step)
            self._decide_observing(step)
            return
        if self.state == State.SERVING:
            if self.request is not None:  # e.g. a periodic attempt postponed by probation
                self._log(step, "RETRAIN_REQUESTED", f"{self.request['reason']} - resuming", to=State.WAITING)
                req = None
            else:
                req = self._poll_trigger(step)
            if req is None and self.state == State.SERVING:
                return
        else:
            # detections while investigating/waiting add nothing to the open case
            self.new_detections = []
            req = None
        if req is not None:
            if req["kind"] == "alarm":
                d = req["detection"]
                self.investigation = {"start": step, "confirmations": 0, "checks": []}
                self._log(
                    step,
                    "ALARM",
                    "ADWIN detected an increase in the scaled error stream; investigating whether error has really worsened",
                    {"adwin_mean_before": _r(d.est_before), "adwin_mean_after": _r(d.est_after), "adwin_width": d.width_after},
                    {"adwin_delta": self.cfg["monitor"]["adwin_delta"]},
                    to=State.INVESTIGATING,
                )
            else:
                self.request = req
                self._log(step, "RETRAIN_REQUESTED", req["reason"], {}, {"interval_batches": self.interval}, to=State.WAITING)
        if self.state == State.INVESTIGATING:
            self._investigate(step)
        if self.state == State.WAITING:
            self._wait_or_train(step)

    # ---------------------------------------------------------------- trigger
    def _poll_trigger(self, step: int) -> dict | None:
        if self.policy == "static":
            return None
        if self.policy == "periodic":
            if step >= self.next_periodic_step:
                self.next_periodic_step = step + self.interval
                return {"kind": "schedule", "reason": f"periodic schedule: retraining attempt every {self.interval} batches", "step": step}
            return None
        if self.policy == "oracle":
            due = [r for r in self.request_steps if r <= step]
            if due:
                self.request_steps = [r for r in self.request_steps if r > step]
                return {"kind": "oracle", "reason": "ORACLE baseline: evaluator-scheduled attempt after the known change", "step": step}
            return None
        if self.policy == "probe":
            return self._probe_trigger(step)
        dets, self.new_detections = self.new_detections, []
        if self.deferred is not None:
            dets = [self.deferred] + dets
            self.deferred = None
        # After a rejected/failed update the deterioration may persist while ADWIN
        # has already adapted to the higher error level; re-check once the
        # cooldown has passed instead of waiting for a fresh alarm.
        if self.persist_check and self._blocked(step) is None:
            ev = evidence.deterioration(self.monitor, self._reference(), self.cfg)
            self.persist_check = False
            if ev["deteriorated"]:
                self._log(
                    step,
                    "DETERIORATION_PERSISTS",
                    f"deterioration still present after the last update attempt ({ev['reason']}); requesting another attempt",
                    {k: _r(v) if isinstance(v, float) else v for k, v in ev.items() if k != "reason"},
                    {"cooldown_batches": self.cfg["policy"]["cooldown_batches"]},
                    to=State.WAITING,
                )
                self.request = {"kind": "deterioration", "reason": "deterioration persists after rejected update", "step": step}
                return None
        if self.bias_trigger and self._bias_check(step):
            return None
        if not dets:
            return None
        inc = [d for d in dets if d.increase]
        if not inc:
            d = dets[-1]
            self._log(
                step,
                "CHANGE_IGNORED",
                "ADWIN detected a change, but error decreased; no action",
                {"adwin_mean_before": _r(d.est_before), "adwin_mean_after": _r(d.est_after)},
            )
            return None
        return {"kind": "alarm", "detection": inc[-1], "step": step}

    def _probe_trigger(self, step: int) -> dict | None:
        """Opportunity-aware trigger: every ``interval_batches`` (sooner when the drift
        detector reports an error increase), fit ONE cheap challenger on recent revealed
        labels and compare it with the current model on the newest eligible held-out
        days. Request a full retraining cycle only if the challenger is better by at
        least ``min_gain`` and a one-sided paired t-test over daily MAE gives p <= alpha.
        No self-reference is involved, so a reference cannot be inflated, and a still
        attainable improvement is visible even when error has not risen."""
        pc = self.pcfg
        dets, self.new_detections = self.new_detections, []
        accel = bool(pc.get("accelerate", True)) and any(d.increase for d in dets) and step - self.last_probe_step >= int(pc.get("min_gap_batches", 3))
        if step < self.next_probe_step and not accel:
            return None
        if self._blocked(step) is not None:
            return None  # cooldown/budget: try again on the next step
        self.last_probe_step = step
        self.next_probe_step = step + int(pc.get("interval_batches", 7))
        r = self._probe(step, accel)
        if r.get("worthwhile"):
            return {"kind": "probe", "reason": f"probe: challenger {r['gain']:+.1%} MAE vs current on {r['n_days']} held-out days (p={r['p']:.3f})", "step": step}
        return None

    def _probe(self, step: int, accelerated: bool) -> dict:
        import time

        from scipy import stats
        from threadpoolctl import threadpool_limits

        pc = self.pcfg
        data = self.view.labelled()
        plan, why = plan_cycle(data, self.registry.active.selection_end_seq, self.cfg)
        if plan is None:
            return {"worthwhile": False, "reason": why}
        first_val = plan.val_idx[0]
        lo = data.ts[first_val] - np.timedelta64(int(pc.get("window_days", 120)), "D")
        before = np.arange(first_val)
        keep = ~outage_mask(data.y[:first_val])
        idx = before[(data.ts[before] >= lo) & keep]
        if len(idx) < self.cfg["retraining"]["min_train_hours"]:
            return {"worthwhile": False, "reason": "insufficient recent training labels for a probe"}
        sub, v = data.take(idx), data.take(plan.val_idx)
        t0 = time.perf_counter()
        with threadpool_limits(self.cfg["retraining"]["threads"]):
            ch = make_model(pc.get("model", "hgb"), seed=self.seed + step, params=pc.get("params")).fit(sub.X, sub.y)
        secs = time.perf_counter() - t0
        self.probes += 1
        self.probe_seconds += secs
        cur_e = np.abs(v.y - self.registry.model(self.registry.active_id).predict(v.X))
        ch_e = np.abs(v.y - ch.predict(v.X))
        day = v.ts.astype("datetime64[D]")
        d_cur = pd.Series(cur_e).groupby(day).mean()
        d_ch = pd.Series(ch_e).groupby(day).mean()
        diff = (d_cur - d_ch).to_numpy()
        gain = float((cur_e.mean() - ch_e.mean()) / max(cur_e.mean(), 1e-9))
        p = float(stats.ttest_1samp(diff, 0.0, alternative="greater").pvalue) if len(diff) >= 5 and diff.std() > 0 else 1.0
        ok = gain >= float(pc.get("min_gain", 0.05)) and p <= float(pc.get("alpha", 0.1))
        self._log(
            step, "PROBE",
            f"{'drift-accelerated ' if accelerated else ''}probe: challenger {gain:+.1%} vs current on {len(diff)} held-out days, p={p:.3f} -> "
            + ("request full retraining" if ok else "no update needed"),
            {"gain": _r(gain), "p": _r(p), "n_days": int(len(diff)), "seconds": _r(secs, 3), "accelerated": accelerated},
            {"min_gain": pc.get("min_gain", 0.05), "alpha": pc.get("alpha", 0.1), "window_days": pc.get("window_days", 120)},
        )
        return {"worthwhile": ok, "gain": gain, "p": p, "n_days": int(len(diff))}

    def _bias_check(self, step: int) -> bool:
        """Persistent total-demand bias is evidence that a refit can help even when
        error is not worse than the model's own reference (e.g. after a partial
        adaptation). Confirmed on the same number of consecutive daily checks."""
        dc = self.cfg["policy"]["deterioration"]
        w = self.monitor.window(dc["recent_hours"])
        if w["n"] < dc["recent_hours"] // 2 or w["bias"] is None:
            self.bias_count = 0
            return False
        self.bias_count = self.bias_count + 1 if abs(w["bias"]) >= float(self.bias_trigger) else 0
        if self.bias_count >= dc["confirm_checks"] and self._blocked(step) is None:
            self.bias_count = 0
            direction = "over" if w["bias"] > 0 else "under"
            self.request = {"kind": "bias", "reason": f"persistent bias: model {direction}-predicts total demand by {abs(w['bias']):.0%}", "step": step}
            self._log(step, "BIAS_CONFIRMED", self.request["reason"] + f" over {w['n']} labelled hours on {dc['confirm_checks']} consecutive checks",
                      {"bias": _r(w["bias"]), "recent_mae": _r(w["mae"], 2)}, {"bias_trigger": self.bias_trigger}, to=State.WAITING)
            return True
        return False

    def _note_trigger_while_busy(self, step: int) -> None:
        # Periodic schedule points falling inside probation are postponed, not skipped.
        if self.policy == "periodic" and step >= self.next_periodic_step and self.request is None:
            self.next_periodic_step = step + self.interval
            self.request = {"kind": "schedule", "reason": f"periodic schedule (postponed until probation ends)", "step": step}
            self._log(step, "RETRAIN_POSTPONED", "scheduled attempt postponed: a promoted model is under probation")
        if self.policy == "adaptive":
            # An error increase detected *during* probation is deferred, not dropped:
            # ADWIN has already absorbed it, so discarding it would hide a change that
            # starts while a new model is on probation. It is investigated once
            # probation ends.
            inc = [d for d in self.new_detections if d.increase]
            if inc and self.deferred is None:
                self.deferred = inc[-1]
                self._log(step, "ALARM_DEFERRED", "ADWIN detected an error increase during probation; will investigate after probation",
                          {"adwin_mean_before": _r(inc[-1].est_before), "adwin_mean_after": _r(inc[-1].est_after)})
            self.new_detections = []

    # ---------------------------------------------------------- investigation
    def _reference(self) -> float:
        ref = float(self.registry.active.reference_signal)
        if self.ref_cap:
            # A model accepted during a shock (e.g. COVID-19) can carry an inflated
            # reference that then masks all later deterioration; never let the bar
            # exceed k x the error level shown to be achievable on calibration data.
            ref = min(ref, self.anchor * float(self.ref_cap))
        return ref

    def signal(self, y, yhat, ts) -> np.ndarray:
        return self.index.signal(scaled_error(y, yhat), months_of(ts))

    def _investigate(self, step: int) -> None:
        inv = self.investigation
        ev = evidence.deterioration(self.monitor, self._reference(), self.cfg)
        inv["confirmations"] = inv["confirmations"] + 1 if ev["deteriorated"] else 0
        inv["checks"].append(bool(ev["deteriorated"]))
        dc = self.cfg["policy"]["deterioration"]
        if inv["confirmations"] >= dc["confirm_checks"]:
            shift = diagnostics.input_shift(self.profiles.get(self.registry.active_id), self.view.recent_covariates(dc["recent_hours"]))
            text = diagnostics.explain(ev, shift, ev.get("bias"))
            self.request = {"kind": "deterioration", "reason": f"sustained deterioration: {text}", "step": step}
            self._log(
                step,
                "DETERIORATION_CONFIRMED",
                self.request["reason"],
                {**{k: _r(v) if isinstance(v, float) else v for k, v in ev.items() if k != "reason"}, "input_shift": shift},
                {"confirm_checks": dc["confirm_checks"], "rel_margin": dc["rel_margin"], "abs_margin": dc["abs_margin"]},
                to=State.WAITING,
            )
            self.investigation = None
        elif step - inv["start"] >= dc["investigate_max_batches"]:
            self._log(
                step,
                "ALARM_DISMISSED",
                f"statistical change signal not accompanied by sustained deterioration ({ev['reason']})",
                {"recent_signal": _r(ev["recent_signal"]), "reference_signal": _r(ev["reference_signal"]), "recent_mae": _r(ev["recent_mae"], 2), "checks": inv["checks"]},
                {"confirm_checks": dc["confirm_checks"], "investigate_max_batches": dc["investigate_max_batches"]},
                to=State.SERVING,
            )
            self.investigation = None

    # ------------------------------------------------------------------ gates
    def _blocked(self, step: int) -> tuple[str, str] | None:
        pc = self.cfg["policy"]
        if self.cycle >= pc["budget_cycles"]:
            return "budget", f"retraining budget exhausted ({self.cycle}/{pc['budget_cycles']} cycles)"
        if self.state == State.RETRAINING:
            return "busy", "a training job is already running"
        if self.last_cycle_step is not None and step - self.last_cycle_step < pc["cooldown_batches"]:
            return "cooldown", f"cooldown: {step - self.last_cycle_step} of {pc['cooldown_batches']} batches since last cycle"
        return None

    def _wait_or_train(self, step: int) -> None:
        if self.request and self.request["kind"] == "deterioration":
            ev = evidence.deterioration(self.monitor, self._reference(), self.cfg)
            if not ev["deteriorated"] and ev["ratio"] is not None:
                self._log(step, "DETERIORATION_RESOLVED", f"error back below threshold while waiting ({ev['reason']})", {"recent_signal": _r(ev["recent_signal"])}, to=State.SERVING)
                self.request, self.wait_reason = None, None
                return
        blocked = self._blocked(step)
        if blocked:
            kind, reason = blocked
            if kind == "budget":
                self._log(step, "RETRAIN_DECLINED", reason, {"cycles": self.cycle}, {"budget_cycles": self.cfg["policy"]["budget_cycles"]}, to=State.SERVING)
                self.request, self.wait_reason = None, None
                return
            if reason.split(":")[0] != (self.wait_reason or "").split(":")[0]:
                self._log(step, "WAIT", reason, {}, {"cooldown_batches": self.cfg["policy"]["cooldown_batches"]})
            self.wait_reason = reason
            return
        data = self.view.labelled()
        plan, why = plan_cycle(data, self.registry.active.selection_end_seq, self.cfg)
        if plan is None:
            if why != self.wait_reason:
                self._log(step, "WAIT", why, {"labelled_rows": len(data)}, {k: self.cfg["retraining"][k] for k in ("min_validation_hours", "min_train_hours")})
            self.wait_reason = why
            return
        self._retrain(step, plan, data)

    # -------------------------------------------------------------- retrain
    def _retrain(self, step: int, plan, data) -> None:
        rc = self.cfg["retraining"]
        self.cycle += 1
        cyc = self.cycle
        self.last_cycle_step = step
        weak = self.fault["weak_candidates"]
        names = ["weak_hgb"] if weak else list(rc["models"])
        self.fault["weak_candidates"] = False
        trigger = self.request or {"kind": "?", "reason": "?"}
        self._log(
            step,
            "RETRAIN_START",
            f"cycle {cyc} ({trigger['kind']}): fitting {len(names) * len(plan.train_idx)} candidates"
            + (" [TEST-ONLY: deliberately weak candidate pool]" if weak else ""),
            {"windows_rows": {str(w): int(len(i)) for w, i in plan.train_idx.items()}, "validation": [plan.val_start, plan.val_end], "n_val": int(len(plan.val_idx))},
            {"windows_days": rc["windows_days"], "validation_hours": rc["validation_hours"]},
            to=State.RETRAINING,
            fault=weak,
        )
        cands = fit_candidates(data, plan, names, self.seed + cyc, rc["threads"], fail=self.fault["fail_training"])
        secs = float(sum(c.seconds for c in cands))
        self.fits += len(cands)
        self.train_seconds += secs
        current = self.registry.model(self.registry.active_id)
        gate = evaluate(current, cands, data, plan, self.cfg)
        win = gate["winner"]
        fitted = [c for c in cands if c.model is not None]
        cur = gate["current"]
        scores = [
            {"model": c.name, "window_days": c.window_days, "val_mae": _r(c.val.get("mae"), 2), "rel_improvement": _r(c.rel_improvement), "passed": c.passed, "seconds": _r(c.seconds, 2), "error": c.error}
            for c in cands
        ]
        outcome = "rejected"
        v = None
        if not fitted:
            outcome = "failed"
            self._log(step, "TRAINING_FAILED", "all candidate fits failed; current model keeps serving", {"candidates": scores}, to=State.SERVING)
        elif win is None:
            best = min(fitted, key=lambda c: c.val.get("mae", np.inf))
            v = self._version_from(best, plan, cyc, step, status="rejected", weak=weak)
            self.registry.add_record(v)
            self._log(
                step,
                "CANDIDATES_REJECTED",
                f"no candidate beat the current model's validation MAE {cur['mae']:.1f} by >= {rc['min_rel_improvement']:.0%} "
                f"(best {best.name}/{best.window_days}d MAE {best.val['mae']:.1f}, {best.rel_improvement:+.1%}); keeping current model",
                {"current_val_mae": _r(cur["mae"], 2), "candidates": scores, "n_val": gate["n_val"]},
                gate["thresholds"],
                to=State.SERVING,
                fault=weak,
            )
        else:
            v = self._version_from(win, plan, cyc, step, status="candidate", weak=weak)
            try:
                if self.fault["fail_save"]:
                    raise ArtifactSaveError("injected artifact save failure")
                prev = self.registry.active_id
                self.registry.promote(v, win.model, step)
            except ArtifactSaveError as exc:
                outcome = "save_failed"
                v.status = "failed"
                v.notes = str(exc)
                self.registry.add_record(v)
                self._log(step, "PROMOTION_FAILED", f"{exc}; current model keeps serving", {"candidates": scores}, to=State.SERVING)
            else:
                outcome = "promoted"
                self.profiles[v.version] = diagnostics.input_profile(data.take(plan.train_idx[win.window_days]).X)
                self.probation = Probation(v.version, prev, step, self.cfg)
                vd = data.take(plan.val_idx)
                keep = ~outage_mask(vd.y)
                val_signal = self.signal(vd.y[keep], win.model.predict(vd.X)[keep], vd.ts[keep])
                v.reference_signal = daily_median(val_signal, vd.ts[keep])
                self.warm[v.version] = val_signal
                self.monitor.reset(step, warm=val_signal)
                self.new_detections = []
                if not self.probation_enabled:  # ablation: no post-promotion observation / rollback
                    self.probation = None
                    self.registry.keep(step)
                self._log(
                    step,
                    "PROMOTED",
                    f"{v.version} ({win.name}, {win.window_days}d window) validation MAE {win.val['mae']:.1f} vs current {cur['mae']:.1f} "
                    f"({win.rel_improvement:+.1%}); {prev} kept as fallback during probation",
                    {"current_val_mae": _r(cur["mae"], 2), "winner_val_mae": _r(win.val["mae"], 2), "candidates": scores, "n_val": gate["n_val"]},
                    gate["thresholds"],
                    to=State.OBSERVING if self.probation_enabled else State.SERVING,
                    fault=weak,
                )
                self._save_version(self.registry.versions[prev])
        if v is not None:
            self._save_version(v)
        for c in cands:
            self.store.add_candidate(
                (
                    self.run_id, cyc, c.name, c.window_days, step, c.n_train, c.train_start, c.train_end,
                    c.val.get("mae"), c.val.get("rmse"), c.val.get("scaled"), cur["mae"], c.rel_improvement,
                    int(c.passed), int(win is c and outcome == "promoted"), c.seconds, c.error,
                )
            )
        self.store.add_cycle(
            (self.run_id, cyc, step, trigger["kind"], outcome, len(cands), secs, plan.val_start, plan.val_end, gate["n_val"], cur["mae"],
             min((c.val["mae"] for c in fitted), default=None))
        )
        self.persist_check = trigger["kind"] == "deterioration" and outcome != "promoted"
        self.request, self.wait_reason = None, None
        # fitted candidate models other than the promoted one are discarded here

    def _version_from(self, c, plan, cyc, step, status, weak=False) -> ModelVersion:
        return ModelVersion(
            version=self.registry.next_id(),
            model_name=c.name,
            window_days=c.window_days,
            status=status,
            train_start=c.train_start,
            train_end=c.train_end,
            train_end_seq=c.train_end_seq,
            n_train=c.n_train,
            val_start=plan.val_start,
            val_end=plan.val_end,
            val_end_seq=plan.val_end_seq,
            n_val=int(len(plan.val_idx)),
            val_mae=c.val.get("mae"),
            val_rmse=c.val.get("rmse"),
            val_scaled=c.val.get("scaled"),
            reference_mae=c.val.get("mae"),
            reference_scaled=c.val.get("scaled"),
            reference_source="validation",
            train_seconds=c.seconds,
            cycle=cyc,
            created_step=step,
            fault_injection=weak,
            notes="TEST-ONLY weak candidate pool" if weak else "",
        )

    # ------------------------------------------------------------ probation
    def _decide_observing(self, step: int) -> None:
        pb = self.probation
        if pb is None or pb.decision is None:
            return
        s = pb.summary()
        meas = {k: _r(v) for k, v in s.items() if k != "windows"} | {"windows": s["windows"]}
        new, prev = pb.new, pb.prev
        if pb.decision == "rollback":
            self.registry.rollback(step)
            restored = self.registry.active
            # Rebase on the *paired* live error of the restored model: the
            # environment may have changed for both models.
            # The restored model returns to the reference on which it was
            # originally accepted (a rebase on the probation window could be
            # inflated by an anomaly and mask later deterioration).
            restored.reference_source = (restored.reference_source or "") + "; restored after rollback"
            self.monitor.reset(step, warm=self.warm.get(prev))
            self.new_detections = []
            self.deferred = None  # it measured the rolled-back model
            self.last_cycle_step = step  # cooldown restarts: prevents promote/rollback loops
            self._log(
                step,
                "ROLLED_BACK",
                f"{new} was worse than {prev} by >= {pb.margin:.0%} MAE in {pb.need} consecutive paired windows; {prev} reactivated",
                meas,
                {"rollback_rel_margin": pb.margin, "consecutive_windows": pb.need},
                to=State.SERVING,
                fault=self.registry.versions[new].fault_injection,
            )
        else:
            self.registry.keep(step)
            active = self.registry.active
            # Rebase on validation + live probation evidence (daily medians):
            # the selected model's validation error alone is optimistically biased.
            live = self.index.signal(scaled_error(np.asarray(pb.all_y, float), np.asarray(pb.all_new, float)), np.asarray(pb.all_m, int))
            live_ref = daily_median(live, np.asarray(pb.all_ts, dtype="datetime64[ns]"))
            active.reference_signal = float(np.median([active.reference_signal, live_ref]))
            active.reference_scaled = s["scaled_new"]
            active.reference_mae = s["mae_new"]
            active.reference_source = "median(validation, live probation)"
            self._log(
                step,
                "KEPT",
                f"probation passed: {new} not consistently worse than {prev} (paired MAE {s['mae_new']:.1f} vs {s['mae_prev']:.1f}); {prev} retired",
                meas,
                {"rollback_rel_margin": pb.margin, "consecutive_windows": pb.need},
                to=State.SERVING,
            )
        self._save_version(self.registry.versions[new])
        self._save_version(self.registry.versions[prev])
        self.probation = None

    # ========================================================= predict phase
    def predict(self, step: int, cb: CovariateBatch, reveal_step: int) -> None:
        act = self.registry.active_id
        yhat = self.registry.model(act).predict(cb.X)
        ts = [str(pd.Timestamp(t)) for t in cb.ts]
        rows = [(self.run_id, int(cb.seq[i]), "active", ts[i], cb.batch, act, float(yhat[i]), step, reveal_step) for i in range(len(yhat))]
        p = Pending(cb.batch, cb.seq, yhat, act)
        if self.probation is not None and self.state == State.OBSERVING:
            prev = self.registry.previous_id
            ys = self.registry.model(prev).predict(cb.X)
            p.shadow_yhat, p.shadow_version = ys, prev
            rows += [(self.run_id, int(cb.seq[i]), "shadow", ts[i], cb.batch, prev, float(ys[i]), step, reveal_step) for i in range(len(ys))]
        self.store.add_predictions(rows)
        self.pending[cb.batch] = p

    def record_step(self, step: int) -> None:
        r = self.monitor.rolling()
        self.store.add_step(
            (self.run_id, step, str(self.now_ts), self.state.value, self.registry.active_id, self.monitor.n,
             r["mae"], r["rmse"], r["scaled"], self.monitor.adwin_width, self.cycle, self.fits, self.train_seconds + self.probe_seconds)
        )

    # ======================================================= operator / fault injection
    def operator_request(self, step: int) -> bool:
        """A human asks for a retraining attempt (logged). It goes through the
        same gates, candidate training, validation gate and probation."""
        if self.state != State.SERVING or self.request is not None:
            self._log(step, "OPERATOR_REQUEST_REFUSED", f"operator request ignored while {self.state.value}")
            return False
        self.request = {"kind": "operator", "reason": "operator requested a retraining attempt", "step": step}
        self._log(step, "OPERATOR_REQUEST", "operator requested a retraining attempt; normal gates apply", to=State.WAITING)
        return True

    def inject_weak_candidates(self, step: int) -> None:
        self.fault["weak_candidates"] = True
        self._log(
            step,
            "FAULT_INJECTION",
            "TEST-ONLY: the next retraining cycle will fit only a deliberately weak candidate (predictions scaled by 0.45); "
            "the validation gate runs unchanged",
            fault=True,
        )

    def force_activate_weak(self, step: int) -> bool:
        """TEST-ONLY: activate a deliberately weak model *bypassing the validation
        gate*, so that probation and rollback can be demonstrated for real."""
        if self.state != State.SERVING or self.registry.previous_id is not None:
            self._log(step, "FAULT_INJECTION_REFUSED", f"forced activation only possible while serving (state={self.state.value})", fault=True)
            return False
        data = self.view.labelled()
        lo = data.ts[-1] - np.timedelta64(365, "D")
        idx = np.flatnonzero((data.ts >= lo) & ~outage_mask(data.y))
        sub = data.take(idx)
        model = make_model("weak_hgb", seed=self.seed).fit(sub.X, sub.y)
        v = ModelVersion(
            version=self.registry.next_id(), model_name="weak_hgb", window_days=365, status="candidate",
            train_start=str(pd.Timestamp(sub.ts[0])), train_end=str(pd.Timestamp(sub.ts[-1])), train_end_seq=int(sub.seq[-1]),
            n_train=len(sub), val_end_seq=int(sub.seq[-1]), created_step=step, fault_injection=True,
            reference_scaled=self.registry.active.reference_scaled, reference_mae=self.registry.active.reference_mae,
            reference_signal=self.registry.active.reference_signal,
            reference_source="inherited (forced activation, no validation)",
            notes="TEST-ONLY forced activation of a deliberately weak model, validation gate bypassed",
        )
        prev = self.registry.active_id
        self.registry.promote(v, model, step)
        self.probation = Probation(v.version, prev, step, self.cfg)
        self.monitor.reset(step)
        self.new_detections = []
        self._save_version(v)
        self._save_version(self.registry.versions[prev])
        self._log(
            step,
            "FAULT_INJECTION_ACTIVATION",
            f"TEST-ONLY: {v.version} (deliberately weak) activated WITHOUT validation; {prev} kept as fallback; probation and rollback logic run normally",
            {"weak_version": v.version, "fallback": prev},
            to=State.OBSERVING,
            fault=True,
        )
        return True
