"""W-01: a measured view of a tiny recorded network, never its hidden state."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from solver_fixtures import line
from ug_cli.export import export_run
from ug_core.assumptions import load_assumptions
from ug_core.runner import run_scenario
from ug_core.store.run import RunStore
from ug_core.truth import TruthEvent
from ug_water.adapter import WaterAdapter
from ug_water.network.model import Sensor

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    network = replace(
        line(40),
        sensors=(Sensor("P1", "pressure", "j1"),),
        sensor_sets={"S_base": ("P1",)},
    )
    monkeypatch.setattr(WaterAdapter, "asset_model", lambda self, config: network)
    solver_type = type(WaterAdapter().solver())
    original = solver_type.run

    def with_private_event(self, *args):
        physical = original(self, *args)
        return replace(physical, events=(TruthEvent("PRIVATE_SENTINEL", "j1", 0),))

    monkeypatch.setattr(solver_type, "run", with_private_event)
    scenario = dict(WaterAdapter().presets()["normal_week"])
    scenario["duration_hours"] = 2
    assumptions = load_assumptions(ROOT / "assumptions/demand_v1.yaml")
    store = tmp_path / "store"
    record = run_scenario(
        WaterAdapter(),
        scenario,
        RunStore(store),
        {"demand_v1": assumptions},
        git_commit=None,
    )
    return store, record.run_id


def test_layout_labels_determinism_no_decision(recorded, tmp_path):
    store, run_id = recorded
    first = export_run(run_id, store, tmp_path / "a")
    second = export_run(run_id, store, tmp_path / "b")

    def files(directory):
        return {
            p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*.json")
        }

    assert files(first) == files(second)
    assert all(b"PRIVATE_SENTINEL" not in data for data in files(first).values())
    assert export_run(run_id, store, tmp_path / "a") == first
    assert set(files(first)) == {
        "manifest.json",
        "network.json",
        "readings.json",
        "incidents.json",
        "series/P1.sensor.json",
        "series/P1.expectation.json",
        "series/P1.residual.json",
    }
    assert json.loads((first / "incidents.json").read_text()) == []
    assert not (first / "decision.json").exists()
    for kind, label in (
        ("sensor", "SENSOR_SIM"),
        ("expectation", "MODEL"),
        ("residual", "CALCULATED"),
    ):
        series = json.loads((first / f"series/P1.{kind}.json").read_text())
        assert series["label"] == label
        assert len(series["values"]) == 25
    assert all(
        r["label"] == "SENSOR_SIM"
        for r in json.loads((first / "readings.json").read_text())
    )


def test_mismatch_refuses_export(recorded, tmp_path, monkeypatch):
    store, run_id = recorded
    monkeypatch.setattr(WaterAdapter, "asset_model", lambda self, config: line(41))
    with pytest.raises(ValueError, match="network version"):
        export_run(run_id, store, tmp_path / "views")
    assert not (tmp_path / "views").exists()


def test_model_version_mismatch_refuses_export(recorded, tmp_path, monkeypatch):
    store, run_id = recorded
    monkeypatch.setattr(
        WaterAdapter, "run_versions", lambda self, asset: {"hydraulics": "b" * 64}
    )
    with pytest.raises(ValueError, match="model versions"):
        export_run(run_id, store, tmp_path / "views")
    assert not (tmp_path / "views").exists()
