#!/usr/bin/env python3
"""Import lint: `platform/` never imports `domains/`, and one domain never imports another.

Master Spec principle P4: the core knows domains only through `DomainAdapter` and the
`ug.domains` entry-point registry. This script reads every Python file with the `ast` module
(nothing is executed) and reports each import of a domain package from where it must not appear.

Detected: `import x`, `from x import y`, and calls of `importlib.import_module` or `__import__`
with a literal module name (positional or `name=`), also through an alias of `importlib`, of
`import_module`, or one re-binding such as `load = importlib.import_module`. Domain packages are
regular packages, namespace packages and single modules under `domains/*/src/`. Not detected: a
module name built at run time, deeper re-binding, or a `sys.path` change that makes a domain
importable under another name. Those would need review, not a linter.

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


def domain_packages(domains_dir: Path) -> dict[str, set[str]]:
    """Top-level importable name -> domain folders that provide it, from `domains/*/src/`.

    Regular packages, namespace packages (folders without `__init__.py`) and single-file modules
    all count. Two domains may share a namespace such as `ug_domains`.
    """
    owners: dict[str, set[str]] = {}
    for src in sorted(domains_dir.glob("*/src")):
        for entry in sorted(src.iterdir()):
            name = entry.stem if entry.suffix == ".py" else entry.name
            hidden = name.startswith(("_", ".")) or entry.name.endswith(".egg-info")
            if hidden or not (entry.is_dir() or entry.suffix == ".py"):
                continue
            owners.setdefault(name, set()).add(src.parent.name)
    return owners


def _provides(domains_dir: Path, domain: str, parts: list[str]) -> bool:
    """Does `domain` contain the module path given by its first two name parts?"""
    base = domains_dir / domain / "src" / parts[0]
    if len(parts) < 2:
        return base.exists() or base.with_suffix(".py").exists()
    return (base / parts[1]).is_dir() or (base / f"{parts[1]}.py").is_file()


def foreign_owners(
    module: str, owner: str | None, owners: dict[str, set[str]], domains_dir: Path
) -> set[str]:
    """Domains that provide `module` and that code in `owner` (None = platform) may not import."""
    candidates = owners.get(module.split(".")[0], set())
    if owner is None:
        return set(candidates)
    if len(candidates) <= 1:
        return candidates - {owner}
    # A namespace shared by several domains: decide by the qualified path.
    parts = module.split(".")
    matched = {d for d in candidates if _provides(domains_dir, d, parts)}
    return set() if owner in matched else matched


def _import_names(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    """Names bound to the importlib module, to builtins, and to a dynamic-import function."""
    modules: set[str] = set()  # names for `importlib` or `builtins`
    functions: set[str] = {"__import__"}  # names that import a module when called
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"importlib", "builtins"}:
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in {
            "importlib",
            "builtins",
        }:
            for alias in node.names:
                if alias.name in {"import_module", "__import__"}:
                    functions.add(alias.asname or alias.name)
    # One level of re-binding: `loader = importlib.import_module`.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
            if isinstance(target, ast.Name) and _is_import_function(
                value, modules, functions
            ):
                functions.add(target.id)
    return modules, functions, set()


def _is_import_function(node: ast.AST, modules: set[str], functions: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in functions
    return (
        isinstance(node, ast.Attribute)
        and node.attr in {"import_module", "__import__"}
        and isinstance(node.value, ast.Name)
        and node.value.id in modules
    )


def imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    """(line, dotted module name) for every absolute import in the tree."""
    modules, functions, _ = _import_names(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
            # `from pkg import child` may import the submodule `pkg.child`.
            found.extend(
                (node.lineno, f"{node.module}.{alias.name}")
                for alias in node.names
                if alias.name != "*"
            )
        elif isinstance(node, ast.Call) and _is_import_function(
            node.func, modules, functions
        ):
            argument = node.args[0] if node.args else None
            if argument is None:
                argument = next(
                    (k.value for k in node.keywords if k.arg == "name"), None
                )
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                found.append((node.lineno, argument.value))
    return found


def scan(root: Path) -> tuple[list[str], int, int]:
    """Return (violations, files checked in platform/, files checked in domains/)."""
    domains_dir = root / "domains"
    owners = domain_packages(domains_dir)
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
            reported: set[tuple[int, frozenset[str]]] = set()
            for line, module in imported_modules(tree):
                if module.split(".")[0] == "domains" and owner is None:
                    violations.append(
                        f"{relative}:{line}: platform code imports 'domains' ({module})"
                    )
                    continue
                foreign = foreign_owners(module, owner, owners, domains_dir)
                if not foreign or (line, frozenset(foreign)) in reported:
                    continue  # one report per line and offending domain
                reported.add((line, frozenset(foreign)))
                names = ", ".join(sorted(foreign))
                if owner is None:
                    violations.append(
                        f"{relative}:{line}: platform code imports '{module}' from domain "
                        f"{names}; use the DomainAdapter registry instead"
                    )
                else:
                    violations.append(
                        f"{relative}:{line}: domain '{owner}' imports '{module}' from domain "
                        f"{names}; cross-domain effects are explicit scenario inputs, never imports"
                    )

    check(root / "platform", None)
    for domain in sorted(domains_dir.iterdir()):
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
