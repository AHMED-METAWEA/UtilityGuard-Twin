"""Regression tests for holes found by review: values and keys that a closed shape alone does not
stop. Each test builds payloads that the contracts must reject and ones they must still accept."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from contract_support import ROOT, is_valid, load_json


def example(name: str, stem: str) -> Any:
    return copy.deepcopy(
        load_json(ROOT / "contracts" / "examples" / name / f"{stem}.json")
    )


def tick() -> Any:
    return example("stream-envelope", "tick_replay_with_suspect_sensor")


def evidence(**changes: Any) -> Any:
    record = example("evidence-record", "cost_24h")
    record.update(changes)
    return record


# --------------------------------------------------------------- operator-visible map keys


RESERVED_KEYS = [
    "truth_value",
    "fault_tag_hidden",
    "probability",
    "confidence_pct",
    "Truth",
    "hidden_state",
    "injected_fault",
    "ground_truth",
    "percent_conf",
    "P05_truth",
]


@pytest.mark.parametrize("key", RESERVED_KEYS)
def test_residual_names_cannot_carry_truth_or_probability_keys(key: str) -> None:
    frame = tick()
    frame["payload"]["detectors"]["d2"]["residuals"] = {key: 1.0}
    assert not is_valid("stream-envelope", frame)


@pytest.mark.parametrize("key", RESERVED_KEYS)
def test_detector_names_cannot_carry_truth_or_probability_keys(key: str) -> None:
    frame = tick()
    frame["payload"]["detectors"][key] = frame["payload"]["detectors"].pop("d2")
    assert not is_valid("stream-envelope", frame)


def test_ordinary_sensor_and_detector_names_still_pass() -> None:
    frame = tick()
    frame["payload"]["detectors"]["d3_pca"] = frame["payload"]["detectors"].pop("d2")
    frame["payload"]["detectors"]["d3_pca"]["residuals"] = {
        "P05": -8.1,
        "F02": 0.4,
        "R_P06": 1,
    }
    assert is_valid("stream-envelope", frame)


# --------------------------------------------------------------- money units


@pytest.mark.parametrize(
    "unit",
    [
        "egp",
        "EGP ",
        "L.E.",
        "LE",
        "USD",
        "$",
        "£",
        "EGP/Year",
        "egp/m3",
        "Egp",
        "pound",
    ],
)
def test_money_must_use_the_canonical_unit_spelling(unit: str) -> None:
    assert not is_valid(
        "evidence-record", evidence(unit=unit, label="MODEL", formula=None, inputs=[])
    )
    assert not is_valid("evidence-record", evidence(unit=unit))  # even when CALCULATED


@pytest.mark.parametrize("unit", ["EGP", "EGP/year", "EGP/month", "EGP/day"])
@pytest.mark.parametrize(
    "label", ["SIMULATION", "MODEL", "SENSOR_SIM", "PUBLIC_GEOMETRY"]
)
def test_money_amounts_are_never_simulator_model_or_sensor_output(
    unit: str, label: str
) -> None:
    assert not is_valid("evidence-record", evidence(unit=unit, label=label))
    assert is_valid(
        "evidence-record", evidence(unit=unit)
    )  # CALCULATED, with its formula


@pytest.mark.parametrize("unit", ["EGP/m3", "EGP/kWh"])
def test_prices_may_be_assumptions(unit: str) -> None:
    record = example("evidence-record", "assumption_input")
    record.update(unit=unit)
    assert is_valid("evidence-record", record)


@pytest.mark.parametrize(
    "unit", ["m", "m3", "L/s", "cm2", "kWh", "h", "fraction", "percent"]
)
def test_physical_units_are_not_mistaken_for_money(unit: str) -> None:
    record = example("evidence-record", "sensor_reading")
    record.update(unit=unit)
    assert is_valid("evidence-record", record)


# --------------------------------------------------------------- inputs and derivations


def test_an_input_cannot_declare_insufficient_evidence() -> None:
    record = evidence()
    record["inputs"][0]["label"] = "INSUFFICIENT_EVIDENCE"
    assert not is_valid("evidence-record", record)
    for label in (
        "OBSERVED",
        "BENCHMARK",
        "PUBLIC_GEOMETRY",
        "SIMULATION",
        "SENSOR_SIM",
        "MODEL",
        "ASSUMPTION",
        "CALCULATED",
    ):
        record["inputs"][0]["label"] = label
        assert is_valid("evidence-record", record), label
    record["inputs"][0]["label"] = "VERIFIED"
    assert not is_valid("evidence-record", record)


def test_quality_scores_carry_a_label_and_a_named_formula() -> None:
    reading = example("telemetry-reading", "pressure_suspect")
    assert reading["quality"]["label"] == "CALCULATED"
    for field in ("label", "formula_ref"):
        broken = copy.deepcopy(reading)
        broken["quality"].pop(field)
        assert not is_valid("telemetry-reading", broken), field
        frame = tick()
        frame["payload"]["readings"][0]["quality"].pop(field)
        assert not is_valid("stream-envelope", frame), field
    for label in ("SENSOR_SIM", "SIMULATION", "MODEL", "ASSUMPTION"):
        broken = copy.deepcopy(reading)
        broken["quality"]["label"] = label
        assert not is_valid("telemetry-reading", broken), label
    broken = copy.deepcopy(reading)
    broken["quality"]["formula_ref"] = "not a template id"
    assert not is_valid("telemetry-reading", broken)


def test_network_confidence_and_detectors_name_their_derivation_and_version() -> None:
    for path, field in (
        (("network_confidence",), "formula_ref"),
        (("detectors", "d2"), "version"),
    ):
        frame = tick()
        node = frame["payload"]
        for part in path:
            node = node[part]
        node.pop(field)
        assert not is_valid("stream-envelope", frame), field


# --------------------------------------------------------------- ranges and formats


def at(instance: Any, path: str, value: Any) -> Any:
    node = instance
    parts = path.split("/")
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    last = parts[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value
    return instance


RANGE_CASES: list[tuple[str, str, str, list[Any], list[Any]]] = [
    # (schema, example, path, rejected values, accepted values)
    (
        "telemetry-reading",
        "pressure_suspect",
        "quality/score",
        [-0.01, 1.01, 5, "0.5"],
        [0, 1, 0.5],
    ),
    ("telemetry-reading", "pressure_suspect", "tick", [-1, 1.5, "3", True], [0, 1000]),
    (
        "telemetry-reading",
        "pressure_suspect",
        "quality/status",
        ["OK", "good", ""],
        ["ok", "suspect", "bad"],
    ),
    (
        "telemetry-reading",
        "pressure_suspect",
        "quality/flags",
        [["q07"], ["Q7"], ["Q07", "Q07"]],
        [[], ["Q07", "Q01"]],
    ),
    (
        "stream-envelope",
        "tick_replay_with_suspect_sensor",
        "payload/network_confidence/value",
        [-0.01, 1.01],
        [0, 1, 0.91],
    ),
    (
        "stream-envelope",
        "tick_replay_with_suspect_sensor",
        "payload/speed",
        [0, -1, "60"],
        [0.5, 60],
    ),
    ("stream-envelope", "tick_replay_with_suspect_sensor", "seq", [-1, 1.5], [0, 8123]),
    (
        "stream-envelope",
        "tick_replay_with_suspect_sensor",
        "payload/detectors/d2/state",
        ["WATCH", "alarm", ""],
        ["normal", "watch", "alert"],
    ),
    ("scenario-config", "leak_gradual_medium", "seed", [-1, 1.5, "42"], [0, 42]),
    (
        "scenario-config",
        "leak_gradual_medium",
        "timestep_minutes",
        [0, -5, 2.5],
        [1, 5],
    ),
    (
        "scenario-config",
        "leak_gradual_medium",
        "duration_hours",
        [0, -1, "72"],
        [0.5, 72],
    ),
    (
        "scenario-config",
        "leak_gradual_medium",
        "demand/heatwave_multiplier",
        [0, -1, "1"],
        [0.5, 1.3],
    ),
    (
        "scenario-config",
        "leak_gradual_medium",
        "demand/zone_multipliers/gov",
        [0, -1, "1"],
        [0.5],
    ),
    (
        "scenario-config",
        "leak_gradual_medium",
        "demand/forecast_error/sigma_pct",
        [-1, "6"],
        [0, 6],
    ),
    (
        "scenario-config",
        "leak_gradual_medium",
        "faults/0/ramp_hours",
        [0, -1, "24"],
        [0.5, 24],
    ),
    (
        "scenario-config",
        "leak_gradual_medium",
        "faults/0/final_area_cm2",
        [0, -1, "6", True],
        [0.1, 6],
    ),
    (
        "scenario-config",
        "leak_gradual_medium",
        "faults/0/start_hour",
        [-1, "20", True],
        [0, 20.5],
    ),
    (
        "scenario-config",
        "leak_gradual_medium",
        "faults/0/location",
        ["P_0217", "node:P_0217", "pipe:", "pipe:a b"],
        ["pipe:P_0217"],
    ),
    (
        "scenario-config",
        "pump_outage_with_dropout",
        "faults/1/probability",
        [0, -0.1, 1.1, "0.4"],
        [0.01, 1],
    ),
    (
        "scenario-config",
        "pump_outage_with_dropout",
        "faults/3/node",
        ["J_0042", "pipe:J_0042"],
        ["node:J_0042"],
    ),
    (
        "scenario-config",
        "pump_outage_with_dropout",
        "faults/3/flow_l_s",
        [0, -3, "40"],
        [40],
    ),
    (
        "run-manifest",
        "leak_gradual_medium_run",
        "versions/network_version",
        [7, None, ["x"]],
        ["capital_f1_v1"],
    ),
    (
        "run-manifest",
        "leak_gradual_medium_run",
        "libraries/numpy",
        [2, None],
        ["2.4.6"],
    ),
    (
        "run-manifest",
        "leak_gradual_medium_run",
        "git_commit",
        ["", "XYZ", "abc", 123, "ABCDEF1"],
        [None, "a04c946"],
    ),
    (
        "run-manifest",
        "leak_gradual_medium_run",
        "output_hashes/truth",
        ["", "0" * 63, "0" * 65, "G" * 64, "A" * 64],
        ["a" * 64],
    ),
    (
        "run-manifest",
        "leak_gradual_medium_run",
        "unordered",
        [["faults", "faults"], [""], "faults"],
        [[], ["faults"]],
    ),
    (
        "evidence-record",
        "cost_24h",
        "uncertainty/p90",
        [None, "19000", [1]],
        [19000, 0],
    ),
    ("evidence-record", "cost_24h", "uncertainty/p10", [None, "7400"], [7400]),
    ("evidence-record", "cost_24h", "uncertainty/basis", ["", 3], ["300 draws"]),
    (
        "evidence-record",
        "cost_24h",
        "explanation_template",
        ["cost", "Cost.lost.v1", "cost.lost_water", "cost.lost_water.v", ""],
        ["cost.lost_water.v2"],
    ),
    ("evidence-record", "cost_24h", "provenance/seed", [-1, 1.5, "42"], [0, 42]),
    (
        "evidence-record",
        "cost_24h",
        "provenance/git_commit",
        ["", "xyz", 5, "abc"],
        ["abcdef1"],
    ),
    ("evidence-record", "cost_24h", "inputs/0/value", [None, [1], {}], [1, "x", True]),
    (
        "assumption-set",
        "placeholder_excerpt",
        "assumptions/water_production_cost/distribution/min",
        ["5", None],
        [5, -1.5],
    ),
    (
        "assumption-set",
        "placeholder_excerpt",
        "assumptions/water_production_cost/unit",
        ["", 3],
        ["EGP/m3"],
    ),
    ("assumption-set", "placeholder_excerpt", "parent", ["", "a b", 3], [None, "v0"]),
    ("incident", "leak_open", "first_detected_tick", [-1, 1.5, "171"], [0, 171]),
    ("incident", "leak_open", "location/candidates/0/score", ["0.9", None], [0.91, -2]),
    (
        "incident",
        "leak_open",
        "contributing_sensors",
        [["P05", "P05"], "P05", [""]],
        [[], ["P05"]],
    ),
    ("incident", "leak_open", "rules_fired", [["R1", "R1"], "R1"], [[]]),
    (
        "incident",
        "leak_open",
        "closed_at",
        ["2026-01-02", "2026-01-02T08:30:00+02:00"],
        [None],
    ),
]


@pytest.mark.parametrize(
    ("schema", "stem", "path", "bad", "good"),
    RANGE_CASES,
    ids=[f"{c[0]}:{c[2]}" for c in RANGE_CASES],
)
def test_values_outside_the_allowed_range_or_format_are_rejected(
    schema: str, stem: str, path: str, bad: list[Any], good: list[Any]
) -> None:
    for value in bad:
        assert not is_valid(schema, at(example(schema, stem), path, value)), (
            path,
            value,
        )
    for value in good:
        assert is_valid(schema, at(example(schema, stem), path, value)), (path, value)


@pytest.mark.parametrize(
    ("schema", "stem", "path"),
    [
        ("scenario-config", "leak_gradual_medium", "start"),
        ("telemetry-reading", "pressure_suspect", "delivered_at"),
        ("stream-envelope", "tick_replay_with_suspect_sensor", "payload/sim_time"),
        ("incident", "false_alarm_closed", "closed_at"),
    ],
)
@pytest.mark.parametrize(
    "stamp",
    [
        "2026-01-01 00:00:00",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:00+02:00",
        "2026-01-01T00:00:00.5Z",
        "2026-01-01T00:00Z",
        "2026-01-01",
        "tomorrow",
        "",
        20260101,
    ],
)
def test_timestamps_are_utc_whole_seconds(
    schema: str, stem: str, path: str, stamp: Any
) -> None:
    assert not is_valid(schema, at(example(schema, stem), path, stamp))


@pytest.mark.parametrize(
    ("schema", "stem", "path"),
    [
        ("telemetry-reading", "pressure_suspect", "sensor_id"),
        ("stream-envelope", "tick_replay_with_suspect_sensor", "run_id"),
        ("scenario-config", "leak_gradual_medium", "scenario_id"),
        ("scenario-config", "leak_gradual_medium", "faults/1/sensor_id"),
        ("evidence-record", "cost_24h", "evidence_id"),
        ("incident", "leak_open", "incident_id"),
        ("incident", "leak_open", "contributing_sensors/0"),
        ("assumption-set", "placeholder_excerpt", "set_id"),
    ],
)
@pytest.mark.parametrize(
    "name", ["", "has space", "-leading", "a" * 129, "tab\there", "ünï", "a/b", 5, None]
)
def test_identifiers_are_plain_tokens(
    schema: str, stem: str, path: str, name: Any
) -> None:
    assert not is_valid(schema, at(example(schema, stem), path, name))


# --------------------------------------------------------------- round 2: grammars, not blacklists

# Template ids are fixed and reviewed, so "confidence" (the network confidence index) is a normal word there.
TEMPLATE_WORDS = {"truth", "fault", "hidden", "ground", "inject"}
RESERVED_WORDS = [
    "truth",
    "fault",
    "hidden",
    "prob",
    "conf",
    "percent",
    "pct",
    "ground",
    "inject",
]


@pytest.mark.parametrize("word", RESERVED_WORDS)
def test_each_reserved_word_is_refused_on_its_own_in_residual_and_detector_names(
    word: str,
) -> None:
    frame = tick()
    frame["payload"]["detectors"]["d2"]["residuals"] = {f"P_{word.upper()}_1": 1.0}
    assert not is_valid("stream-envelope", frame), word
    frame = tick()
    frame["payload"]["detectors"][f"x_{word}_1"] = frame["payload"]["detectors"].pop(
        "d2"
    )
    assert not is_valid("stream-envelope", frame), word
    frame = tick()
    frame["payload"]["detectors"]["d2"]["version"] = f"x_{word}_v1"
    assert not is_valid("stream-envelope", frame), word
    if word in TEMPLATE_WORDS:
        reading = example("telemetry-reading", "pressure_suspect")
        reading["quality"]["formula_ref"] = f"quality.{word}.v1"
        assert not is_valid("telemetry-reading", reading), word


@pytest.mark.parametrize(
    "key",
    [
        "fault.tag",
        "fault-tag",
        "fault__tag",
        "FAULT_TAG",
        "Fault_Tag",
        "fault tag",
        "p05 ",
        "P-05",
        "p05",
        "ТRUTH",
    ],
)
def test_residual_names_are_plain_uppercase_sensor_tokens(key: str) -> None:
    frame = tick()
    frame["payload"]["detectors"]["d2"]["residuals"] = {key: 1.0}
    assert not is_valid("stream-envelope", frame), key


@pytest.mark.parametrize("key", ["P05", "F02", "T2", "SPE", "R_P06", "PU_01"])
def test_ordinary_sensor_tokens_pass(key: str) -> None:
    frame = tick()
    frame["payload"]["detectors"]["d2"]["residuals"] = {key: 1.0}
    assert is_valid("stream-envelope", frame), key


@pytest.mark.parametrize(
    "version", ["fault_tag_hidden:pipe:P123", "d2", "d2_vX", "D2_v1", "d2 v1", "d2_v1 "]
)
def test_detector_versions_are_name_underscore_v_number(version: str) -> None:
    frame = tick()
    frame["payload"]["detectors"]["d2"]["version"] = version
    assert not is_valid("stream-envelope", frame), version


@pytest.mark.parametrize(
    "ref",
    [
        "cost.lost_water.vX",
        "cost.lost_water.vA1",
        "cost.lost_water.v",
        "cost..v1",
        "Cost.v1",
        "cost.v01x",
    ],
)
def test_template_ids_end_in_a_numeric_version(ref: str) -> None:
    reading = example("telemetry-reading", "pressure_suspect")
    reading["quality"]["formula_ref"] = ref
    assert not is_valid("telemetry-reading", reading), ref
    record = evidence(explanation_template=ref)
    assert not is_valid("evidence-record", record), ref


CURRENCY_TOKENS = [
    "EGP", "USD", "EUR", "GBP", "SAR", "AED", "JPY", "CNY", "INR", "KWD", "QAR", "CHF",
    "LE", "L.E.", "E.G.P.", "LE.", "egp", "usd", "eur", "gbp", "sar", "aed", "jpy",
    "pound", "dollar", "euro", "riyal", "dirham",
]  # fmt: skip


@pytest.mark.parametrize("token", CURRENCY_TOKENS)
@pytest.mark.parametrize("suffix", ["", "/year", "/m3"])
@pytest.mark.parametrize("label", ["SIMULATION", "MODEL", "SENSOR_SIM"])
def test_every_recognised_currency_must_be_canonical_egp(
    token: str, suffix: str, label: str
) -> None:
    unit = token + suffix
    record = evidence(unit=unit, label=label, formula=None, inputs=[])
    assert not is_valid("evidence-record", record), unit


@pytest.mark.parametrize(
    "unit",
    [
        "ЕGP",
        "ＥＧＰ",
        "ج.م",
        "EGP​",
        "EGP/m3 ",
        " EGP",
        "E GP",
        "EGP/ year",
        "m²",
        "°C",
        "µS/cm",
    ],
)
def test_units_are_ascii_tokens_without_spaces(unit: str) -> None:
    for record in (
        evidence(unit=unit),
        evidence(unit=unit, label="SENSOR_SIM", formula=None, inputs=[]),
    ):
        assert not is_valid("evidence-record", record), repr(unit)
    reading = example("telemetry-reading", "pressure_suspect")
    reading["unit"] = unit
    assert not is_valid("telemetry-reading", reading), repr(unit)


@pytest.mark.parametrize(
    "unit",
    [
        "m",
        "m3",
        "L/s",
        "m3/h",
        "cm2",
        "kPa",
        "bar",
        "degC",
        "kWh",
        "fraction",
        "percent",
        "%",
        "1",
    ],
)
def test_ordinary_units_pass(unit: str) -> None:
    reading = example("telemetry-reading", "pressure_suspect")
    reading["unit"] = unit
    assert is_valid("telemetry-reading", reading), unit


def test_money_rules_apply_to_the_inputs_of_a_calculation_too() -> None:
    for unit, label in (
        ("EGP", "SIMULATION"),
        ("EGP/year", "MODEL"),
        ("EGP", "SENSOR_SIM"),
        ("EGP", "PUBLIC_GEOMETRY"),
    ):
        record = evidence()
        record["inputs"][0].update(unit=unit, label=label)
        assert not is_valid("evidence-record", record), (unit, label)
    for unit in ("USD", "egp", "JPY", "L.E.", "ЕGP"):
        record = evidence()
        record["inputs"][0].update(unit=unit)
        assert not is_valid("evidence-record", record), unit
    record = evidence()
    record["inputs"][0].update(unit="EGP", label="ASSUMPTION")
    assert is_valid("evidence-record", record)


@pytest.mark.parametrize("value", ["1,000", "1.000,00", "١٬٠٠٠", "1000", "n/a", True])
def test_money_values_are_json_numbers(value: Any) -> None:
    record = evidence(value=value)
    assert not is_valid("evidence-record", record), value
    record = evidence(kind="cost", value=value)
    assert not is_valid("evidence-record", record), value
    record = evidence()
    record["inputs"][0].update(unit="EGP", label="ASSUMPTION", value=value)
    assert not is_valid("evidence-record", record), value
    record = evidence(
        unit="EGP/m3", label="ASSUMPTION", formula=None, inputs=[], value=value
    )
    assert not is_valid("evidence-record", record), value


@pytest.mark.parametrize(
    "label",
    [
        "OBSERVED",
        "BENCHMARK",
        "PUBLIC_GEOMETRY",
        "SIMULATION",
        "SENSOR_SIM",
        "MODEL",
        "ASSUMPTION",
    ],
)
def test_a_dimensionless_record_has_a_null_unit_under_any_label_with_a_value(
    label: str,
) -> None:
    record = {
        "schema_version": "1",
        "evidence_id": "ev_ratio_1",
        "value": 0.5,
        "unit": None,
        "label": label,
        "formula": None,
        "inputs": [],
        "provenance": {"run_id": "r1"},
    }
    assert is_valid("evidence-record", record), label


@pytest.mark.parametrize("unit", [None, "m3", "h", "EGP/m3", "EGP/kWh"])
def test_a_cost_is_an_amount_in_egp(unit: Any) -> None:
    assert not is_valid("evidence-record", evidence(kind="cost", unit=unit))


@pytest.mark.parametrize("value", ["1,000", "1000", True])
def test_a_cost_value_is_a_number_whatever_its_unit(value: Any) -> None:
    assert not is_valid(
        "evidence-record", evidence(kind="cost", unit="EGP", value=value)
    )
    assert not is_valid(
        "evidence-record", evidence(kind="cost", unit=None, value=value)
    )


@pytest.mark.parametrize("unit", ["EGP", "EGP/year", "EGP/month", "EGP/day"])
def test_a_cost_in_a_canonical_amount_unit_passes(unit: str) -> None:
    assert is_valid("evidence-record", evidence(kind="cost", unit=unit))
