"""Incident grouping: one incident, not one alert per sensor per tick.

Grouping rules (docs/assumptions.md):
  * same diagnosis
  * detections no more than `group_window_ticks` apart
  * same suspected location (sensor id, pipe id, pump id), or same network
"""
from __future__ import annotations

from app.config import SETTINGS

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def _same_location(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a == b
    if a == b:
        return True
    # Candidate pipe lists may flip between neighbouring pipes; treat any
    # shared top-3 candidate as the same neighbourhood.
    return False


def _summary(inc: dict) -> str:
    diagnosis = inc["diagnosis"].replace("_", " ")
    where = inc.get("suspected_location") or "an unlocalised location"
    return (
        f"{diagnosis.capitalize()} detected near {where} at "
        f"{inc.get('first_detected_time', 'unknown time')} (simulated tick "
        f"{inc['first_detected_tick']}). Rule strength: {inc.get('strength', 'weak')}. "
        "Advisory only; a human must approve any action."
    )


def build_incidents(
    run_id: str,
    diagnoses: list[dict],
    times: list[str],
    final_tick: int,
) -> tuple[list[dict], dict[str, list[str]]]:
    incidents: list[dict] = []
    active: dict[int, dict] = {}
    counter = 0
    window = SETTINGS.detector.group_window_ticks

    for detection in sorted(diagnoses, key=lambda d: d["tick"]):
        if detection.get("network_state") != "alert":
            continue
        tick = detection["tick"]
        match = None
        for idx, inc in active.items():
            if inc["diagnosis"] != detection["diagnosis"]:
                continue
            if tick - inc["last_tick"] > window:
                continue
            if detection["diagnosis"] == "leak":
                # A leak keeps producing detections for hours; candidate pipe
                # rankings can flip slightly. Keep one incident per event.
                match = idx
                break
            if _same_location(inc["suspected_location"], detection.get("suspected_location")):
                match = idx
                break
        if match is None:
            counter += 1
            inc = {
                "id": f"inc_{run_id[:8]}_{counter:03d}",
                "run_id": run_id,
                "status": "open",
                "severity": detection.get("severity", "low"),
                "diagnosis": detection["diagnosis"],
                "suspected_location": detection.get("suspected_location"),
                "first_detected_tick": tick,
                "last_tick": tick,
                "first_detected_time": times[tick],
                "strength": detection.get("strength", "weak"),
                "sensors": sorted(detection.get("sensors", [])),
                "rules_fired": list(detection.get("rules_fired", [])),
                "candidates": list(detection.get("candidates", [])),
                "quality_context": detection.get("quality_context", {}),
                "evidence_numbers": {
                    "residuals_sigma": detection.get("residuals", {}),
                    "quality_scores": detection.get("quality_scores", {}),
                },
                "tick_count": 1,
                "evidence_refs": [
                    f"run:{run_id}",
                    f"tick:{tick}",
                    f"detector:{SETTINGS.detector_version}",
                ],
                "labels": {
                    "diagnosis": "MODEL",
                    "severity": "MODEL",
                    "strength": "MODEL",
                    "location": "MODEL",
                },
                "advisory": "Advisory only. A human must approve any action.",
            }
            incidents.append(inc)
            active[counter] = inc
        else:
            inc = active[match]
            inc["last_tick"] = tick
            inc["tick_count"] += 1
            inc["sensors"] = sorted(set(inc["sensors"]) | set(detection.get("sensors", [])))
            if SEVERITY_ORDER.get(detection.get("severity", "low"), 0) > SEVERITY_ORDER.get(
                    inc["severity"], 0):
                inc["severity"] = detection["severity"]
            if detection.get("strength") == "strong":
                inc["strength"] = "strong"
            for rule in detection.get("rules_fired", []):
                if rule not in inc["rules_fired"]:
                    inc["rules_fired"].append(rule)
            if not inc.get("candidates") and detection.get("candidates"):
                inc["candidates"] = detection["candidates"]
                inc["suspected_location"] = detection.get("suspected_location")

    # Drop unknown incidents that overlap a specific diagnosis; do not invent
    # certainty, but avoid duplicate incidents for the same event.
    specific = [inc for inc in incidents if inc["diagnosis"] != "unknown"]
    kept: list[dict] = []
    for inc in incidents:
        if inc["diagnosis"] == "unknown":
            # A one-tick ambiguous blip is not an incident; require persistence.
            if inc["tick_count"] < 6:
                continue
            overlaps = any(
                other["first_detected_tick"] - window <= inc["last_tick"]
                and inc["first_detected_tick"] - window <= other["last_tick"]
                for other in specific
            )
            if overlaps:
                continue
        kept.append(inc)

    for inc in kept:
        inc["summary"] = _summary(inc)
        inc["quality_context"]["network_confidence"] = (
            "lower when many sensors are degraded; see quality page"
        )

    alert_events: dict[str, list[str]] = {}
    for inc in kept:
        alert_events.setdefault(str(inc["first_detected_tick"]), []).append(inc["id"])
    return kept, alert_events
