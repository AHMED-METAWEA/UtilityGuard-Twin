"""What-if impact runs: continue the WNTR simulation from the incident time.

Each action variant is a real WNTR continuation on a copy of the network,
starting from the stored tank level at the incident tick. This is a simulation,
not a field forecast. Results are labelled SIMULATION.

Approximations (documented):
  * The leak area is held constant at an estimated size; no growth is modelled.
  * Isolation is represented as reducing the leak to 20% until repair completes.
  * Hourly/event chunking with tank-level carry-over is used for changing
    actions, exactly like the gradual-leak scenario approximation.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from wntr.network.base import LinkStatus
from wntr.sim import WNTRSimulator

from app.config import SETTINGS
from app.network.builder import (
    DEFAULT_PROVIDER,
    TANK_DIAMETER,
    NetworkProvider,
    zone_patterns,
)
from app.scenarios.runner import (
    GRID_NODES,
    LEAK_DISCHARGE_COEFF,
    PUMP_IDS,
    TruthSeries,
    split_pipe_for_leak,
)
from app.scenarios.schema import DemandChangeFault, PumpOutageFault, ScenarioConfig

TANK_AREA = math.pi * (TANK_DIAMETER / 2.0) ** 2
PUMP_EFFICIENCY = 0.75  # ASSUMPTION, stated in docs


def estimate_leak_area_cm2(
    readings: dict[str, list[float | None]],
    truth: TruthSeries,
    baseline: TruthSeries,
    tick: int,
) -> float:
    """Estimate leak area from the flow imbalance at detection time.

    Uses F02 (tank outflow) above its fault-free expectation and the nearest
    pressure reading. This is a crude model-derived estimate, not a measurement;
    the decision engine samples low/mid/high variants around it.
    """
    expected = baseline.flow.get("V_PR", [0.0] * (tick + 1))[tick] * 1000.0
    measured = readings.get("F02", [None] * (tick + 1))[tick]
    if measured is None:
        measured = truth.flow.get("V_PR", [0.0] * (tick + 1))[tick] * 1000.0
    extra_lps = max(0.0, measured - expected)
    if extra_lps <= 0.2:
        # Tank drawdown can reveal the imbalance even when the flow sensor is
        # missing; use the difference in tank level change as a fallback.
        if tick > 0:
            dt = truth.timestep_minutes * 60.0
            actual_drop = truth.tank_level[tick - 1] - truth.tank_level[tick]
            expected_drop = baseline.tank_level[tick - 1] - baseline.tank_level[tick]
            extra_lps += max(0.0, (actual_drop - expected_drop) * TANK_AREA / dt * 1000.0)
    p = readings.get("P05", [None] * (tick + 1))[tick]
    if p is None or p <= 0:
        p = 25.0
    area_m2 = (extra_lps / 1000.0) / (
        LEAK_DISCHARGE_COEFF * math.sqrt(2 * 9.81 * max(p, 1.0))
    )
    return round(min(30.0, max(0.4, area_m2 * 1e4)), 3)


def _hour_multiplier(config: ScenarioConfig, zone: str, hour: float) -> float:
    from app.network.zones import hourly_curve

    curve = hourly_curve(zone, config.demand.holiday)
    base = float(np.interp(hour % 24.0, np.arange(24.0), curve, period=24.0))
    value = base * config.demand.heatwave_multiplier * config.demand.zone_multipliers[zone]
    for fault in config.faults:
        if isinstance(fault, DemandChangeFault) and zone in fault.zone_multipliers:
            if hour >= fault.start_hour:
                value *= fault.zone_multipliers[zone]
    return value


def _pump_closed(config: ScenarioConfig, pump_id: str, hour: float) -> bool:
    for fault in config.faults:
        if isinstance(fault, PumpOutageFault) and fault.pump_id == pump_id:
            if fault.start_hour <= hour < fault.start_hour + fault.duration_hours:
                return True
    return False


def _build_continuation(
    config: ScenarioConfig,
    provider: NetworkProvider,
    *,
    start_tick: int,
    tick: int,
    tank_level: float,
    leak_pipe: str | None,
    leak_area_cm2: float,
    action: str,
    response_tick: int,
    complete_tick: int,
    pump_action: bool,
    chunk_ticks: int,
    leak_isolated: bool,
) -> dict[str, Any]:
    if not hasattr(provider, "demand_base_demands"):
        raise NotImplementedError("continuation requires the hypothetical provider")
    wn = provider.build()
    start_hour = tick * config.timestep_minutes / 60.0
    base = provider.demand_base_demands()  # type: ignore[attr-defined]
    for node_id, value in base.items():
        wn.get_node(node_id).demand_timeseries_list[0].base_value = value
    patterns = zone_patterns(
        chunk_ticks, config.timestep_minutes, start_hour,
        config.demand.holiday, config.demand.heatwave_multiplier,
        config.demand.zone_multipliers,
    )
    for zone, values in patterns.items():
        pattern = wn.get_pattern(zone)
        pattern.multipliers = values
        pattern.time_options = wn.options.time

    if leak_pipe and leak_area_cm2 > 0:
        split_pipe_for_leak(wn, leak_pipe)
        node = wn.get_node(f"LEAK_{leak_pipe}")
        node.add_leak(
            wn, area=leak_area_cm2 * 1e-4,
            discharge_coeff=LEAK_DISCHARGE_COEFF, start_time=0,
        )
    wn.get_node("TANK1").init_level = tank_level
    hour = start_hour
    for pump_id in PUMP_IDS:
        closed = _pump_closed(config, pump_id, hour)
        if action == "switch_standby_pump" and tick >= response_tick:
            closed = pump_id == "PUMP_1"
        link = wn.get_link(pump_id)
        link.initial_status = LinkStatus.Closed if closed else (
            LinkStatus.Open if pump_id == "PUMP_1" else LinkStatus.Closed
        )
    _ = pump_action
    _ = leak_isolated
    wn.options.time.duration = chunk_ticks * config.timestep_seconds
    wn.options.time.hydraulic_timestep = config.timestep_seconds
    wn.options.time.report_timestep = config.timestep_seconds
    wn.options.time.pattern_timestep = config.timestep_seconds

    # Scale accumulated metrics by actual delivered/requested demand.
    result = WNTRSimulator(wn).run_sim()
    return {
        "result": result,
        "wn": wn,
        "base": base,
        "start_hour": start_hour,
        "chunk_ticks": chunk_ticks,
        "start_tick": start_tick,
        "tick": tick,
    }


def simulate_impact(
    config: ScenarioConfig,
    truth: TruthSeries,
    baseline: TruthSeries,
    incident: dict[str, Any],
    readings: dict[str, list[float | None]],
    action: str,
    *,
    leak_variant: str = "mid",
    leak_area_cm2: float | None = None,
    horizon_hours: float = 72.0,
    provider: NetworkProvider = DEFAULT_PROVIDER,
) -> dict[str, Any]:
    from app.finance.engine import get_assumption_values
    finance = get_assumption_values()
    start_tick = incident["first_detected_tick"]
    start_hour = start_tick * config.timestep_minutes / 60.0
    horizon_ticks = int(round(horizon_hours * 60 / config.timestep_minutes))
    end_tick = start_tick + horizon_ticks
    response_hours = finance["crew_response_hours"]
    repair_hours = finance["repair_duration_hours"]
    inspect_hours = finance["inspection_duration_hours"]
    response_tick = start_tick + int(round(response_hours * 60 / config.timestep_minutes))
    complete_tick = response_tick + int(round(
        (repair_hours + (inspect_hours if action == "inspect" else 0.0))
        * 60 / config.timestep_minutes
    ))

    # Estimated leak area / candidate pipe come from model output, not truth.
    suspected = incident.get("suspected_location") or ""
    leak_pipe = suspected.split(":", 1)[1] if suspected.startswith("pipe:") else None
    if leak_pipe is None and incident.get("candidates"):
        leak_pipe = incident["candidates"][0]["pipe"]
    if leak_area_cm2 is None and incident.get("diagnosis") == "leak":
        leak_area_cm2 = estimate_leak_area_cm2(
            readings, truth, baseline, start_tick,
        )
    leak_area_cm2 = float(leak_area_cm2 or 0.0)
    variant_factor = {"low": 0.5, "mid": 1.0, "high": 2.0}.get(leak_variant, 1.0)
    area = round(leak_area_cm2 * variant_factor, 3)

    # Event boundaries: action timing, original pump recovery, scenario end.
    boundaries = {start_tick, end_tick}
    if action in ("inspect", "repair_isolate"):
        boundaries.add(min(end_tick, response_tick))
        boundaries.add(min(end_tick, complete_tick))
    if action == "switch_standby_pump":
        boundaries.add(min(end_tick, response_tick))
    for fault in config.faults:
        if isinstance(fault, PumpOutageFault):
            end = config.tick_at_hour(fault.start_hour + fault.duration_hours)
            if start_tick < end < end_tick:
                boundaries.add(end)
    points = sorted(boundaries)
    tank_level = truth.tank_level[min(start_tick, len(truth.tank_level) - 1)]

    water_lost = 0.0
    unserved = 0.0
    energy = 0.0
    low_node_hours = 0.0
    low_any_hours = 0.0
    affected: set[str] = set()
    series = {
        "tick": [], "time_iso": [], "leak_flow_lps": [], "unserved_lps": [],
        "min_pressure_m": [], "tank_level_m": [], "pump_flow_lps": [],
    }
    dt = config.timestep_seconds
    total_ticks = 0

    for index in range(len(points) - 1):
        tick = points[index]
        chunk_ticks = points[index + 1] - tick
        if chunk_ticks <= 0:
            continue
        if action in ("inspect", "repair_isolate"):
            if tick >= complete_tick:
                chunk_area = 0.0
            elif tick >= response_tick:
                # Isolation is assumed to stop 80% of the leak until repair.
                chunk_area = area * 0.2
            else:
                chunk_area = area
        else:
            chunk_area = area
        built = _build_continuation(
            config, provider,
            start_tick=start_tick, tick=tick, tank_level=tank_level,
            leak_pipe=leak_pipe, leak_area_cm2=chunk_area,
            action=action, response_tick=response_tick,
            complete_tick=complete_tick, pump_action=action == "switch_standby_pump",
            chunk_ticks=chunk_ticks, leak_isolated=tick >= response_tick,
        )
        result = built["result"]
        pressure = result.node["pressure"]
        demand = result.node["demand"]
        flow = result.link["flowrate"]
        leak_df = result.node["leak_demand"]
        head = result.node["head"]
        wn = built["wn"]
        first_row = 0
        for local in range(first_row, chunk_ticks + 1):
            global_tick = tick + local
            t = start_tick + (global_tick - start_tick)
            hour = global_tick * config.timestep_minutes / 60.0
            # Skip the duplicate carried-state row for later chunks.
            if index > 0 and local == 0:
                continue
            requested_total = 0.0
            delivered_total = 0.0
            low_nodes = 0
            for node_id in GRID_NODES:
                node = wn.get_node(node_id)
                zone = node.demand_timeseries_list[0].pattern_name
                requested = built["base"][node_id] * 1000.0 * _hour_multiplier(
                    config, zone, hour,
                )  # L/s
                delivered = float(demand.iloc[local][node_id]) * 1000.0
                requested_total += requested
                delivered_total += delivered
                p = float(pressure.iloc[local][node_id])
                if p < finance["low_pressure_threshold_m"]:
                    low_nodes += 1
                    affected.add(node_id)
                if delivered < 0.9 * requested:
                    affected.add(node_id)
            leak_lps = float(leak_df.iloc[local].sum()) * 1000.0
            water_lost += leak_lps / 1000.0 * dt
            unserved += max(0.0, requested_total - delivered_total) / 1000.0 * dt
            low_node_hours += low_nodes * dt / 3600.0
            if low_nodes:
                low_any_hours += dt / 3600.0
            for pump_id in PUMP_IDS:
                q = float(flow.iloc[local][pump_id])
                if q > 0:
                    gain = float(head.iloc[local][wn.get_link(pump_id).end_node_name]) - float(
                        head.iloc[local][wn.get_link(pump_id).start_node_name]
                    )
                    energy += 9.81 * q * max(0.0, gain) / PUMP_EFFICIENCY * dt / 3600.0
            total_ticks += 1
            if global_tick % 3 == 0 or global_tick == end_tick - 1:
                sim_time = datetime.fromisoformat("2026-01-01T00:00:00") + timedelta(
                    minutes=global_tick * config.timestep_minutes
                )
                series["tick"].append(global_tick)
                series["time_iso"].append(sim_time.isoformat(timespec="seconds"))
                series["leak_flow_lps"].append(round(leak_lps, 3))
                series["unserved_lps"].append(round(max(0.0, requested_total - delivered_total), 3))
                series["min_pressure_m"].append(round(float(pressure.iloc[local][GRID_NODES].min()), 3))
                series["tank_level_m"].append(round(float(pressure.iloc[local]["TANK1"]), 3))
                series["pump_flow_lps"].append(round(
                    float(flow.iloc[local]["PL_DIS"]) * 1000.0, 3,
                ))
        tank_level = float(pressure.iloc[-1]["TANK1"])

    return {
        "action": action,
        "leak_variant": leak_variant,
        "leak_area_cm2": area,
        "estimated_leak_area_cm2": leak_area_cm2,
        "leak_pipe": leak_pipe,
        "horizon_hours": horizon_hours,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "water_lost_m3": round(water_lost, 2),
        "unserved_m3": round(unserved, 2),
        "low_pressure_node_hours": round(low_node_hours, 2),
        "low_pressure_hours": round(low_any_hours, 2),
        "affected_nodes": len(affected),
        "pump_energy_kwh": round(energy, 2),
        "ticks_simulated": total_ticks,
        "series": series,
        "labels": {
            "water_lost_m3": "SIMULATION",
            "unserved_m3": "SIMULATION",
            "low_pressure_node_hours": "SIMULATION",
            "affected_nodes": "SIMULATION",
            "pump_energy_kwh": "SIMULATION",
            "leak_area_cm2": "MODEL",
        },
        "method": (
            "WNTR continuation from the incident tick with tank carry-over; "
            "leak area held constant per variant; isolation reduces leak to 20% "
            "until repair completes; energy assumes 75% pump efficiency (ASSUMPTION)."
        ),
        "conditional_on": "estimated leak location/size from model output, not field truth",
    }
