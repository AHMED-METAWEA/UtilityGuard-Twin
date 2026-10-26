"""Privileged simulation bundle I/O, exclusively for the evaluation harness.

Each channel is quantity:element_id, split at the FIRST colon; both parts must
be non-empty. For every tick and channel, fault_tag_hidden is the sorted,
'+'-joined kinds of events targeting exactly that element whose half-open
[start_tick, end_tick) window contains the tick. None ends at the timebase end.
Repeated active kinds are retained; no active events yields null. The schema
carries SIMULATION as its evidence label. These rows never enter RunReader.
"""

from __future__ import annotations

from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]

from ug_core.numeric import finite
from ug_core.store.layout import StoreError, run_path
from ug_core.store.run import RunDraft, RunStore
from ug_core.store.tables import read_parquet
from ug_core.truth import TruthSeries


def write_truth(run: RunDraft, series: TruthSeries) -> None:
    """Attach the simulation table to a draft; publication is RunStore.write()."""
    data: dict[str, list[Any]] = {
        "tick": [],
        "element_id": [],
        "quantity": [],
        "value": [],
        "fault_tag_hidden": [],
    }
    for channel, values in series.channels.items():
        quantity, separator, element = channel.partition(":")
        if not separator or not quantity or not element:
            raise StoreError(f"channel must be quantity:element_id: {channel!r}")
        events = [event for event in series.events if event.target == element]
        for tick, value in enumerate(values):
            active = sorted(
                event.kind
                for event in events
                if event.start_tick <= tick
                and (event.end_tick is None or tick < event.end_tick)
            )
            data["tick"].append(tick)
            data["element_id"].append(element)
            data["quantity"].append(quantity)
            data["value"].append(finite(value, channel))
            data["fault_tag_hidden"].append("+".join(active) if active else None)
    schema = pa.schema(
        [
            ("tick", "int64", False),
            ("element_id", "string", False),
            ("quantity", "string", False),
            ("value", "float64", False),
            ("fault_tag_hidden", "string", True),
        ],
        metadata={b"label": b"SIMULATION"},
    )
    run._add("truth", pa.table(data, schema=schema))


def read_truth(store: RunStore, identifier: str) -> pa.Table:
    """Evaluation-only access, guarded by complete run verification."""
    store.verify(identifier)
    return read_parquet(run_path(store.root, identifier) / "truth.parquet")
