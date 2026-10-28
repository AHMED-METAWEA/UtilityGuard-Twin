"""The water MeasurementPort: the only telemetry module that reads truth.

Stages: truth -> Gaussian noise -> offset -> drift -> stuck -> half-even
quantization -> dropout -> RTU outage. Flow is converted from m3/s to L/s
before any stage. Drift uses hours elapsed since the configured start hour.
Fault windows are half-open: onset is ceil(h * 3600 / step), end is the same
conversion of start + duration. Only floating round-trip error within two
ULPs of an integer tick is snapped away, so what-if ticks do not start late.

Each sensor uses measure.<sensor_id> and draws, on EVERY tick: one standard
normal, base dropout uniform, fault dropout uniform, and whole-second delivery
delay. Draws continue through stuck, dropout and outage windows. Multiple
dropout faults combine as 1 - product(1 - probability); base dropout always
applies independently. Faults sort by type, sensor id, start, then canonical
payload to break ties. Overlapping stuck faults follow that order, each
holding its pre-dropout candidate from its first active tick.

No events or hidden tags are inspected or copied. Delivery delays are returned
separately, never added to or subclassed into the core TelemetrySeries.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from importlib.resources import files
from types import MappingProxyType
from typing import Any

from ug_core.canonical import canonical_json
from ug_core.ports import MeasurementPort
from ug_core.rng import SeedStreams
from ug_core.telemetry import TelemetrySeries
from ug_core.truth import TruthSeries

from ug_water.network.model import SENSOR_KINDS, Network, Pipe, Pump, Sensor, Valve

_SENSOR_FAULTS = frozenset(
    {
        "sensor_offset",
        "sensor_drift",
        "sensor_stuck",
        "sensor_noise_growth",
        "sensor_dropout",
    }
)
_CHANNELS = {"pressure": "pressure", "flow": "flowrate", "level": "level"}


def rtu_group(sensor: Sensor, network: Network) -> str:
    """RTU routing assumption: level -> tank id; junction -> junction zone.

    A pipe, pump or valve uses its START junction's zone, else its END
    junction's zone, else the link id. START wins for cross-zone links.
    Unknown or unsupported placements fail rather than inventing a group.
    """
    if sensor.kind == "level":
        if sensor.element not in {t.id for t in network.tanks}:
            raise ValueError(f"level sensor {sensor.id} must be on a tank")
        return sensor.element
    zones = {j.id: j.zone for j in network.junctions}
    if sensor.element in zones:
        return zones[sensor.element]
    links: tuple[Pipe | Pump | Valve, ...] = (
        *network.pipes,
        *network.pumps,
        *network.valves,
    )
    for link in links:
        if link.id == sensor.element:
            return zones.get(link.start, zones.get(link.end, link.id))
    raise ValueError(f"sensor {sensor.id} has no supported RTU placement")


def _onset_tick(hours: float, step_seconds: int) -> int:
    position = hours * 3600 / step_seconds
    nearest = round(position)
    if abs(position - nearest) <= 2 * math.ulp(position):
        position = float(nearest)
    return math.ceil(position)


def _number(value: Any, name: str, minimum: float | None = None) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _config(overrides: Mapping[str, Any] | None) -> dict[str, Any]:
    config: dict[str, Any] = json.loads(
        files(__package__).joinpath("data/measurement_v1.json").read_text()
    )
    for name, value in (overrides or {}).items():
        if name not in config:
            raise ValueError(f"unknown measurement parameter {name!r}")
        if name in SENSOR_KINDS:
            if not isinstance(value, Mapping) or set(value) - set(config[name]):
                raise ValueError(f"invalid measurement parameters for {name}")
            config[name] = {**config[name], **value}
        else:
            config[name] = value
    if config["label"] != "ASSUMPTION" or config["version"] != "measurement_v1":
        raise ValueError(
            "measurement parameters must retain their assumption label and version"
        )
    for kind in SENSOR_KINDS:
        for name in ("noise_sigma", "noise_fraction", "quantum"):
            config[kind][name] = _number(config[kind][name], f"{kind}.{name}", 0)
        if config[kind]["quantum"] == 0:
            raise ValueError(f"{kind}.quantum must be positive")
    probability = _number(config["base_dropout_per_tick"], "base_dropout_per_tick", 0)
    if probability > 1:
        raise ValueError("base_dropout_per_tick must be <= 1")
    bounds = config["delivery_delay_s"]
    if not isinstance(bounds, Sequence) or isinstance(bounds, str) or len(bounds) != 2:
        raise ValueError("delivery_delay_s must contain two bounds")
    lower, upper = (_number(b, "delivery_delay_s", 0) for b in bounds)
    if lower > upper or math.ceil(lower) > math.floor(upper):
        raise ValueError("delivery_delay_s must contain at least one whole second")
    config["delivery_delay_s"] = (math.ceil(lower), math.floor(upper))
    return config


class WaterMeasurement(MeasurementPort):
    """Pure measurement evaluations from a network, selected sensors and assumptions.

    Config accepts partial overrides of the bundled JSON, including per-kind
    parameter mappings. Faults are contract sensor/comms dictionaries; physical
    scenario faults are left to the solver and ignored here.
    """

    def __init__(
        self,
        network: Network,
        sensor_set: str,
        faults: Sequence[Mapping[str, Any]] = (),
        config: Mapping[str, Any] | None = None,
    ) -> None:
        if sensor_set not in network.sensor_sets:
            raise ValueError(f"unknown sensor set {sensor_set!r}")
        selected = set(network.sensor_sets[sensor_set])
        self._sensors = tuple(s for s in network.sensors if s.id in selected)
        self._groups = {s.id: rtu_group(s, network) for s in self._sensors}
        self._config = _config(config)
        sensor_ids = {s.id for s in network.sensors}
        measurement_faults = []
        for source in faults:
            kind = source.get("type", "")
            if kind not in _SENSOR_FAULTS and kind != "comms_outage":
                continue
            fault = dict(source)
            fault["start_hour"] = _number(fault["start_hour"], "start_hour", 0)
            if kind in _SENSOR_FAULTS and fault["sensor_id"] not in sensor_ids:
                raise ValueError(f"unknown fault sensor {fault['sensor_id']!r}")
            if kind in {"sensor_stuck", "sensor_dropout", "comms_outage"}:
                duration = _number(fault["duration_hours"], "duration_hours", 0)
                if duration == 0:
                    raise ValueError("duration_hours must be positive")
                _number(fault["start_hour"] + duration, "fault end_hour", 0)
            if (
                kind == "sensor_noise_growth"
                and _number(fault["factor"], "factor") <= 1
            ):
                raise ValueError("noise growth factor must be > 1")
            if kind == "sensor_dropout":
                probability = _number(fault["probability"], "probability")
                if not 0 < probability <= 1:
                    raise ValueError("dropout probability must be in (0, 1]")
            for key in ("magnitude", "drift_per_hour"):
                if key in fault:
                    _number(fault[key], key)
            measurement_faults.append(fault)
        self._faults = sorted(
            measurement_faults,
            key=lambda f: (
                f["type"],
                f.get("sensor_id", ""),
                f["start_hour"],
                canonical_json(f),
            ),
        )

    def measure(self, truth: TruthSeries, seeds: SeedStreams) -> TelemetrySeries:
        return self.measure_with_delivery(truth, seeds)[0]

    def measure_with_delivery(
        self,
        truth: TruthSeries,
        seeds: SeedStreams,
    ) -> tuple[TelemetrySeries, Mapping[str, tuple[float, ...]]]:
        """Return only sensor values and independent per-tick delivery delays (s)."""
        step = truth.timebase.step_seconds
        bounds = self._config["delivery_delay_s"]
        readings: dict[str, tuple[float | None, ...]] = {}
        delays: dict[str, tuple[float, ...]] = {}
        for sensor in self._sensors:
            parameters = self._config[sensor.kind]
            quantum = Decimal(str(parameters["quantum"]))
            channel = f"{_CHANNELS[sensor.kind]}:{sensor.element}"
            if channel not in truth.channels:
                raise ValueError(f"sensor {sensor.id} needs missing channel {channel}")
            faults = [
                f
                for f in self._faults
                if f.get("sensor_id") == sensor.id
                or (
                    f["type"] == "comms_outage"
                    and f["rtu_group"] == self._groups[sensor.id]
                )
            ]
            windows = [
                (
                    f,
                    _onset_tick(f["start_hour"], step),
                    _onset_tick(f["start_hour"] + f["duration_hours"], step)
                    if "duration_hours" in f
                    else truth.timebase.n_ticks,
                )
                for f in faults
            ]
            stream = seeds.stream(f"measure.{sensor.id}")
            held: dict[int, float] = {}
            values: list[float | None] = []
            sensor_delays = []
            for tick, source_value in enumerate(truth.channels[channel]):
                # Fixed draws do not depend on faults, missingness, or other sensors.
                noise = float(stream.standard_normal())
                base_draw, fault_draw = float(stream.random()), float(stream.random())
                sensor_delays.append(float(stream.integers(bounds[0], bounds[1] + 1)))
                active = [
                    (i, f)
                    for i, (f, start, end) in enumerate(windows)
                    if start <= tick < end
                ]
                value = source_value * (1000 if sensor.kind == "flow" else 1)
                sigma = parameters["noise_sigma"] + parameters["noise_fraction"] * abs(
                    value
                )
                for _, fault in active:
                    if fault["type"] == "sensor_noise_growth":
                        sigma *= fault["factor"]
                value += noise * sigma
                for _, fault in active:
                    if fault["type"] == "sensor_offset":
                        value += fault["magnitude"]
                for _, fault in active:
                    if fault["type"] == "sensor_drift":
                        value += fault["drift_per_hour"] * max(
                            0.0, tick * step / 3600 - fault["start_hour"]
                        )
                for index, fault in active:
                    if fault["type"] == "sensor_stuck":
                        value = held.setdefault(index, value)
                quantized = float(
                    (Decimal(str(value)) / quantum).to_integral_value(
                        rounding=ROUND_HALF_EVEN
                    )
                    * quantum
                )
                survival = math.prod(
                    1 - f["probability"]
                    for _, f in active
                    if f["type"] == "sensor_dropout"
                )
                missing = (
                    base_draw < self._config["base_dropout_per_tick"]
                    or fault_draw < 1 - survival
                )
                missing |= any(f["type"] == "comms_outage" for _, f in active)
                values.append(None if missing else quantized)
            readings[sensor.id] = tuple(values)
            delays[sensor.id] = tuple(sensor_delays)
        return TelemetrySeries(truth.timebase, readings), MappingProxyType(delays)
