"""WNTR API manifest: the committed file matches the installed WNTR and detects drift."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from ug_water import wntr_api

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "gen_wntr_manifest.py"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return wntr_api.load_manifest()


def test_committed_manifest_verifies_against_the_installed_wntr(manifest: dict) -> None:
    assert wntr_api.verify(manifest) == []
    assert wntr_api.manifest_problems(manifest) == []


def test_manifest_records_the_version_and_enough_symbols(manifest: dict) -> None:
    assert manifest["wntr_version"] == wntr_api.installed_version()
    assert wntr_api.symbol_count(manifest) >= 81


@pytest.mark.parametrize(
    "path",
    [
        "wntr.sim.EpanetSimulator.run_sim",
        "wntr.sim.WNTRSimulator",
        "wntr.sim.EpanetSimulator",
        "wntr.morph.split_pipe",
        "wntr.morph.break_pipe",
        "wntr.network.WaterNetworkModel.add_control",
        "wntr.network.WaterNetworkModel.remove_control",
        "wntr.network.WaterNetworkModel.reset_initial_values",
        "wntr.network.WaterNetworkModel.get_curve",
        "wntr.network.elements.Pump.add_outage",
        "wntr.network.controls.Control",
        "wntr.network.controls.ControlAction",
        "wntr.network.controls.SimTimeCondition",
        "wntr.metrics.pump_energy",
        "wntr.metrics.pump_power",
    ],
)
def test_b1_callable_is_recorded(manifest: dict, path: str) -> None:
    assert path in manifest["callables"]


@pytest.mark.parametrize(
    ("root", "path"),
    [
        ("wn", "junction_name_list"),
        ("wn", "tank_name_list"),
        ("wn", "reservoir_name_list"),
        ("wn", "pipe_name_list"),
        ("wn", "pump_name_list"),
        ("wn", "valve_name_list"),
        ("wn", "node_name_list"),
        ("wn", "options.hydraulic.headloss"),
        ("wn", "options.time.start_clocktime"),
        ("tank", "elevation"),
        ("reservoir", "base_head"),
        ("pump", "pump_type"),
        ("pump", "pump_curve_name"),
        ("pump", "speed_timeseries.base_value"),
        ("valve", "valve_type"),
        ("valve", "initial_setting"),
    ],
)
def test_b1_member_is_recorded(manifest: dict, root: str, path: str) -> None:
    assert {"root": root, "path": path} in manifest["members"]


def test_b1_velocity_result_key_is_recorded(manifest: dict) -> None:
    assert {"table": "link", "key": "velocity"} in manifest["result_keys"]


def test_generation_is_deterministic() -> None:
    first = json.dumps(wntr_api.generate(), sort_keys=True)
    second = json.dumps(wntr_api.generate(), sort_keys=True)
    assert first == second


def test_committed_manifest_is_what_generate_would_write(manifest: dict) -> None:
    assert manifest == wntr_api.generate()


def test_signatures_hold_no_memory_addresses(manifest: dict) -> None:
    # An address in a recorded signature would make the manifest differ on every run.
    assert not any(" at 0x" in sig for sig in manifest["callables"].values())


def test_every_declared_callable_has_a_signature(manifest: dict) -> None:
    assert set(manifest["callables"]) == set(wntr_api.CALLABLES)
    assert all(sig.startswith("(") for sig in manifest["callables"].values())


def test_verify_names_a_renamed_callable(manifest: dict) -> None:
    broken = copy.deepcopy(manifest)
    broken["callables"]["wntr.network.WaterNetworkModel.add_junctionX"] = broken[
        "callables"
    ].pop("wntr.network.WaterNetworkModel.add_junction")
    problems = wntr_api.verify(broken)
    assert any("add_junctionX" in problem for problem in problems)


def test_verify_names_a_changed_signature(manifest: dict) -> None:
    broken = copy.deepcopy(manifest)
    broken["callables"]["wntr.network.WaterNetworkModel.add_pipe"] = "(self, name)"
    problems = wntr_api.verify(broken)
    assert any(
        "add_pipe" in problem and "signature changed" in problem for problem in problems
    )


def test_verify_names_a_missing_member_and_a_missing_result_key(
    manifest: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Declare two symbols the installed WNTR does not have, and list them in the manifest.
    monkeypatch.setattr(
        wntr_api, "MEMBERS", (*wntr_api.MEMBERS, ("pipe", "no_such_attribute"))
    )
    monkeypatch.setattr(
        wntr_api, "RESULT_KEYS", (*wntr_api.RESULT_KEYS, ("node", "no_such_column"))
    )
    declared = copy.deepcopy(manifest)
    declared["members"].append({"root": "pipe", "path": "no_such_attribute"})
    declared["result_keys"].append({"table": "node", "key": "no_such_column"})
    problems = wntr_api.verify(declared)
    assert any("no_such_attribute" in problem for problem in problems)
    assert any("no_such_column" in problem for problem in problems)


def test_verify_reports_a_different_wntr_version(manifest: dict) -> None:
    broken = copy.deepcopy(manifest)
    broken["wntr_version"] = "0.0.1"
    assert any("WNTR version" in problem for problem in wntr_api.verify(broken))


def test_verify_rejects_unsupported_path_syntax(
    manifest: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_path = "options; __import__('os')"
    monkeypatch.setattr(wntr_api, "MEMBERS", (*wntr_api.MEMBERS, ("wn", bad_path)))
    declared = copy.deepcopy(manifest)
    declared["members"].append({"root": "wn", "path": bad_path})
    problems = wntr_api.verify(declared)
    assert any("unsupported path syntax" in problem for problem in problems)


def test_declared_lists_and_manifest_drift_is_reported(manifest: dict) -> None:
    broken = copy.deepcopy(manifest)
    broken["callables"].pop("wntr.sim.WNTRSimulator.run_sim")
    assert any(
        "run_sim" in problem and "missing from the manifest" in problem
        for problem in wntr_api.manifest_problems(broken)
    )


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_script_check_exits_zero_on_the_installed_wntr() -> None:
    result = run_script("--check")
    assert result.returncode == 0, result.stderr
    assert "WNTR API manifest OK" in result.stdout


def test_script_check_fails_and_names_a_renamed_symbol(
    tmp_path: Path, manifest: dict
) -> None:
    broken = copy.deepcopy(manifest)
    broken["callables"]["wntr.network.WaterNetworkModel.add_tankX"] = broken[
        "callables"
    ].pop("wntr.network.WaterNetworkModel.add_tank")
    copy_path = tmp_path / "manifest.json"
    copy_path.write_text(json.dumps(broken), encoding="utf-8")
    result = run_script("--check", "--manifest", str(copy_path))
    assert result.returncode == 1
    assert "add_tankX" in result.stderr


def test_script_write_then_check_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    assert run_script("--write", "--manifest", str(target)).returncode == 0
    assert run_script("--check", "--manifest", str(target)).returncode == 0
    assert json.loads(target.read_text(encoding="utf-8")) == wntr_api.load_manifest()


class ImportRecorder:
    """A meta-path finder that records every module name Python tries to import."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def find_spec(self, name: str, path: object = None, target: object = None) -> None:
        self.names.append(name)


def test_verify_never_imports_a_module_named_only_in_the_manifest(
    manifest: dict,
) -> None:
    broken = copy.deepcopy(manifest)
    broken["callables"]["review_payload.fn"] = "()"
    recorder = ImportRecorder()
    sys.meta_path.insert(0, recorder)  # type: ignore[arg-type]
    try:
        problems = wntr_api.verify(broken)
    finally:
        sys.meta_path.remove(recorder)  # type: ignore[arg-type]
    assert not any(name.split(".")[0] == "review_payload" for name in recorder.names)
    assert any("review_payload.fn" in problem for problem in problems)


def test_resolver_only_follows_paths_inside_wntr() -> None:
    for path in ("os.getcwd", "review_payload.fn", "wntrx.thing"):
        with pytest.raises(ValueError):
            wntr_api._resolve_callable(path)


def test_verify_requires_every_declared_symbol_to_be_in_the_manifest(
    manifest: dict,
) -> None:
    broken = copy.deepcopy(manifest)
    del broken["callables"]["wntr.network.WaterNetworkModel.add_valve"]
    assert any("add_valve" in p for p in wntr_api.verify(broken))
    for section in ("callables", "members", "result_keys"):
        missing_section = {k: v for k, v in manifest.items() if k != section}
        assert wntr_api.verify(missing_section), section
    short = copy.deepcopy(manifest)
    short["members"].pop()
    short["result_keys"].pop()
    assert len(wntr_api.verify(short)) >= 2


def test_verify_rejects_a_malformed_manifest_without_raising() -> None:
    assert wntr_api.verify({})
    assert wntr_api.verify({"callables": [], "members": {}, "result_keys": 3})
    assert wntr_api.verify(
        {
            "schema_version": "1",
            "wntr_version": wntr_api.installed_version(),
            "callables": {},
            "members": [{"root": "wn"}],
            "result_keys": ["node.pressure"],
        }
    )


def test_verify_fails_when_an_installed_callable_is_unusable(
    manifest: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    import wntr

    monkeypatch.setattr(wntr.network.WaterNetworkModel, "add_valve", None)
    problems = wntr_api.verify(manifest)
    assert any("add_valve" in problem for problem in problems)


@pytest.mark.parametrize("section", ["members", "result_keys"])
def test_duplicate_entries_are_rejected_everywhere(
    manifest: dict, section: str, tmp_path: Path
) -> None:
    broken = copy.deepcopy(manifest)
    broken[section].append(dict(broken[section][0]))
    assert any("listed twice" in p for p in wntr_api.manifest_problems(broken))
    assert any("listed twice" in p for p in wntr_api.verify(broken))
    copy_path = tmp_path / "manifest.json"
    copy_path.write_text(json.dumps(broken), encoding="utf-8")
    result = run_script("--check", "--manifest", str(copy_path))
    assert result.returncode == 1
    assert "listed twice" in result.stderr
