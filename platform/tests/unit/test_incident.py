"""D-05a rule-based incident candidates, validated against the existing contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from ug_intel.detect.cusum import detect
from ug_intel.detect.incident import incident_from


def validator() -> Draft202012Validator:
    root = Path(__file__).resolve().parents[3]
    schemas = [
        json.loads(p.read_text()) for p in (root / "contracts/v1").glob("*.schema.json")
    ]
    registry: Registry[Any] = Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas
    )
    return Draft202012Validator(
        next(s for s in schemas if s["title"] == "Incident"), registry=registry
    )


def candidate(spec: dict[str, tuple[str, str, int, str | None]]):
    readings = {
        s: [0.0] * start + [(-10.0 if direction == "low" else 10.0)] * (330 - start)
        for s, (_, direction, start, _) in spec.items()
    }
    quality = {
        s: [
            {"status": "suspect" if flag else "ok", "flags": [flag] if flag else []}
            for _ in range(330)
        ]
        for s, (_, _, _, flag) in spec.items()
    }
    result = detect(
        readings, {s: [0.0] * 330 for s in spec}, quality, {s: 0.5 for s in spec}
    )
    return incident_from(
        result,
        {s: kind for s, (kind, _, _, _) in spec.items()},
        quality,
        "run-1",
        {s: "z1" for s in spec},
    )


@pytest.mark.parametrize("flag", ["Q04", "Q08"])
def test_sensor_fault(flag: str) -> None:
    payload = candidate({"p": ("pressure", "low", 300, flag)})
    assert payload is not None
    validator().validate(payload)
    assert payload["hypothesis"] == "sensor_fault"
    assert payload["support"] == "weak" and payload["severity"] == "low"
    assert payload["rules_fired"] == ["R_D2_CUSUM", "R_QUALITY_FLAG"]
    assert payload["status"] == "open" and payload["false_alarm"] is False
    assert payload["closed_at"] is None and payload["first_detected_tick"] == 302
    assert payload["location"] == {"zone_id": "z1", "candidates": []}
    assert payload["contributing_sensors"] == ["p"]
    assert "probability" not in json.dumps(payload) and "confidence" not in json.dumps(
        payload
    )


@pytest.mark.parametrize(
    "count, support, severity", [(2, "moderate", "medium"), (3, "strong", "high")]
)
def test_leak_and_support(count: int, support: str, severity: str) -> None:
    spec = {"p": ("pressure", "low", 300, "Q08"), "f": ("flow", "high", 306, None)}
    if count == 3:
        spec["p2"] = ("pressure", "low", 303, None)
    payload = candidate(spec)
    assert payload is not None
    validator().validate(payload)
    assert (payload["hypothesis"], payload["support"], payload["severity"]) == (
        "leak",
        support,
        severity,
    )
    assert payload["rules_fired"] == ["R_D2_CUSUM", "R_MULTI_SENSOR"]
    assert payload["contributing_sensors"] == sorted(spec)
    assert payload == candidate(dict(reversed(list(spec.items()))))
    assert not {"probability", "confidence"} & payload.keys()


@pytest.mark.parametrize(
    "spec",
    [
        {"p": ("pressure", "low", 300, None)},
        {"p": ("pressure", "high", 300, None), "f": ("flow", "low", 300, None)},
        {"p": ("pressure", "low", 300, None), "f": ("flow", "high", 307, None)},
        {"p": ("pressure", "low", 300, "Q08"), "l": ("level", "low", 300, None)},
    ],
)
def test_other_cases_unknown(spec: dict) -> None:
    payload = candidate(spec)
    assert payload is not None
    validator().validate(payload)
    assert payload["hypothesis"] == "unknown" and payload["severity"] == "low"


def test_no_alarm_no_incident() -> None:
    result = detect(
        {"p": [0.0] * 576},
        {"p": [0.0] * 576},
        {"p": [{"status": "ok"}] * 576},
        {"p": 0.01},
    )
    assert (
        incident_from(result, {"p": "pressure"}, {"p": []}, "run-1", {"p": "z1"})
        is None
    )
