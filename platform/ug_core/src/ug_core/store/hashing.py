"""Store hash v1: SHA-256 of the following bytes, without separators or a BOM.

First is ASCII canonical_json of {"columns": [[name, str(Arrow type), nullable],
...], "key": [key names], "label": evidence label, "hash": "store-v1", "rows": row
count}. With the schema and the row count fixed, the byte stream below parses in only
one way, so no string value can imitate a column boundary (lead review).
Columns retain schema order. Rows are sorted ascending by the declared unique,
non-null key using Arrow sort_indices and take (string ordering is UTF-8).

Next, for each column in schema order, append its name encoded as a string,
then all its values in sorted row order. int64 is signed little-endian 8 bytes;
float64 is numpy.rint(value * 1e6) cast to signed little-endian int64 (negative
zero becomes zero). Non-finite floats and magnitudes above 9e12 are refused.
A string is its UTF-8 byte length as unsigned little-endian 4 bytes followed by
those bytes; null is exactly FF FF FF FF, distinct from an empty string. Lengths
must be below 0xFFFFFFFF. A boolean is one byte, 00 or 01. Nothing else is
appended. Only int64, float64, string and boolean columns are supported;
nulls in fixed-width columns and all other Arrow types are refused. Schema
nullability is still hashed, even when a column has no nulls. Metadata is only
the evidence label. Changing this encoding requires a new hash version.

All sorting, key checks and value encoding are columnar. String encoding uses
bounded vectorised byte blocks, never Python iteration over rows or values.
Parquet/compression bytes and chunk boundaries do not participate in the hash.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

from ug_core.canonical import canonical_json
from ug_core.store.layout import StoreError


def _string_bytes(column: pa.Array) -> bytes:
    """Interleave little-endian length prefixes with the Arrow UTF-8 buffer."""
    missing = column.is_null().to_numpy(zero_copy_only=False)
    values = pc.fill_null(column, "") if column.null_count else column
    _, offsets_buffer, data_buffer = values.buffers()
    offsets = np.frombuffer(
        offsets_buffer, dtype="<i4", count=len(values) + 1, offset=values.offset * 4
    ).astype(np.int64)
    lengths = np.diff(offsets)
    prefixes = lengths.astype("<u4")
    prefixes[missing] = 0xFFFFFFFF
    starts = offsets[:-1] - offsets[0] + 4 * np.arange(len(values))
    encoded = np.empty(int(offsets[-1] - offsets[0]) + 4 * len(values), dtype=np.uint8)
    encoded[starts[:, None] + np.arange(4)] = prefixes.view(np.uint8).reshape(-1, 4)
    positions = np.arange(int(offsets[-1] - offsets[0])) + 4 * np.repeat(
        np.arange(1, len(values) + 1), lengths
    )
    encoded[positions] = np.frombuffer(data_buffer, dtype=np.uint8)[
        offsets[0] : offsets[-1]
    ]
    return encoded.tobytes()


def table_hash(table: pa.Table, key: tuple[str, ...]) -> str:
    """Validate supported content and unique keys, then hash in key order."""
    names = table.column_names
    if not key or len(names) != len(set(names)) or not set(key).issubset(names):
        raise StoreError("table requires distinct columns and its declared key")
    metadata = table.schema.metadata or {}
    if set(metadata) != {b"label"} or any(f.metadata for f in table.schema):
        raise StoreError("only the evidence label schema metadata is supported")
    for name in key:
        if table[name].null_count:
            raise StoreError("null table key")
    for f in table.schema:
        if str(f.type) not in {"int64", "double", "string", "bool"}:
            raise StoreError(f"unsupported store-v1 type: {f.type}")
    ordered = table.take(
        pc.sort_indices(table, sort_keys=[(name, "ascending") for name in key])
    )
    if ordered.num_rows > 1:
        equal = None
        for name in key:
            column = ordered[name]
            adjacent = pc.equal(column.slice(1), column.slice(0, ordered.num_rows - 1))
            equal = adjacent if equal is None else pc.and_(equal, adjacent)
        if pc.any(equal).as_py():
            raise StoreError("duplicate table key")
    header = {
        "columns": [[f.name, str(f.type), f.nullable] for f in table.schema],
        "key": list(key),
        "label": metadata[b"label"].decode("ascii"),
        "hash": "store-v1",
        "rows": ordered.num_rows,
    }
    digest = hashlib.sha256(canonical_json(header).encode("ascii"))
    for f, column in zip(ordered.schema, ordered.columns, strict=True):
        name = f.name.encode("utf-8")
        digest.update(len(name).to_bytes(4, "little") + name)
        kind = str(f.type)
        if kind == "string":
            # A block loop bounds temporary byte-index arrays, independent of row count.
            for chunk in column.chunks:
                for start in range(0, len(chunk), 65536):
                    digest.update(_string_bytes(chunk.slice(start, 65536)))
        else:
            if column.null_count:
                raise StoreError("store-v1 fixed-width columns cannot contain nulls")
            values = column.to_numpy(zero_copy_only=False)
            if kind == "double":
                if not np.isfinite(values).all():
                    raise StoreError("store-v1 floats must be finite")
                if (np.abs(values) > 9e12).any():
                    raise StoreError("store-v1 float magnitude exceeds 9e12")
                encoded = np.rint(values * 1e6).astype("<i8")
            else:
                encoded = values.astype(
                    np.uint8 if kind == "bool" else "<i8", copy=False
                )
            digest.update(encoded.tobytes())
    return digest.hexdigest()
