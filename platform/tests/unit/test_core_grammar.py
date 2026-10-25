"""The code refuses what the contracts refuse (card T-A1-002c): identifiers, units, money,
commit and hash formats, versions, repeated names, empty sets. Each rule is tested with the
inputs that used to pass, and with the nearest inputs that must still pass."""

from __future__ import annotations

import json
from dataclasses import replace
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
from ug_core.assumptions import (
    Assumption,
    AssumptionSet,
    Triangular,
    load_assumptions,
    parse_assumptions,
)
from ug_core.canonical import sha256_hex

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


# The contract's recogniser lists common codes; the code catches the rest (review of T-A1-002c):
# every ISO 4217 code, a currency word, and spellings that break the letters apart or add a
# metric prefix. Each of these used to pass as a plain unit.
DISGUISED_CURRENCIES = [
    "E-G-P/m3", "E..G..P", "e-g-p", "EG2P", "kLE/m3", "MLE", "kEGP", "MEGP", "CAD", "cad/m3",
    "m3/CAD", "CAD*h", "AUD", "ZAR/kWh", "XOF", "JOD", "C-A-D", "L-E", "mUSD", "dinar",
    "Dinar/m3", "rupee", "mdollar", "lira", "yuan", "shilling/kWh", "peso", "franc", "naira",
]  # fmt: skip


@pytest.mark.parametrize("unit", DISGUISED_CURRENCIES)
@pytest.mark.parametrize(
    "label", [L.SIMULATION, L.MODEL, L.SENSOR_SIM, L.PUBLIC_GEOMETRY, L.ASSUMPTION]
)
def test_a_disguised_or_unlisted_currency_is_refused_under_every_label(
    unit: str, label: L
) -> None:
    with pytest.raises(ValueError, match="EGP"):
        evidenced(unit=unit, label=label, value=8.0)


def test_every_iso_4217_code_is_recognised_as_a_currency() -> None:
    assert len(grammar.CURRENCY_CODES) >= 150
    assert {"EGP", "CAD", "AUD", "ZAR", "XOF", "JOD", "MAD"} <= set(
        grammar.CURRENCY_CODES
    )
    for code in grammar.CURRENCY_CODES:
        for spelled in (code, code.lower(), f"{code}/m3", f"k{code}"):
            assert grammar.looks_like_money(spelled), spelled
            if spelled not in ("EGP", "EGP/m3"):
                with pytest.raises(ValueError, match="EGP"):
                    evidenced(unit=spelled, label=L.ASSUMPTION, value=1.0)


ORDINARY_UNITS = [
    "m", "m2", "m3", "m3/s", "m3/h", "m3/day", "L/s", "L/min", "l/h", "bar", "mbar", "kPa", "MPa",
    "Pa", "psi", "mg/L", "ug/L", "g/L", "NTU", "pH", "degC", "K", "%", "pct", "ppm", "ppb", "kW",
    "MW", "kWh", "MWh", "kWh/m3", "kVA", "kvar", "MVA", "kV", "V", "A", "mA", "Hz", "h", "min",
    "s", "day", "month", "year", "kg", "g", "t", "km", "mm", "cm", "ha", "m/s", "kg/m3", "W/m2",
    "1/s", "uS/cm", "mS/cm", "mgd", "gpm", "cfs", "cms", "MGD", "mmHg", "kgf/cm2", "N.m", "kg.m2",
    "m3/h/m", "kg/ha/day", "m^3", "m-1", "rpm", "BTU", "kcal", "J", "kJ/kg", "tonne", "tons/day",
    "count", "1", "unitless", "ratio", "fraction", "events/year", "hours", "days", "sensors",
]  # fmt: skip


@pytest.mark.parametrize("unit", ORDINARY_UNITS)
def test_ordinary_physical_units_are_not_mistaken_for_currencies(unit: str) -> None:
    assert not grammar.looks_like_money(unit), unit
    assert evidenced(unit=unit, label=L.SIMULATION, value=2.0).unit == unit


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


def an_assumption(**changes: Any) -> Assumption:
    fields: dict[str, Any] = {
        "name": "x_cost",
        "unit": "EGP",
        "distribution": Triangular(1.0, 2.0, 3.0),
        "source_note": "Vendor quotation 2026-05, ref Q-1042",
        "verified": True,
    }
    fields.update(changes)
    return Assumption(**fields)


@pytest.mark.parametrize(
    "bad", [True, False, float("nan"), float("inf"), "1", None, 2**53 + 1]
)
def test_a_triangular_distribution_takes_finite_non_boolean_numbers(bad: Any) -> None:
    for slot in ("min", "mode", "max"):
        numbers_ = {"min": 1.0, "mode": 2.0, "max": 3.0, slot: bad}
        with pytest.raises((ValueError, TypeError)):
            Triangular(**numbers_)


def test_a_triangular_distribution_stores_floats() -> None:
    dist = Triangular(1, 2, 3)
    assert [type(v) for v in (dist.min, dist.mode, dist.max)] == [float] * 3


@pytest.mark.parametrize("note", ["", "   ", None, 7])
def test_an_assumption_needs_a_note_when_built_directly(note: Any) -> None:
    with pytest.raises(ValueError):
        an_assumption(source_note=note, verified=False)


@pytest.mark.parametrize("verified", [1, 0, "true", None])
def test_verified_is_a_boolean_when_built_directly(verified: Any) -> None:
    with pytest.raises(ValueError):
        an_assumption(verified=verified)


@pytest.mark.parametrize(
    "note",
    ["short", "TBD: ask the vendor", "no source yet, guess", "placeholder value"],
)
def test_a_verified_assumption_must_name_a_source_when_built_directly(
    note: str,
) -> None:
    with pytest.raises(ValueError, match="source"):
        an_assumption(source_note=note, verified=True)
    assert an_assumption(source_note=note, verified=False).verified is False


def test_replace_cannot_smuggle_a_bad_value_past_the_checks() -> None:
    good = an_assumption()
    with pytest.raises(ValueError):
        replace(good, source_note="")
    with pytest.raises(ValueError):
        replace(good, source_note="TBD")
    with pytest.raises(ValueError):
        replace(good, unit="m 2")
    with pytest.raises(ValueError):
        replace(good, distribution="triangular")


@pytest.mark.parametrize("name", ["", "X", "1x", "bad\x00", "a b", "x\n", "café", 5])
def test_assumption_names_follow_the_contract_when_built_directly(name: Any) -> None:
    with pytest.raises(ValueError):
        an_assumption(name=name)
    with pytest.raises(ValueError):
        AssumptionSet("v1", None, "note", {name: an_assumption()})


def test_a_set_key_is_the_name_of_its_assumption() -> None:
    with pytest.raises(ValueError, match="name"):
        AssumptionSet("v1", None, "note", {"other_name": an_assumption()})
    with pytest.raises(ValueError):
        AssumptionSet("v1", None, "note", {"x_cost": {"unit": "EGP"}})


def test_the_assumption_name_pattern_is_the_contracts() -> None:
    schema = json.loads((ROOT / "contracts/v1/assumption-set.schema.json").read_text())
    assert (
        grammar.ASSUMPTION_NAME_PATTERN
        == schema["properties"]["assumptions"]["propertyNames"]["pattern"]
    )


def test_an_evidence_id_fits_the_identifier_grammar_for_any_valid_set() -> None:
    short = load_assumptions(ROOT / "assumptions" / "v1.yaml")
    assert short.evidence_id("inspection_cost") == f"as_inspection_cost@{short.set_id}"
    longest = replace(short, set_id="v" * 128)
    ids = {name: longest.evidence_id(name) for name in longest.assumptions}
    assert len(set(ids.values())) == len(ids)
    for name, evidence_id in ids.items():
        assert grammar.is_identifier(evidence_id), evidence_id
        assert evidence_id == longest.evidence_id(name)  # deterministic
        assert Evidenced(1.0, L.ASSUMPTION, evidence_id, unit="EGP").evidence_id == (
            evidence_id
        )


def test_a_shortened_evidence_id_ends_with_a_digest_of_the_whole() -> None:
    longest = replace(
        load_assumptions(ROOT / "assumptions" / "v1.yaml"), set_id="v" * 128
    )
    for name in longest.assumptions:
        natural = f"as_{name}@{longest.set_id}"
        evidence_id = longest.evidence_id(name)
        assert len(evidence_id) == 128
        assert evidence_id.startswith(f"as_{name}@vvvv")
        assert evidence_id.endswith("-" + sha256_hex(natural)[:20])


def test_two_long_sets_that_differ_late_get_different_evidence_ids() -> None:
    base = load_assumptions(ROOT / "assumptions" / "v1.yaml")
    one = replace(base, set_id="v" * 127 + "1")
    two = replace(base, set_id="v" * 127 + "2")
    assert one.evidence_id("inspection_cost") != two.evidence_id("inspection_cost")


def test_the_shipped_assumptions_still_load() -> None:
    assert len(load_assumptions(ROOT / "assumptions" / "v1.yaml").assumptions) == 13
