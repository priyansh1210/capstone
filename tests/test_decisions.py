"""Insufficient-data, cooldown, budget and duplicate-job decisions."""

from amm.policy.controller import State
from conftest import actions, make_scenario, make_session, small_cfg


def _waits(s):
    return [e["reason"] for e in s.controller.events if e["action"] == "WAIT"]


def test_waits_when_not_enough_validation_labels(store, tmp_path):
    sc = make_scenario()
    cfg = small_cfg(policy={"periodic_interval_batches": 1})
    s = make_session(sc, "periodic", cfg, store, tmp_path)
    s.run(max_steps=2)  # at step 1 only one replay day (24 h < 48 h) is labelled after the cutoff
    assert any("insufficient validation labels" in r for r in _waits(s))
    first_wait = next(e for e in s.controller.events if e["action"] == "WAIT")
    assert first_wait["state_to"] == "waiting" and s.controller.cycle == 0
    s.run(max_steps=3)
    assert s.controller.cycle >= 1  # once labels arrive, the waiting request proceeds


def test_cooldown_postpones_retraining(store, tmp_path):
    sc = make_scenario()
    cfg = small_cfg(policy={"periodic_interval_batches": 2, "cooldown_batches": 8})
    s = make_session(sc, "periodic", cfg, store, tmp_path)
    s.run(max_steps=14)
    assert any(r.startswith("cooldown") for r in _waits(s))
    starts = [e["step"] for e in s.controller.events if e["action"] == "RETRAIN_START"]
    assert all(b - a >= 8 for a, b in zip(starts, starts[1:]))


def test_budget_declines_further_cycles(store, tmp_path):
    sc = make_scenario()
    cfg = small_cfg(policy={"periodic_interval_batches": 4, "cooldown_batches": 0, "budget_cycles": 1})
    s = make_session(sc, "periodic", cfg, store, tmp_path)
    s.run()
    assert s.controller.cycle == 1
    assert "RETRAIN_DECLINED" in actions(s)
    declined = next(e for e in s.controller.events if e["action"] == "RETRAIN_DECLINED")
    assert "budget exhausted" in declined["reason"]


def test_no_second_job_while_training(store, tmp_path):
    sc = make_scenario()
    s = make_session(sc, "periodic", small_cfg(), store, tmp_path)
    c = s.controller
    c.state = State.RETRAINING
    assert c._blocked(10)[0] == "busy"
    # and the session lock refuses a concurrent step
    s.controller.state = State.SERVING
    assert s._lock.acquire(blocking=False)
    try:
        assert s.step() is False
    finally:
        s._lock.release()
    assert s.step() is True


def test_static_never_retrains(store, tmp_path):
    sc = make_scenario(change_day=2)
    s = make_session(sc, "static", small_cfg(), store, tmp_path)
    s.run()
    assert s.controller.cycle == 0 and "RETRAIN_START" not in actions(s)


def test_increase_detected_during_probation_is_investigated_afterwards(store, tmp_path):
    from amm.monitoring.monitor import Detection
    from amm.policy.probation import Probation

    sc = make_scenario()
    s = make_session(sc, "adaptive", small_cfg(), store, tmp_path)
    s.run(max_steps=4)
    c = s.controller
    c.state = State.OBSERVING
    c.probation = Probation("v001", "v000", 4, c.cfg)  # undecided probation
    c.new_detections = [Detection(4, 0, 0.2, 0.4, 100)]
    c.decide(4)
    assert c.events[-1]["action"] == "ALARM_DEFERRED" and c.deferred is not None
    c.probation.decision = "keep"
    c.registry._slots = ("v001", None)  # (keep() would retire the fake previous)
    c.probation = None
    c.state = State.SERVING
    c.decide(5)
    assert "ALARM" in [e["action"] for e in c.events[-2:]] and c.deferred is None


def test_posthoc_options_are_off_in_the_frozen_configuration():
    from amm.config import load_config

    cfg = load_config("configs/full.yaml")
    assert cfg["policy"]["reference_cap_factor"] is None and cfg["policy"]["bias_trigger"] is None


def test_reference_cap_bounds_an_inflated_reference(store, tmp_path):
    sc = make_scenario()
    s = make_session(sc, "adaptive", small_cfg(policy={"reference_cap_factor": 1.5}), store, tmp_path)
    c = s.controller
    c.registry.active.reference_signal = c.anchor * 4  # as after a probation during a shock
    assert abs(c._reference() - 1.5 * c.anchor) < 1e-12
    s2 = make_session(sc, "adaptive", small_cfg(), store, tmp_path, run_id="nocap")
    s2.controller.registry.active.reference_signal = s2.controller.anchor * 4
    assert s2.controller._reference() == s2.controller.anchor * 4  # off: unchanged


def test_bias_trigger_requests_an_update_on_persistent_level_shift(store, tmp_path):
    sc = make_scenario(change_day=1, factor=2.5)
    on = make_session(sc, "adaptive", small_cfg(policy={"bias_trigger": 0.15}), store, tmp_path, run_id="bias-on")
    on.run()
    acts = actions(on)
    assert "BIAS_CONFIRMED" in acts
    i = acts.index("BIAS_CONFIRMED")
    assert "RETRAIN_START" in acts[i:]  # same gates and validation as any other request
    off = make_session(sc, "adaptive", small_cfg(), store, tmp_path, run_id="bias-off")
    off.run()
    assert "BIAS_CONFIRMED" not in actions(off)


def test_probe_requests_update_only_when_challenger_is_significantly_better(store, tmp_path):
    cfg = small_cfg(probe={"interval_batches": 3, "window_days": 14, "min_gain": 0.05, "alpha": 0.1, "model": "ridge", "params": None},
                    retraining={"validation_hours": 168, "min_validation_hours": 120})
    changed = make_session(make_scenario(change_day=1, factor=2.5), "probe", cfg, store, tmp_path, run_id="probe-change")
    changed.run()
    probes = [e for e in changed.controller.events if e["action"] == "PROBE"]
    assert probes and changed.controller.probes == len(probes) and changed.controller.probe_seconds > 0
    hit = next(i for i, e in enumerate(changed.controller.events) if e["action"] == "PROBE" and "request full retraining" in e["reason"])
    assert "RETRAIN_START" in [e["action"] for e in changed.controller.events[hit:]]  # then the normal gate decides
    stable = make_session(make_scenario(), "probe", cfg, store, tmp_path, run_id="probe-stable")
    stable.run()
    sp = [e for e in stable.controller.events if e["action"] == "PROBE"]
    assert sp and stable.controller.cycle <= 1  # no change -> probes rarely justify an update


def test_oracle_attempts_at_supplied_steps_and_disabled_probation_promotes_directly(store, tmp_path):
    from amm.engine import train_initial

    sc = make_scenario(change_day=1, factor=2.5)
    cfg = small_cfg(retraining={"windows_days": [7]}, probation={"enabled": False})
    from amm.engine import Session

    s = Session(sc, "oracle", cfg, store, run_id="oracle", initial=train_initial(sc, cfg), artifact_root=tmp_path / "a", request_steps=[12])
    s.run()
    starts = [e["step"] for e in s.controller.events if e["action"] == "RETRAIN_START"]
    assert starts == [12]
    acts = actions(s)
    if "PROMOTED" in acts:  # without probation the old model is retired at once
        assert "PROBATION_CHECK" not in acts and s.controller.registry.previous_id is None


def test_alternative_detectors_run(store, tmp_path):
    sc = make_scenario(change_day=2, factor=2.5)
    for kind, params in (("page_hinkley", {"threshold": 5.0}), ("kswin", {"alpha": 0.005, "window_size": 100, "stat_size": 30})):
        s = make_session(sc, "adaptive", small_cfg(monitor={"detector": kind, "detector_params": params}), store, tmp_path, run_id=kind)
        s.run()
        assert s.finished
