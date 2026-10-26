#!/usr/bin/env python3
"""Check that the repository layout matches Master Spec section 14.

Standard library only, so it runs before `make install`.
Exit code 0 when the layout is complete, 1 otherwise (with the problems listed).

Usage: python scripts/check_layout.py [--root PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Directories required by Master Spec section 14 (data/ is git-ignored and not checked).
REQUIRED_DIRS = [
    "docs",
    "docs/adr",
    "contracts",
    "assumptions",
    "platform",
    "platform/ug_core",
    "platform/ug_intel",
    "platform/ug_api",
    "platform/ug_cli",
    "platform/tests",
    "domains",
    "domains/water",
    "domains/electricity",
    "domains/cooling",
    "frontend",
    "eval",
    "deploy",
    ".github/workflows",
]

REQUIRED_FILES = ["README.md", "CLAUDE.md", "AGENTS.md"]

# Installable projects: (project folder, importable package).
PACKAGES = [
    ("platform/ug_core", "ug_core"),
    ("platform/ug_intel", "ug_intel"),
    ("platform/ug_api", "ug_api"),
    ("platform/ug_cli", "ug_cli"),
    ("domains/water", "ug_water"),
]


def check(root: Path) -> list[str]:
    problems: list[str] = []
    for rel in REQUIRED_DIRS:
        if not (root / rel).is_dir():
            problems.append(f"missing directory: {rel}/")
    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            problems.append(f"missing file: {rel}")
    for folder, pkg in PACKAGES:
        base = root / folder
        if not (base / "pyproject.toml").is_file():
            problems.append(f"missing {folder}/pyproject.toml")
        if not (base / "src" / pkg / "__init__.py").is_file():
            problems.append(f"missing {folder}/src/{pkg}/__init__.py")
    # platform/ must stay a plain folder: a package named `platform` shadows the standard library.
    if (root / "platform" / "__init__.py").exists():
        problems.append(
            "platform/__init__.py exists: it would shadow the standard-library module `platform`"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    args = parser.parse_args()
    problems = check(args.root)
    if problems:
        print(f"layout check FAILED ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("layout check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
