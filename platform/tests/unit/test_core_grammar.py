"""The code refuses what the contracts refuse (card T-A1-002c): identifiers, units, money,
commit and hash formats, versions, repeated names, empty sets. Each rule is tested with the
inputs that used to pass, and with the nearest inputs that must still pass."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from ug_core import (
    Evidenced,
    EvidenceLabel,
    Manifest,
    TelemetrySeries,
    Timebase,
    grammar,
)
from ug_core.assumptions import AssumptionSet, load_assumptions, parse_assumptions

ROOT = Path(__file__).resolve().parents[3]
COMMON = json.loads((ROOT / "contracts/v1/common.schema.json").read_text())["$defs"]
EVIDENCE = json.loads((ROOT / "contracts/v1/evidence-record.schema.json").read_text())
SCENARIO = json.loads(
    (ROOT / "contracts/examples/scenario-config/leak_gradual_medium.json").read_text()
)
L = EvidenceLabel


def evidenced(**changes: Any) -> Evidenced[Any]:
    fields: dict[str, Any] = {
        "value": 1.5,
        "label": L.SIMULATION,
        "evidence_id": "ev_1",
        "unit": "m",
    }
    fields.update(changes)
    return Evidenced(**fields)


def manifest(**changes: Any) -> Manifest:
    fields: dict[str, Any] = {
        "config": SCENARIO,
        "seed": 5,
        "versions": {"network_version": "n1"},
        "libraries": {"numpy": "2.4.6"},
        "git_commit": "a04c946",
        "unordered": ("faults",),
    }
    fields.update(changes)
    return Manifest(**fields)


# ----------------------------------------------------------------- the grammars are the contract's


def test_grammar_patterns_equal_the_contract_patterns() -> None:
    assert grammar.IDENTIFIER_PATTERN == COMMON["identifier"]["pattern"]
    assert grammar.UNIT_PATTERN == COMMON["unit"]["pattern"]
    assert grammar.SHA256_PATTERN == COMMON["sha256"]["pattern"]
    run_manifest = json.loads(
        (ROOT / "contracts/v1/run-manifest.schema.json").read_text()
    )
    commit = [
        o["pattern"]
        for o in run_manifest["properties"]["git_commit"]["oneOf"]
        if "pattern" in o
    ]
    assert commit == [grammar.GIT_COMMIT_PATTERN]
    money = COMMON["money_consistency"]["allOf"]
    assert (
        grammar.MONEY_LOOKING_PATTERN == money[0]["if"]["properties"]["unit"]["pattern"]
    )
    assert (
        grammar.CANONICAL_MONEY_PATTERN
        == money[0]["then"]["properties"]["unit"]["pattern"]
    )
    assert money[1]["if"]["properties"]["unit"]["pattern"] == "^EGP"
    assert set(money[1]["then"]["properties"]["label"]["enum"]) == {
        label.value for label in L if label.value not in grammar.MONEY_FORBIDDEN_LABELS
    }
    assert EVIDENCE["properties"]["inputs"]["items"]["$ref"] == "#/$defs/input"


@pytest.mark.parametrize(
    "text", ["ev_1\n", "ev_1 ", " ev_1", "ev 1", "", "-a", "a" * 129, "café", "a\u0000"]
)
def test_a_token_with_a_trailing_newline_or_space_is_refused(text: str) -> None:
    """Python's `$` accepts a trailing newline; the code uses a full match, as a JSON Schema
    validator on another platform would."""
    assert grammar.is_identifier(text) is False


# ----------------------------------------------------------------- Evidenced


@pytest.mark.parametrize(
    "bad", ["has a space", "e" * 129, "", "ev\n", "café", 17, None]
)
def test_evidence_ids_are_identifier_tokens(bad: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        evidenced(evidence_id=bad)
    with pytest.raises((ValueError, TypeError)):
        evidenced(label=L.CALCULATED, formula="a", inputs=(bad,))
    assert evidenced(evidence_id="e" * 128).evidence_id == "e" * 128


@pytest.mark.parametrize("bad", ["m 2", "m²", "x" * 25, "", " ", "m\n", 17, "µS/cm"])
def test_units_are_one_ascii_token(bad: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        evidenced(unit=bad)


@pytest.mark.parametrize(
    "good", [None, "m", "m3", "L/s", "kWh", "cm2", "m3/h", "%", "1", "x" * 24]
)
def test_ordinary_units_and_no_unit_pass(good: str | None) -> None:
    assert evidenced(unit=good).unit == good


@pytest.mark.parametrize("bad", ["", "  ", 17, ["a"]])
def test_a_formula_is_absent_or_a_non_blank_text(bad: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        evidenced(formula=bad)
    assert evidenced(formula=None).formula is None
    assert evidenced(formula="a * b").formula == "a * b"


@pytest.mark.parametrize(
    "unit",
    [
        "EGP",
        "EGP/year",
        "EGP/month",
        "EGP/day",
        "EGP/m3",
        "EGP/kWh",
        "EGP/MWh",
        "EGP/kW",
        "EGP/h",
    ],
)
@pytest.mark.parametrize(
    "label", [L.SIMULATION, L.MODEL, L.SENSOR_SIM, L.PUBLIC_GEOMETRY]
)
def test_money_is_never_simulator_model_sensor_or_geometry_output(
    unit: str, label: L
) -> None:
    with pytest.raises(ValueError, match="money"):
        evidenced(unit=unit, label=label, value=8.0)


@pytest.mark.parametrize("unit", ["EGP", "EGP/year", "EGP/m3"])
@pytest.mark.parametrize("label", [L.ASSUMPTION, L.OBSERVED, L.BENCHMARK])
def test_money_can_be_an_assumption_or_an_observation(unit: str, label: L) -> None:
    assert evidenced(unit=unit, label=label, value=8.0).unit == unit


def test_a_calculated_cost_needs_its_formula_and_inputs_like_any_calculation() -> None:
    cost = evidenced(
        unit="EGP",
        label=L.CALCULATED,
        value=11520.0,
        formula="a * b",
        inputs=("a", "b"),
    )
    assert cost.value == 11520.0
    with pytest.raises(ValueError):
        evidenced(unit="EGP", label=L.CALCULATED, value=1.0)


@pytest.mark.parametrize("value", ["1,000", "1000", True, False])
def test_a_money_value_is_a_number(value: Any) -> None:
    with pytest.raises(ValueError, match="number"):
        evidenced(unit="EGP", label=L.ASSUMPTION, value=value)


@pytest.mark.parametrize(
    "unit",
    ["egp", "USD", "EUR", "GBP", "SAR", "AED", "JPY", "CNY", "INR", "KWD", "QAR", "CHF", "LE", "L.E.", "E.G.P.",
     "pound", "dollar", "euro", "riyal", "dirham", "EGP/Year", "Egp/m3", "EGP/yr", "EGPm3", "USD/m3"],
)  # fmt: skip
def test_other_currencies_and_other_spellings_are_refused(unit: str) -> None:
    with pytest.raises(ValueError, match="EGP"):
        evidenced(unit=unit, label=L.ASSUMPTION, value=8.0)


def test_a_declined_money_value_is_still_representable() -> None:
    declined = Evidenced(None, L.INSUFFICIENT_EVIDENCE, "ev_cost_1", unit="EGP")
    assert declined.value is None


def test_negative_money_is_representable() -> None:
    loss = evidenced(
        unit="EGP",
        label=L.CALCULATED,
        value=-2500.5,
        formula="a - b",
        inputs=("a", "b"),
    )
    assert loss.value == -2500.5


# ----------------------------------------------------------------- Manifest


@pytest.mark.parametrize(
    "bad", ["not-a-commit", "ABCDEF1", "abc12", "a" * 41, "", "abc123\n", " abc123", 5]
)
def test_git_commit_is_6_to_40_lower_case_hex_or_none(bad: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        manifest(git_commit=bad)
    for good in (None, "a04c946", "abcdef", "a" * 40):
        assert manifest(git_commit=good).git_commit == good


@pytest.mark.parametrize("bad", ["2", "", "1.0", 1])
def test_only_contract_version_1_is_supported(bad: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        manifest(schema_version=bad)
    assert manifest(schema_version="1").schema_version == "1"


@pytest.mark.parametrize("field", ["versions", "libraries"])
@pytest.mark.parametrize("key", ["a b", "", "k\n", "café", "k" * 129])
def test_version_and_library_names_are_identifier_tokens(field: str, key: str) -> None:
    with pytest.raises((ValueError, TypeError)):
        manifest(**{field: {key: "1"}})
    assert manifest(**{field: {"ok_name-1.2": "1"}})


@pytest.mark.parametrize("name", ["tru th", "", "k\n"])
def test_output_hash_names_are_tokens(name: str) -> None:
    with pytest.raises((ValueError, TypeError)):
        manifest(output_hashes={name: "0" * 64})


@pytest.mark.parametrize(
    "digest", ["not-sha", "", "0" * 63, "0" * 65, "G" * 64, "A" * 64, ("0" * 64) + "\n"]
)
def test_output_hashes_are_lower_case_sha256(digest: str) -> None:
    with pytest.raises((ValueError, TypeError)):
        manifest(output_hashes={"truth": digest})
    assert (
        manifest(output_hashes={"truth": "a" * 64}).output_hashes["truth"] == "a" * 64
    )


@pytest.mark.parametrize(
    "unordered", [("faults", "faults"), ("",), (" ",), ("faults", ""), ("a", "b", "a")]
)
def test_unordered_names_are_unique_and_non_empty(unordered: tuple[str, ...]) -> None:
    with pytest.raises((ValueError, TypeError)):
        manifest(unordered=unordered)
    assert manifest(unordered=("faults", "other")).unordered == ("faults", "other")


def test_with_output_hashes_applies_the_same_rules() -> None:
    base = manifest()
    with pytest.raises((ValueError, TypeError)):
        base.with_output_hashes({"truth": "short"})
    assert (
        base.with_output_hashes({"truth": "b" * 64}).output_hashes["truth"] == "b" * 64
    )


# ----------------------------------------------------------------- TelemetrySeries


@pytest.mark.parametrize(
    "sensor_id", ["bad id", "", "s" * 129, "café", "P05\n", 17, None]
)
def test_sensor_ids_are_identifier_tokens(sensor_id: Any) -> None:
    timebase = Timebase(datetime(2026, 1, 1, tzinfo=UTC), 60, 1)
    with pytest.raises((ValueError, TypeError)):
        TelemetrySeries(timebase, {sensor_id: [1.0]})
    assert (
        TelemetrySeries(timebase, {"P05": [1.0], "R_P06": [None]}).missing_count(
            "R_P06"
        )
        == 1
    )


# ----------------------------------------------------------------- AssumptionSet


def shipped() -> dict[str, Any]:
    return load_assumptions(ROOT / "assumptions" / "v1.yaml").to_dict()


@pytest.mark.parametrize("unit", ["m 2", "", " ", "x" * 25, "m²", 17])
def test_assumption_units_are_one_ascii_token(unit: Any) -> None:
    data = shipped()
    data["assumptions"]["inspection_cost"]["unit"] = unit
    with pytest.raises(ValueError):
        parse_assumptions(data)


@pytest.mark.parametrize("field", ["set_id", "parent"])
@pytest.mark.parametrize("bad", ["a" * 129, "a b", "", "v1\n"])
def test_set_ids_and_parents_are_identifier_tokens(field: str, bad: str) -> None:
    data = shipped()
    data[field] = bad
    with pytest.raises(ValueError):
        parse_assumptions(data)


def test_a_directly_built_set_cannot_be_empty_or_malformed() -> None:
    entries = load_assumptions(ROOT / "assumptions" / "v1.yaml").assumptions
    with pytest.raises(ValueError):
        AssumptionSet("v1", None, "note", {})
    with pytest.raises(ValueError):
        AssumptionSet("bad id", None, "note", dict(entries))
    with pytest.raises(ValueError):
        AssumptionSet("v1", "bad id", "note", dict(entries))
    with pytest.raises(ValueError):
        AssumptionSet("v1", None, " ", dict(entries))
    assert AssumptionSet("v1", None, "note", dict(entries)).set_id == "v1"


def test_the_shipped_assumptions_still_load() -> None:
    assert len(load_assumptions(ROOT / "assumptions" / "v1.yaml").assumptions) == 13
