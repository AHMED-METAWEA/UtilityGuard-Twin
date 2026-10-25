"""Assumption sets: the editable, versioned inputs that carry the label `ASSUMPTION`.

Format: Master Spec Appendix A. A file holds one set (`set_id`, `parent`, `note`) and a table of
named assumptions. Each one has a unit, a triangular distribution (`min <= mode <= max`), a
`source_note` and a `verified` flag. `verified: true` is allowed only when the source note names a
real source; a value that is a placeholder stays `verified: false`, and the UI shows it as such.

The loader is strict on purpose: an unknown key, a missing field, a repeated key, a non-finite
number or a distribution out of order is an error, never a silent default. Wrong money inputs
change decisions without anyone noticing.

`parent` is validated as a set id or `null` but not resolved here; inheritance arrives with the
assumption editor.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ug_core.canonical import canonical_json, sha256_hex
from ug_core.evidence import EvidenceLabel
from ug_core.numeric import NonFiniteError, finite

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_SET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_TOP_KEYS = frozenset({"set_id", "parent", "note", "assumptions"})
_ENTRY_KEYS = frozenset({"unit", "distribution", "source_note", "verified"})
_DISTRIBUTION_KEYS = frozenset({"type", "min", "mode", "max"})
_PLACEHOLDER = re.compile(r"^\s*placeholder", re.IGNORECASE)


class AssumptionError(ValueError):
    """An assumption file does not meet the format."""


@dataclass(frozen=True)
class Triangular:
    min: float
    mode: float
    max: float

    def __post_init__(self) -> None:
        if not (self.min <= self.mode <= self.max):
            raise AssumptionError(
                f"triangular distribution needs min <= mode <= max, got "
                f"min={self.min}, mode={self.mode}, max={self.max}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "triangular",
            "min": self.min,
            "mode": self.mode,
            "max": self.max,
        }


@dataclass(frozen=True)
class Assumption:
    name: str
    unit: str
    distribution: Triangular
    source_note: str
    verified: bool

    label = EvidenceLabel.ASSUMPTION

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit": self.unit,
            "distribution": self.distribution.to_dict(),
            "source_note": self.source_note,
            "verified": self.verified,
        }


@dataclass(frozen=True)
class AssumptionSet:
    set_id: str
    parent: str | None
    note: str
    assumptions: Mapping[str, Assumption]

    def evidence_id(self, name: str) -> str:
        """Stable id of one assumption inside this set, for evidence records (`as_<name>@<set>`)."""
        if name not in self.assumptions:
            raise KeyError(f"no assumption named {name!r} in set {self.set_id!r}")
        return f"as_{name}@{self.set_id}"

    def unverified(self) -> tuple[str, ...]:
        """Names of the assumptions that are not verified, sorted. The UI warns about these."""
        return tuple(sorted(n for n, a in self.assumptions.items() if not a.verified))

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_id": self.set_id,
            "parent": self.parent,
            "note": self.note,
            "assumptions": {
                n: self.assumptions[n].to_dict() for n in sorted(self.assumptions)
            },
        }

    def content_hash(self) -> str:
        """SHA-256 of the canonical content: the same values give the same hash in any order."""
        return sha256_hex(canonical_json(self.to_dict()))


class _UniqueKeyLoader(yaml.SafeLoader):  # type: ignore[misc]
    """`safe_load` that rejects a repeated key instead of keeping the last one."""

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if key in seen:
                raise AssumptionError(
                    f"key {key!r} appears twice (line {key_node.start_mark.line + 1})"
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)  # type: ignore[no-any-return]


def _mapping(value: Any, where: str, required: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AssumptionError(f"{where} must be a mapping")
    unknown = sorted(str(k) for k in value if k not in required)
    if unknown:
        raise AssumptionError(f"{where} has unknown keys: {unknown}")
    missing = sorted(required - set(value))
    if missing:
        raise AssumptionError(f"{where} is missing keys: {missing}")
    return value


def _number(value: Any, where: str) -> float:
    try:
        return finite(value, where)
    except (NonFiniteError, TypeError, ValueError) as exc:
        raise AssumptionError(f"{where} must be a finite number: {exc}") from exc


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssumptionError(f"{where} must be a non-empty string")
    return value


def _parse_entry(name: str, raw: Any) -> Assumption:
    where = f"assumption {name!r}"
    if not _NAME.match(name):
        raise AssumptionError(f"{where}: names are lower-case letters, digits and '_'")
    entry = _mapping(raw, where, _ENTRY_KEYS)
    unit = _text(entry["unit"], f"{where}: unit")
    source_note = _text(entry["source_note"], f"{where}: source_note")
    verified = entry["verified"]
    if not isinstance(verified, bool):
        raise AssumptionError(f"{where}: verified must be true or false")
    if verified and _PLACEHOLDER.match(source_note):
        raise AssumptionError(
            f"{where}: verified is true but the source note says placeholder"
        )
    dist = _mapping(entry["distribution"], f"{where}: distribution", _DISTRIBUTION_KEYS)
    if dist["type"] != "triangular":
        raise AssumptionError(f"{where}: unknown distribution type {dist['type']!r}")
    triangular = Triangular(
        min=_number(dist["min"], f"{where}: distribution.min"),
        mode=_number(dist["mode"], f"{where}: distribution.mode"),
        max=_number(dist["max"], f"{where}: distribution.max"),
    )
    return Assumption(name, unit, triangular, source_note, verified)


def parse_assumptions(data: Any) -> AssumptionSet:
    """Validate parsed YAML or JSON and build the set."""
    top = _mapping(data, "assumption file", _TOP_KEYS)
    set_id = _text(top["set_id"], "set_id")
    if not _SET_ID.match(set_id):
        raise AssumptionError(
            f"set_id {set_id!r} has characters outside letters, digits, . _ -"
        )
    parent = top["parent"]
    if parent is not None and (
        not isinstance(parent, str) or not _SET_ID.match(parent)
    ):
        raise AssumptionError("parent must be null or a set id")
    note = _text(top["note"], "note")
    table = top["assumptions"]
    if not isinstance(table, Mapping) or not table:
        raise AssumptionError("assumptions must be a non-empty mapping")
    entries = {str(name): _parse_entry(str(name), raw) for name, raw in table.items()}
    return AssumptionSet(set_id, parent, note, entries)


def load_assumptions(path: str | Path) -> AssumptionSet:
    """Read and validate an assumption file."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise AssumptionError(f"{path}: not valid YAML: {exc}") from exc
    return parse_assumptions(data)
