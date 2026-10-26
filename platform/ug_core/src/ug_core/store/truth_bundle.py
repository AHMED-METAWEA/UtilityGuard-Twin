"""Privileged simulation bundle I/O, exclusively for the evaluation harness.

Each channel is quantity:element_id, split at the FIRST colon; both parts must
be non-empty. For every tick and channel, fault_tag_hidden is the sorted,
'+'-joined kinds of events targeting exactly that element whose half-open
[start_tick, end_tick) window contains the tick. None ends at the timebase end.
Repeated active kinds are retained; no active events yields null. The schema
carries SIMULATION as its evidence label. These rows never enter RunReader.
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]

from ug_core.store.layout import StoreError, run_path
from ug_core.store.run import RunDraft, RunStore
from ug_core.store.tables import read_parquet
from ug_core.truth import TruthSeries


def write_truth(run: RunDraft, series: TruthSeries) -> None:
    """Attach the simulation table to a draft; publication is RunStore.write()."""
    ticks = np.arange(series.timebase.n_ticks, dtype=np.int64)
    parts = []
    values_by_channel = []
    tags_by_channel = []
    for channel, values in series.channels.items():
        quantity, separator, element = channel.partition(":")
        if not separator or not quantity or not element:
            raise StoreError(f"channel must be quantity:element_id: {channel!r}")
        parts.append((element, quantity))
        values_by_channel.append(values)
        tags = np.full(len(ticks), "", dtype=object)
        for event in sorted(series.events, key=lambda event: event.kind):
            if event.target != element:
                continue
            mask = (ticks >= event.start_tick) & (
                ticks < (event.end_tick if event.end_tick is not None else len(ticks))
            )
            tags[mask] = np.where(
                tags[mask] == "", event.kind, tags[mask] + "+" + event.kind
            )
        tags[tags == ""] = None
        tags_by_channel.append(tags)
    data = {
        "tick": np.tile(ticks, len(parts)),
        "element_id": np.repeat(
            np.asarray([part[0] for part in parts], dtype=object), len(ticks)
        ),
        "quantity": np.repeat(
            np.asarray([part[1] for part in parts], dtype=object), len(ticks)
        ),
        "value": np.asarray(values_by_channel, dtype=np.float64).reshape(-1),
        "fault_tag_hidden": np.asarray(tags_by_channel, dtype=object).reshape(-1),
    }
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
