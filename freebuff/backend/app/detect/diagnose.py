"""Rule-based diagnosis.

Rules are intentionally simple and inspectable. No probabilities are produced;
`strength` is a rule-strength label (weak/moderate/strong), not a confidence
percentage.

Order of precedence:
  1. pump_issue  - flow signature at the pump station / tank drain
  2. leak        - clustered pressure drops plus extra outflow evidence
  3. sensor_fault - one sensor deviates while neighbours/flow/tank agree
  4. demand_change - smooth, network-wide same-sign shift without flow imbalance
  5. unknown     - do not guess
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import exp, hypot

from app.config import SETTINGS
from app.network.builder import DEFAULT_PROVIDER, NetworkProvider

PRESSURE_SENSORS = [f"P{i:02d}" for i in range(1, 9)]
FLOW_SENSORS = ["F01", "F02", "F03"]


@dataclass
class Diagnosis:
    diagnosis: str
    suspected_location: str | None
    strength: str
    rules_fired: list[str] = field(default_factory=list)
    sensors: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    severity: str = "low"
    quality_context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _sensor_coords() -> dict[str, tuple[float, float]]:
    return {s.id: (s.x, s.y) for s in DEFAULT_PROVIDER.describe().sensors}


def _cluster(sensors: list[str], coords: dict[str, tuple[float, float]]) -> list[str]:
    if not sensors:
        return []
    best: list[str] = []
    for seed in sensors:
        group = [
            other for other in sensors
            if _distance(coords[seed], coords[other])
            <= SETTINGS.detector.cluster_distance_m
        ]
        if len(group) > len(best):
            best = group
    return best


def _candidate_pipes(
    residuals: dict[str, float],
    coords: dict[str, tuple[float, float]],
    provider: NetworkProvider,
) -> list[dict]:
    description = provider.describe()
    node_coords = {n.id: (n.x, n.y) for n in description.nodes}
    scores: list[dict] = []
    for link in description.links:
        if link.kind != "pipe" or not link.id.startswith("PIPE_"):
            continue
        start = node_coords.get(link.start)
        end = node_coords.get(link.end)
        if start is None or end is None:
            continue
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        score = 0.0
        for sid, z in residuals.items():
            if sid not in coords or z >= 0:
                continue
            d = _distance(coords[sid], mid)
            score += (-z) * exp(-d / 220.0)
        if score > 0:
            scores.append({"pipe": link.id, "score": round(score, 3)})
    scores.sort(key=lambda item: (-item["score"], item["pipe"]))
    return scores[:3]


def _severity(
    diagnosis: str,
    pressure_drops: list[float],
    n_alert: int,
    tank_residual: float | None,
) -> str:
    if diagnosis == "leak":
        if len(pressure_drops) >= 3 and max(pressure_drops, default=0) > 8:
            return "high"
        return "medium"
    if diagnosis == "pump_issue":
        if tank_residual is not None and tank_residual < -3:
            return "high"
        return "medium"
    if diagnosis == "sensor_fault":
        return "low"
    if diagnosis == "demand_change":
        return "low"
    return "low"


def quality_sensor_diagnosis(
    tick: int,
    sensor_id: str,
    flags: list[str],
    quality_status: dict[str, str],
) -> Diagnosis:
    """Sensor integrity finding raised directly by the quality layer.

    Used for stuck/out-of-range sensors whose residual is intentionally
    down-weighted because the reading is known to be untrustworthy.
    """
    return Diagnosis(
        diagnosis="sensor_fault",
        suspected_location=sensor_id,
        strength="strong",
        rules_fired=[
            "quality layer marked the reading bad",
            f"quality flags: {', '.join(sorted(flags))}",
        ],
        sensors=[sensor_id],
        candidates=[],
        severity="low",
        quality_context={
            "bad_sensors": [s for s, status in quality_status.items()
                            if status == "bad"],
            "sensor_flags": {sensor_id: flags},
        },
    )


def diagnose_tick(
    tick: int,
    residuals: dict[str, float],
    sensor_states: dict[str, str],
    quality_flags: dict[str, list[str]],
    quality_status: dict[str, str],
    provider: NetworkProvider = DEFAULT_PROVIDER,
    smoothed_residuals: dict[str, float] | None = None,
) -> Diagnosis | None:
    available = {
        sid: z for sid, z in residuals.items()
        if z is not None and quality_status.get(sid) != "bad"
    }
    deviating = {
        sid: z for sid, z in available.items()
        if abs(z) >= SETTINGS.detector.watch_threshold
    }
    if not deviating:
        return None
    # A lone tank-level deviation below alert strength is a slow model/state
    # divergence (e.g. the tank recovering after a pump event), not evidence
    # of a fault. Reporting an incident here would be guessing.
    tank_only = set(deviating) == {"T01"}
    if tank_only and abs(deviating["T01"]) < SETTINGS.detector.alert_threshold:
        return None
    # A single sensor at watch strength, with no quality evidence, is a blip.
    # Opening an "unknown" incident for it would be noise, not detection.
    if len(deviating) == 1:
        only_id, only_z = next(iter(deviating.items()))
        strong_flags = {
            "stuck", "stuck_persistent", "drift_vs_neighbors", "rate_spike",
            "out_of_range", "missing",
        }
        if (abs(only_z) < SETTINGS.detector.alert_threshold
                and not strong_flags.intersection(quality_flags.get(only_id, []))):
            return None

    coords = _sensor_coords()
    pressure_neg = [
        sid for sid in PRESSURE_SENSORS
        if sid in deviating and deviating[sid] <= -SETTINGS.detector.watch_threshold
    ]
    pressure_drops = [-deviating[sid] for sid in pressure_neg]
    flow_z = {sid: available.get(sid) for sid in FLOW_SENSORS}
    tank_z = available.get("T01")
    flags: list[str] = []
    quality_context = {
        "bad_sensors": [s for s, status in quality_status.items() if status == "bad"],
        "suspect_sensors": [s for s, status in quality_status.items()
                            if status == "suspect"],
        "flags": {sid: quality_flags.get(sid, []) for sid in deviating},
    }

    # 1. Pump issue: pump discharge collapses while the tank supplies the grid.
    f01 = flow_z.get("F01")
    if f01 is not None and f01 < -6.0 and (
        (tank_z is not None and tank_z < -1.5)
        or (flow_z.get("F02") or 0) > 2.0
    ):
        return Diagnosis(
            diagnosis="pump_issue",
            suspected_location="PUMP_1",
            strength="strong" if f01 < -15 else "moderate",
            rules_fired=[
                "F01 residual below -6 sigma (pump discharge collapsed)",
                "tank level or tank outflow shows the tank is supplying the grid",
            ],
            sensors=["F01", "F02"] + (["T01"] if tank_z is not None else []),
            candidates=[],
            severity=_severity("pump_issue", pressure_drops, 0, tank_z),
            quality_context=quality_context,
        )

    # 2. Leak: clustered pressure drop + extra outflow evidence.
    cluster = _cluster(pressure_neg, coords)
    flow_support = (
        (f01 is not None and f01 > 2.0)
        or ((flow_z.get("F02") is not None and (flow_z.get("F02") or 0) > 2.0))
        or (tank_z is not None and tank_z < -1.5)
    )
    quality_noise = any(
        any(flag in quality_flags.get(sid, [])
            for flag in ("stuck", "drift_vs_neighbors", "missing"))
        for sid in cluster
    )
    if len(cluster) >= SETTINGS.detector.leak_min_sensors and flow_support:
        if quality_noise and len(cluster) <= 2:
            return Diagnosis(
                diagnosis="unknown",
                suspected_location=None,
                strength="weak",
                rules_fired=[
                    "clustered pressure drop is confounded by a sensor quality flag",
                ],
                sensors=sorted(deviating),
                candidates=[],
                severity="low",
                quality_context=quality_context,
            )
        # Localise on the local *excess* drop, subtracting the network-wide
        # median shift so a global demand effect does not dominate the score.
        # Candidate scoring uses a short trailing mean of residuals: a single
        # 5-minute sample has 0.12 m sensor noise, which is the same order as
        # the local gradient, so averaging several ticks is required for the
        # ranking to carry any information at all.
        local_source = smoothed_residuals if smoothed_residuals else available
        pressure_values = sorted(
            local_source[sid] for sid in PRESSURE_SENSORS if sid in local_source
        )
        median_z = (
            pressure_values[len(pressure_values) // 2] if pressure_values else 0.0
        )
        local_residuals = {
            sid: local_source[sid] - median_z
            for sid in PRESSURE_SENSORS if sid in local_source
        }
        candidates = _candidate_pipes(local_residuals, coords, provider)
        strength = "strong" if max(pressure_drops, default=0) > 8 else "moderate"
        return Diagnosis(
            diagnosis="leak",
            suspected_location=(
                f"pipe:{candidates[0]['pipe']}" if candidates else None
            ),
            strength=strength,
            rules_fired=[
                f"{len(cluster)} nearby pressure sensors deviate downward together",
                "flow/tank evidence shows additional outflow",
                "top-3 candidate pipes scored by residual proximity, using a "
                "trailing 30-minute mean of pressure residuals",
            ],
            sensors=sorted(set(cluster + ["F01", "F02"])),
            candidates=candidates,
            severity=_severity("leak", pressure_drops, len(cluster), tank_z),
            quality_context=quality_context,
        )

    # 3. Sensor fault: one sensor deviates while neighbours agree. Require a
    # quality flag plus an alert-level residual (or a very large isolated
    # residual) so random noise stays quiet.
    if len(deviating) == 1 and not flow_support:
        sid = next(iter(deviating))
        qf = quality_flags.get(sid, [])
        strong_flag = any(
            flag in qf for flag in
            ("stuck", "stuck_persistent", "drift_vs_neighbors", "rate_spike")
        )
        if abs(deviating[sid]) >= SETTINGS.detector.alert_threshold and (
                strong_flag or abs(deviating[sid]) > 8.0):
            strength = "strong" if strong_flag else "moderate"
            return Diagnosis(
                diagnosis="sensor_fault",
                suspected_location=sid,
                strength=strength,
                rules_fired=[
                    "exactly one sensor deviates",
                    "hydraulically related sensors, flows and tank remain consistent",
                ] + ([f"quality flags: {', '.join(sorted(qf))}"] if qf else []),
                sensors=[sid],
                candidates=[],
                severity="low",
                quality_context=quality_context,
            )

    # 4. Demand change: broad, strong, same-sign shift without extra outflow.
    pressure_all = [
        sid for sid in PRESSURE_SENSORS
        if sid in available and abs(available[sid]) >= SETTINGS.detector.watch_threshold
    ]
    if len(pressure_all) >= 6 and not flow_support:
        signs = {1 if available[sid] > 0 else -1 for sid in pressure_all}
        magnitudes = sorted(abs(available[sid]) for sid in pressure_all)
        median_magnitude = magnitudes[len(magnitudes) // 2]
        if len(signs) == 1 and median_magnitude >= 4.0:
            return Diagnosis(
                diagnosis="demand_change",
                suspected_location="network",
                strength="moderate",
                rules_fired=[
                    "six or more pressure sensors shift in the same direction",
                    "no pump/tank outflow imbalance",
                    "baseline demand settings are known; an unforecast change is assumed",
                ],
                sensors=sorted(pressure_all),
                candidates=[],
                severity="low",
                quality_context=quality_context,
            )

    return Diagnosis(
        diagnosis="unknown",
        suspected_location=None,
        strength="weak",
        rules_fired=[
            "residuals deviate but no diagnostic rule matches confidently",
        ],
        sensors=sorted(deviating),
        candidates=[],
        severity="low",
        quality_context=quality_context,
    )
