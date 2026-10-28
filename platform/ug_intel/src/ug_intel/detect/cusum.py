"""D2 two-sided CUSUM over readings, model expectations and quality only."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from types import MappingProxyType
from typing import Any, Literal

VERSION = "d2_v1"
FORMULA_REF = "d2.cusum.v1"
# ASSUMPTION, placeholder tuning; versioned together as d2_v1.
PARAMETERS = MappingProxyType({"k": 0.5, "h": 8.0})
CALIBRATION_TICKS = 288
PERSISTENCE_UPDATES = 3


@dataclass(frozen=True)
class SensorD2Result:
    """Per-tick max of the two statistics, labelled CALCULATED (dimensionless).

    sigma is the CALCULATED calibration scale in the sensor's reading unit.
    Alarm metadata records the first persistent exceedance, never hidden tags.
    """

    statistics: tuple[float, ...]
    sigma: float
    alarm_tick: int | None
    direction: Literal["low", "high"] | None
    label: str = "CALCULATED"
    formula_ref: str = FORMULA_REF


@dataclass(frozen=True)
class D2Result:
    sensors: Mapping[str, SensorD2Result]
    version: str = VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "sensors", MappingProxyType(dict(self.sensors)))


def detect(
    readings: Mapping[str, Sequence[float | None]],
    expected: Mapping[str, Sequence[float]],
    quality_flags: Mapping[str, Sequence[Mapping[str, Any]]],
    quanta: Mapping[str, float],
) -> D2Result:
    """Detect independently per sensor; calibration is ticks 0..287 inclusive.

    Calibration uses all non-missing residuals in that window, as specified.
    After calibration, missing/bad ticks hold both statistics and persistence;
    only updated ticks count towards three consecutive strict exceedances.
    Suspect readings remain usable. No residual centering is applied to z.
    """
    results = {}
    for sensor in sorted(readings):
        values, model, quality = (
            readings[sensor],
            expected[sensor],
            quality_flags[sensor],
        )
        quantum = quanta[sensor]
        if isinstance(quantum, bool) or not math.isfinite(quantum) or quantum <= 0:
            raise ValueError(f"sensor {sensor} needs a positive finite quantum")
        if len(model) != len(values) or len(quality) != len(values):
            raise ValueError(f"sensor {sensor} inputs must have equal lengths")
        if any(isinstance(v, bool) or not math.isfinite(v) for v in model) or any(
            v is not None and (isinstance(v, bool) or not math.isfinite(v))
            for v in values
        ):
            raise ValueError(f"sensor {sensor} inputs must be finite or missing")
        if any(q.get("status") not in {"ok", "suspect", "bad"} for q in quality):
            raise ValueError(f"sensor {sensor} needs a quality status per tick")
        residuals = [None if v is None else v - model[t] for t, v in enumerate(values)]
        if any(r is not None and not math.isfinite(r) for r in residuals):
            raise ValueError(f"sensor {sensor} residuals must be finite")
        calibration = [r for r in residuals[:CALIBRATION_TICKS] if r is not None]
        sigma = 2 * quantum
        if calibration:
            center = median(calibration)
            sigma = max(sigma, 1.4826 * median(abs(r - center) for r in calibration))
        if not math.isfinite(sigma):
            raise ValueError(f"sensor {sensor} scale must be finite")
        positive = negative = 0.0
        consecutive = 0
        alarm_tick = None
        direction: Literal["low", "high"] | None = None
        statistics = []
        for tick, residual in enumerate(residuals):
            if (
                tick >= CALIBRATION_TICKS
                and residual is not None
                and quality[tick]["status"] != "bad"
            ):
                z = residual / sigma
                positive = max(0.0, positive + z - PARAMETERS["k"])
                negative = max(0.0, negative - z - PARAMETERS["k"])
                if not math.isfinite(max(positive, negative)):
                    raise ValueError(f"sensor {sensor} statistic must be finite")
                consecutive = (
                    consecutive + 1 if max(positive, negative) > PARAMETERS["h"] else 0
                )
                if alarm_tick is None and consecutive == PERSISTENCE_UPDATES:
                    alarm_tick = tick
                    direction = "low" if negative > PARAMETERS["h"] else "high"
            statistics.append(max(positive, negative))
        results[sensor] = SensorD2Result(
            tuple(statistics), sigma, alarm_tick, direction
        )
    return D2Result(results)
