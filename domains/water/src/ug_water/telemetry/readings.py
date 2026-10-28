"""Serialize telemetry into v1 reading payloads, with no access to twin truth."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from ug_core.telemetry import TelemetrySeries

from ug_water.network.model import Network


def to_readings(
    series: TelemetrySeries,
    network: Network,
    delays: Mapping[str, Sequence[float]] | None = None,
    quality: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Tick/sensor-ordered SENSOR_SIM payloads; delivery is present only with delays.

    Delivery timestamps use the contract's whole-second UTC representation.
    Reject fractional delays rather than silently truncating timestamps.
    """
    if series.label != "SENSOR_SIM":
        raise ValueError("water simulated readings require SENSOR_SIM telemetry")
    sensors = {s.id: s for s in network.sensors}
    for sensor in series.readings:
        if sensor not in sensors:
            raise ValueError(f"unknown sensor {sensor!r}")
        for name, metadata in (("delays", delays), ("quality", quality)):
            if metadata is not None and (
                sensor not in metadata
                or len(metadata[sensor]) != series.timebase.n_ticks
            ):
                raise ValueError(f"{name} must provide every tick for sensor {sensor}")
        if delays is not None and any(
            isinstance(d, bool)
            or not math.isfinite(d)
            or d < 0
            or not float(d).is_integer()
            for d in delays[sensor]
        ):
            raise ValueError(
                "delivery delays must be finite non-negative whole seconds"
            )
    payloads = []
    for tick in series.timebase.ticks():
        for sensor in sorted(series.readings):
            payload: dict[str, Any] = {
                "schema_version": "1",
                "tick": tick,
                "sensor_id": sensor,
                "value": series.readings[sensor][tick],
                "unit": "L/s" if sensors[sensor].kind == "flow" else "m",
                "label": "SENSOR_SIM",
            }
            if delays is not None:
                delivered = series.timebase.time_at(tick) + timedelta(
                    seconds=delays[sensor][tick]
                )
                payload["delivered_at"] = delivered.strftime("%Y-%m-%dT%H:%M:%SZ")
            if quality is not None:
                payload["quality"] = dict(quality[sensor][tick])
            payloads.append(payload)
    return payloads
