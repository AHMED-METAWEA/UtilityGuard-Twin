"""Evidence builder.

Every number exposed by the incident and decision endpoints has a record with
value, unit, evidence label, formula, inputs, sources and a template-generated
explanation. No LLM is involved.
"""
from __future__ import annotations

from typing import Any

from app.config import DETECTOR_VERSION, NETWORK_VERSION, SENSOR_NOISE
from app.store import db

LABELS = {
    "SIMULATION", "SENSOR_SIM", "MODEL", "ASSUMPTION", "CALCULATED",
    "INSUFFICIENT_EVIDENCE",
}


def _record(
    name: str,
    value: Any,
    unit: str,
    label: str,
    formula: str,
    inputs: list[dict[str, Any]],
    sources: dict[str, Any],
    explanation: str,
) -> dict[str, Any]:
    assert label in LABELS, label
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "label": label,
        "formula": formula,
        "inputs": inputs,
        "sources": sources,
        "explanation": explanation,
    }


def build_incident_evidence(incident: dict[str, Any]) -> dict[str, Any]:
    run = db.get_run(incident["run_id"])
    config = run["config"] if run else {}
    decision = db.get_decision(incident["id"])
    sources = {
        "run_id": incident["run_id"],
        "network_version": NETWORK_VERSION,
        "detector_version": DETECTOR_VERSION,
        "assumption_version": (
            decision.get("assumptions_version") if decision else None
        ),
        "seed": config.get("seed"),
        "tick": incident["first_detected_tick"],
    }
    reproducibility = {
        "run_id": incident["run_id"],
        "scenario_id": config.get("scenario_id"),
        "network_version": NETWORK_VERSION,
        "detector_version": DETECTOR_VERSION,
        "seed": config.get("seed"),
        "config": config,
        "assumption_version": sources["assumption_version"],
        "impact_method": (
            decision.get("method_note") if decision else
            "not analyzed yet; use POST /api/incidents/{id}/analyze"
        ),
        "recompute": (
            "Re-run the scenario with this config and seed, then run the "
            "detector and decision engine with the same assumption version."
        ),
    }

    numbers: list[dict[str, Any]] = [
        _record(
            "Incident diagnosis",
            incident["diagnosis"],
            "class",
            "MODEL",
            "rule-based diagnosis over normalized residuals and quality flags",
            [{"name": f"rule: {rule}", "label": "MODEL"} for rule in incident.get("rules_fired", [])],
            sources,
            (
                "The diagnosis is the first matching rule in the documented "
                "precedence order; it is not a probability."
            ),
        ),
        _record(
            "Severity",
            incident["severity"],
            "class",
            "MODEL",
            "severity rule (low/medium/high) based on sensor count, residual size and tank state",
            [{"name": "rule strength", "value": incident.get("strength"), "label": "MODEL"}],
            sources,
            "Severity is a stated rule label, not a calibrated probability.",
        ),
        _record(
            "First detected tick",
            incident["first_detected_tick"],
            "tick",
            "MODEL",
            "first tick at which persistence/CUSUM and diagnosis rules opened this incident",
            [{"name": "first detected time", "value": incident.get("first_detected_time"), "label": "MODEL"}],
            sources,
            "Detection time is relative to the simulated run clock.",
        ),
    ]

    residuals = incident.get("evidence_numbers", {}).get("residuals_sigma", {})
    for sid, z in sorted(residuals.items()):
        numbers.append(_record(
            f"Residual {sid}",
            z,
            "sigma",
            "MODEL",
            "(simulated reading - fault-free baseline expectation) / sensor noise sigma",
            [
                {"name": "simulated reading", "label": "SENSOR_SIM"},
                {"name": "baseline expectation", "label": "SIMULATION"},
                {"name": "sensor sigma", "value": SENSOR_NOISE.get(sid), "unit": "sensor unit", "label": "ASSUMPTION"},
            ],
            sources,
            (
                "A residual of 1 means the reading is one sensor-noise standard "
                "deviation from the fault-free expectation. Residuals are not "
                "probabilities."
            ),
        ))

    for candidate in incident.get("candidates", []):
        numbers.append(_record(
            f"Leak candidate {candidate['pipe']}",
            candidate["score"],
            "score",
            "MODEL",
            "sum over pressure sensors of max(0, -local residual) x exp(-distance/220 m)",
            [{"name": "candidate pipe", "value": candidate["pipe"], "label": "MODEL"}],
            sources,
            "Candidate score is a transparent geometric ranking, not a probability.",
        ))

    if decision:
        for action in decision.get("actions", []):
            for line in action.get("representative_cost_lines", []):
                numbers.append(_record(
                    f"{action['label']}: {line['line']}",
                    line["cost"],
                    "CU",
                    "CALCULATED",
                    line["formula"],
                    [
                        {"name": "quantity", "value": line["quantity"], "unit": line["unit"],
                         "label": line.get("label", "SIMULATION")},
                        {"name": "unit price", "value": line["unit_price"],
                         "unit": line["unit_price_unit"], "label": "ASSUMPTION",
                         "assumption": line["assumption"]},
                    ],
                    {**sources, "assumption_version": decision.get("assumptions_version")},
                    (
                        f"Money line = {line['quantity']} {line['unit']} x "
                        f"{line['unit_price']} CU/{line['unit']}. The unit price "
                        "is an editable placeholder assumption."
                    ),
                ))
            mc = action["monte_carlo"]
            numbers.append(_record(
                f"{action['label']}: expected cost",
                action["expected_cost"],
                "CU",
                "CALCULATED",
                "mean of Monte Carlo total cost over triangular assumption ranges and leak-size variants",
                [
                    {"name": "P10", "value": mc["p10"], "unit": "CU", "label": "CALCULATED"},
                    {"name": "P50", "value": mc["p50"], "unit": "CU", "label": "CALCULATED"},
                    {"name": "P90", "value": mc["p90"], "unit": "CU", "label": "CALCULATED"},
                ],
                sources,
                (
                    "Model-estimated cost conditional on placeholder assumptions. "
                    "Do not read this as a guaranteed or market figure."
                ),
            ))

        for be in decision.get("break_even", []):
            numbers.append(_record(
                f"Break-even: {be['action']}",
                be.get("threshold"),
                "probability threshold",
                "CALCULATED",
                be["formula"],
                [
                    {"name": "monitor cost", "label": "CALCULATED"},
                    {"name": "action cost", "label": "CALCULATED"},
                ],
                sources,
                be["text"],
            ))

    return {
        "incident": {
            "id": incident["id"],
            "run_id": incident["run_id"],
            "status": incident["status"],
            "diagnosis": incident["diagnosis"],
            "severity": incident["severity"],
            "suspected_location": incident.get("suspected_location"),
            "first_detected_time": incident.get("first_detected_time"),
            "rules_fired": incident.get("rules_fired", []),
            "sensors": incident.get("sensors", []),
            "quality_context": incident.get("quality_context", {}),
            "labels": incident.get("labels", {}),
        },
        "numbers": numbers,
        "reproducibility": reproducibility,
        "decision_available": bool(decision),
        "disclaimer": (
            "Virtual utility twin. Hypothetical network, simulated data. "
            "Advisory only; a human must approve any action."
        ),
    }
