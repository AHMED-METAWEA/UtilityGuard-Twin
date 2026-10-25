"""scripts/check_imports.py: platform never imports domains; a domain never imports another."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "check_imports.py"


def make_tree(root: Path) -> Path:
    for folder in (
        "platform/ug_core/src/ug_core",
        "domains/water/src/ug_water",
        "domains/power/src/ug_power",
    ):
        package = root / folder
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
    return root


def lint(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_real_repository_is_clean() -> None:
    result = lint(REPO)
    assert result.returncode == 0, result.stderr


def test_a_clean_tree_passes(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    (root / "platform/ug_core/src/ug_core/a.py").write_text(
        "import json\nfrom ug_core import b\n"
    )
    (root / "domains/water/src/ug_water/a.py").write_text(
        "import ug_core\nfrom ug_water import b\n"
    )
    result = lint(root)
    assert result.returncode == 0, result.stderr
    assert "no forbidden import" in result.stdout


@pytest.mark.parametrize(
    "source",
    [
        "import ug_water",
        "import ug_water.adapter as w",
        "from ug_water import adapter",
        "from ug_water.adapter import WaterAdapter",
        "def late():\n    import ug_water\n",
        "import importlib\nimportlib.import_module('ug_water.adapter')",
        "from importlib import import_module\nimport_module('ug_power')",
        "__import__('ug_water')",
        "import domains.water",
    ],
)
def test_platform_importing_a_domain_is_reported_with_file_and_line(
    tmp_path: Path, source: str
) -> None:
    root = make_tree(tmp_path)
    (root / "platform/ug_core/src/ug_core/bad.py").write_text(source + "\n")
    result = lint(root)
    assert result.returncode == 1
    assert "platform/ug_core/src/ug_core/bad.py:" in result.stderr


def test_a_test_file_under_platform_is_checked_too(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    tests = root / "platform/tests/unit"
    tests.mkdir(parents=True)
    (tests / "test_x.py").write_text("import ug_water\n")
    assert lint(root).returncode == 1


def test_one_domain_importing_another_is_reported(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    (root / "domains/water/src/ug_water/bad.py").write_text(
        "from ug_power import grid\n"
    )
    result = lint(root)
    assert result.returncode == 1
    assert (
        "domain 'water' imports the package 'ug_power' of domain 'power'"
        in result.stderr
    )


def test_a_file_that_cannot_be_parsed_is_reported_not_skipped(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    (root / "platform/ug_core/src/ug_core/broken.py").write_text("def (:\n")
    result = lint(root)
    assert result.returncode == 1
    assert "cannot be parsed" in result.stderr


def test_virtual_environments_are_not_scanned(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    venv = root / "platform/.venv/lib"
    venv.mkdir(parents=True)
    (venv / "dep.py").write_text("import ug_water\n")
    assert lint(root).returncode == 0


def test_a_tree_without_platform_and_domains_is_an_error(tmp_path: Path) -> None:
    assert lint(tmp_path).returncode == 2
