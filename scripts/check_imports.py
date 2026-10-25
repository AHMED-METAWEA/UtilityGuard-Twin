#!/usr/bin/env python3
"""Import lint: `platform/` never imports `domains/`, and one domain never imports another.

Master Spec principle P4: the core knows domains only through `DomainAdapter` and the
`ug.domains` entry-point registry. This script reads every Python file with the `ast` module
(nothing is executed) and reports each import of a domain package from where it must not appear.

Detected: `import x`, `from x import y`, and `importlib.import_module("x")` / `__import__("x")`
with a literal name. Not detected: a module name built at run time, or a `sys.path` change that
makes a domain importable under another name. Those would need review, not a linter.

Exit codes: 0 clean, 1 violations, 2 the tree has no `platform/` or `domains/` folder.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

SKIPPED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"}


def python_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*.py")
        if not (set(path.relative_to(folder).parts) & SKIPPED_DIRS)
        and not any(part.endswith(".egg-info") for part in path.parts)
    )


def domain_packages(domains_dir: Path) -> dict[str, str]:
    """Top-level importable package name -> domain folder name, from `domains/*/src/*/`."""
    packages: dict[str, str] = {}
    for src in sorted(domains_dir.glob("*/src")):
        for package in sorted(src.iterdir()):
            if (package / "__init__.py").is_file():
                packages[package.name] = src.parent.name
    return packages


def imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    """(line, dotted module name) for every absolute import in the tree."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else getattr(func, "id", "")
            )
            first = node.args[0]
            if (
                name in {"import_module", "__import__"}
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
            ):
                found.append((node.lineno, first.value))
    return found


def scan(root: Path) -> tuple[list[str], int, int]:
    """Return (violations, files checked in platform/, files checked in domains/)."""
    packages = domain_packages(root / "domains")
    violations: list[str] = []
    counts = {"platform": 0, "domains": 0}

    def check(folder: Path, owner: str | None) -> None:
        kind = "platform" if owner is None else "domains"
        for path in python_files(folder):
            counts[kind] += 1
            relative = path.relative_to(root)
            try:
                tree = ast.parse(
                    path.read_text(encoding="utf-8"), filename=str(relative)
                )
            except (SyntaxError, UnicodeDecodeError) as exc:
                violations.append(
                    f"{relative}: cannot be parsed, so it cannot be checked ({exc})"
                )
                continue
            for line, module in imported_modules(tree):
                top = module.split(".")[0]
                if top == "domains" and owner is None:
                    violations.append(
                        f"{relative}:{line}: platform code imports 'domains' ({module})"
                    )
                elif top in packages and packages[top] != owner:
                    if owner is None:
                        violations.append(
                            f"{relative}:{line}: platform code imports the domain package "
                            f"'{top}' ({module}); use the DomainAdapter registry instead"
                        )
                    else:
                        violations.append(
                            f"{relative}:{line}: domain '{owner}' imports the package '{top}' of "
                            f"domain '{packages[top]}'; cross-domain effects are explicit "
                            "scenario inputs, never imports"
                        )

    check(root / "platform", None)
    for domain in sorted((root / "domains").iterdir()):
        if domain.is_dir() and domain.name not in SKIPPED_DIRS:
            check(domain, domain.name)
    return violations, counts["platform"], counts["domains"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    root = parser.parse_args(argv).root.resolve()
    if not (root / "platform").is_dir() or not (root / "domains").is_dir():
        print(f"{root} has no platform/ or domains/ folder", file=sys.stderr)
        return 2
    violations, platform_files, domain_files = scan(root)
    if violations:
        print(f"import lint FAILED ({len(violations)} violation(s)):", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1
    print(
        f"import lint OK: {platform_files} files in platform/, {domain_files} in domains/, "
        "no forbidden import"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
