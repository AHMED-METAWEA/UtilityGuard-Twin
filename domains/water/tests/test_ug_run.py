"""Offline CLI integration with short procedural synthetic runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from ug_cli.main import main
from ug_core.assumptions import load_assumptions
from ug_core.runner import RunState
from ug_core.store.layout import StoreError
from ug_core.store.run import RunStore
from ug_core.timebase import Timebase
from ug_core.truth import TruthSeries
from ug_water.adapter import WaterAdapter
from ug_water.demand.calendar import DemandCalendar
from ug_water.demand.model import DemandModel
from ug_water.scenarios import load_preset
from ug_water.solver import load_options

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def scenario_path(tmp_path: Path) -> Path:
    scenario = load_preset("normal_week")
    scenario["duration_hours"] = 2
    path = tmp_path / "normal_week.json"
    path.write_text(json.dumps(scenario))
    return path


def argv(path: Path, tmp_path: Path, *extra: str) -> list[str]:
    return [
        "run",
        str(path),
        "--network",
        "procedural",
        "--store",
        str(tmp_path / "runs"),
        "--assumptions",
        str(ROOT / "assumptions"),
        *extra,
    ]


def test_cli_determinism_provenance_and_restricted_truth(
    scenario_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ug_cli import run
    from ug_core.store import truth_bundle

    monkeypatch.setattr(run, "_git_commit", lambda root: None)

    # Spy on verification to prove the repeat exercises the store's verified no-op.
    verified: list[str] = []
    original = RunStore.verify

    def verify(self: RunStore, identifier: str) -> Any:
        verified.append(identifier)
        return original(self, identifier)

    monkeypatch.setattr(RunStore, "verify", verify)
    assert main(argv(scenario_path, tmp_path, "--seed", "1")) == 0
    first = capsys.readouterr()
    assert first.err == ""
    record = dict(line.split(": ") for line in first.out.splitlines())
    run_id = record["run_id"]
    directory = tmp_path / "runs" / run_id
    before = {
        p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in directory.iterdir()
    }
    assert main(argv(scenario_path, tmp_path, "--seed", "1")) == 0
    second = capsys.readouterr()
    assert first.out == second.out
    assert run_id in verified
    assert before == {
        p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in directory.iterdir()
    }
    store = RunStore(tmp_path / "runs")
    manifest = store.verify(run_id)
    assert manifest.input_hash() == record["input_hash"]
    adapter = WaterAdapter()
    network = adapter.asset_model(dict(manifest.config))
    assert manifest.versions["network"] == network.content_hash()
    assert manifest.versions["hydraulics"] == load_options().config_hash
    assert (
        manifest.versions["assumption_set"]
        == load_assumptions(ROOT / "assumptions/demand_v1.yaml").content_hash()
    )
    assert set(manifest.libraries) == {
        "numpy",
        "pyarrow",
        "duckdb",
        "jsonschema",
        "wntr",
    }
    assert set(manifest.output_hashes) == {"truth"}
    assert truth_bundle.read_truth(store, run_id).schema.metadata == {
        b"label": b"SIMULATION"
    }
    with pytest.raises(StoreError, match="restricted"):
        store.open(run_id).read_table("truth")
    assert main(argv(scenario_path, tmp_path, "--seed", "2")) == 0
    third = capsys.readouterr()
    assert third.out != first.out
    other = dict(line.split(": ") for line in third.out.splitlines())
    assert (
        store.verify(other["run_id"]).config["network_version"]
        == "procedural-capital-v1-seed2"
    )


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--network", "osm"], "T-B1-013"),
        (["--tier", "standard"], "T-B1-013"),
        (["--tier", "full"], "T-B1-013"),
        (["--seed", "-1"], "minimum"),
    ],
)
def test_unavailable_and_invalid_options(
    scenario_path: Path, tmp_path: Path, capsys: Any, extra: list[str], message: str
) -> None:
    assert main(argv(scenario_path, tmp_path, *extra)) == 1
    output = capsys.readouterr()
    assert message in output.err and output.out == ""
    assert not (tmp_path / "runs").exists()


def test_unknown_preset_and_contract_errors(
    scenario_path: Path, tmp_path: Path, capsys: Any
) -> None:
    assert main(["run", "unknown_preset"]) == 1
    assert "known ids:" in capsys.readouterr().err
    scenario = json.loads(scenario_path.read_text())
    del scenario["seed"]
    scenario_path.write_text(json.dumps(scenario))
    assert main(argv(scenario_path, tmp_path)) == 1
    assert "'seed' is a required property" in capsys.readouterr().err


def test_a_fault_on_an_unknown_pipe_is_refused(
    scenario_path: Path, tmp_path: Path, capsys: Any
) -> None:
    scenario = json.loads(scenario_path.read_text())
    scenario["faults"] = [
        {"type": "burst", "location": "pipe:P1", "start_hour": 0, "final_area_cm2": 1}
    ]
    scenario_path.write_text(json.dumps(scenario))
    assert main(argv(scenario_path, tmp_path)) == 1
    assert "unknown pipe 'P1'" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_preset_discovery_uses_registry(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ug_cli import run

    adapter = WaterAdapter()
    scenario = load_preset("normal_week")
    scenario["duration_hours"] = 2
    monkeypatch.setattr(adapter, "presets", lambda: {"normal_week": scenario})
    monkeypatch.setattr(run, "discover", lambda: {"water": adapter})
    assert main(argv(Path("normal_week"), tmp_path)) == 0
    assert "run_id:" in capsys.readouterr().out


def test_calendar_and_zone_heatwave_scaling(monkeypatch: pytest.MonkeyPatch) -> None:
    import ug_water.adapter as module

    adapter = WaterAdapter()
    scenario = load_preset("normal_week")
    network = adapter.asset_model(scenario)
    assumption = load_assumptions(ROOT / "assumptions/demand_v1.yaml")
    from datetime import datetime

    # Cross midnight in the fixed local offset used by the demand model.
    horizon = Timebase(datetime.fromisoformat("2027-03-04T21:00:00+00:00"), 300, 25)
    settings = scenario["demand"]
    settings.update(
        holiday=True,
        ramadan=True,
        heatwave_multiplier=1.5,
        zone_multipliers={network.zones[0].id: 2.0},
    )
    seen: list[DemandCalendar] = []
    original = DemandModel.truth

    def truth(
        self: DemandModel, asset: Any, axis: Any, seed: int, calendar: DemandCalendar
    ) -> Any:
        seen.append(calendar)
        return original(self, asset, axis, seed, calendar)

    def simulate(asset: Any, demand: Any, faults: Any = None) -> Any:
        calendar = seen[0]
        assert len(calendar.holidays) == 2
        assert calendar.holidays == calendar.ramadan
        assert not calendar.heatwave and not calendar.events and not calendar.fire_flows
        expected = original(
            DemandModel(assumption), network, horizon, scenario["seed"], calendar
        )
        factors = [
            settings["zone_multipliers"].get(j.zone, 1) * 1.5 for j in network.junctions
        ]
        np.testing.assert_array_equal(demand.values, expected.values * factors)

        class Result:
            truth = TruthSeries(horizon, {"pressure:J1": [1.0] * horizon.n_ticks})

        return Result()

    monkeypatch.setattr(DemandModel, "truth", truth)
    monkeypatch.setattr(module, "simulate", simulate)
    adapter.solver().run(
        RunState(network, {assumption.set_id: assumption}), scenario, horizon
    )


def test_usage_errors() -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["run"])


@pytest.mark.parametrize("dirty", [False, True])
def test_git_commit_clean_or_warns(
    dirty: bool, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    import subprocess

    from ug_cli import run

    calls: list[list[str]] = []

    def git(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        output = (
            (" M file.py\n" if dirty else "")
            if command[1] == "status"
            else "a" * 40 + "\n"
        )
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(run.subprocess, "run", git)
    assert run._git_commit(ROOT) == (None if dirty else "a" * 40)
    assert len(calls) == (1 if dirty else 2)
    assert ("not tied to a commit" in capsys.readouterr().err) == dirty


@pytest.mark.parametrize(
    "value", [{}, {"network_version": "osm"}, {"network_version": 1}, None]
)
def test_unsupported_network_names_form(value: Any) -> None:
    with pytest.raises(ValueError, match="procedural-capital-v1-seed<N>"):
        WaterAdapter().asset_model(value)


def test_assumption_id_must_match(
    scenario_path: Path, tmp_path: Path, capsys: Any
) -> None:
    text = (ROOT / "assumptions/demand_v1.yaml").read_text()
    assert "set_id: demand_v1" in text
    (tmp_path / "demand_v1.yaml").write_text(
        text.replace("set_id: demand_v1", "set_id: another_set", 1)
    )
    assert main(argv(scenario_path, tmp_path, "--assumptions", str(tmp_path))) == 1
    assert "does not match" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()
