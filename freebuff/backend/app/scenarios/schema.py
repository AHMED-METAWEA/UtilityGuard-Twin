"""Pydantic scenario contract.

The JSON contract in the task is implemented exactly. `demand_change` is a
documented extension used only by the evaluation suite to exercise the
demand-change diagnosis path; presets never require it.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import (
    DEFAULT_HORIZON_HOURS,
    DEFAULT_SEED,
    DEFAULT_TIMESTEP_MINUTES,
    NETWORK_VERSION,
    SIM_START,
)

ZoneName = Literal["gov", "res", "com"]


class DemandSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    holiday: bool = False
    heatwave_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)
    zone_multipliers: dict[ZoneName, float] = Field(
        default_factory=lambda: {"gov": 1.0, "res": 1.0, "com": 1.0}
    )

    @model_validator(mode="after")
    def _check_zone_keys(self) -> "DemandSettings":
        for key, value in self.zone_multipliers.items():
            if value <= 0 or value > 3:
                raise ValueError(f"zone multiplier for {key} must be in (0, 3]")
        return self


class LeakFault(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["leak"] = "leak"
    location: str = Field(pattern=r"^pipe:PIPE_\d{2}$")
    start_hour: float = Field(ge=0)
    profile: Literal["gradual", "sudden"] = "gradual"
    ramp_hours: float = Field(default=0.0, ge=0)
    final_area_cm2: float = Field(gt=0, le=200)


class SensorDriftFault(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["sensor_drift"] = "sensor_drift"
    sensor_id: str
    start_hour: float = Field(ge=0)
    drift_per_hour: float


class SensorStuckFault(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["sensor_stuck"] = "sensor_stuck"
    sensor_id: str
    start_hour: float = Field(ge=0)
    duration_hours: float = Field(gt=0)


class SensorDropoutFault(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["sensor_dropout"] = "sensor_dropout"
    sensor_id: str
    start_hour: float = Field(ge=0)
    duration_hours: float = Field(gt=0)
    probability: float = Field(default=1.0, ge=0, le=1)


class PumpOutageFault(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["pump_outage"] = "pump_outage"
    pump_id: str
    start_hour: float = Field(ge=0)
    duration_hours: float = Field(gt=0)


class DemandChangeFault(BaseModel):
    """Extension: an unforecast zone demand change (e.g. an event)."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["demand_change"] = "demand_change"
    zone_multipliers: dict[ZoneName, float]
    start_hour: float = Field(ge=0)


Fault = Annotated[
    Union[
        LeakFault,
        SensorDriftFault,
        SensorStuckFault,
        SensorDropoutFault,
        PumpOutageFault,
        DemandChangeFault,
    ],
    Field(discriminator="type"),
]


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=80)
    network_version: str = NETWORK_VERSION
    seed: int = DEFAULT_SEED
    duration_hours: float = Field(default=DEFAULT_HORIZON_HOURS, gt=0, le=168)
    timestep_minutes: int = Field(default=DEFAULT_TIMESTEP_MINUTES, ge=1, le=60)
    demand: DemandSettings = Field(default_factory=DemandSettings)
    faults: list[Fault] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "ScenarioConfig":
        steps = self.duration_hours * 60 / self.timestep_minutes
        if abs(steps - round(steps)) > 1e-9:
            raise ValueError("duration_hours must be a whole number of timesteps")
        if self.network_version != NETWORK_VERSION:
            raise ValueError(
                f"this build only provides network_version={NETWORK_VERSION}"
            )
        for fault in self.faults:
            if fault.start_hour >= self.duration_hours:
                raise ValueError(f"fault starts after end of scenario: {fault}")
            if isinstance(fault, (SensorStuckFault, SensorDropoutFault,
                                  PumpOutageFault)):
                if getattr(fault, "duration_hours", 0) > self.duration_hours:
                    raise ValueError("fault duration exceeds scenario duration")
            if isinstance(fault, LeakFault) and fault.profile == "gradual":
                if fault.ramp_hours <= 0:
                    raise ValueError("a gradual leak requires ramp_hours > 0")
            if isinstance(fault, LeakFault):
                pipe_no = int(fault.location.split("_")[-1])
                if not 1 <= pipe_no <= 60:
                    raise ValueError(f"unknown pipe in leak location: {fault.location}")
        return self

    @property
    def timestep_seconds(self) -> int:
        return self.timestep_minutes * 60

    @property
    def ticks(self) -> int:
        return int(round(self.duration_hours * 60 / self.timestep_minutes))

    @property
    def start_time(self) -> datetime:
        return datetime.fromisoformat(SIM_START)

    def time_at_tick(self, tick: int) -> datetime:
        return self.start_time + timedelta(minutes=tick * self.timestep_minutes)

    def tick_at_hour(self, hour: float) -> int:
        return int(round(hour * 60 / self.timestep_minutes))

    def canonical(self) -> dict:
        """Canonical, JSON-safe representation used for hashing/reproducibility."""
        data = self.model_dump(mode="json")
        data["faults"] = sorted(
            data["faults"],
            key=lambda f: (f["start_hour"], f["type"], str(f.get("sensor_id", ""))),
        )
        data["demand"]["zone_multipliers"] = {
            k: data["demand"]["zone_multipliers"][k] for k in ("gov", "res", "com")
        }
        return data
