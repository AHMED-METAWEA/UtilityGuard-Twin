"""Ports: the interfaces between the core and domain code.

`MeasurementPort` is the only way telemetry is derived from truth. It is implemented by a domain
measurement model (water: noise, drift, stuck, dropout per sensor, each with its own named stream).
This module imports `ug_core.truth` on purpose, so only code that is allowed to see truth should
import it: measurement models and the evaluation harness. Detectors, quality checks, the stream and
the operator view must not.
"""

from __future__ import annotations

from typing import Protocol

from ug_core.rng import SeedStreams
from ug_core.telemetry import TelemetrySeries
from ug_core.truth import TruthSeries


class MeasurementPort(Protocol):
    def measure(self, truth: TruthSeries, seeds: SeedStreams) -> TelemetrySeries:
        """Turn truth into what sensors would report; gaps are `None`, never zeros."""
        ...
