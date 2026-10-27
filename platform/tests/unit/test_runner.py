"""The privileged runner publishes truth without returning it to consumers."""

from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from ug_core.adapter import AdapterBase
from ug_core.assumptions import Assumption, AssumptionSet, Triangular
from ug_core.runner import RunRecord, RunState, run_scenario
from ug_core.store.layout import StoreError
from ug_core.store.run import RunStore
from ug_core.timebase import Timebase
from ug_core.truth import TruthSeries


class FakeAdapter(AdapterBase):
    domain_id = "fake"

    def __init__(self) -> None:
        self.asset = object()
        self.states: list[RunState] = []

    def asset_model(self, params: Any) -> Any:
        return self.asset

    def solver(self) -> Any:
        return self

    def run(self, state: RunState, scenario: Any, horizon: Timebase) -> TruthSeries:
        self.states.append(state)
        assert horizon.n_ticks == 3
        assert horizon.step_seconds == 1800
        return TruthSeries(horizon, {"pressure:J1": [1.0, 2.0, 3.0]})

    def run_versions(self, asset: Any) -> dict[str, str]:
        assert asset is self.asset
        return {"network": "fake-v1"}


def recipe() -> dict[str, Any]:
    return {
        "seed": 1,
        "duration_hours": 1,
        "timestep_minutes": 30,
        "start": "2027-01-01T00:00:00Z",
        "assumption_set": "test",
        "faults": [],
    }


def test_state_bundle_record_and_verified_noop(tmp_path: Path, capsys: Any) -> None:
    adapter = FakeAdapter()
    assumptions = {
        "test": AssumptionSet(
            "test",
            None,
            "Test inputs",
            {
                "scale": Assumption(
                    "scale", "ratio", Triangular(1, 1, 1), "Synthetic test input", False
                )
            },
        )
    }
    scenario = recipe()
    store = RunStore(tmp_path)
    result = run_scenario(adapter, scenario, store, assumptions, git_commit=None)
    assert isinstance(result, RunRecord)
    assert {f.name for f in fields(result)} == {"run_id", "input_hash"}
    assert adapter.states[0].asset is adapter.asset
    assert adapter.states[0].assumptions is assumptions
    manifest = store.verify(result.run_id)
    assert manifest.input_hash() == result.input_hash
    assert manifest.versions["assumption_set"] == assumptions["test"].content_hash()
    assert manifest.versions["network"] == "fake-v1"
    assert set(manifest.libraries) == {"numpy", "pyarrow", "duckdb", "jsonschema"}
    assert set(manifest.output_hashes) == {"truth"}
    directory = tmp_path / result.run_id
    before = {
        p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in directory.iterdir()
    }
    assert (
        run_scenario(adapter, scenario, store, assumptions, git_commit=None) == result
    )
    assert before == {
        p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in directory.iterdir()
    }
    with pytest.raises(StoreError, match="restricted"):
        store.open(result.run_id).read_table("truth")
    assert capsys.readouterr() == ("", "")


def test_nonintegral_horizon_is_refused_before_solving(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    scenario = recipe()
    scenario["duration_hours"] = 1.01
    with pytest.raises(ValueError, match="whole number of steps"):
        run_scenario(adapter, scenario, RunStore(tmp_path), {}, git_commit=None)
    assert not adapter.states
    assert not list(tmp_path.iterdir())


def test_optional_adapter_defaults_are_implemented() -> None:
    adapter = AdapterBase()
    assert adapter.presets() == {}
    assert adapter.run_versions(object()) == {}
    assert adapter.run_libraries() == ()
    assert (
        not {"presets", "run_versions", "run_libraries"}
        & adapter.unimplemented_methods()
    )
