import pytest

from app.decision.engine import _break_even
from app.finance import engine as finance


def _impact(water=10.0, unserved=2.0, energy=100.0):
    return {
        "water_lost_m3": water,
        "unserved_m3": unserved,
        "pump_energy_kwh": energy,
    }


def test_cost_lines_are_arithmetic_not_magic():
    assumptions = finance.get_assumption_values()
    impact = _impact()
    lines = finance.cost_lines(
        "monitor", impact, assumptions, emergency=True, include_inspection=False,
    )
    by_name = {line["line"]: line for line in lines}
    assert by_name["lost_water"]["cost"] == pytest.approx(
        impact["water_lost_m3"] * assumptions["water_price_per_m3"]
    )
    assert by_name["unserved_demand"]["cost"] == pytest.approx(
        impact["unserved_m3"] * assumptions["unserved_water_penalty_per_m3"]
    )
    assert by_name["pump_energy"]["cost"] == pytest.approx(
        impact["pump_energy_kwh"] * assumptions["electricity_price_per_kwh"]
    )
    assert by_name["repair"]["cost"] == pytest.approx(assumptions["repair_cost_emergency"])
    for line in lines:
        assert line["label"] in {"ASSUMPTION", "SIMULATION"}
        assert line["cost"] == pytest.approx(line["quantity"] * line["unit_price"], rel=1e-9)


def test_total_cost_averages_variants():
    assumptions = finance.get_assumption_values()
    impacts = {"low": _impact(water=5), "mid": _impact(water=10), "high": _impact(water=20)}
    total, lines = finance.total_cost("monitor", impacts, assumptions)
    assert len(lines) == 3 * 4  # four lines per variant for monitor
    manual = 0.0
    for impact in impacts.values():
        manual += sum(
            line["cost"] for line in finance.cost_lines(
                "monitor", impact, assumptions, emergency=True, include_inspection=False,
            )
        )
    assert total == pytest.approx(manual / 3, abs=0.01)


def test_monte_carlo_is_seeded_and_ordered():
    assumptions_data = finance.load_assumptions()
    impacts = {"mid": _impact()}
    first = finance.monte_carlo("inspect", impacts, assumptions_data, samples=50, seed=11)
    second = finance.monte_carlo("inspect", impacts, assumptions_data, samples=50, seed=11)
    assert first == second
    assert first["p10"] <= first["p50"] <= first["p90"]
    assert first["label"] == "CALCULATED"
    other = finance.monte_carlo("inspect", impacts, assumptions_data, samples=50, seed=12)
    assert other != first


def test_break_even_uses_fixed_cost_when_fault_absent():
    # Monitor costs 100 only if the fault is real; repair costs 40 whether or
    # not it is real. Break-even is then 40/100 = 0.40.
    result = _break_even(
        monitor_cost=100.0,
        monitor_absent=0.0,
        action_cost=40.0,
        action_absent=40.0,
        action_label="Repair now",
    )
    assert result["threshold"] == pytest.approx(0.4)
    assert result["label"] == "CALCULATED"


def test_break_even_reports_when_action_never_pays_off():
    # The action costs more when a fault is present than monitoring does, so
    # the denominator is non-positive and no probability makes it worthwhile.
    result = _break_even(
        monitor_cost=100.0,
        monitor_absent=0.0,
        action_cost=300.0,
        action_absent=0.0,
        action_label="Expensive inspection",
    )
    assert result["threshold"] is None
    assert "does not pay off" in result["text"]


def test_assumption_updates_reject_unknown_and_out_of_range(tmp_path, monkeypatch):
    target = tmp_path / "overrides.json"
    monkeypatch.setattr(finance, "OVERRIDES_PATH", target)
    with pytest.raises(ValueError):
        finance.update_assumptions({"not_a_key": 1.0})
    with pytest.raises(ValueError):
        finance.update_assumptions({"water_price_per_m3": 999.0})
    updated = finance.update_assumptions({"water_price_per_m3": 2.0})
    assert updated["assumptions"]["water_price_per_m3"]["value"] == 2.0
    assert updated["version"].startswith("1.0+rev")
    assert target.exists()


def test_reset_assumptions_removes_override(tmp_path, monkeypatch):
    target = tmp_path / "overrides.json"
    monkeypatch.setattr(finance, "OVERRIDES_PATH", target)
    finance.update_assumptions({"inspection_cost": 1000.0})
    assert finance.get_assumption_values()["inspection_cost"] == 1000.0
    reset = finance.reset_assumptions()
    assert reset["assumptions"]["inspection_cost"]["value"] != 1000.0
    assert not target.exists()
