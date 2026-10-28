"""Offline, fail-closed access to recorded operator-facing run bundles."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}")
SCHEMAS = Path(__file__).resolve().parents[4] / "contracts/v1"


class RunError(Exception):
    """A public, sanitised problem; never include payload values."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)


def identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise RunError(404, "Unknown identifier")
    return value


def _constant(value: str) -> Any:
    raise ValueError("Non-JSON constant")


def _float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite number")
    return result


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate key")
    return result


def parse_json(value: str | bytes) -> Any:
    """Reject repeated keys and non-finite numbers, including float overflow."""
    return json.loads(
        value, parse_constant=_constant, parse_float=_float, object_pairs_hook=_object
    )


class Contracts:
    """Resolve only the checked-in v1 schemas; no network retrieval is installed."""

    def __init__(self) -> None:
        # Imported here, not at module load: the API container installs neither jsonschema nor
        # contracts/, and must start (it serves no run bundle). Reading a bundle there fails
        # loudly with a 500 instead of serving unvalidated data.
        try:
            from jsonschema import (  # type: ignore[import-untyped]
                Draft202012Validator,
            )
            from jsonschema.exceptions import (  # type: ignore[import-untyped]
                ValidationError,
            )
            from referencing import Registry, Resource
        except ImportError:
            raise RunError(500, "Contract validation is not installed") from None
        paths = sorted(SCHEMAS.glob("*.json"))
        if not paths:
            raise RunError(500, "Contract schemas are not installed")
        self.error = ValidationError
        schemas = [parse_json(p.read_bytes()) for p in paths]
        registry: Registry[Any] = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas
        )
        self.validators = {
            schema["$id"]
            .rsplit("/", 1)[1]
            .removesuffix(".schema.json"): Draft202012Validator(
                schema, registry=registry
            )
            for schema in schemas
        }

    def validate(self, name: str, value: Any, file: str, status: int = 500) -> None:
        try:
            # Also guards hook outputs, which did not pass through the JSON parser.
            parse_json(json.dumps(value, allow_nan=False))
            self.validators[name].validate(value)
        except (self.error, ValueError, TypeError):
            raise RunError(status, f"Invalid payload: {file}") from None


@dataclass(frozen=True)
class RunBundle:
    """Validated snapshot passed to the injected what-if engine."""

    run_id: str
    manifest: dict[str, Any]
    network: dict[str, Any]
    series: dict[str, dict[str, Any]]
    incidents: list[dict[str, Any]]
    decision: dict[str, Any] | None
    evidence: dict[str, dict[str, Any]]
    readings: list[dict[str, Any]] | None


WhatIfHook = Callable[[RunBundle, dict[str, Any]], dict[str, Any]]


class RunStore:
    """Validate a whole bundle on each load; never cache partially valid data."""

    def __init__(self, root: Path | None) -> None:
        self.root = root.resolve() if root is not None else None
        self._contracts: Contracts | None = None

    @property
    def contracts(self) -> Contracts:
        """Built on first use, so the app starts where validation is not installed."""
        if self._contracts is None:
            self._contracts = Contracts()
        return self._contracts

    def list(self) -> list[dict[str, Any]]:
        if self.root is None or not self.root.exists():
            return []
        try:
            paths = sorted(self.root.iterdir())
        except OSError:
            raise RunError(500, "Cannot read runs directory") from None
        summaries = []
        for path in paths:
            if path.is_dir() or path.is_symlink():
                bundle = self.load(path.name)
                summaries.append(
                    {
                        "run_id": bundle.run_id,
                        "scenario_id": bundle.manifest["config"]["scenario_id"],
                        "seed": bundle.manifest["seed"],
                        "simulation_start": bundle.manifest["config"]["start"],
                    }
                )
        return summaries

    def load(self, run_id: str) -> RunBundle:
        identifier(run_id)
        if self.root is None:
            raise RunError(404, "Unknown run")
        directory = self.root / run_id
        if directory.is_symlink():
            raise RunError(500, "Invalid bundle directory")
        if not directory.is_dir():
            raise RunError(404, "Unknown run")
        if not directory.resolve().is_relative_to(self.root):
            raise RunError(404, "Unknown run")
        files: dict[str, Any] = {}
        fixed = {
            "manifest.json": "run-manifest",
            "network.json": "network-view",
            "incidents.json": "incident",
            "decision.json": "decision-comparison",
            "readings.json": "telemetry-reading",
        }
        try:
            # Explicit enumeration propagates I/O errors; rglob can silently skip
            # unreadable directories and leave an apparently valid partial bundle.
            entries = []
            for path in sorted(directory.iterdir()):
                if (
                    path.name in {"series", "evidence"}
                    and path.is_dir()
                    and not path.is_symlink()
                ):
                    entries.extend(sorted(path.iterdir()))
                else:
                    entries.append(path)
            for path in entries:
                relative = path.relative_to(directory)
                name = relative.as_posix()
                if path.is_symlink():
                    raise RunError(500, f"Invalid bundle file: {name}")
                schema = fixed.get(name)
                if (
                    len(relative.parts) == 2
                    and relative.parts[0] in {"series", "evidence"}
                    and path.suffix == ".json"
                    and IDENTIFIER.fullmatch(path.stem)
                ):
                    schema = (
                        "time-series"
                        if relative.parts[0] == "series"
                        else "evidence-record"
                    )
                if schema is None or not path.is_file():
                    raise RunError(500, f"Unexpected bundle file: {name}")
                try:
                    value = parse_json(path.read_bytes())
                except (OSError, ValueError, UnicodeError):
                    raise RunError(500, f"Invalid payload: {name}") from None
                if name in {"incidents.json", "readings.json"}:
                    if not isinstance(value, list):
                        raise RunError(500, f"Invalid payload: {name}")
                    for item in value:
                        self.contracts.validate(schema, item, name)
                else:
                    self.contracts.validate(schema, value, name)
                items = value if isinstance(value, list) else [value]
                for item in items:
                    if "run_id" in item and item["run_id"] != run_id:
                        raise RunError(500, f"Invalid payload: {name}")
                if schema in {"time-series", "evidence-record"}:
                    key = "series_id" if schema == "time-series" else "evidence_id"
                    if value[key] != path.stem:
                        raise RunError(500, f"Invalid payload: {name}")
                files[name] = value
        except OSError:
            raise RunError(500, "Cannot read bundle") from None
        for required in ("manifest.json", "network.json", "incidents.json"):
            if required not in files:
                raise RunError(500, f"Missing bundle file: {required}")
        return RunBundle(
            run_id,
            files["manifest.json"],
            files["network.json"],
            {Path(k).stem: v for k, v in files.items() if k.startswith("series/")},
            files["incidents.json"],
            files.get("decision.json"),
            {Path(k).stem: v for k, v in files.items() if k.startswith("evidence/")},
            files.get("readings.json"),
        )

    def validate_whatif(self, value: Any, run_id: str) -> None:
        """Validate the hook envelope and each nested contract before responding."""
        file = "what-if output"
        if (
            not isinstance(value, dict)
            or set(value)
            != {"run_id", "whatif_hash", "series", "incidents", "decision"}
            or value["run_id"] != run_id
        ):
            raise RunError(500, f"Invalid payload: {file}")
        if not isinstance(value["whatif_hash"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", value["whatif_hash"]
        ):
            raise RunError(500, f"Invalid payload: {file}")
        for key, schema in (("series", "time-series"), ("incidents", "incident")):
            if not isinstance(value[key], list):
                raise RunError(500, f"Invalid payload: {file}")
            for item in value[key]:
                self.contracts.validate(schema, item, file)
                if item["run_id"] != run_id:
                    raise RunError(500, f"Invalid payload: {file}")
        if value["decision"] is not None:
            self.contracts.validate("decision-comparison", value["decision"], file)
            if value["decision"]["run_id"] != run_id:
                raise RunError(500, f"Invalid payload: {file}")
