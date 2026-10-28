"""D-05a robust trends and labelled tank warning evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from ug_intel.trend import (
    evidence_for_time_to_threshold,
    theil_sen_slope,
    time_to_threshold,
    trend_anomaly,
)


def test_line_exact_robust_to_outlier_and_missing_time_positions() -> None:
    values: list[float | None] = [float(t) for t in range(12)]
    assert theil_sen_slope(values, 300) == 12.0
    values[5] = 10000.0
    values[2] = None
    assert theil_sen_slope(values, 300) == 12.0
    assert theil_sen_slope([1.0, None, 2.0, 3.0], 300) is None


def test_residual_slope_sigma_per_hour_and_strict_limit() -> None:
    values = [float(t) / 12 for t in range(30)]
    result = trend_anomaly(values, 0.5, 300)
    assert result.slope == 2.0 and result.flagged
    assert (
        result.label == "CALCULATED" and result.formula_ref == "trend.residual_slope.v1"
    )
    assert result == trend_anomaly(values, 0.5, 300)
    assert not trend_anomaly(values, 1.0, 300).flagged
    assert trend_anomaly([-v for v in values], 0.5, 300).flagged
    assert not trend_anomaly([None] * 24, 1.0, 300).flagged
    assert trend_anomaly([None] * 24, 1.0, 300).slope is None
    assert trend_anomaly([1000.0] * 6 + [0.0] * 24, 1.0, 300).slope == 0.0


def falling() -> list[float]:
    # Last level is 4 m, falling at .5 m/h.
    return [4.0 + (11 - t) * 0.5 for t in range(12)]


def test_time_to_threshold_and_unavailable_cases() -> None:
    assert time_to_threshold(falling(), 3600, 1.0) == 6.0
    assert time_to_threshold(list(reversed(falling())), 3600, 1.0) is None
    assert time_to_threshold([4.0] * 12, 3600, 1.0) is None
    assert time_to_threshold([4.0, 3.5, 3.0], 3600, 1.0) is None
    assert time_to_threshold([4.0, 3.0, 2.0, 0.5], 3600, 1.0) == 0.0
    assert time_to_threshold([*falling(), None], 3600, 1.0) is None


@pytest.mark.parametrize(
    "levels, label",
    [
        (falling(), "CALCULATED"),
        (list(reversed(falling())), "INSUFFICIENT_EVIDENCE"),
        ([None] * 12, "INSUFFICIENT_EVIDENCE"),
    ],
)
def test_evidence_contract(levels: list, label: str) -> None:
    root = Path(__file__).resolve().parents[3]
    schemas = [
        json.loads(p.read_text()) for p in (root / "contracts/v1").glob("*.schema.json")
    ]
    registry: Registry[Any] = Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas
    )
    validator = Draft202012Validator(
        next(s for s in schemas if s["title"] == "Evidence record"), registry=registry
    )
    payload = evidence_for_time_to_threshold(levels, 3600, 1.0, run_id="run-1")
    validator.validate(payload)
    assert payload["label"] == label and payload["unit"] == "h"
    assert payload["formula"] == "tank.time_to_threshold.v1"
    inputs = {i["name"]: i for i in payload["inputs"]}
    assert (
        inputs["threshold"]["label"] == "ASSUMPTION"
        and inputs["threshold"]["unit"] == "m"
    )
    if label == "CALCULATED":
        assert payload["value"] == 6.0
        assert inputs["level_now"]["label"] == "SENSOR_SIM"
        assert (
            inputs["slope"]["label"] == "CALCULATED"
            and inputs["slope"]["unit"] == "m/h"
        )
    else:
        assert payload["value"] is None and payload["reason"]


@pytest.mark.parametrize("step", [0, -1, float("nan"), float("inf")])
def test_invalid_step(step: float) -> None:
    with pytest.raises(ValueError):
        theil_sen_slope(falling(), step)


def test_invalid_parameters() -> None:
    with pytest.raises(ValueError):
        trend_anomaly(falling(), 0.0, 300)
    with pytest.raises(ValueError):
        time_to_threshold(falling(), 300, float("nan"))
    with pytest.raises(ValueError):
        theil_sen_slope([float("nan")] * 4, 300)
