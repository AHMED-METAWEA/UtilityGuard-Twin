"""Settings of the hydraulic engine, read from a versioned file labelled `ASSUMPTION`.

The pressure-driven demand (PDD) settings decide how much of the requested demand a junction
receives when its pressure is low: nothing at or below `minimum_pressure_m`, all of it at or above
`required_pressure_m`, and `((p - p_min) / (p_req - p_min)) ** pressure_exponent` in between
(WNTR smooths the two ends over a small pressure band). The values are placeholders, not design
criteria of any utility.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from typing import Any, Literal

from ug_core.canonical import canonical_json, sha256_hex

Engine = Literal["wntr", "epanet"]
ENGINES: frozenset[str] = frozenset({"wntr", "epanet"})
_KEYS = frozenset(
    {
        "version", "label", "note", "engine", "hydraulic_step_s", "headloss", "pdd",
        "water_density_kg_m3", "gravity_m_s2",
    }
)  # fmt: skip
_PDD_KEYS = frozenset(
    {"required_pressure_m", "minimum_pressure_m", "pressure_exponent"}
)


@dataclass(frozen=True)
class HydraulicOptions:
    engine: Engine
    hydraulic_step_s: int
    required_pressure_m: float
    minimum_pressure_m: float
    pressure_exponent: float
    water_density_kg_m3: float
    gravity_m_s2: float
    config_hash: str


def load_options(data: Mapping[str, Any] | None = None) -> HydraulicOptions:
    """Check and read the settings; `None` reads the packaged `data/hydraulics_v1.json`."""
    if data is None:
        text = (
            resources.files("ug_water.solver")
            .joinpath("data/hydraulics_v1.json")
            .read_text(encoding="utf-8")
        )
        data = json.loads(text)
    if set(data) != _KEYS:
        raise ValueError(
            f"hydraulic settings: expected the keys {sorted(_KEYS)}, got {sorted(data)}"
        )
    if data["label"] != "ASSUMPTION":
        raise ValueError(
            "hydraulic settings are chosen, not measured: label ASSUMPTION"
        )
    if data["engine"] not in ENGINES:
        raise ValueError(f"engine must be one of {sorted(ENGINES)}")
    if data["headloss"] != "H-W":
        raise ValueError("the network carries Hazen-Williams roughness: headloss H-W")
    step = data["hydraulic_step_s"]
    if isinstance(step, bool) or not isinstance(step, int) or step <= 0:
        raise ValueError("hydraulic_step_s must be a positive integer")
    pdd = data["pdd"]
    if set(pdd) != _PDD_KEYS:
        raise ValueError(f"pdd: expected the keys {sorted(_PDD_KEYS)}")
    numbers = {
        "required_pressure_m": pdd["required_pressure_m"],
        "minimum_pressure_m": pdd["minimum_pressure_m"],
        "pressure_exponent": pdd["pressure_exponent"],
        "water_density_kg_m3": data["water_density_kg_m3"],
        "gravity_m_s2": data["gravity_m_s2"],
    }
    for name, value in numbers.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{name} must be a number")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if not 0 <= numbers["minimum_pressure_m"] < numbers["required_pressure_m"]:
        raise ValueError("pdd: 0 <= minimum_pressure_m < required_pressure_m")
    if not 0 < numbers["pressure_exponent"] <= 1:
        raise ValueError("pdd: pressure_exponent must be in (0, 1]")
    if numbers["water_density_kg_m3"] <= 0 or numbers["gravity_m_s2"] <= 0:
        raise ValueError("water_density_kg_m3 and gravity_m_s2 must be positive")
    return HydraulicOptions(
        engine=data["engine"],
        hydraulic_step_s=step,
        required_pressure_m=float(numbers["required_pressure_m"]),
        minimum_pressure_m=float(numbers["minimum_pressure_m"]),
        pressure_exponent=float(numbers["pressure_exponent"]),
        water_density_kg_m3=float(numbers["water_density_kg_m3"]),
        gravity_m_s2=float(numbers["gravity_m_s2"]),
        config_hash=sha256_hex(canonical_json(dict(data))),
    )
