"""Parquet persistence and restricted DuckDB queries for consumer tables.

Keys are declared centrally in layout.py, never inferred from input row order.
The blocked stems mirror honesty_support.forbidden_property without importing
that test helper (or its privileged types) into production code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from ug_core.evidence import EvidenceLabel
from ug_core.store.layout import StoreError, table_key

BLOCKED_STEMS = ("truth", "fault_tag", "faulttag", "hidden", "injected", "ground_truth")
BLOCKED_FIELDS = {
    "channels",
    "events",
    "kind",
    "target",
    "start_tick",
    "end_tick",
    "parameters",
}
DEFAULT_LABELS = {
    "truth": "SIMULATION",
    "telemetry": "SENSOR_SIM",
    "expectation": "MODEL",
    "quality": "CALCULATED",
}


def forbidden_column(name: str) -> bool:
    return name.casefold() in BLOCKED_FIELDS or any(
        stem in name.casefold() for stem in BLOCKED_STEMS
    )


def prepare(name: str, table: pa.Table, *, internal: bool = False) -> pa.Table:
    """Attach the evidence label, rejecting ambiguous or privileged schemas."""
    key = table_key(name, internal=internal)
    names = table.column_names
    if len(names) != len(set(names)) or not set(key).issubset(names):
        raise StoreError("table requires distinct columns and its declared key")
    fields = {f.name: str(f.type) for f in table.schema}
    if fields["tick"] != "int64" or any(fields[k] != "string" for k in key[1:]):
        raise StoreError("key types must be tick int64 and identifiers string")
    metadata = table.schema.metadata or {}
    label = metadata.get(b"label", DEFAULT_LABELS.get(name, "MODEL").encode())
    if set(metadata) - {b"label"} or any(f.metadata for f in table.schema):
        raise StoreError("only the evidence label schema metadata is supported")
    try:
        EvidenceLabel(label.decode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise StoreError("invalid evidence label") from exc
    if name in {"truth", "expectation"} and label.decode() != DEFAULT_LABELS[name]:
        raise StoreError(f"{name} requires label {DEFAULT_LABELS[name]}")
    if name != "truth":
        for column in names:
            if forbidden_column(column):
                raise StoreError(f"restricted column: {column!r}")
        # Inspect nested Arrow schemas too, including all-null/empty structs.
        for field in table.schema:
            _check_field(field)
    else:
        expected = [
            ("tick", "int64"),
            ("element_id", "string"),
            ("quantity", "string"),
            ("value", "double"),
            ("fault_tag_hidden", "string"),
        ]
        if list(fields.items()) != expected:
            raise StoreError("invalid bundle schema")
        for column in names[:-1]:
            if table[column].null_count:
                raise StoreError(f"null bundle value: {column}")
    if table["tick"].null_count or pc.any(pc.less(table["tick"], 0)).as_py():
        raise StoreError("tick must be a non-negative integer")
    return table.replace_schema_metadata({b"label": label})


def _check_field(field: Any) -> None:
    if field.metadata:
        raise StoreError("only the evidence label schema metadata is supported")
    if forbidden_column(field.name):
        raise StoreError(f"restricted column: {field.name!r}")
    # Arrow DataType.num_fields/field are introspected in the API evidence probe.
    for index in range(field.type.num_fields):
        _check_field(field.type.field(index))


def write_parquet(table: pa.Table, path: Path) -> None:
    # Preserve nested child names: they are part of the canonical column types.
    pq.write_table(table, path, use_compliant_nested_type=False)


def read_parquet(path: Path) -> pa.Table:
    return pq.read_table(path)


def query_rows(
    path: Path, name: str, ticks: tuple[int, int] | None
) -> list[dict[str, Any]]:
    """Use bound parameters, a half-open window, and a fixed declared key order."""
    key = table_key(name)
    parameters: list[Any] = [str(path)]
    where = ""
    if ticks is not None:
        if (
            len(ticks) != 2
            or any(type(tick) is not int or tick < 0 for tick in ticks)
            or ticks[1] < ticks[0]
        ):
            raise StoreError("ticks must be a non-negative [start, end) window")
        where = " WHERE tick >= ? AND tick < ?"
        parameters.extend(ticks)
    with duckdb.connect(":memory:") as connection:
        result = connection.execute(
            "SELECT * FROM read_parquet(?)" + where + " ORDER BY " + ", ".join(key),
            parameters,
        )
        names = [column[0] for column in result.description]
        return [dict(zip(names, row, strict=True)) for row in result.fetchall()]
