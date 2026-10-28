"""Hydraulic faults of a scenario as WNTR changes, plus their hidden truth events (card D-03).

Rules (every WNTR call used here is declared in the WNTR API manifest):
- a fault starts at the first tick at or after its `start_hour` (ceil); a fault that would start
  at or after the last tick is refused;
- leak and burst: the pipe is split at its midpoint (`wntr.morph.split_pipe`) and the new
  junction gets a WNTR leak (`Junction.add_leak`) of `final_area_cm2` from the start tick on; the
  junction's elevation is the mean of the pipe's end elevations;
- gradual leak: `leak_area` has no setter in WNTR 1.5.0, so the ramp is a staircase of
  `GRADUAL_STEPS` leaks of equal area along the pipe (each split halves the remaining downstream
  segment), starting at k x ramp / steps (k = 0 .. steps - 1); the area reaches `final_area_cm2`
  in the last step, an approximation of the linear ramp (ASSUMPTION);
- pump outage: the pump discharges through a lossless gate valve (TCV, loss coefficient 0, added
  by `build_model`) that exact time controls close at the start tick and reopen at the end tick;
  the pump's own status and level controls are untouched, so the run equals the fault-free run
  before the onset (neither `Pump.add_outage` nor a priority time control holds a pump against
  a level control in WNTR 1.5.0); the
  station's first free standby pump takes over (opened at the start, switched by the duty pump's
  level controls while the outage lasts, closed at the end)
  (`Pump.add_outage` is not used: its rule acts two steps late in WNTR 1.5.0);
- fire flow: extra demand at the node, added to the demand series (`add_fire_flows`);
- the leak's outflow is the hidden truth channel `leak:<pipe>` (m3/s, summed over its steps);
- each fault is a hidden `TruthEvent` targeting the bare element id (the store tags that element's
  channels with it);
Leaks need the WNTR simulator (EPANET has no leak model): an EPANET run with a leak is refused.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import wntr  # type: ignore[import-untyped]
from ug_core.timebase import Timebase
from ug_core.truth import TruthEvent

from ug_water.network.model import Network

# WNTR's default orifice discharge coefficient for a leak (ASSUMPTION, no field calibration).
LEAK_DISCHARGE_COEFF = 0.75
GRADUAL_STEPS = 4
HYDRAULIC_TYPES = frozenset({"leak", "burst", "pump_outage", "fire_flow"})


@dataclass(frozen=True)
class LeakPlan:
    pipe: str
    steps: tuple[tuple[int, float], ...]  # (start time s, area m2), in time order


@dataclass(frozen=True)
class OutagePlan:
    pump: str
    start_s: int
    end_s: int | None
    standby: str | None = None  # the station's standby pump that takes over
    horizon_s: int = (
        0  # the run's end (n_ticks x step): an open outage lasts until then
    )


@dataclass(frozen=True)
class FireFlowPlan:
    node: str
    start_tick: int
    end_tick: int | None
    flow_m3s: float


@dataclass(frozen=True)
class FaultPlan:
    leaks: tuple[LeakPlan, ...] = ()
    outages: tuple[OutagePlan, ...] = ()
    fire_flows: tuple[FireFlowPlan, ...] = ()
    events: tuple[TruthEvent, ...] = ()


def _tick(hours: float, timebase: Timebase, what: str) -> int:
    tick = math.ceil(round(hours * 3600.0 / timebase.step_seconds, 9))
    if tick >= timebase.n_ticks - 1:
        raise ValueError(f"{what} starts at or after the last tick of the run")
    return tick


def _end(start_hour: float, hours: float, timebase: Timebase) -> int | None:
    # Rounded once, from the absolute end time (not start tick + rounded duration).
    end = math.ceil(round((start_hour + hours) * 3600.0 / timebase.step_seconds, 9))
    return None if end >= timebase.n_ticks else end


def plan_faults(
    faults: Sequence[Mapping[str, Any]], network: Network, timebase: Timebase
) -> FaultPlan:
    """Check the scenario's faults against the network and the horizon. Raises `ValueError`."""
    pipes = {p.id for p in network.pipes}
    pumps = {p.id for p in network.pumps}
    junctions = {j.id for j in network.junctions}
    step = timebase.step_seconds
    leaks: list[LeakPlan] = []
    outages: list[OutagePlan] = []
    fires: list[FireFlowPlan] = []
    events: list[TruthEvent] = []
    for fault in faults:
        kind = fault["type"]
        if kind not in HYDRAULIC_TYPES:
            raise ValueError(f"fault type {kind!r} is not in the demo slice (D-03)")
        start = _tick(fault["start_hour"], timebase, f"fault {kind}")
        if kind in ("leak", "burst"):
            pipe = fault["location"].removeprefix("pipe:")
            if pipe not in pipes:
                raise ValueError(f"unknown pipe {pipe!r} in fault {kind}")
            if any(leak.pipe == pipe for leak in leaks):
                raise ValueError(f"more than one leak on pipe {pipe!r}")
            area = fault["final_area_cm2"] / 1e4
            if fault.get("profile") == "gradual":
                ramp = fault["ramp_hours"] * 3600.0
                steps = tuple(
                    (
                        math.ceil(
                            round((start * step + k * ramp / GRADUAL_STEPS) / step, 9)
                        )
                        * step,
                        area / GRADUAL_STEPS,
                    )
                    for k in range(GRADUAL_STEPS)
                )
            else:
                steps = ((start * step, area),)
            leaks.append(LeakPlan(pipe, steps))
            parameters = {
                k: v for k, v in fault.items() if k not in ("type", "start_hour")
            }
            events.append(TruthEvent(kind, pipe, start, None, parameters))
        elif kind == "pump_outage":
            pump = fault["pump_id"]
            if pump not in pumps:
                raise ValueError(f"unknown pump {pump!r} in fault pump_outage")
            end = _end(fault["start_hour"], fault["duration_hours"], timebase)
            if pump in {o.pump for o in outages}:
                raise ValueError(f"more than one outage of pump {pump!r}")
            outages.append(
                OutagePlan(
                    pump,
                    start * step,
                    None if end is None else end * step,
                    None,
                    timebase.n_ticks * step,
                )
            )
            events.append(TruthEvent(kind, pump, start, end, {}))
        else:
            node = fault["node"].removeprefix("node:")
            if node not in junctions:
                raise ValueError(f"unknown junction {node!r} in fault fire_flow")
            end = _end(fault["start_hour"], fault["duration_hours"], timebase)
            flow = fault["flow_l_s"] / 1000.0
            fires.append(FireFlowPlan(node, start, end, flow))
            events.append(
                TruthEvent(kind, node, start, end, {"flow_l_s": fault["flow_l_s"]})
            )
    outages = _assign_standbys(outages, network)
    standby = {o.pump: o.standby for o in outages}
    events = [
        replace(e, parameters={"standby": standby[e.target]})
        if e.kind == "pump_outage"
        else e
        for e in events
    ]
    return FaultPlan(tuple(leaks), tuple(outages), tuple(fires), tuple(events))


def _assign_standbys(outages: list[OutagePlan], network: Network) -> list[OutagePlan]:
    """Give each outage the station's first standby that is free over its window.

    Outages are taken in (start, pump) order, so the result does not depend on the order of the
    scenario's list; a standby is busy only while an earlier assigned window overlaps.
    """
    pumps = {p.id: p for p in network.pumps}
    out = {o.pump for o in outages}
    done: list[OutagePlan] = []
    for outage in sorted(outages, key=lambda o: (o.start_s, o.pump)):
        end = outage.end_s if outage.end_s is not None else outage.horizon_s
        busy = {
            d.standby
            for d in done
            if d.standby is not None
            and d.start_s < end
            and outage.start_s < (d.end_s if d.end_s is not None else d.horizon_s)
        }
        standby = next(
            (
                p.id
                for p in network.pumps
                if p.station == pumps[outage.pump].station
                and p.role == "standby"
                and p.id not in out | busy
            ),
            None,
        )
        done.append(replace(outage, standby=standby))
    return done


# Any size works: a TCV with loss coefficient 0 has no head loss.
GATE_DIAMETER_M = 1.0


def gate_node(pump: str) -> str:
    return f"{pump}~gate_in"


def gate_valve(pump: str) -> str:
    return f"{pump}~gate"


def leak_node(pipe: str, k: int) -> str:
    return f"{pipe}~leak{k}"


def add_fire_flows(demand: Any, plan: FaultPlan) -> Any:
    """The demand series with the fire flows added (a copy; `demand` is a dataclass)."""
    if not plan.fire_flows:
        return demand
    values = np.array(demand.values, dtype=float)
    column = {jid: k for k, jid in enumerate(demand.junction_ids)}
    for fire in plan.fire_flows:
        values[fire.start_tick : fire.end_tick, column[fire.node]] += fire.flow_m3s
    return replace(demand, values=values)


def apply_faults(wn: Any, network: Network, plan: FaultPlan) -> None:
    """Add the leaks and outages of the plan to the WNTR model, in place."""
    elevation = {j.id: j.elevation for j in network.junctions}
    for leak in plan.leaks:
        link = wn.get_link(leak.pipe)
        ends = [
            elevation[n]
            for n in (link.start_node_name, link.end_node_name)
            if n in elevation
        ]
        level = sum(ends) / len(ends) if ends else 0.0
        segment = leak.pipe
        for k, (start_s, area) in enumerate(leak.steps):
            node = leak_node(leak.pipe, k)
            # Split the downstream segment at its midpoint; the new node ends `segment`.
            wntr.morph.split_pipe(
                wn, segment, f"{leak.pipe}~{k + 1}", node, return_copy=False
            )
            segment = f"{leak.pipe}~{k + 1}"
            junction = wn.get_node(node)
            junction.elevation = level
            junction.add_leak(
                wn, area=area, discharge_coeff=LEAK_DISCHARGE_COEFF, start_time=start_s
            )
    controls = wntr.network.controls
    for outage in plan.outages:
        pump = wn.get_link(outage.pump)
        status = type(pump.status)  # WNTR's LinkStatus, read from the pump
        gate = gate_valve(outage.pump)
        times = [(gate, outage.start_s, status.Closed, "start")]
        if outage.end_s is not None:
            times.append((gate, outage.end_s, status.Open, "end"))
        if outage.standby is not None:
            # Failover: the standby starts with the outage, follows the duty pump's level
            # controls while it lasts, and stops at its end.
            times.append((outage.standby, outage.start_s, status.Open, "start"))
            if outage.end_s is not None:
                times.append((outage.standby, outage.end_s, status.Closed, "end"))
            backup = wn.get_link(outage.standby)
            for control in network.controls:
                if control.pump != outage.pump:
                    continue
                tank = wn.get_node(control.tank)
                for suffix, relation, level, value in (
                    ("on", "<", control.on_below_m, status.Open),
                    ("off", ">", control.off_above_m, status.Closed),
                ):
                    wn.add_control(
                        f"outage:{outage.standby}:{control.id}:{suffix}",
                        controls.Control(
                            controls.AndCondition(
                                controls.ValueCondition(tank, "level", relation, level),
                                inside(wn, outage),
                            ),
                            controls.ControlAction(backup, "status", value),
                        ),
                    )
        for link, time_s, value, suffix in times:
            wn.add_control(
                f"outage:{outage.pump}:{link}:{suffix}",
                controls.Control(
                    controls.SimTimeCondition(wn, "=", time_s),
                    controls.ControlAction(wn.get_link(link), "status", value),
                ),
            )


def inside(wn: Any, outage: OutagePlan) -> Any:
    """True while the outage lasts (from its start, until its end if any)."""
    controls = wntr.network.controls
    after = controls.SimTimeCondition(wn, ">=", outage.start_s)
    if outage.end_s is None:
        return after
    return controls.AndCondition(
        after, controls.SimTimeCondition(wn, "<", outage.end_s)
    )
