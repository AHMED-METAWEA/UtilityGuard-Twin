"""The code's outputs validate against the contracts, and code and schemas agree on the rules.

Two directions:
- What the code produces must be valid (`Manifest.to_dict()`, `AssumptionSet.to_payload()`, the
  shared enums, timestamps). If someone renames a key, adds a field or adds a label on one side
  only, a test here fails.
- Where the code is LOOSER than the contract (it accepts something the contract rejects), the
  gap is written down as a strict expected failure with a reason. It is visible, it cannot grow
  silently, and the test fails the day the code is fixed, so the entry has to be removed.

Payload shapes that no code produces yet (scenario-config, stream-envelope, incident, a full
evidence record with resolved inputs and provenance) are listed in `NOT_PRODUCED_YET` and are
covered by the example files only.
"""

from __future__ import annotations

import copy
import json
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from contract_support import ROOT, files, is_valid, load_json, load_schemas
from ug_core import (
    Evidenced,
    EvidenceLabel,
    Manifest,
    StreamSource,
    TelemetrySeries,
    Timebase,
)
from ug_core.assumptions import SCHEMA_VERSION as ASSUMPTION_SCHEMA_VERSION
from ug_core.assumptions import load_assumptions
from ug_core.manifest import MANIFEST_SCHEMA_VERSION
from ug_core.telemetry import TELEMETRY_LABELS

SCHEMAS = load_schemas()
COMMON = SCHEMAS["common"]["$defs"]

# Payloads that no code in `ug_core` produces yet. They exist as contract and examples only.
NOT_PRODUCED_YET = {
    "scenario-config": "no scenario type yet (Spec milestone M1); only used as Manifest config",
    "stream-envelope": "the stream builder arrives with Spec milestone M2",
    "incident": "the incident manager arrives with Spec milestone M3",
}


def scenario_examples() -> list[Path]:
    return [p for p in files("examples") if p.parent.name == "scenario-config"]


# --------------------------------------------------------------------------- shared vocabulary


def test_evidence_labels_in_code_equal_the_schema() -> None:
    assert {label.value for label in EvidenceLabel} == set(
        COMMON["evidence_label"]["enum"]
    )


def test_telemetry_labels_in_code_equal_the_schema() -> None:
    assert {label.value for label in TELEMETRY_LABELS} == set(
        COMMON["telemetry_label"]["enum"]
    )


def test_stream_sources_in_code_equal_the_schema() -> None:
    assert [source.value for source in StreamSource] == COMMON["stream_source"]["enum"]


def test_contract_version_constants_equal_the_schema_constant() -> None:
    version = COMMON["schema_version"]["const"]
    assert MANIFEST_SCHEMA_VERSION == version
    assert ASSUMPTION_SCHEMA_VERSION == version


def test_timestamps_the_timebase_writes_match_the_contract_pattern() -> None:
    pattern = re.compile(COMMON["utc_timestamp"]["pattern"])
    timebase = Timebase(datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC), 300, 50)
    assert pattern.fullmatch(timebase.to_dict()["start"])
    assert all(pattern.fullmatch(timebase.iso_at(tick)) for tick in (0, 1, 49))


# --------------------------------------------------------------------------- run manifest


def make_manifest(config: dict[str, Any], **changes: Any) -> Manifest:
    kwargs: dict[str, Any] = {
        "config": config,
        "seed": config["seed"],
        "versions": {
            "network_version": config["network_version"],
            "contract_version": "1",
        },
        "libraries": {"numpy": "2.4.6", "wntr": "1.5.0"},
        "git_commit": "a04c946",
        "unordered": ("faults",),
    }
    kwargs.update(changes)
    return Manifest(**kwargs)


@pytest.mark.parametrize("path", scenario_examples(), ids=lambda p: p.stem)
def test_manifest_to_dict_validates_for_every_scenario_example(path: Path) -> None:
    manifest = make_manifest(load_json(path))
    assert is_valid("run-manifest", manifest.to_dict())
    with_outputs = manifest.with_output_hashes(
        {"truth": "0" * 64, "telemetry": "f" * 64}
    )
    assert is_valid("run-manifest", with_outputs.to_dict())
    assert is_valid(
        "run-manifest", make_manifest(load_json(path), git_commit=None).to_dict()
    )


def test_manifest_to_dict_has_exactly_the_keys_of_the_schema() -> None:
    payload = make_manifest(load_json(scenario_examples()[0])).to_dict()
    assert set(payload) == set(SCHEMAS["run-manifest"]["properties"])
    assert set(SCHEMAS["run-manifest"]["required"]) == set(
        SCHEMAS["run-manifest"]["properties"]
    )


def test_manifest_payload_survives_a_json_round_trip() -> None:
    payload = make_manifest(load_json(scenario_examples()[0])).to_dict()
    assert is_valid("run-manifest", json.loads(json.dumps(payload, allow_nan=False)))


def test_manifest_to_dict_cannot_be_used_to_smuggle_a_field() -> None:
    payload = make_manifest(load_json(scenario_examples()[0])).to_dict()
    payload["truth"] = {}
    assert not is_valid("run-manifest", payload)


# --------------------------------------------------------------------------- assumption set


def test_shipped_assumptions_file_produces_a_valid_payload() -> None:
    payload = load_assumptions(ROOT / "assumptions" / "v1.yaml").to_payload()
    assert is_valid("assumption-set", payload)
    assert payload["schema_version"] == COMMON["schema_version"]["const"]


def test_assumption_payload_has_exactly_the_keys_of_the_schema() -> None:
    schema = SCHEMAS["assumption-set"]
    payload = load_assumptions(ROOT / "assumptions" / "v1.yaml").to_payload()
    assert set(payload) == set(schema["properties"]) == set(schema["required"])
    entry_schema = schema["$defs"]["assumption"]
    entry = next(iter(payload["assumptions"].values()))
    assert (
        set(entry) == set(entry_schema["properties"]) == set(entry_schema["required"])
    )
    distribution = entry_schema["properties"]["distribution"]
    assert set(entry["distribution"]) == set(distribution["properties"])


def test_a_verified_assumption_the_loader_accepts_gives_a_valid_payload() -> None:
    from ug_core.assumptions import parse_assumptions

    data = load_assumptions(ROOT / "assumptions" / "v1.yaml").to_dict()
    data["assumptions"]["inspection_cost"].update(
        verified=True, source_note="ACUD tariff letter 2026-03, table 2"
    )
    assert is_valid("assumption-set", parse_assumptions(data).to_payload())


def derived_set_dict() -> dict[str, Any]:
    """A set with a parent and a verified entry: the paths the shipped set does not exercise."""
    data = load_assumptions(ROOT / "assumptions" / "v1.yaml").to_dict()
    data.update(
        set_id="v2_draft", parent="v1", note="Derived set used by the conformance test."
    )
    data["assumptions"]["electricity_price"].update(
        verified=True, source_note="ACUD tariff letter 2026-03, table 2"
    )
    return data


def test_a_derived_assumption_set_gives_a_valid_payload_with_exactly_the_schema_keys() -> (
    None
):
    from ug_core.assumptions import parse_assumptions

    payload = parse_assumptions(derived_set_dict()).to_payload()
    assert payload["parent"] == "v1"
    assert is_valid("assumption-set", payload)
    assert set(payload) == set(SCHEMAS["assumption-set"]["properties"])
    entry = payload["assumptions"]["electricity_price"]
    assert entry["verified"] is True
    assert set(entry) == set(
        SCHEMAS["assumption-set"]["$defs"]["assumption"]["properties"]
    )
    assert not is_valid("assumption-set", {**payload, "parent_id": payload["parent"]})


# --------------------------------------------------------------------------- telemetry


def reading_rows(series: TelemetrySeries, unit: str) -> list[dict[str, Any]]:
    """Rows in the shape of `telemetry-reading`. The series carries no unit, so the test supplies
    one (a gap, see `GAPS`)."""
    rows = []
    for sensor_id, values in series.readings.items():
        for tick, value in enumerate(values):
            rows.append(
                {
                    "schema_version": "1",
                    "tick": tick,
                    "sensor_id": sensor_id,
                    "value": value,
                    "unit": unit,
                    "label": str(series.label),
                    "delivered_at": series.timebase.iso_at(tick),
                }
            )
    return rows


@pytest.mark.parametrize("label", sorted(label.value for label in TELEMETRY_LABELS))
def test_telemetry_series_rows_validate_and_a_gap_is_null_never_zero(
    label: str,
) -> None:
    timebase = Timebase(datetime(2026, 1, 1, tzinfo=UTC), 300, 4)
    series = TelemetrySeries(
        timebase,
        {"P05": [31.2, None, 30.8, 30.5], "F02": [10.0, 10.5, None, None]},
        label=EvidenceLabel(label),
    )
    rows = reading_rows(series, "m")
    assert rows and all(is_valid("telemetry-reading", row) for row in rows)
    assert [r["value"] for r in rows if r["sensor_id"] == "P05"][1] is None


def test_labels_a_telemetry_series_rejects_are_rejected_by_the_contract_too() -> None:
    timebase = Timebase(datetime(2026, 1, 1, tzinfo=UTC), 300, 2)
    for label in EvidenceLabel:
        row = {
            "schema_version": "1",
            "tick": 0,
            "sensor_id": "P05",
            "value": 1.0,
            "unit": "m",
            "label": label.value,
        }
        try:
            TelemetrySeries(timebase, {"P05": [1.0, 2.0]}, label=label)
            code_accepts = True
        except ValueError:
            code_accepts = False
        assert code_accepts == is_valid("telemetry-reading", row), label


# --------------------------------------------------------------------------- evidence differential

LABELS = sorted(label.value for label in EvidenceLabel)


def evidence_candidate(
    value: Any, label: str, formula: str | None, inputs: tuple[str, ...], **fields: Any
) -> dict[str, Any]:
    """The payload implied by the ORIGINAL parameters, built without the object. The object has
    no provenance and keeps its inputs as ids, so a provenance and one resolved input per id are
    filled in. This is the oracle: it must not depend on what the constructor made of the input."""
    candidate: dict[str, Any] = {
        "schema_version": "1",
        "evidence_id": "ev_probe_1",
        "value": value,
        "unit": "m",
        "label": label,
        "formula": formula,
        "inputs": [
            {
                "name": f"in{i}",
                "value": 1.0,
                "unit": "m3",
                "label": "SIMULATION",
                "ref": ref,
            }
            for i, ref in enumerate(inputs)
        ],
        "provenance": {"run_id": "run_0001"},
    }
    candidate.update(fields)
    if label == "INSUFFICIENT_EVIDENCE":
        candidate["reason"] = "the system declines a number here"
    return candidate


def evidence_payload(evidenced: Evidenced[Any]) -> dict[str, Any]:
    """The payload of a constructed object (its own fields), same filling as the candidate."""
    return evidence_candidate(
        evidenced.value,
        str(evidenced.label),
        evidenced.formula,
        evidenced.inputs,
        evidence_id=evidenced.evidence_id,
        unit=evidenced.unit,
    )


def construct(
    value: Any, label: str, formula: str | None, inputs: tuple[str, ...], **fields: Any
) -> Evidenced[Any] | None:
    """The object, or None when the code refuses the combination."""
    kwargs: dict[str, Any] = {"evidence_id": "ev_probe_1", "unit": "m"}
    kwargs.update(fields)
    try:
        return Evidenced(
            value, EvidenceLabel(label), formula=formula, inputs=inputs, **kwargs
        )
    except ValueError:
        return None


@pytest.mark.parametrize("label", LABELS)
@pytest.mark.parametrize("value", [None, 1.5, "text", True])
@pytest.mark.parametrize("formula", [None, "a * b"])
@pytest.mark.parametrize("inputs", [(), ("ev_in_1",)])
def test_evidence_rules_agree_between_code_and_contract(
    label: str, value: Any, formula: str | None, inputs: tuple[str, ...]
) -> None:
    """Label, value, formula and inputs: the code accepts exactly the combinations the schema
    accepts. The oracle is built from the original parameters, so a constructor that quietly
    repairs the input (a missing value turned into 0.0) shows up as a disagreement."""
    schema_accepts = is_valid(
        "evidence-record", evidence_candidate(value, label, formula, inputs)
    )
    evidenced = construct(value, label, formula, inputs)
    assert (evidenced is not None) == schema_accepts, (label, value, formula, inputs)
    if evidenced is not None:
        # What the object holds is what was given, and it serialises to a valid payload.
        assert evidenced.value == value and type(evidenced.value) is type(value)
        assert is_valid("evidence-record", evidence_payload(evidenced))


# --------------------------------------------------------------------------- generated inputs and gaps
#
# Instead of a hand-made list of inputs, each code type is fed a few thousand generated inputs
# (fixed seed, so the run is reproducible): right and wrong types, empty and blank strings,
# boundary lengths, other currencies, repeated and empty collections. For each input the code
# either refuses it (fine), or builds an object whose payload must validate. A payload that does
# not validate is a GAP, described by its SIGNATURE: (schema, top-level field, schema keyword).
#
# - A signature that is not listed below fails the suite: a new looseness cannot appear silently.
# - A listed signature that no generated input produces any more fails too: close the gap in the
#   code, then delete the entry.
# - What the object stores must equal what it was given (nothing repaired on the way in).
# Card T-A1-002c closed every gap but one: Manifest.config is generic by design.

SAMPLES = 1200
Signature = tuple[str, str, str]


def signatures(schema: str, payload: dict[str, Any]) -> set[Signature]:
    """What is wrong with a payload, by field and keyword (empty when it is valid)."""
    from contract_support import validator_for

    found: set[Signature] = set()
    for error in validator_for(schema).iter_errors(payload):
        top = str(error.absolute_path[0]) if error.absolute_path else "(root)"
        found.add((schema, top, str(error.validator)))
    return found


def pick(rng: random.Random, choices: list[Any]) -> Any:
    return choices[rng.randrange(len(choices))]


def sample_inputs(
    seed: int, domains: dict[str, list[Any]], base: dict[str, Any]
) -> list[dict[str, Any]]:
    """Half fully random inputs, half a valid base with one or two fields replaced (so deep
    paths are reached instead of being refused for an unrelated first field)."""
    rng = random.Random(seed)
    samples = []
    for index in range(SAMPLES):
        if index % 2 == 0:
            samples.append({k: pick(rng, v) for k, v in domains.items()})
            continue
        sample = dict(base)
        for key in rng.sample(sorted(domains), rng.choice([1, 2])):
            sample[key] = pick(rng, domains[key])
        samples.append(sample)
    return samples


# --- Evidenced

EVIDENCE_DOMAINS: dict[str, list[Any]] = {
    "value": [None, 0, 1.5, -2.0, 1e308, True, False, "text", "", "1,000", 12345678901234567890],
    "label": [*LABELS, *[EvidenceLabel(label) for label in LABELS]],
    "evidence_id": ["ev_1", "", " ", "a b", "a" * 128, "a" * 129, "caf\u00e9", 17],
    "unit": [None, "m", "m3", "L/s", "EGP", "EGP/m3", "EGP/year", "egp", "USD", "", " ", "m 2", "m\u00b2", "x" * 25, 17],
    "formula": [None, "a", "", "  ", "a * b", 17],
    "inputs": [(), ("a",), ("a", "b"), ("a b",), ("",), ("a" * 129,), (17,)],
}  # fmt: skip


EVIDENCE_BASE: dict[str, Any] = {
    "value": 1.5,
    "label": "SIMULATION",
    "evidence_id": "ev_1",
    "unit": "m",
    "formula": None,
    "inputs": (),
}


def evidence_samples() -> list[dict[str, Any]]:
    return sample_inputs(20261025, EVIDENCE_DOMAINS, EVIDENCE_BASE)


def evidence_outcome(sample: dict[str, Any]) -> set[Signature] | None:
    """None when the code refuses the sample; otherwise the signatures of its payload."""
    try:
        obj = Evidenced(
            sample["value"],
            sample["label"],
            sample["evidence_id"],
            unit=sample["unit"],
            formula=sample["formula"],
            inputs=sample["inputs"],
        )
    except (ValueError, TypeError):
        return None
    # Nothing repaired on the way in.
    assert obj.unit == sample["unit"] and obj.formula == sample["formula"], sample
    assert (
        obj.inputs == tuple(sample["inputs"])
        and obj.evidence_id == sample["evidence_id"]
    ), sample
    assert obj.value == sample["value"] and type(obj.value) is type(sample["value"]), (
        sample
    )
    assert str(obj.label) == str(sample["label"]), sample
    return signatures("evidence-record", evidence_payload(obj))


# --- Manifest

MANIFEST_DOMAINS: dict[str, list[Any]] = {
    "config": ["scenario", "scenario", {}, {"x": 1}],
    "seed": [0, 5, -1, True, 1.5, "1", 2**40],
    "versions": [{"network_version": "n1"}, {"a b": "x"}, {"": "x"}, {}, {"k": "v" * 300}],
    "libraries": [{}, {"numpy": "2.4.6"}, {"num py": "1"}, {"numpy": ""}],
    "git_commit": [None, "a04c946", "abc123", "ABCDEF1", "xyz", "", "a" * 41, "a" * 5],
    "unordered": [(), ("faults",), ("faults", "faults"), ("",), ("x",)],
    "output_hashes": [{}, {"truth": "0" * 64}, {"truth": "x"}, {"a b": "0" * 64}, {"t": "G" * 64}],
    "schema_version": ["1", "2", ""],
}  # fmt: skip


def manifest_samples() -> list[dict[str, Any]]:
    scenario = load_json(scenario_examples()[0])
    base = {
        "config": scenario,
        "seed": 5,
        "versions": {"network_version": "n1"},
        "libraries": {"numpy": "2.4.6"},
        "git_commit": "a04c946",
        "unordered": ("faults",),
        "output_hashes": {},
        "schema_version": "1",
    }
    samples = sample_inputs(20261026, MANIFEST_DOMAINS, base)
    for sample in samples:
        if sample["config"] == "scenario":
            sample["config"] = scenario
    return samples


def manifest_outcome(sample: dict[str, Any]) -> set[Signature] | None:
    try:
        manifest = Manifest(**sample)
    except (ValueError, TypeError):
        return None
    payload = manifest.to_dict()
    assert (
        payload["seed"] == sample["seed"]
        and payload["git_commit"] == sample["git_commit"]
    ), sample
    assert payload["unordered"] == list(sample["unordered"]), sample
    assert payload["output_hashes"] == sample["output_hashes"], sample
    return signatures("run-manifest", payload)


# --- TelemetrySeries

TELEMETRY_DOMAINS: dict[str, list[Any]] = {
    "sensor_id": ["P05", "F02", "bad id", "", "s" * 128, "s" * 129, 17, "caf\u00e9"],
    "value": [1.0, None, 0, -3.5, True, "x", float("nan"), float("inf"), 1e308],
    "label": [*TELEMETRY_LABELS, EvidenceLabel.SIMULATION, EvidenceLabel.MODEL, "SENSOR_SIM", "nope"],
}  # fmt: skip


def telemetry_samples() -> list[dict[str, Any]]:
    base = {"sensor_id": "P05", "value": 1.0, "label": "SENSOR_SIM"}
    return sample_inputs(20261027, TELEMETRY_DOMAINS, base)


def telemetry_outcome(sample: dict[str, Any]) -> set[Signature] | None:
    timebase = Timebase(datetime(2026, 1, 1, tzinfo=UTC), 60, 2)
    try:
        series = TelemetrySeries(
            timebase,
            {sample["sensor_id"]: [sample["value"], None]},
            label=sample["label"],
        )
    except (ValueError, TypeError):
        return None
    stored = series.readings[sample["sensor_id"]]
    if isinstance(sample["value"], bool | str):
        # A flag or text is not a reading: the schema would also refuse it, but the object stores
        # a float, so the payload looks valid. Report it as its own signature.
        return {("telemetry-reading", "value", "accepted a bool or text reading")}
    assert stored[1] is None, sample  # a gap stays a gap
    assert stored[0] is None or stored[0] == sample["value"], sample
    found: set[Signature] = set()
    for row in reading_rows(series, "m"):
        found |= signatures("telemetry-reading", row)
    return found


# --- AssumptionSet (parsed, and built directly)

ASSUMPTION_DOMAINS: dict[str, list[Any]] = {
    "set_id": ["v1", "v2_draft", "a b", "", "a" * 128, "a" * 129],
    "parent": [None, "v0", "", "a b", "a" * 129, 3],
    "note": ["n", "", " ", 5],
    "unit": ["EGP/m3", "m", "m 2", "", " ", "x" * 25, "m\u00b2", 17],
    "source_note": ["Placeholder", "", " ", "ACUD tariff letter 2026-03", 3],
    "verified": [False, False, True, "yes"],
    "mode": [4000, 5, -1, True, "4000", 1e308],
    "name": ["inspection_cost", "inspection_cost", "Bad Name", "a" * 40],
}  # fmt: skip


def assumption_samples() -> list[dict[str, Any]]:
    base = {
        "set_id": "v1",
        "parent": None,
        "note": "n",
        "unit": "m",
        "source_note": "Placeholder",
        "verified": False,
        "mode": 5,
        "name": "inspection_cost",
    }
    return sample_inputs(20261028, ASSUMPTION_DOMAINS, base)


def assumption_outcome(sample: dict[str, Any]) -> set[Signature] | None:
    from ug_core.assumptions import parse_assumptions

    data = load_assumptions(ROOT / "assumptions" / "v1.yaml").to_dict()
    data.update(set_id=sample["set_id"], parent=sample["parent"], note=sample["note"])
    entry = data["assumptions"].pop("inspection_cost")
    entry.update(
        unit=sample["unit"],
        source_note=sample["source_note"],
        verified=sample["verified"],
    )
    entry["distribution"] = {
        "type": "triangular",
        "min": -10,
        "mode": sample["mode"],
        "max": 1e308,
    }
    data["assumptions"][sample["name"]] = entry
    try:
        payload = parse_assumptions(data).to_payload()
    except (ValueError, TypeError):
        return None
    assert (
        payload["set_id"] == sample["set_id"] and payload["parent"] == sample["parent"]
    ), sample
    return signatures("assumption-set", payload)


def direct_assumption_set_outcome() -> set[Signature]:
    """Built without the loader. An empty or malformed set is refused by the dataclass now; if a
    future change lets it through, its payload is judged by the schema like any other."""
    from ug_core.assumptions import AssumptionSet

    try:
        payload = AssumptionSet("v1", None, "note", {}).to_payload()
    except ValueError:
        return set()
    return signatures("assumption-set", payload)


# --- the gaps (signature -> why the code is looser, or why it is by design)

BY_DESIGN = (
    "by design: Manifest.config is generic; the contract narrows it to a scenario"
)
GAPS: dict[Signature, str] = {
    ("run-manifest", "config", "required"): BY_DESIGN,
    ("run-manifest", "config", "additionalProperties"): BY_DESIGN,
}

OUTCOMES = {
    "Evidenced": (evidence_samples, evidence_outcome, "evidence-record"),
    "Manifest": (manifest_samples, manifest_outcome, "run-manifest"),
    "TelemetrySeries": (telemetry_samples, telemetry_outcome, "telemetry-reading"),
    "AssumptionSet": (assumption_samples, assumption_outcome, "assumption-set"),
}


def observed(kind: str) -> tuple[set[Signature], int, int]:
    samples, outcome, _ = OUTCOMES[kind]
    seen: set[Signature] = set()
    refused = accepted = 0
    for sample in samples():
        result = outcome(sample)
        if result is None:
            refused += 1
            continue
        accepted += 1
        seen |= result
    if kind == "AssumptionSet":
        seen |= direct_assumption_set_outcome()
    return seen, refused, accepted


OBSERVED = {kind: observed(kind) for kind in OUTCOMES}


@pytest.mark.parametrize("kind", sorted(OUTCOMES))
def test_the_generated_inputs_exercise_both_refusal_and_acceptance(kind: str) -> None:
    _, refused, accepted = OBSERVED[kind]
    assert refused > 100 and accepted > 100, (kind, refused, accepted)


@pytest.mark.parametrize("kind", sorted(OUTCOMES))
def test_no_unlisted_gap_between_the_code_and_the_contract(kind: str) -> None:
    """Every way the code can build a payload the contract rejects is listed in GAPS."""
    seen, _, _ = OBSERVED[kind]
    unlisted = sorted(sig for sig in seen if sig not in GAPS)
    assert unlisted == [], (
        f"{kind}: code accepts input the contract rejects: {unlisted}"
    )


@pytest.mark.parametrize("kind", sorted(OUTCOMES))
def test_no_listed_gap_is_stale(kind: str) -> None:
    """A listed gap that no generated input produces any more has been closed: delete it."""
    schema = OUTCOMES[kind][2]
    seen, _, _ = OBSERVED[kind]
    stale = sorted(sig for sig in GAPS if sig[0] == schema and sig not in seen)
    assert stale == [], f"{kind}: closed gaps still listed: {stale}"


def test_every_gap_belongs_to_a_checked_schema() -> None:
    assert {sig[0] for sig in GAPS} <= {schema for _, _, schema in OUTCOMES.values()}


# --------------------------------------------------------------------------- coverage of the list


def test_every_contract_is_either_checked_against_code_or_listed_as_not_produced() -> (
    None
):
    checked = {"run-manifest", "assumption-set", "telemetry-reading", "evidence-record"}
    names = {
        p.name.removesuffix(".schema.json")
        for p in (ROOT / "contracts" / "v1").glob("*.json")
    }
    assert checked | set(NOT_PRODUCED_YET) == names - {"common"}


def test_the_test_helpers_do_not_mutate_the_examples() -> None:
    before = copy.deepcopy(load_json(scenario_examples()[0]))
    make_manifest(load_json(scenario_examples()[0])).to_dict()
    assert load_json(scenario_examples()[0]) == before
