"""Offline checks that development constraints match the shipped runtime."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "scripts/gen_constraints.py"
LOCK = ROOT / "deploy/requirements-api.lock"
RUNTIME = ROOT / "constraints/runtime.txt"


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def lock_pins() -> dict[str, str]:
    """Read the real lock independently of the generator."""
    return {
        re.sub(r"[-_.]+", "-", name).lower(): pinned
        for name, pinned in re.findall(
            r"^([A-Za-z0-9._-]+)==([^\s\\]+)",
            LOCK.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    }


def test_committed_constraints_match_generated_output(tmp_path: Path) -> None:
    output = tmp_path / "runtime.txt"
    result = run_generator("--output", str(output))
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == RUNTIME.read_bytes()
    assert run_generator("--check").returncode == 0


def test_runtime_contains_every_lock_pin_and_nothing_else() -> None:
    lines = [
        line
        for line in RUNTIME.read_text(encoding="utf-8").splitlines()
        if not line.startswith("#")
    ]
    expected = lock_pins()
    assert expected
    assert lines == [f"{name}=={expected[name]}" for name in sorted(expected)]


@pytest.mark.parametrize(
    "content",
    [
        "fastapi>=0.143\n",
        "fastapi==0.143.0\n--index-url https://example.invalid\n",
        "fastapi==0.143.0\n-r hidden.txt\n",
        "# no pins\n\n--hash=sha256:aa\n",
    ],
)
def test_generator_rejects_invalid_lock(tmp_path: Path, content: str) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text(content, encoding="utf-8")
    output = tmp_path / "runtime.txt"
    result = run_generator("--lock", str(lock), "--output", str(output))
    assert result.returncode == 2
    assert "ERROR" in result.stderr
    assert not output.exists()


def test_generator_normalizes_and_sorts_pins(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        "# comment\nZope.Interface==7.0 \\\n    --hash=sha256:aa\n"
        "Typing_Extensions==4.16.0\n\n",
        encoding="utf-8",
    )
    output = tmp_path / "runtime.txt"
    result = run_generator("--lock", str(lock), "--output", str(output))
    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8").splitlines()[2:] == [
        "typing-extensions==4.16.0",
        "zope-interface==7.0",
    ]


def test_check_reports_stale_constraints_without_writing(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_bytes(LOCK.read_bytes())
    output = tmp_path / "runtime.txt"
    stale = "fastapi==0.0.0\n"
    output.write_text(stale, encoding="utf-8")
    result = run_generator("--check", "--lock", str(lock), "--output", str(output))
    assert result.returncode == 1
    assert "-fastapi==0.0.0" in result.stdout
    assert "+fastapi==0.143.0" in result.stdout
    assert output.read_text(encoding="utf-8") == stale


def test_build_pin_satisfies_all_repository_build_requirements() -> None:
    pins = [
        line
        for line in (ROOT / "constraints/build.txt").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert len(pins) == 1
    match = re.fullmatch(r"setuptools==([0-9]+(?:\.[0-9]+)*)", pins[0])
    assert match is not None
    pinned = match.group(1)
    # Tracked paths include the reference pyproject without traversing environments.
    tracked = subprocess.run(
        ["git", "ls-files", "*pyproject.toml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    paths = tracked.stdout.splitlines()
    assert paths
    checked = 0
    for path in paths:
        project = tomllib.loads((ROOT / path).read_text(encoding="utf-8"))
        for raw in project.get("build-system", {}).get("requires", []):
            requirement = Requirement(raw)
            assert requirement.name == "setuptools", path
            assert pinned in requirement.specifier, (path, raw, pinned)
            checked += 1
    assert checked


@pytest.mark.parametrize(
    ("path", "target", "requirements"),
    [
        (
            "Makefile",
            "install",
            [
                "--constraint constraints/runtime.txt",
                "--build-constraint constraints/build.txt",
                "$(addprefix -e ,$(PACKAGES))",
            ],
        ),
        (
            "mk/ci.mk",
            "install-dev",
            ["--constraint constraints/runtime.txt", "-r requirements-dev.txt"],
        ),
    ],
)
def test_install_recipes_pass_constraints(
    path: str, target: str, requirements: list[str]
) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(rf"^{target}:[^\n]*\n((?:\t[^\n]*\n)+)", text, re.MULTILINE)
    assert match is not None
    install_lines = [
        line for line in match.group(1).splitlines() if "-m pip install" in line
    ]
    assert any(all(flag in line for flag in requirements) for line in install_lines)


@pytest.mark.parametrize("name", ["fastapi", "starlette", "pydantic", "uvicorn"])
def test_installed_runtime_version_matches_lock(name: str) -> None:
    assert version(name) == lock_pins()[name]
