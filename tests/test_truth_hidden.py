"""Scenario truth (manifest, change point, scenario name) stays inaccessible to the controller."""

import copy
import inspect
import re
from pathlib import Path

import numpy as np
import pandas as pd

import amm
from amm.data.scenarios import Scenario
from amm.engine import train_initial
from amm.policy.controller import Controller
from amm.stream.simulator import ReplaySimulator
from conftest import make_scenario, make_session, small_cfg

SRC = Path(amm.__file__).parent


def test_controller_interface_has_no_truth_inputs():
    params = set(inspect.signature(Controller.__init__).parameters)
    assert not params & {"scenario", "manifest", "change", "change_point", "stream"}


def test_controller_side_modules_never_import_scenarios():
    for rel in ["policy", "monitoring", "stream/view.py", "models"]:
        files = [SRC / rel] if rel.endswith(".py") else list((SRC / rel).glob("*.py"))
        for f in files:
            text = f.read_text(encoding="utf-8")
            assert not re.search(r"^\s*(from|import)\s+amm\.data(\.scenarios|\s+import\s+.*scenarios)", text, re.M), f
            assert not re.search(r"\.manifest|change_seq\(", text), f


def _walk(obj, seen, depth=0):
    if id(obj) in seen or depth > 4:
        return
    seen.add(id(obj))
    yield obj
    if isinstance(obj, dict):
        children = list(obj.values())
    elif isinstance(obj, (list, tuple, set)):
        children = list(obj)
    elif hasattr(obj, "__dict__") and type(obj).__module__.startswith("amm"):
        children = list(vars(obj).values())
    else:
        children = []
    for c in children:
        yield from _walk(c, seen, depth + 1)


def test_controller_object_graph_holds_no_simulator_or_scenario(store, tmp_path):
    sc = make_scenario(change_day=3)
    s = make_session(sc, "adaptive", small_cfg(), store, tmp_path)
    s.run(max_steps=10)
    for o in _walk(s.controller, set()):
        assert not isinstance(o, (ReplaySimulator, Scenario))
        if isinstance(o, dict):
            assert "change" not in o or o is s.controller.cfg.get("scenarios")
    # the view only holds revealed labels
    lab = s.sim.view.labelled()
    first_unrevealed = s.sim._seq[s.sim.batch_slice(s.t - 1)].min()
    assert lab.seq.max() < first_unrevealed


def test_changing_the_hidden_manifest_does_not_change_decisions(tmp_path):
    from amm.storage.store import Store

    sc = make_scenario(change_day=3)
    cfg = small_cfg()
    init = train_initial(sc, cfg)
    sc2 = copy.deepcopy(sc)
    sc2.manifest["change"]["start"] = "2001-01-02 00:00:00"  # lie about the change point
    sc2.name = "renamed"
    runs = []
    for i, scen in enumerate((sc, sc2)):
        st = Store(tmp_path / f"{i}.sqlite")
        s = make_session(scen, "adaptive", cfg, st, tmp_path / str(i), initial=init, run_id="x")
        s.run()
        runs.append(([(e["step"], e["action"]) for e in s.controller.events],
                     st.query("SELECT y_pred FROM predictions WHERE run_id='x' ORDER BY seq, role")["y_pred"].to_numpy()))
    assert runs[0][0] == runs[1][0]
    np.testing.assert_allclose(runs[0][1], runs[1][1])
