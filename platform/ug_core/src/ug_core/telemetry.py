"""Telemetry: what sensors report. The only series detectors and the operator view may see.

This module must never import `ug_core.truth` (an import-graph test enforces it). A missing
reading is `None`, never 0.0 (pitfall P-17), and non-finite numbers are rejected.

How a `TelemetrySeries` is produced:
- simulated: by a domain measurement model (the `MeasurementPort` in `ug_core.ports`), from truth
  plus an error model, label `SENSOR_SIM`;
- real or benchmark data imported through a dataset adapter, labels `OBSERVED` or `BENCHMARK`.
Nothing here carries any link back to truth, hidden fault tags included.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from ug_core import grammar
from ug_core.canonical import canonical_json, sha256_hex
from ug_core.evidence import EvidenceLabel
from ug_core.numeric import finite, round_for_hash
from ug_core.timebase import Timebase

TELEMETRY_LABELS = frozenset(
    {EvidenceLabel.SENSOR_SIM, EvidenceLabel.OBSERVED, EvidenceLabel.BENCHMARK}
)


class StreamSource(StrEnum):
    """Where a stream comes from. Always visible in the UI (Honesty Rule 2)."""

    REPLAY = "REPLAY"
    SIMULATED = "SIMULATED"
    LIVE = "LIVE"


@dataclass(frozen=True)
class TelemetrySeries:
    timebase: Timebase
    readings: Mapping[
        str, Sequence[float | None]
    ]  # stored as a read-only mapping of tuples
    label: EvidenceLabel = EvidenceLabel.SENSOR_SIM

    def __post_init__(self) -> None:
        if not isinstance(self.label, EvidenceLabel):
            object.__setattr__(self, "label", EvidenceLabel(self.label))
        if self.label not in TELEMETRY_LABELS:
            allowed = sorted(label.value for label in TELEMETRY_LABELS)
            raise ValueError(
                f"telemetry label must be one of {allowed}, got {self.label}"
            )
        frozen: dict[str, tuple[float | None, ...]] = {}
        for sensor_id, values in self.readings.items():
            grammar.require_identifier(sensor_id, "a sensor id")
            series = tuple(
                None if v is None else finite(v, f"reading {sensor_id!r}")
                for v in values
            )
            if len(series) != self.timebase.n_ticks:
                raise ValueError(
                    f"sensor {sensor_id!r} has {len(series)} readings, "
                    f"timebase has {self.timebase.n_ticks}"
                )
            frozen[sensor_id] = series
        object.__setattr__(self, "readings", MappingProxyType(frozen))

    def missing_count(self, sensor_id: str) -> int:
        return sum(1 for v in self.readings[sensor_id] if v is None)

    def content_hash(self) -> str:
        payload = {
            "timebase": self.timebase.to_dict(),
            "label": str(self.label),
            "readings": {
                s: [None if v is None else round_for_hash(v) for v in vs]
                for s, vs in self.readings.items()
            },
        }
        return sha256_hex(canonical_json(payload))
