"""CLI acceptance and failure-path tests; no domain implementation imports."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from ug_cli import __version__, doctor
from ug_cli.main import main
from ug_core.adapter import HealthCheck
from ug_core.registry import DomainRegistrationError

ROOT = Path(__file__).resolve().parents[3]
UG = shutil.which("ug") or str(Path(sys.executable).parent / "ug")


@pytest.mark.parametrize(
    ("argv", "code", "message"),
    [
        (["--version"], 0, f"ug {__version__}"),
        ([], 2, "usage: ug"),
        (["unknown"], 2, "invalid choice"),
    ],
)
def test_parser(
    argv: list[str], code: int, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == code
    captured = capsys.readouterr()
    assert message in (captured.out if code == 0 else captured.err)


@pytest.mark.parametrize(
    ("command", "milestone"),
    [
        ("reproduce", "M4"),
        ("eval", "M5"),
        ("import", "M1"),
    ],
)
def test_stubs(
    command: str, milestone: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([command]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"ug {command}: not implemented yet (planned for Spec milestone {milestone})\n"
    )


def test_real_doctor_json_is_stable(capsys: pytest.CaptureFixture[str]) -> None:
    outputs = []
    for _ in range(2):
        assert main(["doctor", "--json", "--root", str(ROOT)]) == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        outputs.append(captured.out)
    assert outputs[0] == outputs[1]
    report = json.loads(outputs[0])
    assert report["schema_version"] == "1"
    assert report["ok"] is True
    names = [check["name"] for check in report["checks"]]
    assert names[:4] == [
        "python",
        "domains",
        "water.wntr_version",
        "water.wntr_api_manifest",
    ]
    assert names[-2:] == ["node", "docker"]
    assert "contracts" in names
    contract_names = [name for name in names if name.startswith("contracts.")]
    assert contract_names == [
        f"contracts.{path.stem}"
        for path in sorted((ROOT / "contracts/v1").glob("*.schema.json"))
    ]
    for status in ("ok", "warn", "fail"):
        assert report["counts"][status] == sum(
            check["status"] == status for check in report["checks"]
        )


def test_real_script_and_module() -> None:
    for command in ([UG, "doctor"], [sys.executable, "-m", "ug_cli", "doctor"]):
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "[ok] water.wntr_api_manifest:" in completed.stdout
        assert "Summary:" in completed.stdout
        assert completed.stderr == ""
        assert all(
            line.startswith(("[ok]", "[warn]", "[FAIL]", "Summary:"))
            for line in completed.stdout.splitlines()
        )


def test_edited_manifest_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = json.loads(
        (ROOT / "domains/water/src/ug_water/wntr_api_manifest.json").read_text()
    )
    original = next(iter(manifest["callables"]))
    renamed = original + "_cli_missing_symbol"
    manifest["callables"][renamed] = manifest["callables"].pop(original)
    edited = tmp_path / "manifest.json"
    edited.write_text(json.dumps(manifest))
    monkeypatch.setenv("UG_WNTR_MANIFEST", str(edited))
    completed = subprocess.run(
        [UG, "doctor", "--json", "--root", str(ROOT)], capture_output=True, text=True
    )
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stderr == ""
    report = json.loads(completed.stdout)
    assert report["ok"] is False
    check = next(c for c in report["checks"] if c["name"] == "water.wntr_api_manifest")
    assert check["status"] == "fail"
    assert renamed in check["detail"]


@pytest.fixture
def contracts_root(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "contracts", tmp_path / "contracts")
    return tmp_path


@pytest.mark.parametrize(
    ("contents", "detail"),
    [
        (
            '{"$ref":"missing.schema.json#/$defs/nope"}',
            "missing.schema.json#/$defs/nope",
        ),
        ('{"type":"not-a-type"}', "not-a-type"),
        ('{"type":"string","type":"number"}', "duplicate key"),
        ('{"default":NaN}', "NaN"),
        ('{"default":Infinity}', "Infinity"),
        ('{"default":-Infinity}', "-Infinity"),
        (
            '{"$ref":"https://unreachable.invalid/schema"}',
            "https://unreachable.invalid/schema",
        ),
        ('{"$ref":"common.schema.json#/$defs/missing"}', "$defs/missing"),
        ('{"$dynamicRef":"#missing_anchor"}', "unresolvable $dynamicRef"),
        # Gate round 1 (T-A1-013): a reference that resolves to something that is not a schema.
        ('{"$ref":"#/default","default":{"type":"not-a-type"}}', "not-a-type"),
        ('{"$ref":"#/default","default":5}', "#/default"),
        # Round 2 of the gate: a reference inside a resolved target is followed too.
        (
            '{"$ref":"#/default","default":{"$ref":"#/examples/0"},"examples":[5]}',
            "#/examples/0",
        ),
        (
            '{"$dynamicRef":"#/default","default":{"$dynamicRef":"#/examples/0"},"examples":[5]}',
            "#/examples/0",
        ),
        (
            '{"$ref":"#/default","default":{"$ref":"#/examples/0"},"examples":[{"$ref":"#/examples/1"},{"minimum":"x"}]}',
            "#/examples/1",
        ),
        # A number that overflows to infinity is not finite JSON either.
        ('{"default":1e9999}', "not a finite number"),
        ('{"default":-1e9999}', "not a finite number"),
    ],
)
def test_bad_contract(
    contracts_root: Path,
    contents: str,
    detail: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = contracts_root / "contracts/v1/probe.schema.json"
    path.write_text(contents)
    assert main(["doctor", "--json", "--root", str(contracts_root)]) == 1
    report = json.loads(capsys.readouterr().out)
    check = next(c for c in report["checks"] if c["name"] == "contracts.probe.schema")
    assert check["status"] == "fail"
    assert path.name in check["detail"]
    assert detail in check["detail"]
    assert (
        next(c for c in report["checks"] if c["name"] == "contracts")["status"]
        == "fail"
    )


def test_two_schema_files_cannot_share_an_id(
    contracts_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = json.loads((ROOT / "contracts/v1/common.schema.json").read_text())
    copy = contracts_root / "contracts/v1/zz-copy.schema.json"
    copy.write_text(json.dumps({"$id": common["$id"], "type": "object"}))
    assert main(["doctor", "--json", "--root", str(contracts_root)]) == 1
    report = json.loads(capsys.readouterr().out)
    check = next(c for c in report["checks"] if c["name"] == "contracts.zz-copy.schema")
    assert check["status"] == "fail"
    assert copy.name in check["detail"]
    assert "duplicate schema $id" in check["detail"]


def test_human_output_marks_each_status(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    missing = tmp_path_factory.mktemp("no-contracts")
    assert main(["doctor", "--root", str(missing)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert any(line.startswith("[ok] python: ") for line in lines)
    assert any(line.startswith("[warn] node: ") for line in lines)
    assert any(line.startswith("[warn] docker: ") for line in lines)
    assert any(line.startswith("[FAIL] contracts: ") for line in lines)
    assert lines[-1].startswith("Summary: ")
    assert lines[-1].endswith("2 warn, 1 fail")


def test_nested_ids_anchors_and_literal_refs(contracts_root: Path) -> None:
    schema = {
        "$id": "https://utilityguard.invalid/contracts/v1/probe.schema.json",
        "$defs": {
            "nested": {
                "$id": "nested/child.json",
                "$defs": {"target": {"$anchor": "target", "type": "string"}},
                "$ref": "#target",
            }
        },
        "$ref": "nested/child.json",
        "const": {"$ref": "this-is-instance-data-not-a-schema"},
    }
    path = contracts_root / "contracts/v1/probe.schema.json"
    path.write_text(json.dumps(schema))
    assert all(c.status == "ok" for c in doctor.check_contracts(contracts_root))
    schema["$defs"]["nested"]["$ref"] = "#missing"  # type: ignore[index]
    path.write_text(json.dumps(schema))
    checks = doctor.check_contracts(contracts_root)
    assert any(c.status == "fail" and "#missing" in c.detail for c in checks)


def test_contract_root_search_and_missing(
    contracts_root: Path,
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(contracts_root / "contracts/v1")
    assert all(c.status == "ok" for c in doctor.check_contracts(None))
    missing = tmp_path_factory.mktemp("no-contracts")
    results = doctor.check_contracts(missing)
    assert len(results) == 1
    assert results[0].status == "fail"
    assert "--root" in results[0].detail
    monkeypatch.chdir(missing)
    assert doctor.check_contracts(None)[0].status == "fail"
    empty = tmp_path / "empty/contracts/v1"
    empty.mkdir(parents=True)
    assert doctor.check_contracts(empty.parents[1])[0].status == "fail"


def test_tools_missing_warn_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    assert main(["doctor", "--json", "--root", str(ROOT)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [(c["name"], c["status"]) for c in report["checks"][-2:]] == [
        ("node", "warn"),
        ("docker", "warn"),
    ]
    assert report["counts"]["fail"] == 0


@pytest.mark.parametrize(
    ("version", "status"),
    [
        ("v22.12.9", "warn"),
        ("v22.13.0", "ok"),
        ("v22.9.0", "warn"),
        ("v23.0.0", "ok"),
        ("garbage", "warn"),
    ],
)
def test_node_versions(
    version: str, status: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/fake/node")

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert args == ["/fake/node", "--version"]
        assert kwargs["timeout"] == 10
        return subprocess.CompletedProcess(args, 0, version + "\n", "")

    monkeypatch.setattr(doctor.subprocess, "run", run)
    assert doctor.check_tool("node").status == status


@pytest.mark.parametrize("tool", ["node", "docker"])
@pytest.mark.parametrize("failure", ["exit", "oserror", "timeout"])
def test_tool_execution_failure_warns(
    tool: Any, failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/fake/tool")

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if failure == "oserror":
            raise OSError("cannot execute")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 10)
        return subprocess.CompletedProcess(args, 1, "", "error")

    monkeypatch.setattr(doctor.subprocess, "run", run)
    assert doctor.check_tool(tool).status == "warn"


def test_domain_no_hook_and_sorted_order(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoHealthHook:
        pass

    monkeypatch.setattr(
        doctor, "discover", lambda: {"z": NoHealthHook(), "a": NoHealthHook()}
    )
    checks = doctor.check_domains()
    assert [c.name for c in checks] == ["domains", "a", "z"]
    assert [(c.status, c.detail) for c in checks[1:]] == [
        ("warn", "a: no health checks"),
        ("warn", "z: no health checks"),
    ]


@pytest.mark.parametrize("empty", [True, False])
def test_discovery_failure(empty: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    def discover() -> dict[str, Any]:
        if empty:
            return {}
        raise DomainRegistrationError("broken entry point")

    monkeypatch.setattr(doctor, "discover", discover)
    checks = doctor.check_domains()
    assert len(checks) == 1 and checks[0].status == "fail"
    assert ("no domains" if empty else "broken entry point") in checks[0].detail


def test_health_exception_and_failed_check(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken:
        def health_checks(self) -> list[HealthCheck]:
            raise RuntimeError("health probe\nfailed")

    class Unhealthy:
        def health_checks(self) -> list[HealthCheck]:
            return [HealthCheck("probe", False, "probe failed")]

    monkeypatch.setattr(
        doctor, "discover", lambda: {"broken": Broken(), "bad": Unhealthy()}
    )
    checks = doctor.check_domains()
    assert [(c.name, c.status) for c in checks] == [
        ("domains", "ok"),
        ("bad.probe", "fail"),
        ("broken", "fail"),
    ]
    assert "RuntimeError" in checks[-1].detail
    assert "\n" not in checks[-1].detail


def test_python_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    from collections import namedtuple

    Version = namedtuple("Version", "major minor micro")
    for version, status in [(Version(3, 10, 9), "fail"), (Version(3, 11, 0), "ok")]:
        monkeypatch.setattr(doctor.sys, "version_info", version)
        assert doctor.check_python().status == status


def test_cli_has_no_domain_imports() -> None:
    for path in (ROOT / "platform/ug_cli/src/ug_cli").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith("ug_water") for alias in node.names
                )
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("ug_water")


@pytest.mark.parametrize(
    "mode", ["no_hook", "empty", "registration_error", "health_error"]
)
def test_domain_cli_exit_and_json(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Broken:
        def health_checks(self) -> list[HealthCheck]:
            raise LookupError("probe unavailable")

    def discover() -> dict[str, Any]:
        if mode == "registration_error":
            raise DomainRegistrationError("registration unavailable")
        if mode == "empty":
            return {}
        return {"fake": Broken() if mode == "health_error" else object()}

    monkeypatch.setattr(doctor, "discover", discover)
    expected_ok = mode == "no_hook"
    assert main(["doctor", "--json", "--root", str(ROOT)]) == (0 if expected_ok else 1)
    captured = capsys.readouterr()
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report["ok"] is expected_ok
    assert (report["counts"]["fail"] == 0) is expected_ok
    if expected_ok:
        check = next(c for c in report["checks"] if c["name"] == "fake")
        assert check["status"] == "warn"
    if mode == "health_error":
        assert "LookupError" in captured.out


def test_a_reference_chain_through_data_in_another_file_is_followed(
    contracts_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = contracts_root / "contracts/v1"
    (folder / "chain.schema.json").write_text(
        '{"$ref":"chain_target.schema.json#/default"}'
    )
    (folder / "chain_target.schema.json").write_text(
        '{"default":{"$ref":"#/examples/0"},"examples":[5]}'
    )
    assert main(["doctor", "--json", "--root", str(contracts_root)]) == 1
    report = json.loads(capsys.readouterr().out)
    check = next(c for c in report["checks"] if c["name"] == "contracts.chain.schema")
    assert check["status"] == "fail"
    assert "chain.schema.json" in check["detail"] and "#/examples/0" in check["detail"]


@pytest.mark.parametrize(
    "contents",
    [
        '{"$ref":"#/$defs/a","$defs":{"a":{"$ref":"#/$defs/b"},"b":{"$ref":"#/$defs/a"}}}',
        '{"$ref":"#/$defs/t","$defs":{"t":true}}',
        '{"$ref":"#/$defs/t","$defs":{"t":{"$ref":"#/$defs/u"},"u":false}}',
        '{"$ref":"#","type":"object"}',
        '{"$ref":"#/$defs/a","$defs":{"a":{"properties":{"x":{"$ref":"#/$defs/a"}}}}}',  # a tree
        '{"$ref":"#/default","default":{"type":"string","$ref":"#/default"}}',
    ],
)
def test_cycles_and_boolean_targets_are_still_fine(
    contracts_root: Path, contents: str
) -> None:
    (contracts_root / "contracts/v1/probe.schema.json").write_text(contents)
    results = doctor.check_contracts(contracts_root)
    assert all(c.status == "ok" for c in results), [
        c for c in results if c.status != "ok"
    ]
