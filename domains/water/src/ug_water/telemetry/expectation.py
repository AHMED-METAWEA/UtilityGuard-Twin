"""Forecast-driven water sensor expectations."""

from ug_core.evidence import EvidenceLabel

from ug_water.demand.model import DemandSeries
from ug_water.network.model import Network
from ug_water.solver import simulate

VERSION = "expectation_v1"
LABEL = EvidenceLabel.MODEL


def expected_readings(
    network: Network, sensor_set: str, forecast: DemandSeries
) -> dict[str, tuple[float, ...]]:
    """MODEL, expectation_v1: noise-free, fault-free channels driven only by forecast.

    Pressure and tank level are m; flow is L/s, as in WaterMeasurement before
    noise and quantization. No actual-run truth is accepted by this boundary.
    """
    if forecast.label != EvidenceLabel.MODEL:
        raise ValueError("expectation requires MODEL-labelled forecast demand")
    if sensor_set not in network.sensor_sets:
        raise ValueError(f"unknown sensor set {sensor_set!r}")
    quantities = {"pressure": "pressure", "flow": "flowrate", "level": "level"}
    selected = set(network.sensor_sets[sensor_set])
    needed = {
        f"{quantities[s.kind]}:{s.element}" for s in network.sensors if s.id in selected
    }
    channels = simulate(network, forecast, channels=needed).truth.channels
    result = {}
    for sensor in network.sensors:
        if sensor.id not in selected:
            continue
        channel = f"{quantities[sensor.kind]}:{sensor.element}"
        if channel not in channels:
            raise ValueError(f"sensor {sensor.id} needs missing channel {channel}")
        result[sensor.id] = tuple(
            v * (1000 if sensor.kind == "flow" else 1) for v in channels[channel]
        )
    return result
