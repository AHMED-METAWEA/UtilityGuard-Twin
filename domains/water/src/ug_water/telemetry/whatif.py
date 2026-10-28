"""Telemetry-only what-if instructions; never modify network or hydraulic truth."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ug_core.grammar import require_identifier


@dataclass(frozen=True)
class SensorWhatIf:
    sensor_id: str
    mode: Literal["disable", "stuck", "drift"]
    from_tick: int
    drift_per_hour: float | None = None

    def __post_init__(self) -> None:
        require_identifier(self.sensor_id, "sensor id")
        if self.mode not in {"disable", "stuck", "drift"}:
            raise ValueError("unknown sensor what-if mode")
        if (
            isinstance(self.from_tick, bool)
            or not isinstance(self.from_tick, int)
            or self.from_tick < 0
        ):
            raise ValueError("from_tick must be a non-negative integer")
        if self.mode == "drift":
            if (
                isinstance(self.drift_per_hour, bool)
                or self.drift_per_hour is None
                or not math.isfinite(self.drift_per_hour)
            ):
                raise ValueError("drift mode requires finite drift_per_hour")
        elif self.drift_per_hour is not None:
            raise ValueError("drift_per_hour is only valid for drift mode")


def as_faults(
    whatifs: Sequence[SensorWhatIf], step_seconds: int, horizon_ticks: int
) -> list[dict[str, Any]]:
    """Contract faults: start = from_tick * step / 3600, duration to horizon.

    Duration = (horizon_ticks - from_tick) * step_seconds / 3600.
    The measurement onset rule round-trips this start to exactly from_tick.
    """
    for name, value in (
        ("step_seconds", step_seconds),
        ("horizon_ticks", horizon_ticks),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    faults = []
    for whatif in whatifs:
        if whatif.from_tick >= horizon_ticks:
            raise ValueError("from_tick must be less than horizon_ticks")
        kind = {
            "disable": "sensor_dropout",
            "stuck": "sensor_stuck",
            "drift": "sensor_drift",
        }[whatif.mode]
        fault: dict[str, Any] = {
            "type": kind,
            "sensor_id": whatif.sensor_id,
            "start_hour": whatif.from_tick * step_seconds / 3600,
        }
        if whatif.mode == "drift":
            fault["drift_per_hour"] = whatif.drift_per_hour
        else:
            fault["duration_hours"] = (
                (horizon_ticks - whatif.from_tick) * step_seconds / 3600
            )
            if whatif.mode == "disable":
                fault["probability"] = 1.0
        faults.append(fault)
    return faults
