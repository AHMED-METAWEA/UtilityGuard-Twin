"""Finance engine: traceable cost lines and Monte Carlo ranges.

No value here is a market price. Every assumption is labelled ASSUMPTION and
can be edited in the UI; the resulting numbers are conditional on those inputs.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from app.config import DATA_DIR

ASSUMPTIONS_PATH = Path(__file__).with_name("assumptions.yaml")
OVERRIDES_PATH = DATA_DIR / "assumption_overrides.json"
CURRENCY = "CU (placeholder currency units)"


def _base() -> dict[str, Any]:
    with ASSUMPTIONS_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data


def _overrides() -> dict[str, Any]:
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        return json.loads(OVERRIDES_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def load_assumptions() -> dict[str, Any]:
    base = _base()
    overrides = _overrides()
    values = overrides.get("values", {})
    assumptions = base["assumptions"]
    for key, value in values.items():
        if key in assumptions:
            assumptions[key]["value"] = value
    version = base["version"]
    if overrides:
        version = f"{base['version']}+rev{overrides.get('revision', 1)}"
    return {
        "version": version,
        "base_version": base["version"],
        "currency": base.get("currency", CURRENCY),
        "updated_at": overrides.get("updated_at", base.get("updated_at")),
        "assumptions": assumptions,
        "labels": {key: item["label"] for key, item in assumptions.items()},
        "disclaimer": (
            "All prices and ranges are placeholder assumptions, not real "
            "tariffs or contractor quotes. Costs are model estimates conditional "
            "on these inputs."
        ),
        "editable": True,
    }


def get_assumption_values() -> dict[str, float]:
    data = load_assumptions()
    return {key: float(item["value"]) for key, item in data["assumptions"].items()}


def update_assumptions(values: dict[str, float]) -> dict[str, Any]:
    base = _base()
    assumptions = base["assumptions"]
    current = _overrides()
    merged = dict(current.get("values", {}))
    for key, value in values.items():
        if key not in assumptions:
            raise ValueError(f"unknown assumption: {key}")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"{key} must be finite")
        item = assumptions[key]
        if not (float(item["low"]) <= value <= float(item["high"])):
            raise ValueError(
                f"{key} must be within plausible range "
                f"[{item['low']}, {item['high']}]"
            )
        merged[key] = value
    revision = int(current.get("revision", 0)) + 1
    payload = {
        "revision": revision,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "values": merged,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OVERRIDES_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return load_assumptions()


def reset_assumptions() -> dict[str, Any]:
    if OVERRIDES_PATH.exists():
        OVERRIDES_PATH.unlink()
    return load_assumptions()


def cost_lines(
    action: str,
    impact: dict[str, Any],
    assumptions: dict[str, float],
    *,
    emergency: bool,
    include_inspection: bool,
) -> list[dict[str, Any]]:
    """Each money line derives from exactly one physical quantity.

    Returns quantity, unit, unit price, formula, and ASSUMPTION label so the UI
    can trace every value.
    """
    lines: list[dict[str, Any]] = []
    if include_inspection:
        lines.append({
            "line": "inspection",
            "quantity": 1.0,
            "unit": "inspection",
            "unit_price": assumptions["inspection_cost"],
            "unit_price_unit": "CU/inspection",
            "assumption": "inspection_cost",
            "formula": "1 x inspection_cost",
            "label": "ASSUMPTION",
            "evidence": "Inspection is a fixed cost assumption.",
        })
    if action in ("monitor", "inspect", "repair_isolate"):
        key = "repair_cost_emergency" if emergency else "repair_cost_planned"
        lines.append({
            "line": "repair",
            "quantity": 1.0,
            "unit": "repair",
            "unit_price": assumptions[key],
            "unit_price_unit": "CU/repair",
            "assumption": key,
            "formula": f"1 x {key}",
            "label": "ASSUMPTION",
            "evidence": (
                "Repair cost placeholder. Monitor is charged an emergency "
                "repair at the end of the horizon; planned actions use planned "
                "repair cost."
            ),
        })
    lines.append({
        "line": "lost_water",
        "quantity": impact["water_lost_m3"],
        "unit": "m3",
        "unit_price": assumptions["water_price_per_m3"],
        "unit_price_unit": "CU/m3",
        "assumption": "water_price_per_m3",
        "formula": "water_lost_m3 x water_price_per_m3",
        "label": "SIMULATION",
    })
    lines.append({
        "line": "unserved_demand",
        "quantity": impact["unserved_m3"],
        "unit": "m3",
        "unit_price": assumptions["unserved_water_penalty_per_m3"],
        "unit_price_unit": "CU/m3",
        "assumption": "unserved_water_penalty_per_m3",
        "formula": "unserved_m3 x unserved_water_penalty_per_m3",
        "label": "SIMULATION",
    })
    lines.append({
        "line": "pump_energy",
        "quantity": impact["pump_energy_kwh"],
        "unit": "kWh",
        "unit_price": assumptions["electricity_price_per_kwh"],
        "unit_price_unit": "CU/kWh",
        "assumption": "electricity_price_per_kwh",
        "formula": "pump_energy_kwh x electricity_price_per_kwh",
        "label": "SIMULATION",
    })
    for line in lines:
        line["cost"] = round(line["quantity"] * line["unit_price"], 2)
    return lines


def total_cost(
    action: str,
    impacts: dict[str, dict[str, Any]],
    assumptions: dict[str, float],
) -> tuple[float, list[dict[str, Any]]]:
    """Expected cost for one action over leak-size variants (equal weights)."""
    totals = 0.0
    lines: list[dict[str, Any]] = []
    include_inspection = action == "inspect"
    repair = action == "repair_isolate"
    for variant, impact in impacts.items():
        variant_lines = cost_lines(
            action, impact, assumptions,
            emergency=(action == "monitor"),
            include_inspection=include_inspection,
        )
        _ = variant
        totals += sum(line["cost"] for line in variant_lines)
        lines.extend(variant_lines)
    return round(totals / max(1, len(impacts)), 2), lines


def monte_carlo(
    action: str,
    impacts_by_variant: dict[str, dict[str, Any]],
    assumptions_data: dict[str, Any],
    *,
    samples: int = 300,
    seed: int = 42,
) -> dict[str, Any]:
    """Triangular Monte Carlo over ASSUMPTION ranges and leak-size variants."""
    rng = np.random.default_rng(seed)
    cfg = assumptions_data["assumptions"]
    keys = [
        "water_price_per_m3", "unserved_water_penalty_per_m3",
        "electricity_price_per_kwh", "inspection_cost",
        "repair_cost_planned", "repair_cost_emergency",
    ]
    draws = {
        key: rng.triangular(
            float(cfg[key]["low"]), float(cfg[key]["value"]),
            float(cfg[key]["high"]), size=samples,
        )
        for key in keys
    }
    variants = list(impacts_by_variant)
    indexes = rng.integers(0, len(variants), size=samples)
    totals: list[float] = []
    for i in range(samples):
        impact = impacts_by_variant[variants[int(indexes[i])]]
        sample_assumptions = {key: float(draws[key][i]) for key in keys}
        lines = cost_lines(
            action, impact, sample_assumptions,
            emergency=(action == "monitor"),
            include_inspection=action == "inspect",
        )
        totals.append(sum(line["cost"] for line in lines))
    arr = np.array(totals)
    return {
        "samples": samples,
        "p10": round(float(np.percentile(arr, 10)), 2),
        "p50": round(float(np.percentile(arr, 50)), 2),
        "p90": round(float(np.percentile(arr, 90)), 2),
        "mean": round(float(arr.mean()), 2),
        "label": "CALCULATED",
        "formula": (
            "sum over Monte Carlo samples of (quantity x triangular-sampled "
            "unit price); P10/P50/P90 are percentiles of total cost"
        ),
        "conditional_on": {
            key: {
                "low": cfg[key]["low"], "mode": cfg[key]["value"],
                "high": cfg[key]["high"], "unit": cfg[key]["unit"],
                "label": "ASSUMPTION",
            }
            for key in keys
        },
        "note": "Conditional on the assumed triangular ranges; not field data.",
    }
