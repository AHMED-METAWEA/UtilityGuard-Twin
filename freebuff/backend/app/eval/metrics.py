"""Evaluation metrics for the detector, quality layer and localisation.

The evaluation runs every preset through the same code path as the API and
compares model output with the *declared* scenario faults. It measures this
prototype on its own synthetic network only; it is not field validation.
"""
from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from app.config import NETWORK_VERSION
from app.network.builder import DEFAULT_PROVIDER, NetworkProvider
from app.scenarios.runner import TruthSeries
from app.scenarios.schema import (
    DemandChangeFault,
    LeakFault,
    PumpOutageFault,
    ScenarioConfig,
    SensorDropoutFault,
    SensorDriftFault,
    SensorStuckFault,
)

EXPECTED_DIAGNOSIS = {
    "leak": "leak",
    "pump_outage": "pump_issue",
    "sensor_drift": "sensor_fault",
    "sensor_stuck": "sensor_fault",
    "sensor_dropout": "sensor_fault",
    "demand_change": "demand_change",
}


class DetectedIncident(BaseModel):
    id: str
    diagnosis: str
    suspected_location: str | None
    severity: str
    first_detected_tick: int
    first_detected_time: str
    tick_count: int
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class DetectionScore(BaseModel):
    expected_diagnosis: str
    expected_location: str | None
    fault_start_tick: int
    detected: bool
    matched_incident_id: str | None
    latency_ticks: int | None
    latency_minutes: float | None
    location_correct: bool | None
    candidate_top3_contains_truth: bool | None
    localisation_error_m: float | None
    matching_rule: str


class QualityScore(BaseModel):
    faulted_sensor: str | None
    fault_window_ticks: int
    flagged_ticks: int
    flag_coverage: float | None
    bad_ticks: int
    suspect_ticks: int
    false_flags_on_fault_free_run: int


class ScenarioResult(BaseModel):
    scenario_id: str
    description: str
    network_version: str = NETWORK_VERSION
    seed: int
    ticks: int
    timestep_minutes: int
    runtime_seconds: float
    output_hash: str
    fault_free: bool
    incident_count: int
    incidents: list[DetectedIncident]
    alert_ticks: int
    watch_ticks: int
    alert_tick_fraction: float
    detection: DetectionScore | None
    quality: QualityScore
    labels: dict[str, str] = Field(
        default_factory=lambda: {
            "incidents": "MODEL",
            "alert_ticks": "MODEL",
            "latency": "MODEL",
            "quality": "MODEL",
            "ground_truth_faults": "ASSUMPTION",
        }
    )


class EvalSummary(BaseModel):
    scenarios: int
    fault_scenarios: int
    fault_scenarios_detected: int
    detection_rate: float
    mean_latency_minutes: float | None
    leaks_detected: int
    leaks_total: int
    leak_localisation_top1: int
    leak_localisation_top3: int
    fault_free_incidents: int
    fault_free_alert_tick_fraction: float
    notes: list[str]


class EvalReport(BaseModel):
    generated_at: str
    engine: str
    network_version: str
    detector_version: str
    presets: list[str]
    results: list[ScenarioResult]
    summary: EvalSummary
    determinism: dict[str, Any]
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = (
        "Virtual utility twin. Hypothetical network, simulated data. "
        "Metrics describe this prototype on its own synthetic network only."
    )


def fault_start_tick(config: ScenarioConfig) -> int | None:
    if not config.faults:
        return None
    return min(config.tick_at_hour(fault.start_hour) for fault in config.faults)


def expected_for_config(config: ScenarioConfig) -> tuple[str | None, str | None]:
    """Return (expected diagnosis, expected location) for the primary fault."""
    if not config.faults:
        return None, None
    fault = sorted(config.faults, key=lambda item: item.start_hour)[0]
    diagnosis = EXPECTED_DIAGNOSIS[fault.type]
    location: str | None = None
    if isinstance(fault, LeakFault):
        location = fault.location
    elif isinstance(fault, (SensorDriftFault, SensorStuckFault, SensorDropoutFault)):
        location = fault.sensor_id
    elif isinstance(fault, PumpOutageFault):
        location = fault.pump_id
    elif isinstance(fault, DemandChangeFault):
        location = "network"
    return diagnosis, location


def _pipe_midpoint(pipe_id: str, provider: NetworkProvider = DEFAULT_PROVIDER) -> tuple[float, float] | None:
    description = provider.describe()
    node_coords = {node.id: (node.x, node.y) for node in description.nodes}
    for link in description.links:
        if link.id == pipe_id:
            start = node_coords.get(link.start)
            end = node_coords.get(link.end)
            if start is None or end is None:
                return None
            return ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    return None


def localisation_error(
    suspected: str | None, truth: str | None
) -> float | None:
    if not suspected or not truth:
        return None
    if not suspected.startswith("pipe:") or not truth.startswith("pipe:"):
        return None
    a = _pipe_midpoint(suspected.split(":", 1)[1])
    b = _pipe_midpoint(truth.split(":", 1)[1])
    if a is None or b is None:
        return None
    return round(math.hypot(a[0] - b[0], a[1] - b[1]), 1)


def score_quality(
    config: ScenarioConfig,
    truth: TruthSeries,
    quality: dict[str, dict[str, list[Any]]],
    *,
    fault_free: bool,
) -> QualityScore:
    faulted = None
    window: list[int] = []
    for fault in config.faults:
        if isinstance(fault, (SensorDriftFault, SensorStuckFault, SensorDropoutFault)):
            faulted = fault.sensor_id
            start = config.tick_at_hour(fault.start_hour)
            duration = getattr(fault, "duration_hours", 0.0)
            if isinstance(fault, SensorDriftFault):
                end = config.ticks
            else:
                end = min(config.ticks, config.tick_at_hour(fault.start_hour + duration))
            window.extend(range(start, end + 1))
    flagged = 0
    bad = 0
    suspect = 0
    if faulted and window:
        series = quality[faulted]
        for tick in window:
            status = series["status"][tick]
            if status != "good":
                flagged += 1
            if status == "bad":
                bad += 1
            elif status == "suspect":
                suspect += 1
    false_flags = 0
    if fault_free:
        for series in quality.values():
            false_flags += sum(1 for status in series["status"] if status != "good")
    return QualityScore(
        faulted_sensor=faulted,
        fault_window_ticks=len(window),
        flagged_ticks=flagged,
        flag_coverage=round(flagged / len(window), 3) if window else None,
        bad_ticks=bad,
        suspect_ticks=suspect,
        false_flags_on_fault_free_run=false_flags,
    )
