"""Residual detector with persistence/CUSUM, exposed behind a small interface.

The rule-based detector is the baseline. A future ML detector can implement
`Detector` and be compared on the same inputs/outputs without touching the
quality layer, alert manager, or UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.config import SETTINGS, DetectorConfig, SENSOR_NOISE
from app.detect.baseline import ExpectedModel
from app.detect.diagnose import Diagnosis, diagnose_tick, quality_sensor_diagnosis
from app.network.builder import DEFAULT_PROVIDER, NetworkProvider
from app.quality.checks import QualityResult


@dataclass
class DetectorOutput:
    residuals: list[dict[str, float]] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    per_sensor_state: dict[str, list[str]] = field(default_factory=dict)
    confidence: list[dict] = field(default_factory=list)
    diagnoses: list[dict] = field(default_factory=list)


class Detector(Protocol):
    version: str

    def run(
        self,
        readings: dict[str, list[float | None]],
        expected: ExpectedModel,
        quality: dict[str, QualityResult],
        ticks: int,
    ) -> DetectorOutput: ...


class RuleBasedDetector:
    version = "rules-v1"

    def __init__(self, config: DetectorConfig | None = None,
                 provider: NetworkProvider = DEFAULT_PROVIDER):
        self.cfg = config or SETTINGS.detector
        self.provider = provider
        self.sensors = [s.id for s in provider.describe().sensors]

    def run(
        self,
        readings: dict[str, list[float | None]],
        expected: ExpectedModel,
        quality: dict[str, QualityResult],
        ticks: int,
    ) -> DetectorOutput:
        out = DetectorOutput(
            residuals=[{} for _ in range(ticks)],
            states=["normal"] * ticks,
            per_sensor_state={sid: ["normal"] * ticks for sid in self.sensors},
            confidence=[{"level": "high", "good_fraction": 1.0} for _ in range(ticks)],
            diagnoses=[],
        )
        consecutive = {sid: 0 for sid in self.sensors}
        cusum_pos = {sid: 0.0 for sid in self.sensors}
        cusum_neg = {sid: 0.0 for sid in self.sensors}
        # Trailing residual history used only for leak-candidate scoring. A
        # single 5-minute sample is too noisy to rank pipes reliably.
        history: dict[str, list[float]] = {sid: [] for sid in self.sensors}
        smoothing_ticks = 6

        for tick in range(ticks):
            residuals: dict[str, float] = {}
            states: dict[str, str] = {}
            flags_at_tick: dict[str, list[str]] = {}
            status_at_tick: dict[str, str] = {}
            good = 0
            degraded = 0
            for sid in self.sensors:
                q = quality[sid]
                status = q.status[tick]
                status_at_tick[sid] = status
                flags_at_tick[sid] = q.flags[tick]
                if status == "bad":
                    degraded += 1
                else:
                    good += 1
                value = readings[sid][tick]
                if value is None:
                    states[sid] = "normal"
                    out.per_sensor_state[sid][tick] = "normal"
                    continue
                z = expected.residual_sigma(sid, value, tick)
                if z is None:
                    states[sid] = "normal"
                    out.per_sensor_state[sid][tick] = "normal"
                    continue
                # Down-weight degraded sensors rather than trusting them fully.
                # Bad readings are still allowed to support a sensor-fault
                # diagnosis (a stuck sensor must not silently disappear).
                if status == "bad":
                    z_for_logic = z * 0.25
                elif status == "suspect":
                    z_for_logic = z * 0.5
                else:
                    z_for_logic = z
                residuals[sid] = round(float(z), 2)
                if status != "bad":
                    history[sid].append(float(z))
                    if len(history[sid]) > smoothing_ticks:
                        history[sid].pop(0)
                cusum_pos[sid] = max(0.0, cusum_pos[sid] + z_for_logic - self.cfg.cusum_drift)
                cusum_neg[sid] = max(0.0, cusum_neg[sid] - z_for_logic - self.cfg.cusum_drift)
                if abs(z_for_logic) > self.cfg.watch_threshold:
                    consecutive[sid] += 1
                else:
                    consecutive[sid] = 0
                cusum_triggered = (
                    cusum_pos[sid] > self.cfg.cusum_threshold
                    or cusum_neg[sid] > self.cfg.cusum_threshold
                )
                alert = (
                    (consecutive[sid] >= self.cfg.persistence_ticks
                     and abs(z_for_logic) >= self.cfg.alert_threshold)
                    # CUSUM must be corroborated by a current deviation; this
                    # prevents stale alerts after a fault clears.
                    or (cusum_triggered
                        and abs(z_for_logic) >= self.cfg.watch_threshold)
                )
                if alert:
                    state = "alert"
                elif abs(z_for_logic) > self.cfg.watch_threshold:
                    state = "watch"
                else:
                    state = "normal"
                states[sid] = state
                out.per_sensor_state[sid][tick] = state
                out.residuals[tick] = residuals

            bad_fraction = degraded / max(1, len(self.sensors))
            suspect_fraction = sum(
                1 for s in status_at_tick.values() if s == "suspect"
            ) / max(1, len(self.sensors))
            if bad_fraction >= self.cfg.network_confidence_bad_fraction:
                level = "low"
            elif bad_fraction >= 0.1 or suspect_fraction >= 0.2:
                level = "medium"
            else:
                level = "high"
            out.confidence[tick] = {
                "level": level,
                "good_fraction": round(good / max(1, len(self.sensors)), 3),
            }
            network_state = "alert" if "alert" in states.values() else (
                "watch" if "watch" in states.values() else "normal"
            )
            out.states[tick] = network_state

            diagnoses: list[Diagnosis] = []
            if network_state != "normal":
                smoothed = {
                    sid: round(sum(values) / len(values), 2)
                    for sid, values in history.items()
                    if len(values) >= 3
                }
                diagnosis = diagnose_tick(
                    tick, residuals, states, flags_at_tick, status_at_tick,
                    self.provider, smoothed_residuals=smoothed,
                )
                if diagnosis is not None:
                    diagnoses.append(diagnosis)

            # Sensor integrity findings do not require a residual alert: a
            # stuck or out-of-range reading is itself the evidence.
            for sid, status in status_at_tick.items():
                qf = flags_at_tick.get(sid, [])
                if status == "bad" and any(
                    flag in qf for flag in
                    ("stuck", "stuck_persistent", "out_of_range")
                ):
                    diagnoses.append(quality_sensor_diagnosis(
                        tick, sid, qf, status_at_tick,
                    ))
                    if out.states[tick] != "alert":
                        out.states[tick] = "alert"
            for diagnosis in diagnoses:
                payload = diagnosis.to_dict()
                payload["tick"] = tick
                payload["residuals"] = dict(residuals)
                payload["quality_scores"] = {
                    sid: quality[sid].score[tick] for sid in self.sensors
                }
                payload["network_state"] = (
                    "alert" if diagnosis.diagnosis == "sensor_fault"
                    and diagnosis.quality_context.get("sensor_flags")
                    else out.states[tick]
                )
                payload["confidence"] = out.confidence[tick]
                out.diagnoses.append(payload)
        return out


DETECTOR: Detector = RuleBasedDetector()
