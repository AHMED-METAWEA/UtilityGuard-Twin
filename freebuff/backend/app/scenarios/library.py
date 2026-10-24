"""Preset hypothetical scenarios. Seeds are fixed so demos are reproducible."""
from __future__ import annotations

from typing import Any

from app.scenarios.schema import (
    DemandSettings,
    LeakFault,
    PumpOutageFault,
    ScenarioConfig,
    SensorDriftFault,
    SensorStuckFault,
)


def _base(scenario_id: str, seed: int, **kwargs: Any) -> ScenarioConfig:
    return ScenarioConfig(scenario_id=scenario_id, seed=seed, **kwargs)


PRESETS: dict[str, ScenarioConfig] = {
    "normal": _base("normal", 101),
    "holiday": _base(
        "holiday", 102,
        demand=DemandSettings(holiday=True),
    ),
    "heatwave": _base(
        "heatwave", 103,
        demand=DemandSettings(heatwave_multiplier=1.25),
    ),
    "leak_gradual": _base(
        "leak_gradual", 104,
        faults=[LeakFault(
            location="pipe:PIPE_17", start_hour=12, profile="gradual",
            ramp_hours=24, final_area_cm2=6.0,
        )],
    ),
    "leak_sudden": _base(
        "leak_sudden", 105,
        faults=[LeakFault(
            location="pipe:PIPE_17", start_hour=12, profile="sudden",
            ramp_hours=0.0, final_area_cm2=8.0,
        )],
    ),
    "sensor_drift": _base(
        "sensor_drift", 106,
        faults=[SensorDriftFault(
            sensor_id="P05", start_hour=10, drift_per_hour=0.3,
        )],
    ),
    "sensor_stuck": _base(
        "sensor_stuck", 107,
        faults=[SensorStuckFault(
            sensor_id="P02", start_hour=20, duration_hours=6,
        )],
    ),
    "pump_outage": _base(
        "pump_outage", 108,
        faults=[PumpOutageFault(
            pump_id="PUMP_1", start_hour=18, duration_hours=4,
        )],
    ),
    "leak_plus_sensor_drift": _base(
        "leak_plus_sensor_drift", 109,
        faults=[
            LeakFault(
                location="pipe:PIPE_17", start_hour=12, profile="gradual",
                ramp_hours=24, final_area_cm2=6.0,
            ),
            SensorDriftFault(sensor_id="P05", start_hour=10, drift_per_hour=0.3),
        ],
    ),
}

PRESET_NOTES: dict[str, str] = {
    "normal": "Baseline 48 h, no faults. Used to measure false alerts.",
    "holiday": "Government demand assumed 40% lower all day.",
    "heatwave": "All demand assumed 25% higher all day.",
    "leak_gradual": "6 cm2 leak ramping over 24 h on PIPE_17, starts hour 12.",
    "leak_sudden": "8 cm2 leak appears at hour 12 on PIPE_17.",
    "sensor_drift": "P05 drifts +0.3 m/h from hour 10 (physics unaffected).",
    "sensor_stuck": "P02 freezes at its hour-20 value for 6 h.",
    "pump_outage": "Duty pump PUMP_1 trips at hour 18 for 4 h; standby is not automatic.",
    "leak_plus_sensor_drift": "Gradual PIPE_17 leak plus P05 drift; ambiguous case.",
}


def get_preset(scenario_id: str) -> ScenarioConfig:
    if scenario_id not in PRESETS:
        raise KeyError(f"unknown preset: {scenario_id}")
    return PRESETS[scenario_id].model_copy(deep=True)


def list_presets() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": key,
            "note": PRESET_NOTES[key],
            "config": cfg.model_dump(mode="json"),
        }
        for key, cfg in PRESETS.items()
    ]
