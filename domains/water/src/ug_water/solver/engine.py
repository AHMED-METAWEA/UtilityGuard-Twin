"""Run the hydraulics of a network with a demand series and return the twin's truth.

The engine is WNTR's `WNTRSimulator` (its leak model is what the fault cards use) or, on request,
WNTR's `EpanetSimulator` (EPANET 2.2; no leaks), both with pressure-driven demand. Results become
a `TruthSeries` (label `SIMULATION`) with one channel per quantity and element, named
`"<quantity>:<element id>"`, sampled at the ticks of the demand series:
- junctions: `pressure` (m), `head` (m), `demand` (delivered, m3/s);
- tanks: `level` (m above the tank bottom) and `head` (m);
- pipes, pumps and valves: `flowrate` (m3/s); pipes also `velocity` (m/s);
- pumps: `power` (kW).

Between two ticks WNTR may solve extra hydraulic steps when something changes (a tank reaches a
level limit, a control acts). `WNTRSimulator` reports all of them (`report_timestep = "ALL"`): the
truth is sampled at the ticks, and the energy of a pump integrates its power over every interval
between two solved times, the power at the start of each interval held to its end, as EPANET does
for its own steps. `EpanetSimulator` cannot report those extra steps, so it returns no energy
(`None`, never a number that may be wrong).

Pump power is `rho * g * Q * (H_out - H_in) / efficiency`, from the flow through the pump and the
heads at its two ends; it is zero when the pump carries no flow. Errors, never values: a
simulation that does not converge; a non-finite result; a table whose time axis differs from the
others or misses a tick; reverse flow through a pump; a pump that carries flow while losing head
(it runs past the flow where its curve reaches zero head, which WNTR only warns about).
"""

from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import wntr  # type: ignore[import-untyped]
from ug_core.canonical import canonical_json, sha256_hex
from ug_core.numeric import round_for_hash
from ug_core.truth import TruthSeries

from ug_water.network.model import Network
from ug_water.solver.build import DemandInput, build_model
from ug_water.solver.faults import FaultPlan, leak_node
from ug_water.solver.options import HydraulicOptions, load_options

LABEL = "SIMULATION"
# Reverse flow through a pump smaller than this (m3/s) is numerical noise and counts as none.
PUMP_FLOW_NOISE = 1e-9
# Head lost across a pump carrying flow beyond this (m) means it runs past its curve.
PUMP_HEAD_NOISE = 1e-6


class HydraulicsError(RuntimeError):
    """The hydraulics could not be computed, or the results cannot be trusted."""


@dataclass(frozen=True)
class HydraulicResult:
    truth: TruthSeries
    energy_kwh: Mapping[str, float] | None  # per pump over the run; None: not computed
    engine: str
    options_hash: str
    label: str = LABEL

    @property
    def total_energy_kwh(self) -> float | None:
        if self.energy_kwh is None:
            return None
        return math.fsum(self.energy_kwh.values())

    def content_hash(self) -> str:
        payload = {
            "truth": self.truth.content_hash(),
            "energy_kwh": None
            if self.energy_kwh is None
            else {k: round_for_hash(v) for k, v in sorted(self.energy_kwh.items())},
            "engine": self.engine,
            "options": self.options_hash,
            "label": self.label,
        }
        return sha256_hex(canonical_json(payload))


def simulate(
    network: Network,
    demand: DemandInput,
    options: HydraulicOptions | None = None,
    faults: FaultPlan | None = None,
    channels: Collection[str] | None = None,
) -> HydraulicResult:
    """The truth of the network under the demand series and the faults' plan (`plan_faults`).

    Fire flows must already be in `demand` (`add_fire_flows`). `channels`, when given, keeps
    only those truth channels (the solve is the same; it saves memory, e.g. for the expectation,
    which needs only the sensors' channels). Raises `HydraulicsError`.
    """
    options = options or load_options()
    try:
        wn = build_model(network, demand, options, faults)
    except ValueError as exc:
        raise HydraulicsError(
            f"the network or the demand cannot be modelled: {exc}"
        ) from exc
    results = _run(wn, options)
    return _truth(network, demand, results, options, faults or FaultPlan(), channels)


def _run(wn: Any, options: HydraulicOptions) -> Any:
    try:
        if options.engine == "wntr":
            return wntr.sim.WNTRSimulator(wn).run_sim(convergence_error=True)
        with tempfile.TemporaryDirectory(prefix="ug-epanet-") as folder:
            return wntr.sim.EpanetSimulator(wn).run_sim(
                file_prefix=os.path.join(folder, "run"), convergence_error=True
            )
    except (
        Exception
    ) as exc:  # WNTR reports non-convergence as RuntimeError, EPANET as others
        raise HydraulicsError(
            f"the {options.engine} engine did not solve the network: {exc}. "
            "Check the network first (network validation, T-B1-014)."
        ) from exc


class _Results:
    """The result tables on one checked time axis: every table must carry exactly the axis of
    the node pressures, which must start at 0, rise strictly and hold every tick."""

    def __init__(self, results: Any, timebase: Any) -> None:
        self.results = results
        step = timebase.step_seconds
        reference = results.node["pressure"].index
        times = np.asarray(reference, dtype=float)
        expected = np.arange(timebase.n_ticks, dtype=float) * step
        if (
            len(times) == 0
            or not np.isfinite(times).all()
            or times[0] != 0
            or (np.diff(times) <= 0).any()
            or times[-1] != expected[-1]
            or not np.isin(expected, times).all()
        ):
            raise HydraulicsError(
                "the results' time axis is not the demand series' axis "
                f"({len(times)} solved times, {len(expected)} ticks at {step} s expected)"
            )
        self.reference = reference
        self.times = times
        self.ticks = np.searchsorted(times, expected)
        if not np.array_equal(times[self.ticks], expected):
            raise HydraulicsError(
                "the results' time axis does not hold every tick exactly"
            )

    def frame(self, table: str, key: str, ids: list[str], what: str) -> np.ndarray:
        """Values at every solved time, shape (times, ids)."""
        frame = getattr(self.results, table)[key]
        if not frame.index.equals(self.reference):
            raise HydraulicsError(
                f"the time axis of the {what} table differs from the pressure table's"
            )
        missing = sorted(set(ids) - set(frame.columns))
        if missing:
            raise HydraulicsError(f"the results hold no {what} for {missing[:5]}")
        values = frame[ids].to_numpy(dtype=float)
        bad = ~np.isfinite(values)
        if bad.any():
            row, column = (int(i) for i in np.argwhere(bad)[0])
            raise HydraulicsError(
                f"non-finite {what} for {ids[column]} at {self.times[row]:g} s: "
                f"{values[row, column]}"
            )
        return values

    def at_ticks(self, values: np.ndarray) -> np.ndarray:
        return values[self.ticks]


def _truth(
    network: Network,
    demand: DemandInput,
    results: Any,
    options: HydraulicOptions,
    faults: FaultPlan,
    keep: Collection[str] | None = None,
) -> HydraulicResult:
    axis = _Results(results, demand.timebase)
    channels: dict[str, np.ndarray] = {}
    junctions = [j.id for j in network.junctions]
    for key in ("pressure", "head", "demand"):
        values = axis.at_ticks(axis.frame("node", key, junctions, f"junction {key}"))
        for k, jid in enumerate(junctions):
            channels[f"{key}:{jid}"] = values[:, k]
    tanks = list(network.tanks)
    if tanks:
        heads = axis.at_ticks(
            axis.frame("node", "head", [t.id for t in tanks], "tank head")
        )
        for k, tank in enumerate(tanks):
            channels[f"head:{tank.id}"] = heads[:, k]
            channels[f"level:{tank.id}"] = heads[:, k] - tank.elevation
    links = [
        *(p.id for p in network.pipes),
        *(p.id for p in network.pumps),
        *(v.id for v in network.valves),
    ]
    flows = axis.frame("link", "flowrate", links, "flow")
    # Index the ticks once: one copy per link would also keep every copy alive through its
    # column view (gigabytes on the standard tier).
    tick_flows = axis.at_ticks(flows)
    for k, lid in enumerate(links):
        channels[f"flowrate:{lid}"] = tick_flows[:, k]
    pipes = [p.id for p in network.pipes]
    velocity = axis.at_ticks(axis.frame("link", "velocity", pipes, "velocity"))
    for k, pid in enumerate(pipes):
        channels[f"velocity:{pid}"] = velocity[:, k]
    for leak in faults.leaks:
        nodes = [leak_node(leak.pipe, k) for k in range(len(leak.steps))]
        outflow = axis.at_ticks(
            axis.frame("node", "leak_demand", nodes, "leak outflow")
        )
        channels[f"leak:{leak.pipe}"] = outflow.sum(axis=1)
    energy: dict[str, float] = {}
    if network.pumps:
        nodes = sorted({n for pump in network.pumps for n in (pump.start, pump.end)})
        heads = axis.frame("node", "head", nodes, "pump head")
        column = {n: k for k, n in enumerate(nodes)}
        position = {lid: k for k, lid in enumerate(links)}
        intervals = np.diff(axis.times)
        for pump in network.pumps:
            q = flows[:, position[pump.id]]
            gain = heads[:, column[pump.end]] - heads[:, column[pump.start]]
            _check_pump(pump.id, q, gain, axis.times)
            q = np.where(q > PUMP_FLOW_NOISE, q, 0.0)
            power_kw = (
                (options.water_density_kg_m3 * options.gravity_m_s2 * q * gain)
                / pump.efficiency
                / 1000.0
            )
            channels[f"power:{pump.id}"] = axis.at_ticks(power_kw)
            energy[pump.id] = math.fsum(power_kw[:-1] * intervals / 3600.0)
            if not (np.isfinite(power_kw).all() and math.isfinite(energy[pump.id])):
                raise HydraulicsError(f"non-finite power or energy for {pump.id}")
    truth = TruthSeries(
        demand.timebase,
        {
            name: v.tolist()
            for name, v in sorted(channels.items())
            if keep is None or name in keep
        },
        faults.events,
    )
    return HydraulicResult(
        truth=truth,
        energy_kwh=MappingProxyType(dict(sorted(energy.items())))
        if options.engine == "wntr"
        else None,
        engine=options.engine,
        options_hash=options.config_hash,
    )


def _check_pump(pump: str, q: np.ndarray, gain: np.ndarray, times: np.ndarray) -> None:
    reverse = q < -PUMP_FLOW_NOISE
    if reverse.any():
        row = int(np.argmax(reverse))
        raise HydraulicsError(
            f"reverse flow {q[row]} m3/s through {pump} at {times[row]:g} s"
        )
    overrun = (q > PUMP_FLOW_NOISE) & (gain < -PUMP_HEAD_NOISE)
    if overrun.any():
        row = int(np.argmax(overrun))
        raise HydraulicsError(
            f"{pump} carries {q[row]:.4f} m3/s while losing {-gain[row]:.2f} m of head at "
            f"{times[row]:g} s: it runs past the flow where its curve reaches zero head; "
            "check the network and the pump curve"
        )
