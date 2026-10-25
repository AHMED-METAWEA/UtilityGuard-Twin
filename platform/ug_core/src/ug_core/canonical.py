"""Canonical JSON and hashing.

Same content must give the same bytes on every machine and in every process, whatever the insertion
order of dictionaries or the hash seed of the interpreter.

Rules:
- Dictionary keys must be strings and are sorted; list and tuple order is kept (order that does not
  matter is sorted by the caller before hashing, see `Manifest`).
- Numbers must be finite. A float with an integral value is written as an integer (`1.0` and `1`
  hash the same, so a YAML loader and a JSON loader agree); other floats use the shortest
  round-trip representation. Negative zero is written as 0.
- Sets, datetimes and other types are rejected: convert them explicitly first.
"""

from __future__ import annotations

import hashlib
import json
import numbers
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from ug_core.numeric import finite

_MAX_EXACT_INT = 2**53


def canonical(obj: Any) -> Any:
    """Return `obj` reduced to plain JSON types in canonical form."""
    if obj is None or isinstance(obj, str | bool):
        return obj
    if isinstance(obj, numbers.Integral):
        return int(obj)
    if isinstance(obj, numbers.Real):
        number = finite(obj)
        if number.is_integer() and abs(number) < _MAX_EXACT_INT:
            return int(number)
        return number
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"mapping keys must be strings, got {type(key).__name__}"
                )
            out[key] = canonical(value)
        return out
    if isinstance(obj, list | tuple):
        return [canonical(item) for item in obj]
    raise TypeError(
        f"cannot canonicalize {type(obj).__name__}; convert it to JSON types first"
    )


def canonical_json(obj: Any) -> str:
    """Canonical JSON text of `obj` (sorted keys, no spaces, ASCII only, finite numbers only)."""
    return json.dumps(
        canonical(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze(obj: Any) -> Any:
    """Deeply immutable copy: mappings become read-only views, lists become tuples."""
    if isinstance(obj, Mapping):
        return MappingProxyType({key: freeze(value) for key, value in obj.items()})
    if isinstance(obj, list | tuple):
        return tuple(freeze(item) for item in obj)
    return obj


def thaw(obj: Any) -> Any:
    """Inverse of `freeze`: plain dicts and lists, for serialization."""
    if isinstance(obj, Mapping):
        return {key: thaw(value) for key, value in obj.items()}
    if isinstance(obj, list | tuple):
        return [thaw(item) for item in obj]
    return obj
