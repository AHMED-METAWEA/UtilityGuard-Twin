"""Data-quality layer.

Runs before any detector use. For each simulated reading it emits
`ok | suspect | bad`, a 0-1 score, and a list of flags. The score is a
transparent subtraction from 1.0, not a probability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot

from app.config import (
    SETTINGS,
    QUALITY_RANGES,
    SENSOR_NOISE,
    QualityConfig,
)
from app.detect.baseline import ExpectedModel
from app.network.builder import DEFAULT_PROVIDER, TANK_DIAMETER, NetworkProvider
from app.scenarios.runner import TruthSeries


@dataclass
class QualityResult:
    status: list[str] = field(default_factory=list)
    score: list[float] = field(default_factory=list)
    rolling_score: list[float] = field(default_factory=list)
    flags: list[list[str]] = field(default_factory=list)


FLAG_PENALTY = {
    "missing": 1.0,
    "out_of_range": 1.0,
    "stuck": 0.35,
    "stuck_persistent": 0.6,
    "rate_spike": 0.2,
    "drift_vs_neighbors": 0.25,
    "deviation_from_baseline": 0.1,
    "mass_balance": 0.25,
}


def _sensor_kind(sensor_id: str) -> str:
    for sensor in DEFAULT_PROVIDER.describe().sensors:
        if sensor.id == sensor_id:
            return sensor.kind
    return "pressure"


def _rolling(values: list[float], window: int = 12) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        out.append(round(sum(chunk) / len(chunk), 3))
    return out


def _pressure_neighbors() -> dict[str, list[str]]:
    sensors = [s for s in DEFAULT_PROVIDER.describe().sensors if s.kind == "pressure"]
    out: dict[str, list[str]] = {}
    for sensor in sensors:
        out[sensor.id] = [
            other.id for other in sensors
            if other.id != sensor.id
            and hypot(other.x - sensor.x, other.y - sensor.y) <= 250.0
        ]
    return out


def evaluate_quality(
    readings: dict[str, list[float | None]],
    truth: TruthSeries,
    expected_model: ExpectedModel,
    config: QualityConfig | None = None,
    provider: NetworkProvider = DEFAULT_PROVIDER,
) -> dict[str, QualityResult]:
    cfg = config or SETTINGS.quality
    sensors = provider.describe().sensors
    sensor_by_id = {s.id: s for s in sensors}
    neighbors = _pressure_neighbors()
    tick_count = len(truth.time_iso)
    results: dict[str, QualityResult] = {}

    # Residual z-scores are also used by neighbour checks.
    residual_z: dict[str, list[float | None]] = {}
    for sensor in sensors:
        series: list[float | None] = []
        for tick in range(tick_count):
            value = readings[sensor.id][tick]
            if value is None:
                series.append(None)
            else:
                series.append(expected_model.residual_sigma(sensor.id, value, tick))
        residual_z[sensor.id] = series

    for sensor in sensors:
        sid = sensor.id
        kind = sensor.kind
        sigma = SENSOR_NOISE[sid]
        result = QualityResult()
        for tick in range(tick_count):
            value = readings[sid][tick]
            expected = expected_model.expected(sid, tick)
            flags: list[str] = []
            score = 1.0
            if value is None:
                flags.append("missing")
                score = 0.0
                result.status.append("bad")
                result.score.append(0.0)
                result.flags.append(flags)
                continue

            low, high = QUALITY_RANGES[kind]
            if not (low <= value <= high):
                flags.append("out_of_range")

            # Stuck check over a trailing window (no future data).
            window = readings[sid][max(0, tick - cfg.stuck_window + 1): tick + 1]
            if (len(window) == cfg.stuck_window and all(v is not None for v in window)):
                epsilon = {
                    "pressure": cfg.stuck_epsilon_pressure,
                    "flow": cfg.stuck_epsilon_flow,
                    "level": cfg.stuck_epsilon_level,
                }[kind]
                if max(window) - min(window) <= epsilon:  # type: ignore[type-var]
                    flags.append("stuck")
                    if tick >= cfg.stuck_window * 2:
                        flags.append("stuck_persistent")

            # Rate-of-change spike.
            if tick > 0 and readings[sid][tick - 1] is not None:
                limit = {
                    "pressure": cfg.rate_limit_pressure,
                    "flow": cfg.rate_limit_flow,
                    "level": cfg.rate_limit_level,
                }[kind]
                if abs(value - readings[sid][tick - 1]) > limit:  # type: ignore[operator]
                    flags.append("rate_spike")

            z = residual_z[sid][tick]
            if z is not None and abs(z) > cfg.drift_baseline_sigma:
                flags.append("deviation_from_baseline")

            # Drift relative to neighbouring pressure sensors. A network-wide
            # event moves neighbours together and therefore does not flag.
            if kind == "pressure" and z is not None:
                neighbour_values = [
                    residual_z[other][tick] for other in neighbors.get(sid, [])
                    if residual_z[other][tick] is not None
                    and readings[other][tick] is not None
                ]
                if len(neighbour_values) >= 2:
                    neighbour_values.sort()
                    median = neighbour_values[len(neighbour_values) // 2]
                    if (abs(z - median) > cfg.drift_neighbor_sigma
                            and abs(z) >= cfg.drift_min_sigma):
                        flags.append("drift_vs_neighbors")

            # Tank mass balance over a trailing window: comparing a single
            # 5-minute level step against instantaneous flows is dominated by
            # level noise (sigma 1 cm on a 154 m2 tank). A 30-minute window
            # raises the signal roughly sixfold while keeping the check causal.
            window_ticks = cfg.mass_balance_window_ticks
            if sid == "T01" and tick >= window_ticks:
                f_in_series = readings.get("F01", [None])
                f_out_series = readings.get("F02", [None])
                in_values = f_in_series[tick - window_ticks + 1: tick + 1]
                out_values = f_out_series[tick - window_ticks + 1: tick + 1]
                previous = readings[sid][tick - window_ticks]
                if (len(in_values) == window_ticks
                        and all(v is not None for v in in_values + out_values)
                        and previous is not None):
                    area = 3.141592653589793 * (TANK_DIAMETER / 2.0) ** 2
                    net_volume = sum(
                        (float(f_in) - float(f_out)) for f_in, f_out in zip(in_values, out_values)
                    ) / 1000.0 * (truth.timestep_minutes * 60.0)
                    expected_delta = net_volume / area
                    actual_delta = value - previous  # type: ignore[operator]
                    tolerance = max(
                        cfg.mass_balance_floor_m,
                        cfg.mass_balance_rel_tolerance * abs(expected_delta),
                    )
                    if abs(actual_delta - expected_delta) > tolerance:
                        flags.append("mass_balance")

            for flag in flags:
                score -= FLAG_PENALTY.get(flag, 0.1)
            if score <= 0.45:
                status = "bad"
            elif score < 0.8:
                status = "suspect"
            else:
                status = "ok"
            result.status.append(status)
            result.score.append(round(max(0.0, min(1.0, score)), 3))
            result.flags.append(sorted(set(flags)))
        result.rolling_score = _rolling(result.score)
        results[sid] = result
    return results


def quality_dict(results: dict[str, QualityResult]) -> dict[str, dict]:
    return {
        sid: {
            "status": r.status,
            "score": r.score,
            "rolling_score": r.rolling_score,
            "flags": r.flags,
        }
        for sid, r in results.items()
    }
