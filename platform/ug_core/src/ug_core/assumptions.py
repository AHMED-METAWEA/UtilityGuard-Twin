"""Assumption sets: the editable, versioned inputs that carry the label `ASSUMPTION`.

Format: Master Spec Appendix A. A file holds one set (`set_id`, `parent`, `note`) and a table of
named assumptions. Each one has a unit, a triangular distribution (`min <= mode <= max`), a
`source_note` and a `verified` flag. `verified: true` is allowed only when the source note names a
source; a value that is a placeholder stays `verified: false`, and the UI shows it as such. The
loader checks the note for hygiene only (long enough, and not beginning with "placeholder", "TBD"
and the like, nor saying "no source"). It cannot judge whether a source is real, so a human
reviews every verified entry.

The loader is strict on purpose: an unknown key, a missing field, a repeated key, a non-finite
number or a distribution out of order is an error, never a silent default. Wrong money inputs
change decisions without anyone noticing.

`parent` is validated as a set id or `null` but not resolved here; inheritance arrives with the
assumption editor.
"""

from __future__ import annotations

import numbers
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ug_core import grammar
from ug_core.canonical import canonical_json, freeze, sha256_hex
from ug_core.evidence import EvidenceLabel
from ug_core.numeric import NonFiniteError, finite

_TOP_KEYS = frozenset({"set_id", "parent", "note", "assumptions"})
_ENTRY_KEYS = frozenset({"unit", "distribution", "source_note", "verified"})
_DISTRIBUTION_KEYS = frozenset({"type", "min", "mode", "max"})
_MAX_EXACT_INT = 2**53
# Contract version of the `assumption-set` payload (contracts/v1/assumption-set.schema.json).
SCHEMA_VERSION = "1"
# A note that BEGINS with one of these, or says outright that there is no source, is not a source.
# Hygiene only: the words are not searched anywhere else, because real citations mention them
# ("replaces the placeholder in v1"), and a human decides whether a named source is real.
_NO_SOURCE_START = re.compile(
    r"^[\W_]*(placeholder|unverified|not verified|tbd|to ?do|n/a|dummy|made up|no source"
    r"|unsourced|قيمة افتراضية|غير موثق|بدون مصدر)",
    re.IGNORECASE,
)
_NO_SOURCE_ANYWHERE = re.compile(
    r"\bno source\b|\bunsourced\b|بدون مصدر", re.IGNORECASE
)
_MIN_SOURCE_NOTE = 10
_MAX_EVIDENCE_ID = 128
_DIGEST_CHARS = 32
_NAME_CHARS = 40


class AssumptionError(ValueError):
    """An assumption file does not meet the format."""


@dataclass(frozen=True)
class Triangular:
    min: float
    mode: float
    max: float

    def __post_init__(self) -> None:
        # The same number rules as the loader (finite, not a bool, exact), also when built directly.
        for slot in ("min", "mode", "max"):
            object.__setattr__(
                self, slot, _number(getattr(self, slot), f"distribution.{slot}")
            )
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

    def __post_init__(self) -> None:
        where = f"assumption {self.name!r}"
        if not grammar.is_assumption_name(self.name):
            raise AssumptionError(
                f"{where}: names are lower-case letters, digits and '_', starting with a letter"
            )
        try:
            grammar.require_unit(self.unit, f"{where}: unit")
        except (TypeError, ValueError) as exc:
            raise AssumptionError(str(exc)) from exc
        if not isinstance(self.distribution, Triangular):
            raise AssumptionError(f"{where}: distribution must be a Triangular")
        _text(self.source_note, f"{where}: source_note")
        if not isinstance(self.verified, bool):
            raise AssumptionError(f"{where}: verified must be true or false")
        if self.verified and (
            len(self.source_note.strip()) < _MIN_SOURCE_NOTE
            or _NO_SOURCE_START.match(self.source_note)
            or _NO_SOURCE_ANYWHERE.search(self.source_note)
        ):
            raise AssumptionError(
                f"{where}: verified is true, but the source note does not name a source"
            )

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

    def __post_init__(self) -> None:
        for what, value in (("set_id", self.set_id), ("parent", self.parent)):
            if value is None and what == "parent":
                continue
            if not grammar.is_identifier(value):
                raise AssumptionError(
                    f"{what} must be an identifier token, got {value!r}"
                )
        if not isinstance(self.note, str) or not self.note.strip():
            raise AssumptionError("note must be a non-empty string")
        if not isinstance(self.assumptions, Mapping) or not self.assumptions:
            raise AssumptionError("an assumption set needs at least one assumption")
        for key, entry in self.assumptions.items():
            if not isinstance(entry, Assumption):
                raise AssumptionError(f"assumption {key!r} is not an Assumption")
            if key != entry.name:
                raise AssumptionError(
                    f"assumption key {key!r} must be the name of its assumption "
                    f"({entry.name!r})"
                )
        # A read-only copy: validated money inputs must not change after a hash was taken.
        object.__setattr__(self, "assumptions", freeze(dict(self.assumptions)))

    def evidence_id(self, name: str) -> str:
        """Stable id of one assumption inside this set, for evidence records (`as_<name>@<set>`).

        At most 128 characters, as the contract requires (see below for a long set id)."""
        if name not in self.assumptions:
            raise KeyError(f"no assumption named {name!r} in set {self.set_id!r}")
        natural = f"as_{name}@{self.set_id}"
        if len(natural) <= _MAX_EVIDENCE_ID:
            return natural
        # A long set id or name would give an id the contract refuses (128 characters at most).
        # The short form starts with `asd_` (as, digest), which no natural id can: they start with
        # `as_`. So a short id never equals the natural id of another set. It keeps the start of
        # the name and ends with a digest of the whole natural id.
        digest = sha256_hex(natural)[:_DIGEST_CHARS]
        return f"asd_{name[:_NAME_CHARS]}-{digest}"

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

    def to_payload(self) -> dict[str, Any]:
        """The set as the `assumption-set` contract payload: `to_dict()` plus `schema_version`."""
        return {"schema_version": SCHEMA_VERSION, **self.to_dict()}

    def content_hash(self) -> str:
        """SHA-256 of the canonical content: the same values give the same hash in any order."""
        return sha256_hex(canonical_json(self.to_dict()))


class _UniqueKeyLoader(yaml.SafeLoader):
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
        return super().construct_mapping(node, deep=deep)


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
    if isinstance(value, numbers.Integral) and not isinstance(value, bool):
        if abs(int(value)) > _MAX_EXACT_INT:  # NumPy integers count too
            raise AssumptionError(
                f"{where} must be exactly representable (at most 2**53), got {int(value)}"
            )
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
    if not grammar.is_assumption_name(name):
        raise AssumptionError(f"{where}: names are lower-case letters, digits and '_'")
    entry = _mapping(raw, where, _ENTRY_KEYS)
    unit = _text(entry["unit"], f"{where}: unit")
    if not grammar.is_unit(unit):
        raise AssumptionError(
            f"{where}: unit must be one ASCII token of 1 to 24 characters, got {unit!r}"
        )
    source_note = _text(entry["source_note"], f"{where}: source_note")
    verified = entry["verified"]
    if not isinstance(verified, bool):
        raise AssumptionError(f"{where}: verified must be true or false")
    if verified and (
        len(source_note.strip()) < _MIN_SOURCE_NOTE
        or _NO_SOURCE_START.match(source_note)
        or _NO_SOURCE_ANYWHERE.search(source_note)
    ):
        raise AssumptionError(
            f"{where}: verified is true, but the source note does not name a source"
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
    if not grammar.is_identifier(set_id):
        raise AssumptionError(f"set_id must be an identifier token, got {set_id!r}")
    parent = top["parent"]
    if parent is not None and not grammar.is_identifier(parent):
        raise AssumptionError("parent must be null or a set id (an identifier token)")
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
