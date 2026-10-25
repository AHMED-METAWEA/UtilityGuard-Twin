"""Verify the installed packages and the standard-library platform boundary."""

import platform
from pathlib import Path

import ug_api
import ug_cli
import ug_core
import ug_intel
import ug_water


def test_package_versions() -> None:
    for package in (ug_core, ug_intel, ug_api, ug_cli, ug_water):
        assert isinstance(package.__version__, str)


def test_platform_is_standard_library() -> None:
    assert Path(platform.__file__).name == "platform.py"


def test_platform_directory_is_not_a_package() -> None:
    root = Path(__file__).resolve().parents[3]
    assert not (root / "platform" / "__init__.py").exists()
