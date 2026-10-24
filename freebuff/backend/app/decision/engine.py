"""Decision support: expected-cost comparison, constraints, break-even.

Advisory only. Every number is model-estimated and conditional on the
ASSUMPTION ranges in finance/assumptions.yaml. No failure probability is
invented; where a probability matters we report a break-even threshold.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.config import SETTINGS
from app.finance.engine import (
    cost_lines,
    get_assumption_values,
    load_assumptions,
    monte_carlo,
    total_cost,
)
from app.impact.runner import simulate_impact
from app.scenarios.runner import TruthSeries
from app.scenarios.schema import ScenarioConfig
from app.store import db

ACTION_LABELS = {
    "monitor": "Monitor only",
    "inspect": "Inspect, then repair if confirmed",
    "repair_isolate": "Isolate and repair now",
    "switch_standby_pump": "Switch to standby pump",
}

SEVERITY_ACTIONS = {
    "leak": ["monitor", "inspect", "repair_isolate"],
    "pump_issue": ["monitor", "inspect", "switch_standby_pump"],
    "sensor_fault": ["monitor", "inspect"],
    "demand_change": ["monitor"],
    "unknown": ["monitor", "inspect"],
}


def _applicable_actions(diagnosis: str) -> list[str]:
    return SEVERITY_ACTIONS.get(diagnosis, ["monitor", "inspect"])


def _break_even(
    monitor_cost: float,
    monitor_absent: float,
    action_cost: float,
    action_absent: float,
    action_label: str,
) -> dict[str, Any]:
    denominator = (monitor_cost - monitor_absent) - (action_cost - action_absent)
    if denominator <= 0:
        return {
            "action": action_label,
            "threshold": None,
            "text": (
                f"Under these assumptions {action_label.lower()} does not pay off "
                "at any probability: its cost when a fault is present is not lower "
                "than monitoring."
            ),
            "label": "CALCULATED",
            "formula": (
                "p* = (action_cost_absent - monitor_cost_absent) / "
                "[(monitor_cost_present - monitor_cost_absent) - "
                "(action_cost_present - action_cost_absent)]"
            ),
        }
    p = (action_absent - monitor_absent) / denominator
    if p < 0:
        text = (
            f"{action_label} is cheaper even if the fault is absent; "
            "the break-even probability is below 0."
        )
    elif p > 1:
        text = (
            f"{action_label} only pays off above P = {p:.2f}, which is outside "
            "the possible [0,1] range; monitoring remains cheaper in this model."
        )
    else:
        text = (
            f"{action_label} pays off if P(fault is real) exceeds {p:.2%}. "
            "This is a break-even threshold, not an estimated probability."
        )
    return {
        "action": action_label,
        "threshold": round(p, 4) if -1 <= p <= 2 else None,
        "text": text,
        "label": "CALCULATED",
        "formula": (
            "p* = (action_cost_absent - monitor_cost_absent) / "
            "[(monitor_cost_present - monitor_cost_absent) - "
            "(action_cost_present - action_cost_absent)]"
        ),
    }


def _cost_with_assumption(
    action: str,
    impacts: dict[str, dict[str, Any]],
    assumptions: dict[str, float],
) -> float:
    return total_cost(action, impacts, assumptions)[0]


def _sensitivity(
    actions: list[dict[str, Any]],
    assumptions_data: dict[str, Any],
) -> list[dict[str, Any]]:
    if len(actions) < 2:
        return []
    cfg = assumptions_data["assumptions"]
    base_values = {key: float(item["value"]) for key, item in cfg.items()}
    action_names = [a["action"] for a in actions]

    relevant = [
        "water_price_per_m3", "unserved_water_penalty_per_m3",
        "electricity_price_per_kwh", "inspection_cost",
        "repair_cost_planned", "repair_cost_emergency",
    ]
    by_action = {a["action"]: a["impacts"] for a in actions}
    results: list[dict[str, Any]] = []
    for key in relevant:
        low = float(cfg[key]["low"])
        high = float(cfg[key]["high"])
        values = dict(base_values)
        values[key] = low
        low_scores = {a: _cost_with_assumption(a, by_action[a], values) for a in action_names}
        values[key] = high
        high_scores = {a: _cost_with_assumption(a, by_action[a], values) for a in action_names}
        low_winner = min(low_scores, key=low_scores.get)
        high_winner = min(high_scores, key=high_scores.get)
        flips = low_winner != high_winner
        flip_value = None
        if flips:
            values[key] = base_values[key]
            base_diff = (
                _cost_with_assumption(low_winner, by_action[low_winner], values)
                - _cost_with_assumption(high_winner, by_action[high_winner], values)
            )
            lo, hi = min(low, high), max(low, high)
            for _ in range(30):
                mid = (lo + hi) / 2
                values[key] = mid
                diff = (
                    _cost_with_assumption(low_winner, by_action[low_winner], values)
                    - _cost_with_assumption(high_winner, by_action[high_winner], values)
                )
                if (diff > 0) == (base_diff > 0):
                    lo = mid
                else:
                    hi = mid
            flip_value = round((lo + hi) / 2, 4)
        results.append({
            "assumption": key,
            "unit": cfg[key]["unit"],
            "low": low,
            "mode": base_values[key],
            "high": high,
            "winner_at_low": low_winner,
            "winner_at_high": high_winner,
            "flips_ranking": flips,
            "flip_value": flip_value,
            "label": "CALCULATED",
            "note": (
                "Sensitivity varies cost assumptions with impacts held fixed; "
                "operational-duration assumptions need re-simulation and are "
                "not included here."
            ),
        })
    return results


def analyze_incident(
    incident: dict[str, Any],
    *,
    budget: float | None = None,
    max_unserved_m3: float | None = None,
) -> dict[str, Any]:
    run = db.get_run(incident["run_id"], include_blobs=True)
    if run is None or run["status"] != "ready":
        raise ValueError("the source run is not ready")
    config = ScenarioConfig(**run["config"])
    truth = TruthSeries.from_canon(run["truth"])
    baseline = TruthSeries.from_canon(run["baseline"])
    readings = run["readings"]
    assumptions_data = load_assumptions()
    assumptions = get_assumption_values()
    horizon = assumptions["decision_horizon_hours"]
    max_unserved = (
        max_unserved_m3 if max_unserved_m3 is not None
        else assumptions["max_unserved_m3"]
    )
    actions_names = _applicable_actions(incident["diagnosis"])
    leak_variants = ["low", "mid", "high"] if incident["diagnosis"] == "leak" else ["mid"]

    actions: list[dict[str, Any]] = []
    for action in actions_names:
        impacts: dict[str, dict[str, Any]] = {}
        for variant in leak_variants:
            impacts[variant] = simulate_impact(
                config, truth, baseline, incident, readings, action,
                leak_variant=variant,
                horizon_hours=horizon,
            )
        expected, lines = total_cost(action, impacts, assumptions)
        mc = monte_carlo(
            action, impacts, assumptions_data,
            samples=int(assumptions["monte_carlo_samples"]),
            seed=config.seed + 7,
        )
        worst = max(impacts.values(), key=lambda item: item["unserved_m3"])
        mid = impacts.get("mid", next(iter(impacts.values())))
        remaining_risk = {
            "water_lost_m3": worst["water_lost_m3"],
            "unserved_m3": worst["unserved_m3"],
            "low_pressure_node_hours": worst["low_pressure_node_hours"],
            "affected_nodes": worst["affected_nodes"],
            "label": "SIMULATION",
        }
        actions.append({
            "action": action,
            "label": ACTION_LABELS.get(action, action),
            "applicable": True,
            "expected_cost": mc["mean"],
            "mode_cost": expected,
            "cost_p10": mc["p10"],
            "cost_p50": mc["p50"],
            "cost_p90": mc["p90"],
            "cost_lines": lines,
            "representative_cost_lines": cost_lines(
                action, mid, assumptions,
                emergency=(action == "monitor"),
                include_inspection=(action == "inspect"),
            ),
            "impacts": impacts,
            "remaining_risk": remaining_risk,
            "constraint_ok": worst["unserved_m3"] <= max_unserved,
            "within_budget": budget is None or mc["p50"] <= budget,
            "monte_carlo": mc,
            "action_cost_evidence": {
                "label": "CALCULATED",
                "formula": "action_cost + water + unserved + energy + repair",
                "assumption_version": assumptions_data["version"],
            },
        })

    feasible = [
        a for a in actions
        if a["constraint_ok"] and (budget is None or a["within_budget"])
    ]
    ranking = sorted(actions, key=lambda a: a["expected_cost"])
    feasible_ranking = sorted(feasible, key=lambda a: a["expected_cost"])
    recommended = feasible_ranking[0]["action"] if feasible_ranking else "monitor"
    monitor = next(a for a in actions if a["action"] == "monitor")
    chosen = next(a for a in actions if a["action"] == recommended)
    savings = round(monitor["expected_cost"] - chosen["expected_cost"], 2)
    monitor_cost = monitor["monte_carlo"]["mean"]

    break_evens = []
    for candidate in ranking:
        if candidate["action"] == "monitor":
            continue
        # Cost incurred even if the fault turns out to be absent. A repair is
        # paid whether or not the suspected fault is real; an inspection is a
        # fixed crew cost. Without this, repairing looks free when no fault
        # exists and the break-even threshold collapses to zero.
        absent = 0.0
        if candidate["action"] == "inspect":
            absent = assumptions["inspection_cost"]
        elif candidate["action"] == "repair_isolate":
            absent = assumptions["repair_cost_planned"]
        break_evens.append(_break_even(
            monitor_cost, 0.0,
            candidate["monte_carlo"]["mean"], absent,
            candidate["label"],
        ))

    decision = {
        "decision_id": f"dec_{incident['id']}",
        "incident_id": incident["id"],
        "run_id": incident["run_id"],
        "scenario_id": config.scenario_id,
        "created_at": None,
        "diagnosis": incident["diagnosis"],
        "actions": actions,
        "ranking": [a["action"] for a in ranking],
        "feasible_ranking": [a["action"] for a in feasible_ranking],
        "recommended_action": recommended,
        "recommended_label": ACTION_LABELS.get(recommended, recommended),
        "savings_vs_monitor": savings,
        "savings_label": "CALCULATED",
        "savings_note": (
            "Model-estimated savings conditional on assumptions; not a "
            "guaranteed figure. Negative values mean monitoring is cheaper."
        ),
        "break_even": break_evens,
        "sensitivity": _sensitivity(actions, assumptions_data),
        "constraints": {
            "max_unserved_m3": max_unserved,
            "budget": budget,
            "constraint_ok": bool(feasible),
            "note": (
                "Feasible actions satisfy the unserved-demand constraint and "
                "optional budget. If none are feasible, monitoring is shown."
            ),
        },
        "horizon_hours": horizon,
        "assumptions_version": assumptions_data["version"],
        "assumption_values": assumptions,
        "labels": {
            "impacts": "SIMULATION",
            "costs": "CALCULATED",
            "unit_prices": "ASSUMPTION",
            "recommendation": "MODEL",
            "savings": "CALCULATED",
        },
        "advisory": (
            "Advisory only. A human must approve any action. Costs are model "
            "estimates conditional on placeholder assumptions."
        ),
        "method_note": (
            "Impacts are WNTR continuations from the incident time for the "
            "decision horizon; leak-size low/mid/high variants reflect "
            "uncertainty. Costs use triangular Monte Carlo ranges."
        ),
        "evidence": {
            "reproducibility": {
                "run_id": incident["run_id"],
                "seed": config.seed,
                "network_version": config.network_version,
                "detector_version": SETTINGS.detector_version,
                "assumptions_version": assumptions_data["version"],
                "horizon_hours": horizon,
                "policy": "same config + seed + assumptions -> same decision inputs",
            },
            "cost_lines": [
                {
                    "action": action["action"],
                    "variant": "mid",
                    "lines": action["representative_cost_lines"],
                }
                for action in actions
            ],
        },
    }
    db.save_decision(incident["id"], decision["decision_id"], decision)
    return decision
