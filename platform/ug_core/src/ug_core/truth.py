"""Twin truth: what the simulated world is actually doing.

Honesty Rule: truth is separate from telemetry. Detectors, the stream and the operator view never
receive it. Rules this module helps enforce:
- It lives in its own module, `ug_core.truth`, and is NOT re-exported from `ug_core`, so any
  import of it is explicit, greppable and checkable by an import-graph test.
- `TruthSeries` and `TelemetrySeries` share no base class and no fields.
- The hidden fault tags (`TruthEvent`) exist only here.

Only the solver, the measurement model and the evaluation harness may import this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from ug_core.canonical import canonical_json, freeze, sha256_hex, thaw
from ug_core.numeric import finite, round_for_hash
from ug_core.timebase import Timebase


@dataclass(frozen=True)
class TruthEvent:
    """An injected fault or physical event that really happened (hidden from detectors).

    `end_tick` is exclusive; `None` means until the end of the series.
    """

    kind: str
    target: str
    start_tick: int
    end_tick: int | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind or not self.target:
            raise ValueError("kind and target must be non-empty")
        if self.start_tick < 0:
            raise ValueError("start_tick must be >= 0")
        if self.end_tick is not None and self.end_tick <= self.start_tick:
            raise ValueError("end_tick must be greater than start_tick")
        object.__setattr__(self, "parameters", freeze(self.parameters))
        canonical_json(
            thaw(self.parameters)
        )  # fail early on non-finite or non-JSON content

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "parameters": thaw(self.parameters),
        }


@dataclass(frozen=True)
class TruthSeries:
    """Physical quantities per channel over a shared time axis, plus the hidden events."""

    timebase: Timebase
    channels: Mapping[str, Sequence[float]]  # stored as a read-only mapping of tuples
    events: tuple[TruthEvent, ...] = ()

    def __post_init__(self) -> None:
        frozen: dict[str, tuple[float, ...]] = {}
        for name, values in self.channels.items():
            series = tuple(finite(v, f"channel {name!r}") for v in values)
            if len(series) != self.timebase.n_ticks:
                raise ValueError(
                    f"channel {name!r} has {len(series)} values, "
                    f"timebase has {self.timebase.n_ticks}"
                )
            frozen[name] = series
        object.__setattr__(self, "channels", MappingProxyType(frozen))
        for event in self.events:
            last = (
                event.end_tick if event.end_tick is not None else self.timebase.n_ticks
            )
            if (
                event.start_tick >= self.timebase.n_ticks
                or last > self.timebase.n_ticks
            ):
                raise ValueError(f"event outside the time axis: {event.to_dict()}")
        ordered = sorted(self.events, key=lambda e: canonical_json(e.to_dict()))
        object.__setattr__(self, "events", tuple(ordered))

    def content_hash(self) -> str:
        """SHA-256 of the content, with values rounded to the hash precision."""
        payload = {
            "timebase": self.timebase.to_dict(),
            "channels": {
                n: [round_for_hash(v) for v in vs] for n, vs in self.channels.items()
            },
            "events": [e.to_dict() for e in self.events],
        }
        return sha256_hex(canonical_json(payload))
