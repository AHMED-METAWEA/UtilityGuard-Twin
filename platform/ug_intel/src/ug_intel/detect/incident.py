"""Deterministic incident hypotheses from D2 alarms; no probabilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ug_core.canonical import canonical_json, sha256_hex
from ug_core.grammar import require_identifier

from ug_intel.detect.cusum import D2Result


def incident_from(
    result: D2Result,
    sensor_kinds: Mapping[str, str],
    quality_flags: Mapping[str, Sequence[Mapping[str, Any]]],
    run_id: str,
    zone_of: Mapping[str, str | None],
) -> dict[str, Any] | None:
    """Build one v1 candidate, ordered by alarm tick then sensor id.

    Leak contributors are pressure-low/flow-high alarms within six ticks of
    the first alarm. Other hypotheses retain all alarming sensors. Zone
    membership is caller-supplied telemetry metadata, never a network object.
    """
    alarms = sorted(
        (r.alarm_tick, s) for s, r in result.sensors.items() if r.alarm_tick is not None
    )
    if not alarms:
        return None
    require_identifier(run_id, "run id")
    first_tick, first_sensor = alarms[0]
    for _, sensor in alarms:
        require_identifier(sensor, "sensor id")
        if zone_of[sensor] is not None:
            require_identifier(zone_of[sensor], "zone id")
    contributors = sorted(s for _, s in alarms)
    leak_sensors = sorted(
        s
        for tick, s in alarms
        if tick <= first_tick + 6
        and (sensor_kinds[s], result.sensors[s].direction)
        in {("pressure", "low"), ("flow", "high")}
    )
    flagged = bool(
        {"Q08", "Q04"} & set(quality_flags[first_sensor][first_tick].get("flags", ()))
    )
    related_alarm = any(
        s != first_sensor and zone_of[s] == zone_of[first_sensor] for _, s in alarms
    )
    hypothesis = "unknown"
    if len(alarms) == 1 and flagged and not related_alarm:
        hypothesis = "sensor_fault"
    elif len(leak_sensors) >= 2:
        hypothesis = "leak"
        contributors = leak_sensors
    count = len(contributors)
    support = "strong" if count >= 3 else "moderate" if count == 2 else "weak"
    rules = ["R_D2_CUSUM"]
    if count >= 2:
        rules.append("R_MULTI_SENSOR")
    if hypothesis == "sensor_fault":
        rules.append("R_QUALITY_FLAG")
    identity = {
        "run_id": run_id,
        "alarms": alarms,
        "hypothesis": hypothesis,
        "contributing_sensors": contributors,
    }
    return {
        "schema_version": "1",
        "incident_id": "incident-" + sha256_hex(canonical_json(identity))[:24],
        "run_id": run_id,
        "status": "open",
        "false_alarm": False,
        "severity": ("high" if support == "strong" else "medium")
        if hypothesis == "leak"
        else "low",
        "hypothesis": hypothesis,
        "support": support,
        "rules_fired": rules,
        "location": {"zone_id": zone_of[first_sensor], "candidates": []},
        "first_detected_tick": first_tick,
        "closed_at": None,
        "contributing_sensors": contributors,
    }
