"""D-06: hand calculations, paired sampling, evidence and decision invariants."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from ug_core.assumptions import AssumptionSet, Triangular, load_assumptions
from ug_core.evidence import Evidenced, EvidenceLabel
from ug_core.rng import SeedStreams
from ug_intel.cost import (
    DEFAULT_OPTIONS,
    CostEngine,
    ExposureRates,
    Option,
    Rate,
    compare,
)

ROOT = Path(__file__).resolve().parents[3]


def assumptions(collapsed: bool = False, **modes: float) -> AssumptionSet:
    original = load_assumptions(ROOT / "assumptions/v1.yaml")
    entries = dict(original.assumptions)
    for name, entry in entries.items():
        if collapsed or name in modes:
            mode = modes.get(name, entry.distribution.mode)
            entries[name] = replace(entry, distribution=Triangular(mode, mode, mode))
    return replace(original, assumptions=entries)


def rates(lost: float = 10, isolated: float | None = None) -> ExposureRates:
    return ExposureRates(
        Rate(lost, "m3/h", "SIMULATION", "ev_lost"),
        Rate(0, "m3/h", "MODEL", "ev_unserved"),
        Rate(0, "kWh/h", "SIMULATION", "ev_energy"),
        None if isolated is None else Rate(isolated, "m3/h", "MODEL", "ev_isolated"),
    )


def provenance(seed: int = 42) -> dict[str, Any]:
    return dict(
        run_id="run_test",
        scenario_id="leak_test",
        seed=seed,
        network_version="network_v1",
        detector_version="d2_v1",
        assumption_set="v1",
        cost_model="cost_v1",
    )


def engine(collapsed: bool = True, **kwargs: Any) -> CostEngine:
    return CostEngine(
        kwargs.pop("rates", rates()),
        kwargs.pop("assumptions", assumptions(collapsed)),
        seed=kwargs.pop("seed", 42),
        decision_id="decision_test",
        provenance=kwargs.pop("provenance", provenance()),
        **kwargs,
    )


def comparison(**kwargs: Any) -> dict[str, Any]:
    return compare(
        kwargs.pop("rates", rates()),
        kwargs.pop("assumptions", assumptions(True)),
        seed=42,
        provenance=provenance(),
        decision_id="decision_test",
        incident_id="incident_test",
        **kwargs,
    )


def records(payload: dict[str, Any]) -> dict[str, Any]:
    return {record["evidence_id"]: record for record in payload["evidence"]}


def test_collapsed_modes_hand_calculation() -> None:
    model = engine()
    lines = model.cost_lines("fix_now")
    assert [line["value"] for line in lines] == [1280, 0, 0, 45000, 4000]
    payload = comparison()
    assert records(payload)[payload["options"][0]["expected_cost"]]["value"] == 50280


def test_lines_have_one_quantity_one_price_and_only_duration_extras() -> None:
    model = engine(False)
    for option in model.options:
        for line in model.cost_lines(option):
            assert line["kind"] == "cost"
            assert line["unit"] == "EGP" and line["label"] == "CALCULATED"
            quantity, price, *durations = line["inputs"]
            assert quantity["unit"] in {"m3", "kWh", "count"}
            assert price["unit"] in {"EGP/m3", "EGP/kWh", "EGP"}
            assert price["label"] == "ASSUMPTION"
            assert all(
                d["unit"] == "h" and d["label"] == "ASSUMPTION" for d in durations
            )
            assert line["formula"].count(" * ") == 1
    for label in ("SIMULATION", "MODEL"):
        with pytest.raises(ValueError):
            Rate(10, "EGP", label, "ev_money")
        with pytest.raises(ValueError):
            Evidenced(10, EvidenceLabel(label), "ev_money", unit="EGP")


def test_determinism_and_seeded_estimates() -> None:
    first = engine(False)
    assert first.cost_lines("wait_24h") == engine(False).cost_lines("wait_24h")
    other = engine(False, seed=43, provenance=provenance(43))
    a, b = first.cost_lines("wait_24h")[0], other.cost_lines("wait_24h")[0]
    assert a["uncertainty"] != b["uncertainty"]
    for key in ("evidence_id", "formula", "explanation_template", "label", "unit"):
        assert a[key] == b[key]
    assert comparison() == comparison()


def test_sorted_draw_order_and_common_random_numbers() -> None:
    model = engine(False, n_samples=73)
    rng = SeedStreams(42).stream("cost.samples")
    expected = {}
    for name in sorted(model.assumption_samples):
        d = model.assumptions.assumptions[name].distribution
        expected[name] = rng.triangular(d.min, d.mode, d.max, size=73)
        np.testing.assert_array_equal(model.assumption_samples[name], expected[name])
    totals = np.stack([model.total_samples(o) for o in model.options])
    regrets = np.stack([model.regret_samples(o) for o in model.options])
    np.testing.assert_array_equal(regrets, totals - totals.min(axis=0))
    np.testing.assert_array_equal(regrets.min(axis=0), np.zeros(73))
    assert np.all(regrets >= 0)
    for o in model.options:
        total = model.total_samples(o)
        assert np.mean(model.regret_samples(o)) >= 0
        p10, p50, p90 = np.percentile(total, [10, 50, 90], method="linear")
        evidence = records(comparison(assumptions=assumptions(False), n_samples=73))
        record = evidence[model.evidence_id(o, "total")]
        assert record["value"] == float(total.mean())
        assert [record["uncertainty"][p] for p in ("p10", "p50", "p90")] == [
            p10,
            p50,
            p90,
        ]


def test_negative_net_benefit_is_present() -> None:
    payload = comparison(rates=rates(0.01))
    net = records(payload)["ev_decision_test_wait_24h_net_benefit"]
    assert net["value"] == pytest.approx(0.01 * 24 * 8 - 20000)
    assert net["value"] < 0 and net["label"] == "CALCULATED"


def test_break_even_solves_collapsed_equality() -> None:
    payload = comparison()
    crossing = records(payload)[payload["break_even"][0]["evidence_id"]]
    q = crossing["value"]
    assert q == pytest.approx(20000 / (24 * 8))
    model = engine(rates=rates(q))
    assert (
        abs(
            model.total_samples("fix_now").mean()
            - model.total_samples("wait_24h").mean()
        )
        < 1e-9
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"repair_cost_planned": 50000},
        {"water_production_cost": 0},
    ],
)
def test_no_nonnegative_break_even(changes: dict[str, float]) -> None:
    payload = comparison(assumptions=assumptions(True, **changes))
    crossing = records(payload)[payload["break_even"][0]["evidence_id"]]
    assert crossing["value"] is None
    assert crossing["label"] == "INSUFFICIENT_EVIDENCE"
    assert crossing["reason"] == "no break-even within non-negative leak rates"
    assert "uncertainty" not in crossing


def test_isolation_uses_only_response_before_isolation_and_unserved_during_repair() -> (
    None
):
    base = rates(10, isolated=12)
    base = replace(
        base,
        unserved_m3_per_h=Rate(3, "m3/h", "MODEL", "ev_unserved"),
        extra_energy_kwh_per_h=Rate(2, "kWh/h", "SIMULATION", "ev_energy"),
    )
    model = engine(rates=base)
    assert len(model.options) == 5
    lines = model.cost_lines("isolate_then_fix")
    assert [line["value"] for line in lines] == [
        480,
        (3 * 6 + 12 * 10) * 15,
        24,
        45000,
        4000,
    ]
    assert len(engine().options) == 4
    with pytest.raises(ValueError, match="isolated"):
        engine(
            options=(
                *DEFAULT_OPTIONS,
                Option("isolate", "isolate_then_fix", 0, "emergency"),
            )
        )


@pytest.mark.parametrize(
    "collapsed, isolated, price",
    [(False, 12, None), (True, None, 0), (True, None, None)],
)
def test_every_record_validates_and_refs_resolve(
    collapsed: bool, isolated: float | None, price: float | None
) -> None:
    registry: Registry = Registry()
    for path in (ROOT / "contracts/v1").glob("*.schema.json"):
        schema = json.loads(path.read_text())
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    schema = json.loads((ROOT / "contracts/v1/evidence-record.schema.json").read_text())
    validator = Draft202012Validator(schema, registry=registry)
    used_assumptions = assumptions(
        collapsed, **({"water_production_cost": price} if price is not None else {})
    )
    payload = comparison(
        rates=rates(10, isolated=isolated), assumptions=used_assumptions
    )
    by_id = records(payload)
    assert len(by_id) == len(payload["evidence"])
    for record in by_id.values():
        validator.validate(record)
        for item in record["inputs"]:
            if item["ref"].startswith("ev_decision_test_"):
                assert item["ref"] in by_id
    assert len(payload["options"]) >= 2 and payload["advisory"] is True
    minimum = min(by_id[o["expected_cost"]]["value"] for o in payload["options"])
    winners = [
        o["option_id"]
        for o in payload["options"]
        if by_id[o["expected_cost"]]["value"] == minimum
    ]
    assert payload["preferred_by_expected_cost"] == (
        winners[0] if len(winners) == 1 else None
    )
    for option in payload["options"]:
        assert len(option["cost_lines"]) == 5
        for ref in (
            *option["cost_lines"],
            option["expected_cost"],
            option["worst_case"],
            option["expected_regret"],
        ):
            assert ref in by_id
        worst = by_id[option["worst_case"]]
        assert worst["value"] == by_id[option["expected_cost"]]["uncertainty"]["p90"]

    def check_keys(value: Any) -> None:
        if isinstance(value, dict):
            assert not ({"probability", "confidence", "recommendation"} & value.keys())
            for child in value.values():
                check_keys(child)
        elif isinstance(value, list):
            for child in value:
                check_keys(child)

    check_keys(payload)
    json.dumps(payload, allow_nan=False)


def test_tie_has_no_preferred_option() -> None:
    payload = comparison(
        rates=rates(0), assumptions=assumptions(True, repair_cost_planned=45000)
    )
    assert payload["preferred_by_expected_cost"] is None


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, "1"])
def test_rate_rejects_invalid_numbers(bad: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        Rate(bad, "m3/h", "MODEL", "ev_bad")


def test_frozen_inputs_units_and_option_validation() -> None:
    value = rates()
    with pytest.raises(FrozenInstanceError):
        value.lost_water_m3_per_h.value = 5  # type: ignore[misc]
    with pytest.raises(ValueError):
        ExposureRates(
            Rate(1, "kWh/h", "MODEL", "ev_bad"),
            value.unserved_m3_per_h,
            value.extra_energy_kwh_per_h,
        )
    for action, delay, repair in [
        ("fix_now", 1, "emergency"),
        ("unknown", 0, "planned"),
        ("wait", -1, "planned"),
        ("wait", 0, "unknown"),
        ("isolate_then_fix", 1, "emergency"),
    ]:
        with pytest.raises(ValueError):
            Option("bad", action, delay, repair)
    with pytest.raises(ValueError):
        Rate(1, "m3/h", "OBSERVED", "ev_bad")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_samples": 0},
        {"n_samples": True},
        {"seed": -1},
        {"provenance": provenance(1)},
        {"provenance": {**provenance(), "cost_model": "other_v1"}},
        {"options": (DEFAULT_OPTIONS[0], DEFAULT_OPTIONS[0])},
    ],
)
def test_engine_rejects_invalid_inputs(kwargs: dict[str, Any]) -> None:
    with pytest.raises((TypeError, ValueError)):
        engine(**kwargs)


def test_wait_quantities_prices_modes_and_duration_provenance() -> None:
    base = replace(
        rates(),
        unserved_m3_per_h=Rate(3, "m3/h", "MODEL", "ev_unserved"),
        extra_energy_kwh_per_h=Rate(2, "kWh/h", "SIMULATION", "ev_energy"),
    )
    model = engine(rates=base)
    lines = model.cost_lines("wait_24h")
    assert [line["value"] for line in lines] == [
        10 * 40 * 8,
        3 * 40 * 15,
        2 * 40 * 2,
        25000,
        4000,
    ]
    for line, rate in zip(
        lines[:3],
        (base.lost_water_m3_per_h, base.unserved_m3_per_h, base.extra_energy_kwh_per_h),
        strict=True,
    ):
        quantity, price, *durations = line["inputs"]
        assert quantity["value"] == rate.value * 40
        assert quantity["label"] == rate.label and quantity["ref"] == rate.ref
        entry = model.assumptions.assumptions[price["name"]]
        assert price["value"] == entry.distribution.mode
        assert price["ref"] == model.assumptions.evidence_id(price["name"])
        assert {d["name"]: d["value"] for d in durations} == {
            "delay_hours": 24,
            "crew_response_hours": 6,
            "repair_duration_hours": 10,
        }
        assert (
            line["uncertainty"]["basis"]
            == "1000 seeded samples of the assumption ranges (assumption set v1)"
        )


def test_option_order_and_isolation_do_not_change_shared_draws() -> None:
    original = engine(False)
    reordered = engine(False, options=tuple(reversed(DEFAULT_OPTIONS)))
    isolated = engine(False, rates=rates(isolated=12))
    for option in DEFAULT_OPTIONS:
        np.testing.assert_array_equal(
            original.total_samples(option), reordered.total_samples(option)
        )
        np.testing.assert_array_equal(
            original.total_samples(option), isolated.total_samples(option)
        )
    values = original.total_samples("fix_now")
    values[:] = -1
    assert np.all(original.total_samples("fix_now") >= 0)


def test_stochastic_break_even_uses_sampled_joint_exposure_price() -> None:
    base = replace(
        rates(),
        unserved_m3_per_h=Rate(3, "m3/h", "MODEL", "ev_unserved"),
        extra_energy_kwh_per_h=Rate(2, "kWh/h", "SIMULATION", "ev_energy"),
    )
    model = engine(False, rates=base)
    payload = comparison(rates=base, assumptions=assumptions(False))
    q = records(payload)[payload["break_even"][0]["evidence_id"]]["value"]
    assert q is not None
    crossed = engine(
        False,
        rates=replace(
            base, lost_water_m3_per_h=replace(base.lost_water_m3_per_h, value=q)
        ),
    )
    assert crossed.total_samples("fix_now").mean() == pytest.approx(
        crossed.total_samples("wait_24h").mean(), abs=1e-9, rel=0
    )
    # Use the actual common draws, including unserved and energy in F.
    draws = model.assumption_samples
    avoided_delay_cost = 24 * (
        3 * draws["unserved_water_penalty"] + 2 * draws["electricity_price"]
    )
    numerator = np.mean(
        draws["repair_cost_planned"]
        - draws["repair_cost_emergency"]
        + avoided_delay_cost
    )
    assert q == pytest.approx(numerator / np.mean(-24 * draws["water_production_cost"]))


def test_isolation_quantity_traces_both_rates() -> None:
    payload = comparison(rates=rates(isolated=12))
    by_id = records(payload)
    line = by_id["ev_decision_test_isolate_then_fix_unserved"]
    quantity = by_id[line["inputs"][0]["ref"]]
    assert {i["ref"] for i in quantity["inputs"]} >= {"ev_unserved", "ev_isolated"}
    assert quantity["value"] == 120
    assert len(line["inputs"]) == 4  # one quantity, one price, two durations


def test_money_input_guard_rejects_direct_bad_line_construction() -> None:
    model = engine()
    for label in ("SIMULATION", "MODEL"):
        with pytest.raises(ValueError, match="money"):
            model.record(
                "fix_now",
                "invalid",
                100,
                unit="EGP",
                formula="q * p",
                inputs=[
                    dict(name="p", value=100, unit="EGP", label=label, ref="ev_bad")
                ],
                template="cost.invalid.v1",
            )
