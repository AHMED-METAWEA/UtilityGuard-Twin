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
    assert "domain 'water' imports 'ug_power' from domain power" in result.stderr


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


@pytest.mark.parametrize(
    "source",
    [
        "from importlib import import_module as load\nload('ug_water.adapter')",
        "import importlib\nimportlib.import_module(name='ug_water.adapter')",
        "import importlib as il\nil.import_module('ug_water')",
        "from importlib import import_module\nimport_module(name='ug_power')",
        "__import__(name='ug_water')",
        "import builtins\nbuiltins.__import__('ug_water')",
    ],
)
def test_dynamic_imports_are_found_through_aliases_and_keywords(
    tmp_path: Path, source: str
) -> None:
    root = make_tree(tmp_path)
    (root / "platform/ug_core/src/ug_core/bad.py").write_text(source + "\n")
    assert lint(root).returncode == 1


def test_an_unrelated_method_named_import_module_is_not_an_import(
    tmp_path: Path,
) -> None:
    root = make_tree(tmp_path)
    source = (
        "class Catalog:\n"
        "    def import_module(self, name):\n"
        "        return name\n"
        "\n"
        "Catalog().import_module('ug_water')\n"
    )
    (root / "platform/ug_core/src/ug_core/ok.py").write_text(source)
    result = lint(root)
    assert result.returncode == 0, result.stderr


def test_namespace_packages_and_single_modules_are_domain_packages(
    tmp_path: Path,
) -> None:
    root = make_tree(tmp_path)
    (
        root / "domains/water/src/ug_water/__init__.py"
    ).unlink()  # now a namespace package
    (root / "domains/water/src/ug_single.py").write_text("")
    for module in ("ug_water.adapter", "ug_single"):
        (root / "platform/ug_core/src/ug_core/bad.py").write_text(f"import {module}\n")
        result = lint(root)
        assert result.returncode == 1, module
        assert module.split(".")[0] in result.stderr


def test_domains_sharing_a_namespace_keep_their_own_ownership(tmp_path: Path) -> None:
    root = tmp_path
    for domain in ("water", "power"):
        package = root / "domains" / domain / "src" / "ug_domains" / domain
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
    (root / "platform/ug_core/src/ug_core").mkdir(parents=True)
    (root / "platform/ug_core/src/ug_core/__init__.py").write_text("")
    water = root / "domains/water/src/ug_domains/water"
    (water / "own.py").write_text("from ug_domains.water import other\n")
    assert lint(root).returncode == 0
    (water / "bad.py").write_text("import ug_domains.power.grid\n")
    result = lint(root)
    assert result.returncode == 1
    assert "domain 'water' imports" in result.stderr
    (water / "bad.py").unlink()
    (root / "platform/ug_core/src/ug_core/bad.py").write_text(
        "import ug_domains.water\n"
    )
    assert lint(root).returncode == 1


def test_from_imports_of_a_shared_namespace_resolve_the_imported_child(
    tmp_path: Path,
) -> None:
    root = tmp_path
    for domain in ("water", "power"):
        package = root / "domains" / domain / "src" / "ug_domains" / domain
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
    (root / "platform/ug_core/src/ug_core").mkdir(parents=True)
    (root / "platform/ug_core/src/ug_core/__init__.py").write_text("")
    water = root / "domains/water/src/ug_domains/water"
    for own in ("from ug_domains import water", "from ug_domains.water import x"):
        (water / "own.py").write_text(own + "\n")
        result = lint(root)
        assert result.returncode == 0, (own, result.stderr)
    for foreign in (
        "from ug_domains import power",
        "from ug_domains.power import grid",
    ):
        (water / "bad.py").write_text(foreign + "\n")
        result = lint(root)
        assert result.returncode == 1, foreign
        assert "from domain power" in result.stderr
        assert result.stderr.count("bad.py:1") == 1  # one report per offending line
