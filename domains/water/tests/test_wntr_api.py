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
    assert wntr_api.declared_matches_manifest(manifest) == []


def test_manifest_records_the_version_and_enough_symbols(manifest: dict) -> None:
    assert manifest["wntr_version"] == wntr_api.installed_version()
    assert wntr_api.symbol_count(manifest) >= 40


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


def test_verify_names_a_missing_member_and_a_missing_result_key(manifest: dict) -> None:
    broken = copy.deepcopy(manifest)
    broken["members"].append({"root": "pipe", "path": "no_such_attribute"})
    broken["result_keys"].append({"table": "node", "key": "no_such_column"})
    problems = wntr_api.verify(broken)
    assert any("no_such_attribute" in problem for problem in problems)
    assert any("no_such_column" in problem for problem in problems)


def test_verify_reports_a_different_wntr_version(manifest: dict) -> None:
    broken = copy.deepcopy(manifest)
    broken["wntr_version"] = "0.0.1"
    assert any("WNTR version" in problem for problem in wntr_api.verify(broken))


def test_verify_rejects_unsupported_path_syntax(manifest: dict) -> None:
    broken = copy.deepcopy(manifest)
    broken["members"].append({"root": "wn", "path": "options; __import__('os')"})
    problems = wntr_api.verify(broken)
    assert any("unsupported path syntax" in problem for problem in problems)


def test_declared_lists_and_manifest_drift_is_reported(manifest: dict) -> None:
    broken = copy.deepcopy(manifest)
    broken["callables"].pop("wntr.sim.WNTRSimulator.run_sim")
    assert wntr_api.declared_matches_manifest(broken)


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
