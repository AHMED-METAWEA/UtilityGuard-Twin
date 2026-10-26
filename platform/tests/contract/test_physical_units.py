"""A sensor reports a physical quantity (gate round 1, T-A1-013).

`telemetry-reading` and the stream envelope's readings accepted a reading such as
`{"value": 100, "unit": "EGP", "label": "SENSOR_SIM"}`: money labelled as sensor output. Their
`unit` is now `common.schema.json#/$defs/physical_unit`, a pattern built from the same vocabulary
as the code (`ug_core.grammar.PHYSICAL_UNIT_ATOMS`), so a currency cannot be spelled past it.
"""

from __future__ import annotations

import copy
import random
import re
from typing import Any

import pytest
from contract_support import ROOT, is_valid, load_json
from ug_core import grammar

COMMON = load_json(ROOT / "contracts/v1/common.schema.json")["$defs"]
READING = load_json(ROOT / "contracts/examples/telemetry-reading/pressure_suspect.json")
TICK = load_json(
    ROOT / "contracts/examples/stream-envelope/tick_replay_with_suspect_sensor.json"
)

GOOD_UNITS = [
    "m", "m2", "m3", "cm2", "m3/s", "m3/h", "L/s", "L/min", "bar", "mbar", "kPa", "MPa", "Pa",
    "psi", "mg/L", "ug/L", "NTU", "pH", "degC", "%", "pct", "ppm", "kW", "kWh", "MWh", "kWh/m3",
    "kVA", "kvar", "V", "A", "Hz", "uS/cm", "h", "min", "s", "day", "kg", "t", "ha", "m/s",
    "kg/m3", "1/s", "m^3", "m^-3", "m-1", "N.m", "kg.m2", "rpm", "count", "%/h", "mm/h", "percent", "fraction",
]  # fmt: skip
BAD_UNITS = [
    "EGP", "EGP/m3", "USD", "CAD", "CAD.m^-3", "AUD.kWh^-1", "C.A.D.m^-3", "E-G-P/m3", "kLE/m3",
    "E..G..P", "dinar", "furlong", "quatloo", "xyz/m3", "gallons", "unitless", "sensors",
    "m3/CAD", "m%", "m^", "1m", "2/s", "/s", "m//s", "-", "",
]  # fmt: skip


def reading(unit: str, **changes: Any) -> dict[str, Any]:
    out = copy.deepcopy(READING)
    out.update(unit=unit, **changes)
    return out


def tick(unit: str) -> dict[str, Any]:
    out = copy.deepcopy(TICK)
    out["payload"]["readings"][0]["unit"] = unit
    return out


def test_the_schema_pattern_is_the_code_s_vocabulary() -> None:
    physical = COMMON["physical_unit"]
    patterns = [part["pattern"] for part in physical["allOf"] if "pattern" in part]
    assert patterns == [grammar.PHYSICAL_UNIT_PATTERN]
    assert {"$ref": "#/$defs/unit"} in physical["allOf"]


@pytest.mark.parametrize("unit", GOOD_UNITS)
def test_a_physical_unit_is_accepted_in_every_reading(unit: str) -> None:
    assert grammar.is_physical_unit(unit)
    assert is_valid("telemetry-reading", reading(unit)), unit
    assert is_valid("stream-envelope", tick(unit)), unit


@pytest.mark.parametrize("unit", BAD_UNITS)
@pytest.mark.parametrize("label", ["SENSOR_SIM", "OBSERVED", "BENCHMARK"])
def test_money_and_unknown_units_are_refused_in_every_reading(
    unit: str, label: str
) -> None:
    assert not grammar.is_physical_unit(unit)
    assert not is_valid("telemetry-reading", reading(unit, label=label)), unit
    envelope = tick(unit)
    envelope["payload"]["readings"][0]["label"] = label
    assert not is_valid("stream-envelope", envelope), unit


def test_a_missing_reading_keeps_its_physical_unit() -> None:
    missing = load_json(
        ROOT / "contracts/examples/telemetry-reading/missing_reading.json"
    )
    assert missing["value"] is None and is_valid("telemetry-reading", missing)
    missing["unit"] = "EGP"
    assert not is_valid("telemetry-reading", missing)


def test_the_pattern_accepts_exactly_what_the_code_accepts() -> None:
    """Fuzz: strings made of vocabulary pieces and one-character edits of them."""
    rng = random.Random(20261026)
    pieces = [
        *grammar.PHYSICAL_UNIT_ATOMS,
        *grammar._PHYSICAL_PREFIXES,
        *"/*.%-^0123456789",
        "EGP", "CAD", "x", "e", "LE",
    ]  # fmt: skip
    pattern = re.compile(grammar.PHYSICAL_UNIT_PATTERN)
    seen_true = seen_false = 0
    for _ in range(40000):
        text = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 6)))
        if rng.random() < 0.3 and text:
            i = rng.randrange(len(text))
            text = text[:i] + rng.choice("aZ/.^-3% ") + text[i + 1 :]
        if len(text) > 24 or not grammar.is_unit(text):
            continue
        expected = grammar.is_physical_unit(text)
        assert (pattern.fullmatch(text) is not None) == expected, text
        seen_true += expected
        seen_false += not expected
    assert seen_true > 2000 and seen_false > 2000  # the fuzz covers both outcomes
