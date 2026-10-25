"""Loading the contracts for tests: strict JSON, schemas with working cross-file references."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "contracts"
SCHEMA_DIR = CONTRACTS / "v1"
ID_BASE = "https://utilityguard.invalid/contracts/v1/"
SUFFIX = ".schema.json"


def _no_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON; use null for a missing value")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate key in {keys}")
    return dict(pairs)


def parse_json(text: str) -> Any:
    """Strict JSON: no NaN or infinity literals, no repeated keys."""
    return json.loads(
        text, parse_constant=_no_constant, object_pairs_hook=_no_duplicate_keys
    )


def load_json(path: Path) -> Any:
    return parse_json(path.read_text(encoding="utf-8"))


def schema_names() -> list[str]:
    """Names of the payload schemas (everything except the shared definitions)."""
    return sorted(
        p.name.removesuffix(SUFFIX)
        for p in SCHEMA_DIR.glob(f"*{SUFFIX}")
        if p.name != f"common{SUFFIX}"
    )


def load_schemas() -> dict[str, Any]:
    return {
        p.name.removesuffix(SUFFIX): load_json(p)
        for p in sorted(SCHEMA_DIR.glob(f"*{SUFFIX}"))
    }


def build_registry() -> Registry:  # type: ignore[type-arg]
    registry: Registry = Registry()  # type: ignore[type-arg]
    for schema in load_schemas().values():
        resource = Resource.from_contents(schema, default_specification=DRAFT202012)
        registry = registry.with_resource(schema["$id"], resource)
    return registry


def validator_for(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schemas()[name], registry=build_registry())


def files(kind: str) -> list[Path]:
    """Every JSON file under contracts/examples or contracts/invalid, in a stable order."""
    return sorted((CONTRACTS / kind).rglob("*.json"))
