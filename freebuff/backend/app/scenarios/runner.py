"""Deterministic scenario runner.

Strategy
--------
The *whole* scenario is simulated once when a run is created. The stream later
replays the stored time series; WNTR is never called inside the streaming loop.

WNTR models a leak with a constant area. A gradual leak is therefore split into
hourly chunks: at each chunk boundary the leak area is updated and the tank
level from the previous chunk is carried forward. This is an approximation
(documented in docs/scenario_schema.md); hydraulics inside a chunk are solved
normally by WNTR with pressure-dependent demand.

The fault-free baseline is a second run with the same demand assumptions and
the same topology, but no leak / pump outage / unforecast demand change.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from wntr.network import WaterNetworkModel
from wntr.network.base import LinkStatus
from wntr.sim import WNTRSimulator

from app.config import NETWORK_VERSION, SETTINGS, SIM_START
from app.network.builder import (
    DEFAULT_PROVIDER,
    GRID_PIPE_MAX,
    HypotheticalGridProvider,
    NetworkProvider,
    zone_patterns,
)
from app.scenarios.schema import (
    DemandChangeFault,
    LeakFault,
    PumpOutageFault,
    ScenarioConfig,
    SensorDropoutFault,
    SensorDriftFault,
    SensorStuckFault,
)

GRID_NODES = [f"J{i:02d}" for i in range(1, 37)]
PUMP_IDS = ("PUMP_1", "PUMP_2")
TANK_ID = "TANK1"
LEAK_DISCHARGE_COEFF = 0.75
FLOAT_DIGITS = 6


@dataclass
class TruthSeries:
    ticks: int
    timestep_minutes: int
    time_iso: list[str]
    pressure: dict[str, list[float]] = field(default_factory=dict)
    demand: dict[str, list[float]] = field(default_factory=dict)
    flow: dict[str, list[float]] = field(default_factory=dict)
    tank_level: list[float] = field(default_factory=list)
    leak_flow_lps: list[float] = field(default_factory=list)
    pump_status: dict[str, list[str]] = field(default_factory=dict)
    delivered_lps: dict[str, list[float]] = field(default_factory=dict)
    leak_node: str | None = None
    leak_pipe: str | None = None
    leak_area_cm2: list[float] = field(default_factory=list)

    def sensor_value(self, kind: str, target: str, tick: int) -> float | None:
        if kind == "pressure":
            values = self.pressure.get(target)
        elif kind == "flow":
            values = self.flow.get(target)
        elif kind == "level":
            values = self.tank_level
            tick = min(tick, len(values) - 1)
            return float(values[tick])
        else:
            return None
        if values is None or tick >= len(values):
            return None
        return float(values[tick])

    def canon(self) -> dict[str, Any]:
        return {
            "ticks": self.ticks,
            "timestep_minutes": self.timestep_minutes,
            "time_iso": self.time_iso,
            "pressure": self.pressure,
            "demand": self.demand,
            "flow": self.flow,
            "tank_level": self.tank_level,
            "leak_flow_lps": self.leak_flow_lps,
            "pump_status": self.pump_status,
            "delivered_lps": self.delivered_lps,
            "leak_node": self.leak_node,
            "leak_pipe": self.leak_pipe,
            "leak_area_cm2": self.leak_area_cm2,
        }

    @classmethod
    def from_canon(cls, data: dict[str, Any]) -> "TruthSeries":
        return cls(**data)


@dataclass
class RunBundle:
    config: ScenarioConfig
    truth: TruthSeries
    baseline: TruthSeries
    readings: dict[str, list[float | None]]
    runtime_seconds: float
    output_hash: str

    def canon(self) -> dict[str, Any]:
        return {
            "config": self.config.canonical(),
            "truth": self.truth.canon(),
            "baseline": self.baseline.canon(),
            "readings": self.readings,
        }

    def compute_hash(self) -> str:
        payload = json.dumps(self.canon(), sort_keys=True, separators=(",", ":"),
                             allow_nan=False)
        return hashlib.sha256(payload.encode()).hexdigest()


def _round(value: float) -> float:
    if value is None or not math.isfinite(float(value)):
        return 0.0
    return round(float(value), FLOAT_DIGITS)


def _leak_area_cm2(fault: LeakFault, hour: float) -> float:
    if hour < fault.start_hour:
        return 0.0
    if fault.profile == "sudden":
        return float(fault.final_area_cm2)
    elapsed = hour - fault.start_hour
    if fault.ramp_hours <= 0:
        return float(fault.final_area_cm2)
    return float(fault.final_area_cm2) * min(1.0, elapsed / fault.ramp_hours)


def _leak_fault(config: ScenarioConfig) -> LeakFault | None:
    for fault in config.faults:
        if isinstance(fault, LeakFault):
            return fault
    return None


def _chunk_boundaries(config: ScenarioConfig) -> list[int]:
    ticks = config.ticks
    points = {0, ticks}
    for fault in config.faults:
        start = min(ticks, max(0, config.tick_at_hour(fault.start_hour)))
        points.add(start)
        if isinstance(fault, LeakFault):
            if fault.profile == "gradual":
                step = max(1, int(round(60 / config.timestep_minutes)))
                for tick in range(start, min(ticks, config.tick_at_hour(
                        fault.start_hour + fault.ramp_hours)) + 1, step):
                    points.add(tick)
        elif isinstance(fault, (PumpOutageFault, SensorStuckFault,
                                SensorDropoutFault)):
            end = min(ticks, config.tick_at_hour(
                fault.start_hour + fault.duration_hours))
            points.add(end)
    return sorted(points)


def _demand_multipliers(
    config: ScenarioConfig,
    zone: str,
    ticks: int,
    start_hour: float,
    apply_unforecast: bool,
) -> list[float]:
    demand = config.demand
    values = zone_patterns(
        ticks=ticks,
        timestep_minutes=config.timestep_minutes,
        start_hour=start_hour,
        holiday=demand.holiday,
        heatwave=demand.heatwave_multiplier,
        zone_multipliers=demand.zone_multipliers,
    )[zone]
    if apply_unforecast:
        for fault in config.faults:
            if isinstance(fault, DemandChangeFault) and zone in fault.zone_multipliers:
                factor = fault.zone_multipliers[zone]
                for i in range(len(values)):
                    tick = int(round((start_hour * 60 / config.timestep_minutes))) + i
                    hour = tick * config.timestep_minutes / 60
                    if hour >= fault.start_hour:
                        values[i] = values[i] * factor
    return values


def _configure_demands(
    wn: WaterNetworkModel,
    provider: NetworkProvider,
    config: ScenarioConfig,
    chunk_start_tick: int,
    chunk_ticks: int,
    apply_unforecast: bool,
) -> None:
    if not isinstance(provider, HypotheticalGridProvider):
        raise NotImplementedError("only the hypothetical provider is implemented")
    for node_id, base in provider.demand_base_demands().items():
        wn.get_node(node_id).demand_timeseries_list[0].base_value = base
    start_hour = chunk_start_tick * config.timestep_minutes / 60.0
    for zone in ("gov", "res", "com"):
        multipliers = _demand_multipliers(
            config, zone, chunk_ticks, start_hour, apply_unforecast,
        )
        pattern = wn.get_pattern(zone)
        pattern.multipliers = multipliers
        pattern.time_options = wn.options.time


def split_pipe_for_leak(
    wn: WaterNetworkModel, pipe_id: str
) -> tuple[str, tuple[str, str], tuple[float, float]]:
    """Split `pipe_id` at its midpoint and return the new leak junction.

    Verified against WNTR 1.5: leaks attach to junctions via
    `Junction.add_leak`, so a mid-pipe leak needs a new junction. The split
    preserves diameter, roughness, minor loss, and status and halves length.
    """
    if pipe_id not in wn.link_name_list:
        raise ValueError(
            f"leak location {pipe_id} is not a pipe in this network "
            "(three grid edges are valves: PIPE_10, PIPE_25, PIPE_45)"
        )
    pipe = wn.get_link(pipe_id)
    if pipe.link_type != "Pipe":
        raise ValueError(f"leak location {pipe_id} is a {pipe.link_type}, not a pipe")
    start = wn.get_node(pipe.start_node_name)
    end = wn.get_node(pipe.end_node_name)
    new_node = f"LEAK_{pipe_id}"
    new_pipes = (f"{pipe_id}_A", f"{pipe_id}_B")
    xs = [start.coordinates[0], end.coordinates[0]]
    ys = [start.coordinates[1], end.coordinates[1]]
    coord = (sum(xs) / 2.0, sum(ys) / 2.0)
    elevation = (start.elevation + end.elevation) / 2.0
    length = pipe.length
    diameter = pipe.diameter
    roughness = pipe.roughness
    minor_loss = pipe.minor_loss
    status = pipe.initial_status
    wn.remove_link(pipe_id)
    wn.add_junction(new_node, base_demand=0.0, elevation=elevation,
                    coordinates=coord)
    wn.add_pipe(new_pipes[0], start.name, new_node, length=length / 2.0,
                diameter=diameter, roughness=roughness, minor_loss=minor_loss,
                initial_status=status)
    wn.add_pipe(new_pipes[1], new_node, end.name, length=length / 2.0,
                diameter=diameter, roughness=roughness, minor_loss=minor_loss,
                initial_status=status)
    return new_node, new_pipes, coord


def _pump_closed_at(config: ScenarioConfig, pump_id: str, tick: int) -> bool:
    hour = tick * config.timestep_minutes / 60.0
    for fault in config.faults:
        if isinstance(fault, PumpOutageFault) and fault.pump_id == pump_id:
            if fault.start_hour <= hour < fault.start_hour + fault.duration_hours:
                return True
    return False


def _configure_pumps(
    wn: WaterNetworkModel, config: ScenarioConfig, tick: int, *, baseline: bool
) -> None:
    for pump_id in PUMP_IDS:
        link = wn.get_link(pump_id)
        closed = False if baseline else _pump_closed_at(config, pump_id, tick)
        # WNTR 1.5 exposes `status` read-only; `initial_status` also sets the
        # user status used by the solver at t=0 (verified by introspection).
        link.initial_status = LinkStatus.Closed if closed else (
            LinkStatus.Open if pump_id == "PUMP_1" else LinkStatus.Closed
        )


class _Accumulator:
    def __init__(self, ticks: int, node_names: list[str], link_names: list[str]):
        self.ticks = ticks
        self.time_iso = [""] * (ticks + 1)
        self.pressure = {n: [0.0] * (ticks + 1) for n in node_names}
        self.demand = {n: [0.0] * (ticks + 1) for n in GRID_NODES}
        self.flow = {l: [0.0] * (ticks + 1) for l in link_names}
        self.tank_level = [0.0] * (ticks + 1)
        self.leak_flow = [0.0] * (ticks + 1)
        self.pump_status = {p: ["CLOSED"] * (ticks + 1) for p in PUMP_IDS}
        self.delivered = {z: [0.0] * (ticks + 1) for z in ("gov", "res", "com", "total")}
        self.leak_area = [0.0] * (ticks + 1)

    def fill(self, tick: int, values: dict[str, Any]) -> None:
        self.time_iso[tick] = values["time_iso"]
        for n, v in values["pressure"].items():
            self.pressure[n][tick] = v
        for n, v in values["demand"].items():
            self.demand[n][tick] = v
        for l, v in values["flow"].items():
            self.flow[l][tick] = v
        self.tank_level[tick] = values["tank_level"]
        self.leak_flow[tick] = values["leak_flow_lps"]
        for p, v in values["pump_status"].items():
            self.pump_status[p][tick] = v
        for z, v in values["delivered_lps"].items():
            self.delivered[z][tick] = v
        self.leak_area[tick] = values["leak_area_cm2"]

    def build(self, config: ScenarioConfig, leak_node: str | None,
              leak_pipe: str | None) -> TruthSeries:
        return TruthSeries(
            ticks=self.ticks,
            timestep_minutes=config.timestep_minutes,
            time_iso=self.time_iso,
            pressure=self.pressure,
            demand=self.demand,
            flow=self.flow,
            tank_level=self.tank_level,
            leak_flow_lps=self.leak_flow,
            pump_status=self.pump_status,
            delivered_lps=self.delivered,
            leak_node=leak_node,
            leak_pipe=leak_pipe,
            leak_area_cm2=self.leak_area,
        )


def _simulate(
    config: ScenarioConfig,
    provider: NetworkProvider,
    *,
    baseline: bool,
) -> TruthSeries:
    if not isinstance(provider, HypotheticalGridProvider):
        raise NotImplementedError("only the hypothetical provider is implemented")
    description = provider.describe()
    leak_fault = _leak_fault(config)
    leak_pipe = leak_fault.location.split(":", 1)[1] if leak_fault else None
    leak_node = f"LEAK_{leak_pipe}" if leak_pipe else None

    node_names = [n.id for n in description.nodes]
    link_names = [l.id for l in description.links]
    if leak_pipe is not None:
        if leak_pipe not in link_names:
            raise ValueError(
                f"leak location {leak_pipe} is not a pipe in this network")
        link_names = [name for name in link_names if name != leak_pipe]
        link_names.extend([f"{leak_pipe}_A", f"{leak_pipe}_B"])
        node_names.append(leak_node)

    boundaries = _chunk_boundaries(config)
    accumulator = _Accumulator(config.ticks, node_names, link_names)
    start_clock = datetime.fromisoformat(SIM_START)
    tank_level = 4.0  # TANK_INIT_LEVEL, replaced after the first chunk

    for index in range(len(boundaries) - 1):
        start_tick, end_tick = boundaries[index], boundaries[index + 1]
        chunk_ticks = end_tick - start_tick
        if chunk_ticks <= 0:
            continue
        chunk_start_hour = start_tick * config.timestep_minutes / 60.0
        wn = provider.build()
        _configure_demands(
            wn, provider, config, start_tick, chunk_ticks,
            apply_unforecast=not baseline,
        )
        if leak_pipe:
            split_pipe_for_leak(wn, leak_pipe)
        area_cm2 = 0.0
        if leak_fault is not None and not baseline:
            area_cm2 = _leak_area_cm2(leak_fault, chunk_start_hour)
            if area_cm2 > 0 and leak_node is not None:
                node = wn.get_node(leak_node)
                node.add_leak(
                    wn,
                    area=area_cm2 * 1e-4,
                    discharge_coeff=LEAK_DISCHARGE_COEFF,
                    start_time=0,
                )
        wn.get_node(TANK_ID).init_level = tank_level
        _configure_pumps(wn, config, start_tick, baseline=baseline)
        wn.options.time.duration = chunk_ticks * config.timestep_seconds
        wn.options.time.hydraulic_timestep = config.timestep_seconds
        wn.options.time.report_timestep = config.timestep_seconds
        wn.options.time.pattern_timestep = config.timestep_seconds

        result = WNTRSimulator(wn).run_sim()
        pressure_df = result.node["pressure"]
        demand_df = result.node["demand"]
        flow_df = result.link["flowrate"]
        status_df = result.link["status"]
        leak_df = result.node["leak_demand"]

        rows = chunk_ticks + 1
        first_row = 0 if start_tick == 0 else 1
        for local in range(first_row, rows):
            # Later chunks skip row 0 (it duplicates the carried state), so
            # row `local` always represents global tick start_tick + local.
            tick = start_tick + local
            if tick > config.ticks:
                break
            pressure = {n: _round(pressure_df.iloc[local][n]) for n in node_names}
            demand = {n: _round(demand_df.iloc[local][n]) for n in GRID_NODES}
            flow = {l: _round(flow_df.iloc[local][l]) for l in link_names}
            status = {
                p: ("CLOSED" if int(status_df.iloc[local][p]) == 0 else "OPEN")
                for p in PUMP_IDS
            }
            total_leak = sum(
                float(leak_df.iloc[local][n]) for n in leak_df.columns
            )
            delivered = {
                "gov": _round(sum(demand[n] for n in description.zones[0].node_ids) * 1000),
                "res": _round(sum(demand[n] for n in description.zones[1].node_ids) * 1000),
                "com": _round(sum(demand[n] for n in description.zones[2].node_ids) * 1000),
            }
            delivered["total"] = _round(sum(delivered.values()))
            sim_time = start_clock + timedelta(
                minutes=tick * config.timestep_minutes
            )
            accumulator.fill(tick, {
                "time_iso": sim_time.isoformat(timespec="seconds"),
                "pressure": pressure,
                "demand": demand,
                "flow": flow,
                "tank_level": _round(float(pressure_df.iloc[local][TANK_ID])),
                "leak_flow_lps": _round(total_leak * 1000.0),
                "pump_status": status,
                "delivered_lps": delivered,
                "leak_area_cm2": _round(area_cm2),
            })
        tank_level = float(pressure_df.iloc[-1][TANK_ID])

    return accumulator.build(config, leak_node, leak_pipe)


# ---------------------------------------------------------------------------
# Sensor measurement layer (separate from physics)
# ---------------------------------------------------------------------------

def _sensor_faults(config: ScenarioConfig) -> dict[str, list[Any]]:
    by_sensor: dict[str, list[Any]] = {}
    for fault in config.faults:
        if isinstance(fault, (SensorDriftFault, SensorStuckFault,
                              SensorDropoutFault)):
            by_sensor.setdefault(fault.sensor_id, []).append(fault)
    return by_sensor


def simulate_sensors(
    truth: TruthSeries,
    config: ScenarioConfig,
    provider: NetworkProvider = DEFAULT_PROVIDER,
) -> dict[str, list[float | None]]:
    """Create simulated measurements from ground truth, with noise and faults.

    Ground truth is never mixed into the returned readings except through the
    declared noise/fault model. A missing reading is `None`.
    """
    description = provider.describe()
    sensors = description.sensors
    rng = np.random.default_rng(config.seed)
    readings: dict[str, list[float | None]] = {
        s.id: [None] * (truth.ticks + 1) for s in sensors
    }
    faults = _sensor_faults(config)
    held: dict[str, float | None] = {}
    sigma = {s.id: s.sigma for s in sensors}
    kind = {s.id: s.kind for s in sensors}
    target = {s.id: s.target for s in sensors}

    for tick in range(truth.ticks + 1):
        hour = tick * config.timestep_minutes / 60.0
        for sensor in sensors:
            sid = sensor.id
            true_value = truth.sensor_value(kind[sid], target[sid], tick)
            if true_value is None:
                readings[sid][tick] = None
                continue
            if kind[sid] == "flow":
                # Ground truth stores WNTR SI flow (m3/s); sensors report L/s.
                true_value = true_value * 1000.0
            value = true_value + float(rng.normal(0.0, sigma[sid]))
            drift = 0.0
            missing = False
            stuck = False
            for fault in faults.get(sid, []):
                if isinstance(fault, SensorDriftFault) and hour >= fault.start_hour:
                    drift += fault.drift_per_hour * (hour - fault.start_hour)
                elif isinstance(fault, SensorStuckFault):
                    if fault.start_hour <= hour < fault.start_hour + fault.duration_hours:
                        stuck = True
                elif isinstance(fault, SensorDropoutFault):
                    if fault.start_hour <= hour < fault.start_hour + fault.duration_hours:
                        if float(rng.random()) < fault.probability:
                            missing = True
            value += drift
            if stuck:
                if sid not in held or held[sid] is None:
                    held[sid] = float(value)
                value = float(held[sid])
            else:
                held.pop(sid, None)
            readings[sid][tick] = None if missing else _round(value)
    return readings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_scenario(
    config: ScenarioConfig,
    provider: NetworkProvider = DEFAULT_PROVIDER,
) -> RunBundle:
    started = time.perf_counter()
    truth = _simulate(config, provider, baseline=False)
    baseline = _simulate(config, provider, baseline=True)
    readings = simulate_sensors(truth, config, provider)
    bundle = RunBundle(
        config=config,
        truth=truth,
        baseline=baseline,
        readings=readings,
        runtime_seconds=0.0,
        output_hash="",
    )
    bundle.output_hash = bundle.compute_hash()
    bundle.runtime_seconds = round(time.perf_counter() - started, 3)
    return bundle
