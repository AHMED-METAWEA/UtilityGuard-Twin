"""Expected-behaviour model: the fault-free twin run.

The detector compares simulated measurements against a full fault-free WNTR
run with the same (known) holiday/heatwave demand settings. This assumes the
demand forecast is known; see docs/assumptions.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import SENSOR_NOISE
from app.network.builder import NetworkProvider, DEFAULT_PROVIDER
from app.scenarios.runner import TruthSeries


@dataclass
class ExpectedModel:
    baseline: TruthSeries
    provider: NetworkProvider = DEFAULT_PROVIDER

    def expected(self, sensor_id: str, tick: int) -> float | None:
        sensor = next(
            (s for s in self.provider.describe().sensors if s.id == sensor_id),
            None,
        )
        if sensor is None:
            return None
        value = self.baseline.sensor_value(sensor.kind, sensor.target, tick)
        if value is None:
            return None
        return value * 1000.0 if sensor.kind == "flow" else value

    def sigma(self, sensor_id: str) -> float:
        return SENSOR_NOISE[sensor_id]

    def residual_sigma(self, sensor_id: str, reading: float, tick: int) -> float | None:
        expected = self.expected(sensor_id, tick)
        if expected is None:
            return None
        return (reading - expected) / self.sigma(sensor_id)
