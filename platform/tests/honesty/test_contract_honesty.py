"""Contract payload honesty: truth exclusion, evidence labels, and stream source."""

import re
from copy import deepcopy

import pytest
from honesty_support import (
    ROOT,
    forbidden_property,
    labelled_numbers,
    load_json,
    money_violations,
    payload_violations,
    validator_for,
)
from ug_core import EvidenceLabel, StreamSource

CONTRACTS = ROOT / "contracts"
OPERATOR_CONTRACTS = ("telemetry-reading", "stream-envelope")
LABELLED_CONTRACTS = (*OPERATOR_CONTRACTS, "evidence-record", "incident")


def example_paths(names):
    return sorted(
        path
        for name in names
        for path in (CONTRACTS / "examples" / name).rglob("*.json")
    )


@pytest.mark.parametrize("name", OPERATOR_CONTRACTS)
def test_operator_schemas_exclude_truth(name):
    """P-01/P-02: all properties, definitions and locally referenced schemas are clean."""
    path = CONTRACTS / "v1" / f"{name}.schema.json"
    errors = payload_violations(load_json(path), str(path), schema=True, path=path)
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("path", example_paths(OPERATOR_CONTRACTS))
def test_operator_payloads_exclude_truth(path):
    """P-01/P-02: every JSON key, including dynamic maps, must exclude hidden truth."""
    errors = payload_violations(load_json(path), str(path))
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize(
    "key",
    [
        "channels",
        "events",
        "parameters",
        "target",
        "start_tick",
        "end_tick",
        "kind",
        "TRUTH_value",
        "faultTag",
        "fault_tag",
        "hidden_state",
        "injected_at",
        "ground_truth",
    ],
)
def test_payload_walker_bites(key):
    """P-01/P-02: synthetic schemas and nested dynamic payload keys expose leaks."""
    assert forbidden_property(key), f"P-01/P-02: denylist missed {key}"
    assert payload_violations({"readings": [{"dynamic": {key: 30.9}}]}), (
        f"P-01/P-02: payload walker missed readings[0].dynamic.{key}"
    )
    assert payload_violations(
        {"$defs": {"unused": {"properties": {key: {"type": "number"}}}}},
        schema=True,
    ), f"P-01/P-02: schema walker missed {key}"


def test_payload_walker_refs(tmp_path):
    """P-01/P-02: follow local cross-file refs, internal refs and ref cycles."""
    first = tmp_path / "first.json"
    other = tmp_path / "common.json"
    first.write_text('{"$ref": "common.json#/$defs/reading"}')
    other.write_text(
        '{"$defs":{"reading":{"properties":{"truth_value":{"type":"number"}},'
        '"$ref":"first.json"}}}'
    )
    errors = payload_violations(load_json(first), schema=True, path=first)
    assert errors and any("truth_value" in error for error in errors), (
        "P-01/P-02: cross-file/ref-cycle walker missed common.json truth_value"
    )
    assert not payload_violations({"timebase": {"value": 2}, "P01": 1}), (
        "P-01/P-02: shared fields or ordinary map keys falsely denied"
    )


def test_nine_labels_match_authority():
    """P-14: schema and Python labels must equal the nine labels in AGENTS.md."""
    line = next(
        line
        for line in (ROOT / "AGENTS.md").read_text().splitlines()
        if line.startswith("- Every displayed number carries an evidence label:")
    )
    authority = re.findall(r"\b[A-Z][A-Z_]+\b", line)
    labels = load_json(CONTRACTS / "v1/common.schema.json")["$defs"]["evidence_label"][
        "enum"
    ]
    assert len(authority) == len(labels) == 9, (
        "P-14: authority/schema needs nine labels"
    )
    assert set(labels) == set(authority), (
        "P-14: common.schema.json labels drifted from AGENTS.md"
    )
    assert {v.value for v in EvidenceLabel} == set(labels), (
        "P-14: ug_core labels drifted"
    )


@pytest.mark.parametrize("path", example_paths(LABELLED_CONTRACTS))
def test_displayed_numbers_have_labels(path):
    """P-14: numeric values, scores, quantiles and residuals inherit nearest labels."""
    labels = load_json(CONTRACTS / "v1/common.schema.json")["$defs"]["evidence_label"][
        "enum"
    ]
    errors = labelled_numbers(load_json(path), labels, str(path))
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("path", sorted((CONTRACTS / "examples").rglob("*.json")))
def test_money_labels(path):
    """P-14: money must never be described as simulator, sensor or model output."""
    errors = money_violations(load_json(path), str(path))
    assert not errors, "\n".join(errors)


def test_label_walker_controls():
    """P-14: nested quantiles/residuals need nearest valid labels, including overrides."""
    labels = {v.value for v in EvidenceLabel}
    for payload in (
        {"value": 1},
        {"score": 0},
        {"p10": 1},
        {"p50": 1},
        {"p90": 1},
        {"residuals": {"P01": 0}},
        {"residuals": [0, 1]},
        {"label": "MODEL", "child": {"label": "BAD", "value": 2}},
    ):
        assert labelled_numbers(payload, labels), f"P-14: scanner missed {payload}"
    assert not labelled_numbers(
        {"label": "CALCULATED", "uncertainty": {"p10": 0, "p90": 2}}, labels
    ), "P-14: valid inherited label was rejected"
    for unit in ("EGP", "EGP/day", "EGP/month", "EGP/year"):
        assert money_violations({"nested": [{"unit": unit, "label": "SIMULATION"}]}), (
            f"P-14: money scanner missed {unit}"
        )


def test_stream_source():
    """P-04: every example stream identifies its source and missing-source negatives do not."""
    sources = {"REPLAY", "SIMULATED", "LIVE"}
    assert {member.value for member in StreamSource} == sources, (
        "P-04: StreamSource drifted"
    )
    examples = example_paths(["stream-envelope"])
    assert examples, "P-04: no stream examples checked"
    for path in examples:
        assert load_json(path)["payload"].get("stream_source") in sources, (
            f"P-04: {path}: payload.stream_source missing or invalid"
        )
    rejected = sorted(
        (CONTRACTS / "invalid/stream-envelope").glob("*missing_stream_source*.json")
    )
    assert rejected, "P-04: missing_stream_source negative fixtures absent"
    for path in rejected:
        payload = load_json(path)
        assert "stream_source" not in payload["payload"], (
            f"P-04: {path}: not actually missing"
        )
        assert not validator_for("stream-envelope").is_valid(payload), (
            f"P-04: {path}: missing stream source was accepted"
        )


@pytest.mark.parametrize("mutation", ["type", "parameter", "schema_version"])
def test_unknown_scenario_fields_rejected(mutation):
    """P-18: unknown fault catalogue entries, parameters and schema versions are rejected."""
    path = CONTRACTS / "examples/scenario-config/every_fault_type.json"
    original = load_json(path)
    validator = validator_for("scenario-config")
    assert validator.is_valid(original), f"P-18: baseline scenario invalid: {path}"
    changed = deepcopy(original)
    if mutation == "type":
        changed["faults"][0]["type"] = "not_in_the_catalogue"
    elif mutation == "parameter":
        changed["faults"][0]["unknown_parameter"] = 1
    else:
        changed["schema_version"] = "2"
    assert not validator.is_valid(changed), f"P-18: {path}: unknown {mutation} accepted"
