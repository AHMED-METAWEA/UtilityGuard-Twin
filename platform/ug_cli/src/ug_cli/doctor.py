"""Read-only, offline environment checks for the UtilityGuard CLI."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from ug_core.adapter import HasHealthChecks
from ug_core.registry import DomainRegistrationError, discover

if TYPE_CHECKING:
    from referencing.typing import Resolver


@dataclass(frozen=True)
class Result:
    name: str
    status: Literal["ok", "warn", "fail"]
    detail: str

    def __post_init__(self) -> None:
        # Plugin and parser messages can span lines; each CLI check occupies one line.
        object.__setattr__(self, "detail", " ".join(self.detail.splitlines()))


def check_python() -> Result:
    version = sys.version_info
    return Result(
        "python",
        "ok" if version >= (3, 11) else "fail",
        f"Python {version.major}.{version.minor}.{version.micro}; requires >= 3.11",
    )


def check_domains() -> list[Result]:
    try:
        adapters = discover()
    except DomainRegistrationError as exc:
        return [Result("domains", "fail", f"Domain discovery: {exc}")]
    if not adapters:
        return [Result("domains", "fail", "Domain discovery: no domains installed")]
    results = [
        Result("domains", "ok", "Installed domains: " + ", ".join(sorted(adapters)))
    ]
    for name, adapter in sorted(adapters.items()):
        try:
            if not isinstance(adapter, HasHealthChecks):
                results.append(Result(name, "warn", f"{name}: no health checks"))
                continue
            checks = [
                Result(
                    f"{name}.{check.name}", "ok" if check.ok else "fail", check.detail
                )
                for check in adapter.health_checks()
            ]
            results.extend(checks)
        except Exception as exc:
            results.append(
                Result(
                    name,
                    "fail",
                    f"{name} health checks raised {type(exc).__name__}: {exc}",
                )
            )
    return results


def _no_constant(value: str) -> Any:
    raise ValueError(f"{value} is not valid JSON")


def _finite_float(text: str) -> float:
    """A number such as 1e9999 overflows to infinity: JSON Schema accepts that, a contract must not."""
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"{text} is not a finite number")
    return value


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _check_refs(resource: Resource[Any], resolver: Resolver[Any]) -> None:
    """Walk schema locations, preserving nested IDs without following reference cycles."""
    schema = resource.contents
    if isinstance(schema, dict):
        for keyword in ("$ref", "$dynamicRef"):
            if keyword in schema:
                ref = schema[keyword]
                try:
                    resolved = resolver.lookup(ref)
                except Exception as exc:
                    raise ValueError(f"unresolvable {keyword} {ref!r}: {exc}") from exc
                # The target must itself be a schema: a pointer into arbitrary data (a `default`,
                # an `examples` entry) resolves, but would crash the validator later.
                try:
                    Draft202012Validator.check_schema(resolved.contents)
                except SchemaError as exc:
                    raise ValueError(
                        f"{keyword} {ref!r} does not point at a valid schema: {exc.message}"
                    ) from exc
    for child in sorted(
        resource.subresources(),
        key=lambda child: json.dumps(child.contents, sort_keys=True),
    ):
        _check_refs(child, resolver.in_subresource(child))


def check_contracts(root: Path | None) -> list[Result]:
    if root is None:
        cwd = Path.cwd()
        root = next(
            (p for p in (cwd, *cwd.parents) if (p / "contracts/v1").is_dir()), None
        )
    if root is None or not (root / "contracts/v1").is_dir():
        return [
            Result(
                "contracts",
                "fail",
                "Contracts folder contracts/v1 not found; use --root PATH",
            )
        ]
    paths = sorted((root / "contracts/v1").glob("*.schema.json"))
    registry: Registry[Any] = Registry()
    resources: dict[Path, Resource[Any]] = {}
    results: dict[Path, Result] = {}
    ids: set[str] = set()
    for path in paths:
        try:
            schema = json.loads(
                path.read_text(encoding="utf-8"),
                parse_constant=_no_constant,
                parse_float=_finite_float,
                object_pairs_hook=_unique_keys,
            )
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema, default_specification=DRAFT202012)
            identifier = resource.id() or path.resolve().as_uri()
            if identifier in ids:
                raise ValueError(f"duplicate schema $id {identifier!r}")
            ids.add(identifier)
            registry = registry.with_resource(identifier, resource)
            resources[path] = resource
        except Exception as exc:
            results[path] = Result(
                f"contracts.{path.stem}",
                "fail",
                f"{path.name}: {type(exc).__name__}: {exc}",
            )
    for path, resource in resources.items():
        try:
            resolver = registry.resolver(resource.id() or path.resolve().as_uri())
            _check_refs(resource, resolver)
            results[path] = Result(
                f"contracts.{path.stem}",
                "ok",
                f"{path.name}: strict JSON, Draft 2020-12 schema and references valid",
            )
        except Exception as exc:
            results[path] = Result(
                f"contracts.{path.stem}",
                "fail",
                f"{path.name}: {type(exc).__name__}: {exc}",
            )
    failures = sum(result.status == "fail" for result in results.values())
    return [results[path] for path in paths] + [
        Result(
            "contracts",
            "fail" if failures or not paths else "ok",
            f"Contracts: {len(paths)} schema files checked; {failures} failed"
            if paths
            else "Contracts: no *.schema.json files found in contracts/v1",
        )
    ]


def check_tool(name: Literal["node", "docker"]) -> Result:
    executable = shutil.which(name)
    if executable is None:
        return Result(name, "warn", f"{name} --version: executable not found")
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Result(name, "warn", f"{name} --version: {type(exc).__name__}: {exc}")
    if completed.returncode:
        return Result(name, "warn", f"{name} --version exited {completed.returncode}")
    version = completed.stdout.strip()
    if name == "docker":
        return Result(name, "ok", f"docker --version: {version}")
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    ok = match is not None and tuple(map(int, match.groups())) >= (22, 13, 0)
    return Result(
        name, "ok" if ok else "warn", f"node --version: {version!r}; requires >= 22.13"
    )


def run_doctor(root: Path | None) -> list[Result]:
    return [
        check_python(),
        *check_domains(),
        *check_contracts(root),
        check_tool("node"),
        check_tool("docker"),
    ]
