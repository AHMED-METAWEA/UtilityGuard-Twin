"""Safe run and table names; fixed keys from Master Spec section 11.2."""

from __future__ import annotations

import re
from pathlib import Path

from ug_core import grammar
from ug_core.manifest import Manifest


class StoreError(ValueError):
    """An invalid, damaged or non-deterministic stored run."""


def run_id(manifest: Manifest) -> str:
    return "run_" + manifest.input_hash()[:16]


def run_path(root: Path, identifier: str) -> Path:
    if not re.fullmatch(r"run_[0-9a-f]{16}", identifier):
        raise StoreError(f"invalid run id: {identifier!r}")
    return root / identifier


def table_key(name: str, *, internal: bool = False) -> tuple[str, ...]:
    if internal and name == "truth":
        return ("tick", "element_id", "quantity")
    if "truth" in name.casefold():
        raise StoreError(f"restricted table: {name!r}")
    if name in {"telemetry", "expectation", "quality"}:
        return ("tick", "sensor_id")
    if (
        name.startswith("detector_")
        and grammar.is_identifier(name)
        and grammar.is_identifier(name.removeprefix("detector_"))
    ):
        return ("tick",)
    raise StoreError(f"table outside Spec 11.2: {name!r}")
