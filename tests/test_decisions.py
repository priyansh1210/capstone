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
