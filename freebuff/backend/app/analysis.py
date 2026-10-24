"""Offline analysis pipeline run once per scenario, after the WNTR runs.

The streaming loop only replays these results; it never recomputes physics or
detection. Keeping this stage offline makes the stream deterministic and cheap.
"""
from __future__ import annotations

from app.alerts.manager import build_incidents
from app.config import DETECTOR_VERSION, SETTINGS
from app.detect.baseline import ExpectedModel
from app.detect.detector import RuleBasedDetector
from app.quality.checks import evaluate_quality, quality_dict
from app.scenarios.runner import RunBundle


def analyze_bundle(bundle: RunBundle, run_id: str) -> dict:
    expected = ExpectedModel(bundle.baseline)
    quality = evaluate_quality(bundle.readings, bundle.truth, expected)
    detector = RuleBasedDetector()
    detection = detector.run(
        bundle.readings, expected, quality, bundle.truth.ticks + 1,
    )
    incidents, alert_events = build_incidents(
        run_id, detection.diagnoses, bundle.truth.time_iso,
        bundle.truth.ticks,
    )
    incident_summaries = [
        {
            "id": inc["id"],
            "diagnosis": inc["diagnosis"],
            "severity": inc["severity"],
            "first_detected_tick": inc["first_detected_tick"],
            "last_tick": inc["last_tick"],
            "suspected_location": inc["suspected_location"],
        }
        for inc in incidents
    ]
    return {
        "quality": quality_dict(quality),
        "detector": {
            "version": DETECTOR_VERSION,
            "state": detection.states,
            "residuals": detection.residuals,
            "confidence": detection.confidence,
            "per_sensor_state": detection.per_sensor_state,
        },
        "diagnoses": detection.diagnoses,
        "incidents": incidents,
        "alert_events": alert_events,
        "summary": {
            "incidents": len(incidents),
            "incident_summaries": incident_summaries,
            "alert_ticks": sum(1 for s in detection.states if s == "alert"),
            "quality_bad_readings": sum(
                1 for q in quality.values() for s in q.status if s == "bad"
            ),
        },
        "labels": {
            "quality": "MODEL",
            "detector": "MODEL",
            "diagnosis": "MODEL",
            "incidents": "MODEL",
        },
        "notes": [
            "Detector compares simulated measurements to a fault-free WNTR run.",
            "Results are on simulated faults, not field validation.",
            "Rules are transparent; no probabilities are produced.",
        ],
        "detector_config": SETTINGS.detector.model_dump(),
        "quality_config": SETTINGS.quality.model_dump(),
    }
