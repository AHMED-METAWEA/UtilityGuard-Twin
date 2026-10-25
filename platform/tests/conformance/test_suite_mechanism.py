"""The suite itself must catch an adapter that lies about what it has implemented.

Each case writes a small test file that runs the real `conformance_params` over a fake adapter in a
separate pytest process, then reads the outcome.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent

CASE = """
import pytest
from adapter_suite import conformance_params
from ug_core.adapter import AdapterBase
from ug_core.adapter.conformance import check_method

class Marker:
    pass

class Solver:
    def run(self, state, scenario, horizon):
        raise NotImplementedError

class Honest(AdapterBase):
    domain_id = "fake"

class {name}(AdapterBase):
    domain_id = "fake"
{body}

@pytest.mark.parametrize(("adapter", "method"), conformance_params({{"fake": {name}()}}))
def test_method(adapter, method):
    check_method(adapter, method)
"""


def run_case(tmp_path: Path, name: str, body: str) -> subprocess.CompletedProcess[str]:
    case = tmp_path / "test_case.py"
    case.write_text(
        CASE.format(name=name, body=textwrap.indent(textwrap.dedent(body), "    "))
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(case),
            "-q",
            "-rxX",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env={"PYTHONPATH": str(HERE), "PATH": "/usr/bin:/bin"},
    )


def test_untouched_adapter_base_is_all_expected_failures(tmp_path: Path) -> None:
    result = run_case(tmp_path, "Plain", "pass")
    assert result.returncode == 0, result.stdout
    assert "12 xfailed" in result.stdout
    assert "fake.solver: not implemented yet" in result.stdout


def test_a_method_that_returns_data_while_declared_unimplemented_fails(
    tmp_path: Path,
) -> None:
    body = """
    @classmethod
    def unimplemented_methods(cls):
        return frozenset({"fault_library"})
    def fault_library(self):
        return Marker()
    def asset_model(self, params):
        return Marker()
    def solver(self):
        return Solver()
    def measurement_model(self):
        raise NotImplementedError
    """
    result = run_case(tmp_path, "Liar", body)
    assert result.returncode == 1, result.stdout
    assert "XPASS(strict)" in result.stdout
    assert "fault_library" in result.stdout


def test_an_implemented_method_that_returns_nothing_fails(tmp_path: Path) -> None:
    body = """
    def solver(self):
        return None
    """
    result = run_case(tmp_path, "Empty", body)
    assert result.returncode == 1, result.stdout
    assert "must return PhysicalSolver" in result.stdout


def test_a_method_declared_implemented_that_raises_not_implemented_fails(
    tmp_path: Path,
) -> None:
    body = """
    @classmethod
    def unimplemented_methods(cls):
        return frozenset()
    """
    result = run_case(tmp_path, "Lazy", body)
    assert result.returncode == 1, result.stdout
    assert "NotImplementedError" in result.stdout
