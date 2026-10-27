"""Turn a `Network` and a demand series into a WNTR model.

Mapping rules (every WNTR call used here is declared in the WNTR API manifest):
- each junction gets its own demand pattern: base demand = the mean of its series, multipliers =
  series / mean, one value per tick (a junction whose series is all zero gets base 0, no pattern);
  WNTR reads pattern value k at time k x step, so tick k of the series is the demand at tick k;
- duty pumps start open, standby pumps closed; each pump has its own head curve; a level
  control switches its pump on below a tank level and off above another (two WNTR controls);
- isolation valves are throttle control valves (TCV) with loss coefficient 0, open; a PRV keeps
  its setting (m of pressure head downstream);
- the time step of the hydraulics and the patterns is the step of the demand series, which must
  equal `hydraulic_step_s`; the duration is (ticks - 1) x step; `WNTRSimulator` reports every
  solved time (`"ALL"`), EPANET every tick;
- pressure-driven demand with the settings of `HydraulicOptions`, Hazen-Williams head loss.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import wntr  # type: ignore[import-untyped]
from ug_core.timebase import Timebase

from ug_water.network.model import Network
from ug_water.solver.options import HydraulicOptions


class DemandInput(Protocol):
    """What the engine needs from a demand series (the demand model's `DemandSeries` is one)."""

    @property
    def timebase(self) -> Timebase: ...

    @property
    def junction_ids(self) -> tuple[str, ...]: ...

    @property
    def values(self) -> np.ndarray: ...  # (ticks, junctions), m3/s


def check_demand(
    network: Network, demand: DemandInput, options: HydraulicOptions
) -> None:
    """Refuse a demand series that does not fit the network or the engine."""
    expected = tuple(sorted(j.id for j in network.junctions))
    if tuple(demand.junction_ids) != expected:
        missing = sorted(set(expected) - set(demand.junction_ids))
        extra = sorted(set(demand.junction_ids) - set(expected))
        raise ValueError(
            "the demand series must list exactly the network's junctions, sorted; "
            f"missing {missing[:5]}, extra {extra[:5]}"
        )
    values = np.asarray(demand.values)
    ticks = demand.timebase.n_ticks
    if values.shape != (ticks, len(expected)):
        raise ValueError(
            f"demand values have shape {values.shape}, expected {(ticks, len(expected))}"
        )
    if ticks < 2:
        raise ValueError("a hydraulic run needs at least two ticks")
    if demand.timebase.step_seconds != options.hydraulic_step_s:
        raise ValueError(
            f"the demand step is {demand.timebase.step_seconds} s, the hydraulic step "
            f"{options.hydraulic_step_s} s"
        )
    if not np.isfinite(values).all():
        raise ValueError("the demand series holds a non-finite value")
    if (values < 0).any():
        raise ValueError("the demand series holds a negative value")


def build_model(
    network: Network, demand: DemandInput, options: HydraulicOptions
) -> Any:
    """The WNTR model of the network with the demand series (a `WaterNetworkModel`)."""
    check_demand(network, demand, options)
    values = np.asarray(demand.values, dtype=float)
    column = {jid: k for k, jid in enumerate(demand.junction_ids)}
    wn = wntr.network.WaterNetworkModel()
    for junction in network.junctions:
        series = values[:, column[junction.id]]
        base = float(series.mean())
        pattern = None
        if base > 0:
            pattern = f"demand:{junction.id}"
            wn.add_pattern(pattern, [float(v) for v in series / base])
        wn.add_junction(
            junction.id,
            base_demand=base,
            demand_pattern=pattern,
            elevation=junction.elevation,
            coordinates=(junction.x, junction.y),
        )
    for reservoir in network.reservoirs:
        wn.add_reservoir(
            reservoir.id,
            base_head=reservoir.head,
            coordinates=(reservoir.x, reservoir.y),
        )
    for tank in network.tanks:
        wn.add_tank(
            tank.id,
            elevation=tank.elevation,
            init_level=tank.init_level,
            min_level=tank.min_level,
            max_level=tank.max_level,
            diameter=tank.diameter,
            coordinates=(tank.x, tank.y),
        )
    for pipe in network.pipes:
        wn.add_pipe(
            pipe.id,
            pipe.start,
            pipe.end,
            length=pipe.length,
            diameter=pipe.diameter,
            roughness=pipe.roughness,
            minor_loss=pipe.minor_loss,
        )
    for pump in network.pumps:
        if len(pump.curve) == 2:
            # WNTR 1.5 computes the slope of a two-point curve from squared flows but solves it
            # as a straight line (wntr/network/elements.py:1438-1441): the operating point is
            # wrong without any error (review round 2). One or three or more points only.
            raise ValueError(
                f"pump {pump.id}: a two-point head curve is solved wrongly by WNTR 1.5; "
                "give one point or three or more"
            )
        curve = f"head:{pump.id}"
        wn.add_curve(curve, "HEAD", [[q, h] for q, h in pump.curve])
        wn.add_pump(
            pump.id,
            pump.start,
            pump.end,
            pump_type="HEAD",
            pump_parameter=curve,
            initial_status="OPEN" if pump.role == "duty" else "CLOSED",
        )
    for valve in network.valves:
        if valve.kind == "prv":
            wn.add_valve(
                valve.id,
                valve.start,
                valve.end,
                diameter=valve.diameter,
                valve_type="PRV",
                initial_setting=valve.setting,
                initial_status="ACTIVE",
            )
        else:
            wn.add_valve(
                valve.id,
                valve.start,
                valve.end,
                diameter=valve.diameter,
                valve_type="TCV",
                initial_setting=0.0,
                initial_status="OPEN",
            )
    for control in network.controls:
        # A pump switched by a tank level: two WNTR controls, on below and off above.
        tank, pump = wn.get_node(control.tank), wn.get_link(control.pump)
        status = type(
            pump.status
        )  # WNTR's LinkStatus, read from the pump (members declared)
        for suffix, relation, level, value in (
            ("on", "<", control.on_below_m, status.Open),
            ("off", ">", control.off_above_m, status.Closed),
        ):
            wn.add_control(
                f"{control.id}:{suffix}",
                wntr.network.controls.Control(
                    wntr.network.controls.ValueCondition(
                        tank, "level", relation, level
                    ),
                    wntr.network.controls.ControlAction(pump, "status", value),
                ),
            )
    step = demand.timebase.step_seconds
    wn.options.time.duration = (demand.timebase.n_ticks - 1) * step
    wn.options.time.hydraulic_timestep = step
    wn.options.time.pattern_timestep = step
    # WNTRSimulator reports every solved time (extra steps when a tank reaches a limit or a
    # control acts), so the engine can integrate energy over them; EPANET cannot ("ALL" is a
    # WNTRSimulator option) and reports at the ticks.
    wn.options.time.report_timestep = "ALL" if options.engine == "wntr" else step
    wn.options.hydraulic.headloss = "H-W"
    # Pressure-driven demand: WNTR accepts "PDD" and stores it as "PDA" (its setter, 1.5.0).
    wn.options.hydraulic.demand_model = "PDA"
    wn.options.hydraulic.required_pressure = options.required_pressure_m
    wn.options.hydraulic.minimum_pressure = options.minimum_pressure_m
    wn.options.hydraulic.pressure_exponent = options.pressure_exponent
    return wn
