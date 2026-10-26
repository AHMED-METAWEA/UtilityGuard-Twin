"""T-B1-016: the engine settings are a checked file labelled ASSUMPTION."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ug_water.solver import load_options
from ug_water.solver import options as O

PACKAGED = Path(O.__file__).parent / "data" / "hydraulics_v1.json"


def data() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(PACKAGED.read_text())
    return loaded


def test_the_packaged_settings() -> None:
    options = load_options()
    assert options.engine == "wntr" and options.hydraulic_step_s == 300
    assert (options.required_pressure_m, options.minimum_pressure_m) == (20.0, 0.0)
    assert options.pressure_exponent == 0.5
    assert data()["label"] == "ASSUMPTION"
    assert load_options(data()).config_hash == options.config_hash


def test_a_changed_value_changes_the_hash() -> None:
    changed = data()
    changed["pdd"]["required_pressure_m"] = 25.0
    assert load_options(changed).config_hash != load_options().config_hash


def pdd(**values: float) -> dict[str, Any]:
    changed = data()
    changed["pdd"] = {**changed["pdd"], **values}
    return changed


@pytest.mark.parametrize(
    ("changed", "message"),
    [
        ({**data(), "label": "OBSERVED"}, "ASSUMPTION"),
        ({**data(), "engine": "magic"}, "engine"),
        ({**data(), "headloss": "D-W"}, "Hazen-Williams"),
        ({**data(), "hydraulic_step_s": 0}, "positive integer"),
        ({**data(), "hydraulic_step_s": 300.0}, "positive integer"),
        ({**data(), "extra": 1}, "expected the keys"),
        (pdd(required_pressure_m=0.0), "minimum_pressure_m < required"),
        (pdd(minimum_pressure_m=-1.0), "minimum_pressure_m < required"),
        (pdd(pressure_exponent=0.0), "pressure_exponent"),
        (pdd(pressure_exponent=1.5), "pressure_exponent"),
        (pdd(required_pressure_m=float("nan")), "finite"),
        ({**data(), "water_density_kg_m3": 0}, "positive"),
    ],
)
def test_broken_settings_are_refused(changed: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_options(changed)
