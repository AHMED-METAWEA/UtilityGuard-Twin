"""Robust telemetry trends and advisory tank warnings; no truth inputs."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

from ug_core.grammar import require_identifier

TREND_FORMULA = "trend.residual_slope.v1"
TANK_FORMULA = "tank.time_to_threshold.v1"


def _finite(value: float, name: str, *, positive: bool = False) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"{name} must be finite{' and positive' if positive else ''}")


def _window(
    values: Sequence[float | None], window_ticks: int
) -> Sequence[float | None]:
    if (
        isinstance(window_ticks, bool)
        or not isinstance(window_ticks, int)
        or window_ticks <= 0
    ):
        raise ValueError("window_ticks must be a positive integer")
    return values[-window_ticks:]


def theil_sen_slope(
    values: Sequence[float | None], step_seconds: float
) -> float | None:
    """Median pairwise slope per hour; keep original tick gaps at missing points."""
    _finite(step_seconds, "step_seconds", positive=True)
    points = []
    for tick, value in enumerate(values):
        if value is not None:
            _finite(value, "value")
            points.append((tick, value))
    if len(points) < 4:
        return None
    slope = median(
        (v2 - v1) * 3600 / ((t2 - t1) * step_seconds)
        for i, (t1, v1) in enumerate(points)
        for t2, v2 in points[i + 1 :]
    )
    _finite(slope, "slope")
    return slope


@dataclass(frozen=True)
class TrendResult:
    """Slope in sigma/h; flagged is a rule outcome, never a probability."""

    slope: float | None
    flagged: bool
    label: str
    formula_ref: str = TREND_FORMULA


def trend_anomaly(
    residuals: Sequence[float | None],
    sigma: float,
    step_seconds: float,
    window_ticks: int = 24,
    limit_sigma_per_hour: float = 1.0,
) -> TrendResult:
    """CALCULATED, trend.residual_slope.v1: last-window slope in sigma per hour."""
    _finite(sigma, "sigma", positive=True)
    _finite(limit_sigma_per_hour, "limit_sigma_per_hour")
    if limit_sigma_per_hour < 0:
        raise ValueError("limit_sigma_per_hour must be non-negative")
    slope = theil_sen_slope(_window(residuals, window_ticks), step_seconds)
    if slope is None:
        return TrendResult(None, False, "INSUFFICIENT_EVIDENCE")
    slope /= sigma
    _finite(slope, "normalized slope")
    return TrendResult(slope, abs(slope) > limit_sigma_per_hour, "CALCULATED")


def _tank_inputs(
    levels: Sequence[float | None],
    step_seconds: float,
    threshold_m: float,
    window_ticks: int,
) -> tuple[float | None, float | None]:
    _finite(threshold_m, "threshold_m")
    window = _window(levels, window_ticks)
    slope = theil_sen_slope(window, step_seconds)
    return (window[-1] if window else None), slope


def _time(
    level_now: float | None, slope: float | None, threshold_m: float
) -> float | None:
    if level_now is None or slope is None or slope >= 0:
        return None
    hours = max(0.0, (level_now - threshold_m) / -slope)
    _finite(hours, "time to threshold")
    return hours


def time_to_threshold(
    levels: Sequence[float | None],
    step_seconds: float,
    threshold_m: float,
    window_ticks: int = 12,
) -> float | None:
    """CALCULATED, tank.time_to_threshold.v1, in h; threshold_m is ASSUMPTION.

    Require a current reading, at least four non-null points and a negative
    last-window slope. Missing current levels never become stale forecasts.
    """
    level_now, slope = _tank_inputs(levels, step_seconds, threshold_m, window_ticks)
    return _time(level_now, slope, threshold_m)


def evidence_for_time_to_threshold(
    levels: Sequence[float | None],
    step_seconds: float,
    threshold_m: float,
    window_ticks: int = 12,
    *,
    run_id: str,
    evidence_id: str = "tank_time_to_threshold",
) -> dict[str, Any]:
    """v1 evidence record for SENSOR_SIM levels and an ASSUMPTION threshold.

    Unavailable inputs are omitted, never assigned invented numeric values.
    """
    require_identifier(run_id, "run id")
    require_identifier(evidence_id, "evidence id")
    level_now, slope = _tank_inputs(levels, step_seconds, threshold_m, window_ticks)
    hours = _time(level_now, slope, threshold_m)
    inputs = [
        {
            "name": name,
            "value": value,
            "unit": unit,
            "label": label,
            "ref": f"{evidence_id}.{name}",
        }
        for name, value, unit, label in (
            ("level_now", level_now, "m", "SENSOR_SIM"),
            ("slope", slope, "m/h", "CALCULATED"),
            ("threshold", threshold_m, "m", "ASSUMPTION"),
        )
        if value is not None
    ]
    payload: dict[str, Any] = {
        "schema_version": "1",
        "evidence_id": evidence_id,
        "value": hours,
        "unit": "h",
        "label": "CALCULATED" if hours is not None else "INSUFFICIENT_EVIDENCE",
        "formula": TANK_FORMULA,
        "inputs": inputs,
        "provenance": {"run_id": run_id},
    }
    if hours is None:
        payload["reason"] = (
            "A current level, at least four non-null window points and a negative slope are required."
        )
    return payload
