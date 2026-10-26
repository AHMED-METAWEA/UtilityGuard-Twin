"""Verify the installed packages and the standard-library platform boundary."""

import platform
from importlib.metadata import version
from pathlib import Path

import ug_api
import ug_cli
import ug_core
import ug_intel


def test_package_versions() -> None:
    for package in (ug_core, ug_intel, ug_api, ug_cli):
        assert isinstance(package.__version__, str)


def test_all_five_packages_are_installed() -> None:
    # Installation metadata only: `platform/` must never import a domain package, so the water
    # package is checked here without importing it (its own tests import it).
    for distribution in ("ug-core", "ug-intel", "ug-api", "ug-cli", "ug-water"):
        assert version(distribution) == "0.0.0"


def test_platform_is_standard_library() -> None:
    assert Path(platform.__file__).name == "platform.py"


def test_platform_directory_is_not_a_package() -> None:
    root = Path(__file__).resolve().parents[3]
    assert not (root / "platform" / "__init__.py").exists()
