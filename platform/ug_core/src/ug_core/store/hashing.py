"""Content hashes: canonical schema, declared key, evidence label and sorted rows.

The digest is SHA-256 of canonical JSON with keys columns, key, label, rows.
Columns include name, Arrow type and nullability, in schema order. Rows are
arrays in that same order, sorted by the declared unique key. Floating point
values are rounded only for hashing, never for storage. JSON is fed incrementally
to the digest to avoid constructing a second full copy of a week-long table.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]

from ug_core.canonical import canonical_json
from ug_core.numeric import round_for_hash
from ug_core.store.layout import StoreError


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round_for_hash(value)
    if isinstance(value, list | tuple):
        return [_rounded(item) for item in value]
    if isinstance(value, dict):
        return {name: _rounded(item) for name, item in value.items()}
    return value


def table_hash(table: pa.Table, key: tuple[str, ...]) -> str:
    """Validate scalar content and unique keys, then hash independently of row order."""
    names = table.column_names
    if len(names) != len(set(names)) or not set(key).issubset(names):
        raise StoreError("table requires distinct columns and its declared key")
    data = table.to_pydict()
    keys = list(zip(*(data[name] for name in key), strict=True))
    if any(any(value is None for value in item) for item in keys):
        raise StoreError("null table key")
    if len(set(keys)) != len(keys):
        raise StoreError("duplicate table key")
    order = sorted(range(table.num_rows), key=keys.__getitem__)
    metadata = table.schema.metadata or {}
    if set(metadata) != {b"label"} or any(f.metadata for f in table.schema):
        raise StoreError("only the evidence label schema metadata is supported")
    header = {
        "columns": [[f.name, str(f.type), f.nullable] for f in table.schema],
        "key": list(key),
        "label": metadata[b"label"].decode("ascii"),
    }
    digest = hashlib.sha256()
    digest.update((canonical_json(header)[:-1] + ',"rows":[').encode("ascii"))
    columns = [data[name] for name in names]
    for position, index in enumerate(order):
        if position:
            digest.update(b",")
        digest.update(
            canonical_json([_rounded(column[index]) for column in columns]).encode(
                "ascii"
            )
        )
    digest.update(b"]}")
    return digest.hexdigest()
