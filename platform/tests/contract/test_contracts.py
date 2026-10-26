"""Contracts v1: every schema is sound and closed, examples validate, invalid files are rejected
for the reason they are named after, and the Honesty Rules are visible in the schemas."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from contract_support import (
    ID_BASE,
    ROOT,
    SCHEMA_DIR,
    SUFFIX,
    files,
    load_json,
    load_schemas,
    parse_json,
    schema_names,
    validator_for,
)
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SCHEMAS = load_schemas()
NINE_LABELS = {
    "OBSERVED",
    "BENCHMARK",
    "PUBLIC_GEOMETRY",
    "SIMULATION",
    "SENSOR_SIM",
    "MODEL",
    "ASSUMPTION",
    "CALCULATED",
    "INSUFFICIENT_EVIDENCE",
}


def walk(
    node: Any, path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], Any]]:
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, (*path, str(index)))


def property_names(schema: Any) -> set[str]:
    """Every name declared under a `properties` map, and every name in a `required` list."""
    names: set[str] = set()
    for path, node in walk(schema):
        if path and path[-1] == "properties" and isinstance(node, dict):
            names |= set(node)
        if path and path[-1] == "required" and isinstance(node, list):
            names |= {item for item in node if isinstance(item, str)}
    return names


# --------------------------------------------------------------------------- the schemas


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_schema_is_valid_draft_2020_12_with_a_matching_id(name: str) -> None:
    schema = SCHEMAS[name]
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == f"{ID_BASE}{name}{SUFFIX}"
    assert schema["title"] and schema["description"]


@pytest.mark.parametrize("name", schema_names())
def test_every_payload_requires_the_contract_version(name: str) -> None:
    schema = SCHEMAS[name]
    assert "schema_version" in schema["required"]
    assert schema["properties"]["schema_version"]["$ref"].endswith(
        "#/$defs/schema_version"
    )
    assert SCHEMAS["common"]["$defs"]["schema_version"] == {
        "const": "1",
        "description": SCHEMAS["common"]["$defs"]["schema_version"]["description"],
    }


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_no_object_is_open_by_omission(name: str) -> None:
    """Every declared object says explicitly whether extra keys are allowed (they are not)."""
    for path, node in walk(SCHEMAS[name]):
        if (
            isinstance(node, dict)
            and node.get("type") == "object"
            and "$ref" not in node
        ):
            where = "/".join(path) or "(root)"
            closed = (
                node.get("additionalProperties") is not None
                or node.get("unevaluatedProperties") is False
            )
            assert closed, (
                f"{name}: object at {where} neither closes nor types its extra keys"
            )
            if "properties" in node:
                assert (
                    node.get("additionalProperties") is False
                    or node.get("unevaluatedProperties") is False
                ), f"{name}: object at {where} with named properties must be closed"


TRUTH_NAME = re.compile(
    r"truth|fault_?tag|hidden|injected|ground_?truth", re.IGNORECASE
)


@pytest.mark.parametrize("name", ["telemetry-reading", "stream-envelope"])
def test_telemetry_and_stream_have_no_truth_or_fault_tag_field(name: str) -> None:
    offending = sorted(n for n in property_names(SCHEMAS[name]) if TRUTH_NAME.search(n))
    assert offending == []


def test_no_schema_declares_a_probability_or_a_percent_confidence() -> None:
    """Honesty Rules: no invented probabilities, no 'AI confidence' percentage."""
    pattern = re.compile(r"probab|confidence_?pct|percent_conf", re.IGNORECASE)
    allowed = {
        ("scenario-config", "probability")
    }  # the dropout fault: an input of the scenario
    for name, schema in SCHEMAS.items():
        for prop in property_names(schema):
            if pattern.search(prop):
                assert (name, prop) in allowed, f"{name} declares {prop!r}"


def test_label_lists_equal_the_honesty_rules() -> None:
    labels = set(SCHEMAS["common"]["$defs"]["evidence_label"]["enum"])
    assert labels == NINE_LABELS
    rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    match = re.search(r"evidence label: ([A-Z_, ]+)\.", rules)
    assert match, "label list not found in AGENTS.md"
    assert labels == {item.strip() for item in match.group(1).split(",")}
    spec = (ROOT / "docs" / "UtilityGuard_Master_Spec.md").read_text(encoding="utf-8")
    table = spec.split("## 2. Honesty rules", 1)[1].split("## 3.", 1)[0]
    in_spec = set(re.findall(r"^\| `([A-Z_]+)` \|", table, flags=re.MULTILINE))
    assert in_spec == labels  # the Spec table lists all nine since PR #6
    assert set(SCHEMAS["common"]["$defs"]["telemetry_label"]["enum"]) <= labels
    assert SCHEMAS["common"]["$defs"]["stream_source"]["enum"] == [
        "REPLAY",
        "SIMULATED",
        "LIVE",
    ]


def fault_types() -> set[str]:
    defs = SCHEMAS["scenario-config"]["$defs"]
    return {
        d["properties"]["type"]["const"] for name, d in defs.items() if name != "fault"
    }


def test_fault_catalogue_matches_the_spec_catalogue() -> None:
    """One family per fault of Master Spec 5.4, except demand change (not a fault) and compound
    (a list of faults). Every definition is one alternative of `fault`, and nothing else is."""
    defs = SCHEMAS["scenario-config"]["$defs"]
    alternatives = {
        entry["$ref"].removeprefix("#/$defs/") for entry in defs["fault"]["oneOf"]
    }
    assert alternatives == set(defs) - {"fault"}
    assert len(fault_types()) == 14
    assert len(alternatives) == 15  # the leak has a gradual and a sudden form


def test_json_loader_is_strict() -> None:
    with pytest.raises(ValueError):
        parse_json('{"a": NaN}')
    with pytest.raises(ValueError):
        parse_json('{"a": Infinity}')
    with pytest.raises(ValueError):
        parse_json('{"a": 1, "a": 2}')


# --------------------------------------------------------------------------- examples


def schema_of(path: Path) -> str:
    return path.parent.name


EXAMPLES = files("examples")
INVALID = files("invalid")


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_example_validates(path: Path) -> None:
    errors = list(validator_for(schema_of(path)).iter_errors(load_json(path)))
    assert errors == [], [e.message for e in errors]


def test_every_schema_has_examples_and_rejected_files() -> None:
    for name in schema_names():
        assert any(schema_of(p) == name for p in EXAMPLES), f"{name}: no valid example"
        assert any(schema_of(p) == name for p in INVALID), f"{name}: no invalid file"
    assert {schema_of(p) for p in EXAMPLES + INVALID} <= set(schema_names())


REQUIRED_REASONS = {
    "missing_schema_version",
    "extra_field",
    "truth_field_in_telemetry",
    "unknown_label",
    "unknown_fault_type",
    "cost_labelled_simulation",
    "missing_stream_source",
}


def test_the_named_rejection_reasons_all_exist() -> None:
    assert REQUIRED_REASONS <= {p.stem for p in INVALID}


# What each invalid file must be rejected for: the JSON Schema keyword, where, and what the message
# names. EVERY error must match, so a file cannot be rejected by accident for another reason.
Expect = tuple[set[str], str, str]  # (keywords, path, text the message must contain)
ADDITIONAL = {"additionalProperties"}
EXPECTED: dict[str, Expect] = {
    "assumption-set/extra_field": (
        ADDITIONAL,
        "assumptions/electricity_price",
        "price",
    ),
    "assumption-set/missing_schema_version": ({"required"}, "", "schema_version"),
    "assumption-set/missing_verified": (
        {"required"},
        "assumptions/electricity_price",
        "verified",
    ),
    "assumption-set/unknown_distribution_type": (
        {"const"},
        "assumptions/electricity_price/distribution/type",
        "",
    ),
    "assumption-set/verified_with_a_short_note": (
        {"minLength"},
        "assumptions/electricity_price/source_note",
        "",
    ),
    "evidence-record/calculated_without_formula": ({"type"}, "formula", ""),
    "evidence-record/calculated_without_inputs": ({"minItems"}, "inputs", ""),
    "evidence-record/cost_labelled_simulation": ({"enum"}, "label", "SIMULATION"),
    "evidence-record/extra_field": (ADDITIONAL, "", "confidence_pct"),
    "evidence-record/insufficient_evidence_with_value": ({"type"}, "value", ""),
    "evidence-record/insufficient_evidence_with_estimates": (
        {"not"},
        "uncertainty",
        "",
    ),
    "evidence-record/currency_in_a_simulation_unit": ({"pattern"}, "unit", ""),
    "evidence-record/insufficient_evidence_without_reason": (
        {"required"},
        "",
        "reason",
    ),
    "evidence-record/missing_schema_version": ({"required"}, "", "schema_version"),
    "evidence-record/money_labelled_model": ({"enum"}, "label", "MODEL"),
    "evidence-record/unknown_label": ({"enum"}, "label", "VERIFIED"),
    "evidence-record/value_missing_under_a_real_label": ({"not"}, "value", ""),
    "incident/closed_without_timestamp": ({"type"}, "closed_at", ""),
    "incident/missing_schema_version": ({"required"}, "", "schema_version"),
    "incident/model_score_without_label": ({"required"}, "model_score", "label"),
    "incident/open_with_closed_at": ({"type"}, "closed_at", ""),
    "incident/probability_field": (ADDITIONAL, "", "probability"),
    "incident/unknown_hypothesis": ({"enum"}, "hypothesis", "gremlins"),
    "incident/unknown_status": ({"enum"}, "status", "finished"),
    "run-manifest/bad_output_hash": ({"pattern"}, "output_hashes/truth", ""),
    "run-manifest/config_is_not_a_scenario": ({"required"}, "config", "faults"),
    "run-manifest/extra_field": (ADDITIONAL, "", "truth"),
    "run-manifest/missing_schema_version": ({"required"}, "", "schema_version"),
    "scenario-config/cross_domain_input_not_defined_in_v1": (
        {"maxItems"},
        "cross_domain_inputs",
        "",
    ),
    "scenario-config/extra_field": (ADDITIONAL, "", "region"),
    "scenario-config/fault_missing_parameter": ({"oneOf"}, "faults/1", ""),
    "scenario-config/fault_with_foreign_parameter": ({"oneOf"}, "faults/1", ""),
    "scenario-config/gradual_leak_without_ramp": ({"oneOf"}, "faults/0", ""),
    "scenario-config/missing_schema_version": ({"required"}, "", "schema_version"),
    "scenario-config/non_positive_duration": (
        {"exclusiveMinimum"},
        "duration_hours",
        "",
    ),
    "scenario-config/schema_version_wrong": ({"const"}, "schema_version", ""),
    "scenario-config/sudden_leak_with_ramp": ({"oneOf"}, "faults/0", ""),
    "scenario-config/unknown_fault_type": ({"oneOf"}, "faults/0", "meteor_strike"),
    "stream-envelope/detector_without_label": (
        {"required"},
        "payload/detectors/d2",
        "label",
    ),
    "stream-envelope/fault_tag_in_tick": (ADDITIONAL, "payload", "fault_tag_hidden"),
    "stream-envelope/frame_type_without_a_shape_in_v1": (
        {"enum"},
        "type",
        "notification",
    ),
    "stream-envelope/missing_schema_version": ({"required"}, "", "schema_version"),
    "stream-envelope/missing_stream_source": ({"required"}, "payload", "stream_source"),
    "stream-envelope/network_confidence_out_of_range": (
        {"maximum"},
        "payload/network_confidence/value",
        "",
    ),
    "stream-envelope/reading_without_label": (
        {"required"},
        "payload/readings/0",
        "label",
    ),
    "stream-envelope/truth_field_in_reading": (
        ADDITIONAL,
        "payload/readings/0",
        "truth_value",
    ),
    "stream-envelope/unknown_stream_source": (
        {"enum"},
        "payload/stream_source",
        "REPLAYED",
    ),
    "telemetry-reading/money_in_a_sensor_reading": ({"pattern"}, "unit", ""),
    "telemetry-reading/currency_in_a_product_unit": ({"pattern"}, "unit", ""),
    "telemetry-reading/unit_that_is_not_physical": ({"pattern"}, "unit", ""),
    "stream-envelope/money_in_a_stream_reading": (
        {"pattern"},
        "payload/readings/0/unit",
        "",
    ),
    "stream-envelope/currency_in_a_stream_unit": (
        {"pattern"},
        "payload/readings/0/unit",
        "",
    ),
    "telemetry-reading/fault_tag_in_telemetry": (ADDITIONAL, "", "fault_tag_hidden"),
    "telemetry-reading/label_simulation_not_allowed": ({"enum"}, "label", "SIMULATION"),
    "telemetry-reading/missing_schema_version": ({"required"}, "", "schema_version"),
    "telemetry-reading/missing_value_field": ({"required"}, "", "value"),
    "telemetry-reading/truth_field_in_telemetry": (ADDITIONAL, "", "truth_value"),
    "stream-envelope/truth_key_in_residuals": (
        {"not"},
        "payload/detectors/d2/residuals",
        "TRUTH_VALUE",
    ),
    "stream-envelope/probability_key_in_residuals": (
        {"not"},
        "payload/detectors/d2/residuals",
        "PROBABILITY",
    ),
    "stream-envelope/truth_key_as_detector_name": (
        {"not"},
        "payload/detectors",
        "fault_tag_hidden",
    ),
    "stream-envelope/network_confidence_without_formula_ref": (
        {"required"},
        "payload/network_confidence",
        "formula_ref",
    ),
    "stream-envelope/detector_without_version": (
        {"required"},
        "payload/detectors/d2",
        "version",
    ),
    "stream-envelope/quality_without_label": (
        {"required"},
        "payload/readings/0/quality",
        "label",
    ),
    "telemetry-reading/quality_without_label": ({"required"}, "quality", "label"),
    "telemetry-reading/quality_without_formula_ref": (
        {"required"},
        "quality",
        "formula_ref",
    ),
    "evidence-record/money_unit_wrong_spelling": ({"pattern"}, "unit", "egp"),
    "evidence-record/annual_amount_labelled_simulation": (
        {"enum"},
        "label",
        "SIMULATION",
    ),
    "evidence-record/input_labelled_insufficient_evidence": (
        {"enum"},
        "inputs/0/label",
        "INSUFFICIENT_EVIDENCE",
    ),
    "stream-envelope/lowercase_key_in_residuals": (
        {"pattern"},
        "payload/detectors/d2/residuals",
        "truth_value",
    ),
    "stream-envelope/detector_version_not_a_name_and_number": (
        {"pattern", "not"},
        "payload/detectors/d2/version",
        "fault_tag_hidden",
    ),
    "evidence-record/input_in_another_currency": ({"pattern"}, "inputs/0/unit", "USD"),
    "evidence-record/money_value_as_formatted_text": ({"type"}, "value", "1,000"),
    "evidence-record/unit_with_lookalike_letters": ({"anyOf"}, "unit", ""),
    "telemetry-reading/unknown_label": ({"enum"}, "label", "VERIFIED"),
}


# A `oneOf` error says "no alternative matched"; the cause is in its sub-errors. For each such
# file: the keyword and text that SOME alternative must report (the alternative of the right type).
ONEOF_CAUSE: dict[str, tuple[set[str], str]] = {
    "scenario-config/fault_missing_parameter": ({"required"}, "drift_per_hour"),
    "scenario-config/fault_with_foreign_parameter": (
        {"additionalProperties"},
        "final_area_cm2",
    ),
    "scenario-config/gradual_leak_without_ramp": ({"required"}, "ramp_hours"),
    "scenario-config/sudden_leak_with_ramp": ({"additionalProperties"}, "ramp_hours"),
}


# Records labelled as simulator output with a currency unit break two rules at once: the one named
# after the file, and the physical-unit rule (a currency is not a physical unit).
ALSO_NOT_A_PHYSICAL_UNIT = {
    "evidence-record/annual_amount_labelled_simulation",
    "evidence-record/cost_labelled_simulation",
    "evidence-record/money_labelled_model",
    "evidence-record/unit_with_lookalike_letters",
}


def error_path(error: ValidationError) -> str:
    return "/".join(str(part) for part in error.absolute_path)


def test_every_invalid_file_has_an_expectation_and_the_other_way_round() -> None:
    present = {f"{schema_of(p)}/{p.stem}" for p in INVALID}
    assert present == set(EXPECTED)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_invalid_file_is_rejected_for_the_reason_it_is_named_after(path: Path) -> None:
    keywords, where, text = EXPECTED[f"{schema_of(path)}/{path.stem}"]
    errors = list(validator_for(schema_of(path)).iter_errors(load_json(path)))
    assert errors, "the file is not rejected"
    key = f"{schema_of(path)}/{path.stem}"
    for error in errors:
        if (
            key in ALSO_NOT_A_PHYSICAL_UNIT
            and error.validator == "pattern"
            and error_path(error) == "unit"
        ):
            continue  # a simulator-labelled record must also carry a physical unit (round 1)
        assert error.validator in keywords, (error.validator, error.message)
        assert error_path(error) == where, (error_path(error), error.message)
        assert text in error.message, (text, error.message)
        if error.validator != "oneOf":
            continue
        context = error.context or []
        if key in ONEOF_CAUSE:
            cause_keywords, cause_text = ONEOF_CAUSE[key]
            assert any(
                c.validator in cause_keywords and cause_text in c.message
                for c in context
            )
        else:  # an unknown type: every alternative rejects it at its `type` constant
            alternatives = len(error.schema["oneOf"])
            rejected_at_type = {
                c.schema_path[0]
                for c in context
                if c.validator == "const" and list(c.absolute_path)[-1] == "type"
            }
            assert rejected_at_type == set(range(alternatives)), [
                c.message for c in context
            ]


# --------------------------------------------------------------------------- mutations of examples


def valid(name: str, instance: Any) -> bool:
    return not list(validator_for(name).iter_errors(instance))


def example(name: str, stem: str) -> Any:
    return copy.deepcopy(
        load_json(ROOT / "contracts" / "examples" / name / f"{stem}.json")
    )


def test_changing_any_one_required_field_to_missing_is_rejected() -> None:
    """For every payload and every required top-level field: removing it makes it invalid."""
    for path in EXAMPLES:
        name = schema_of(path)
        if name == "evidence-record" and path.stem == "insufficient_evidence":
            continue  # `reason` is required here; covered by its own invalid file
        for field in SCHEMAS[name]["required"]:
            instance = load_json(path)
            instance.pop(field)
            assert not valid(name, instance), (
                f"{name}/{path.stem} accepted without {field}"
            )


def test_money_rules_of_the_evidence_record() -> None:
    cost = example("evidence-record", "cost_24h")
    assert valid("evidence-record", cost)
    for label in ("SIMULATION", "MODEL", "SENSOR_SIM", "PUBLIC_GEOMETRY"):
        broken = copy.deepcopy(cost)
        broken["label"] = label
        assert not valid("evidence-record", broken), f"EGP amount accepted as {label}"
    as_cost = copy.deepcopy(cost)
    as_cost["kind"] = "cost"
    assert valid("evidence-record", as_cost)
    for label in ("ASSUMPTION", "OBSERVED", "SIMULATION"):
        broken = copy.deepcopy(as_cost)
        broken["label"] = label
        assert not valid("evidence-record", broken), f"cost accepted as {label}"
    # A price (a rate) is not an amount: an assumption input may carry the ASSUMPTION label.
    price = example("evidence-record", "assumption_input")
    price["unit"] = "EGP/m3"
    price["label"] = "ASSUMPTION"
    assert valid("evidence-record", price)


def test_a_negative_net_benefit_style_value_is_representable() -> None:
    cost = example("evidence-record", "cost_24h")
    cost["value"] = -2500.5
    assert valid("evidence-record", cost)


def test_a_missing_reading_is_null_never_zero() -> None:
    missing = example("telemetry-reading", "missing_reading")
    assert missing["value"] is None and valid("telemetry-reading", missing)
    missing["value"] = "n/a"
    assert not valid("telemetry-reading", missing)


def test_telemetry_label_set_is_closed() -> None:
    reading = example("telemetry-reading", "pressure_suspect")
    for label in ("SENSOR_SIM", "OBSERVED", "BENCHMARK"):
        reading["label"] = label
        assert valid("telemetry-reading", reading)
    for label in NINE_LABELS - {"SENSOR_SIM", "OBSERVED", "BENCHMARK"}:
        reading["label"] = label
        assert not valid("telemetry-reading", reading), label


def test_every_catalogue_fault_has_a_valid_form_and_a_missing_parameter_is_rejected() -> (
    None
):
    forms: dict[str, dict[str, Any]] = {
        "leak": {
            "location": "pipe:P1",
            "profile": "gradual",
            "ramp_hours": 4,
            "final_area_cm2": 2,
        },
        "burst": {"location": "pipe:P1", "final_area_cm2": 20},
        "background_leakage": {"zone_id": "res", "fraction": 0.05},
        "sensor_drift": {"sensor_id": "P05", "drift_per_hour": 0.3},
        "sensor_offset": {"sensor_id": "P05", "magnitude": 1.5},
        "sensor_stuck": {"sensor_id": "P05", "duration_hours": 3},
        "sensor_noise_growth": {"sensor_id": "P05", "factor": 3},
        "sensor_dropout": {"sensor_id": "P05", "duration_hours": 2, "probability": 0.3},
        "comms_outage": {"rtu_group": "RTU_1", "duration_hours": 2},
        "pump_outage": {"pump_id": "PU_1", "duration_hours": 4},
        "pump_degradation": {"pump_id": "PU_1", "rate_per_hour": 0.001},
        "valve_state": {"valve_id": "V1", "state": "closed"},
        "fire_flow": {"node": "node:J1", "flow_l_s": 30, "duration_hours": 2},
        "power_loss": {"station_id": "PS_1", "duration_hours": 3},
    }
    assert set(forms) == fault_types()
    base = example("scenario-config", "normal_week")
    for fault_type, parameters in forms.items():
        scenario = copy.deepcopy(base)
        scenario["faults"] = [{"type": fault_type, "start_hour": 5, **parameters}]
        assert valid("scenario-config", scenario), fault_type
        for missing in parameters:
            reduced = copy.deepcopy(scenario)
            reduced["faults"][0].pop(missing)
            assert not valid("scenario-config", reduced), (
                f"{fault_type} accepted without {missing}"
            )
        no_start = copy.deepcopy(scenario)
        no_start["faults"][0].pop("start_hour")
        assert not valid("scenario-config", no_start), fault_type
    sudden = copy.deepcopy(base)
    sudden["faults"] = [
        {
            "type": "leak",
            "start_hour": 5,
            "location": "pipe:P1",
            "profile": "sudden",
            "final_area_cm2": 2,
        }
    ]
    assert valid("scenario-config", sudden)
    sudden["faults"][0]["ramp_hours"] = 3
    assert not valid("scenario-config", sudden)
    sudden["faults"][0].pop("ramp_hours")
    sudden["faults"][0]["profile"] = "creeping"
    assert not valid("scenario-config", sudden)


# --------------------------------------------------------------------------- the Spec payloads


def spec_json_block(heading: str, after: str | None = None) -> Any:
    spec = (ROOT / "docs" / "UtilityGuard_Master_Spec.md").read_text(encoding="utf-8")
    section = spec.split(heading, 1)[1]
    if after:
        section = section.split(after, 1)[1]
    block = section.split("```json\n", 1)[1].split("```", 1)[0]
    return parse_json(block)


def test_spec_scenario_example_validates_unchanged() -> None:
    assert valid("scenario-config", spec_json_block("### 12.3 Scenario configuration"))


def test_spec_evidence_example_validates_once_it_carries_the_contract_version() -> None:
    record = spec_json_block("### 10.1 Evidence record")
    assert not valid("evidence-record", record)  # no schema_version in the Spec text
    assert valid("evidence-record", {"schema_version": "1", **record})


def test_spec_tick_example_validates_unchanged() -> None:
    """Master Spec 12.2 was updated to the stricter tick payload (labels, formula references,
    detector versions), so its example validates as written once wrapped in the envelope."""
    payload = spec_json_block("### 12.2 WebSocket", "Tick payload:")
    envelope = {
        "schema_version": "1",
        "type": "tick",
        "run_id": "run_0042",
        "seq": 8123,
        "payload": payload,
    }
    assert valid("stream-envelope", envelope)
    for field in (
        "label",
        "formula_ref",
    ):  # the Spec text and the schema cannot drift apart
        broken = copy.deepcopy(envelope)
        broken["payload"]["network_confidence"].pop(field)
        assert not valid("stream-envelope", broken), field
    broken = copy.deepcopy(envelope)
    broken["payload"]["detectors"]["d2"].pop("version")
    assert not valid("stream-envelope", broken)


def test_schema_files_are_listed_in_the_readme() -> None:
    readme = (ROOT / "contracts" / "README.md").read_text(encoding="utf-8")
    for name in schema_names():
        assert f"{name}{SUFFIX}" in readme, (
            f"contracts/README.md does not mention {name}"
        )
    assert SCHEMA_DIR.is_dir()


Checker = Callable[[], None]
