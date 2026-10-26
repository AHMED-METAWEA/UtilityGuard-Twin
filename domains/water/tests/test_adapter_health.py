"""WaterAdapter.health_checks: what `ug doctor` learns about the water environment."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from ug_core.adapter import HasHealthChecks, HealthCheck
from ug_core.registry import discover
from ug_water import wntr_api
from ug_water.adapter import WaterAdapter


def by_name(checks: list[HealthCheck]) -> dict[str, HealthCheck]:
    return {check.name: check for check in checks}


def write_manifest(tmp_path: Path, mutate) -> Path:  # type: ignore[no-untyped-def]
    manifest = copy.deepcopy(wntr_api.load_manifest())
    mutate(manifest)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_the_registered_water_adapter_offers_health_checks() -> None:
    adapter = discover()["water"]
    assert isinstance(adapter, HasHealthChecks)


def test_a_sound_environment_reports_ok_with_facts() -> None:
    checks = by_name(list(WaterAdapter().health_checks()))
    assert set(checks) == {"wntr_version", "wntr_api_manifest"}
    assert all(isinstance(c, HealthCheck) and c.ok for c in checks.values())
    version = wntr_api.installed_version()
    assert version in checks["wntr_version"].detail
    manifest = wntr_api.load_manifest()
    assert str(wntr_api.symbol_count(manifest)) in checks["wntr_api_manifest"].detail
    assert version in checks["wntr_api_manifest"].detail


def test_the_checks_are_repeatable() -> None:
    first = [(c.name, c.ok, c.detail) for c in WaterAdapter().health_checks()]
    second = [(c.name, c.ok, c.detail) for c in WaterAdapter().health_checks()]
    assert first == second


def test_a_renamed_symbol_fails_the_manifest_check_and_names_the_symbol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def rename(manifest: dict) -> None:  # type: ignore[type-arg]
        key = "wntr.network.WaterNetworkModel.add_pipe"
        manifest["callables"]["wntr.network.WaterNetworkModel.add_pipeX"] = manifest[
            "callables"
        ].pop(key)

    monkeypatch.setenv("UG_WNTR_MANIFEST", str(write_manifest(tmp_path, rename)))
    checks = by_name(list(WaterAdapter().health_checks()))
    assert not checks["wntr_api_manifest"].ok
    assert "add_pipe" in checks["wntr_api_manifest"].detail
    assert checks["wntr_version"].ok  # the version itself is still right


def test_a_changed_signature_fails_and_names_the_symbol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def change(manifest: dict) -> None:  # type: ignore[type-arg]
        manifest["callables"]["wntr.sim.WNTRSimulator.run_sim"] = "(self)"

    monkeypatch.setenv("UG_WNTR_MANIFEST", str(write_manifest(tmp_path, change)))
    checks = by_name(list(WaterAdapter().health_checks()))
    assert not checks["wntr_api_manifest"].ok
    assert "run_sim" in checks["wntr_api_manifest"].detail


def test_another_wntr_version_fails_both_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "UG_WNTR_MANIFEST",
        str(write_manifest(tmp_path, lambda m: m.update(wntr_version="0.0.1"))),
    )
    checks = by_name(list(WaterAdapter().health_checks()))
    assert not checks["wntr_version"].ok and "0.0.1" in checks["wntr_version"].detail
    assert not checks["wntr_api_manifest"].ok


@pytest.mark.parametrize("content", ["", "not json", "[]", '{"schema_version": "1"}'])
def test_an_unreadable_or_incomplete_manifest_is_a_failure_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setenv("UG_WNTR_MANIFEST", str(path))
    checks = by_name(list(WaterAdapter().health_checks()))
    assert not checks["wntr_api_manifest"].ok
    assert checks["wntr_api_manifest"].detail.strip()


def test_a_missing_manifest_is_a_failure_that_says_where(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nope.json"
    monkeypatch.setenv("UG_WNTR_MANIFEST", str(missing))
    checks = by_name(list(WaterAdapter().health_checks()))
    assert not checks["wntr_api_manifest"].ok
    assert "nope.json" in checks["wntr_api_manifest"].detail


def test_the_override_is_only_a_path_to_a_manifest_that_is_still_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hand-made manifest cannot make a wrong environment look right: it is checked against
    the installed library and against the symbols declared in the code, like the packaged one."""
    monkeypatch.setenv(
        "UG_WNTR_MANIFEST",
        str(
            write_manifest(
                tmp_path, lambda m: m["callables"].pop("wntr.sim.WNTRSimulator.run_sim")
            )
        ),
    )
    assert not by_name(list(WaterAdapter().health_checks()))["wntr_api_manifest"].ok


def test_the_adapter_still_conforms_and_other_methods_are_still_unimplemented() -> None:
    assert WaterAdapter.unimplemented_methods()
    assert "solver" in WaterAdapter.unimplemented_methods()
