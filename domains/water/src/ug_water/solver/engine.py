"""Run the hydraulics of a network with a demand series and return the twin's truth.

The engine is WNTR's `WNTRSimulator` (its leak model is what the fault cards use) or, on request,
WNTR's `EpanetSimulator` (EPANET 2.2; no leaks), both with pressure-driven demand. Results become
a `TruthSeries` (label `SIMULATION`) with one channel per quantity and element, named
`"<quantity>:<element id>"`:
- junctions: `pressure` (m), `head` (m), `demand` (delivered, m3/s);
- tanks: `level` (m above the tank bottom) and `head` (m);
- pipes, pumps and valves: `flowrate` (m3/s); pipes also `velocity` (m/s);
- pumps: `power` (kW).

Pump power is `rho * g * Q * (H_out - H_in) / efficiency`, from the flow through the pump and the
heads at its two ends; it is zero when the pump carries no flow. The energy of a run is the power
at each report time held over the step that follows it, as EPANET does: the last report time
starts no step. A non-finite result, a time axis that is not the series' axis, a simulation
that does not converge, or reverse flow through a pump beyond numerical noise is an error,
never a value.
"""

from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Mapping
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
from ug_water.solver.options import HydraulicOptions, load_options

LABEL = "SIMULATION"
# Reverse flow through a pump smaller than this (m3/s) is numerical noise and counts as none.
PUMP_FLOW_NOISE = 1e-9


class HydraulicsError(RuntimeError):
    """The hydraulics could not be computed, or the results cannot be trusted."""


@dataclass(frozen=True)
class HydraulicResult:
    truth: TruthSeries
    energy_kwh: Mapping[str, float]  # per pump, over the run
    engine: str
    options_hash: str
    label: str = LABEL

    @property
    def total_energy_kwh(self) -> float:
        return math.fsum(self.energy_kwh.values())

    def content_hash(self) -> str:
        payload = {
            "truth": self.truth.content_hash(),
            "energy_kwh": {
                k: round_for_hash(v) for k, v in sorted(self.energy_kwh.items())
            },
            "engine": self.engine,
            "options": self.options_hash,
            "label": self.label,
        }
        return sha256_hex(canonical_json(payload))


def simulate(
    network: Network,
    demand: DemandInput,
    options: HydraulicOptions | None = None,
) -> HydraulicResult:
    """The truth of the network under the demand series. Raises `HydraulicsError`."""
    options = options or load_options()
    try:
        wn = build_model(network, demand, options)
    except ValueError as exc:
        raise HydraulicsError(
            f"the network or the demand cannot be modelled: {exc}"
        ) from exc
    results = _run(wn, options)
    return _truth(network, demand, results, options)


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


def _frame(results: Any, table: str, key: str, ids: list[str], what: str) -> np.ndarray:
    frame = getattr(results, table)[key]
    missing = sorted(set(ids) - set(frame.columns))
    if missing:
        raise HydraulicsError(f"the results hold no {what} for {missing[:5]}")
    values = frame[ids].to_numpy(dtype=float)
    bad = ~np.isfinite(values)
    if bad.any():
        tick, column = (int(i) for i in np.argwhere(bad)[0])
        raise HydraulicsError(
            f"non-finite {what} for {ids[column]} at tick {tick}: {values[tick, column]}"
        )
    return values


def _truth(
    network: Network, demand: DemandInput, results: Any, options: HydraulicOptions
) -> HydraulicResult:
    timebase = demand.timebase
    step = timebase.step_seconds
    expected = [k * step for k in range(timebase.n_ticks)]
    index = [int(t) for t in results.node["pressure"].index]
    if index != expected:
        raise HydraulicsError(
            "the results' time axis is not the demand series' axis "
            f"({len(index)} report times, expected {len(expected)} at {step} s)"
        )
    channels: dict[str, np.ndarray] = {}
    junctions = [j.id for j in network.junctions]
    for key, quantity in (
        ("pressure", "pressure"),
        ("head", "head"),
        ("demand", "demand"),
    ):
        values = _frame(results, "node", key, junctions, f"junction {quantity}")
        for k, jid in enumerate(junctions):
            channels[f"{quantity}:{jid}"] = values[:, k]
    tanks = list(network.tanks)
    if tanks:
        heads = _frame(results, "node", "head", [t.id for t in tanks], "tank head")
        for k, tank in enumerate(tanks):
            channels[f"head:{tank.id}"] = heads[:, k]
            channels[f"level:{tank.id}"] = heads[:, k] - tank.elevation
    links = [
        *(p.id for p in network.pipes),
        *(p.id for p in network.pumps),
        *(v.id for v in network.valves),
    ]
    flows = _frame(results, "link", "flowrate", links, "flow")
    for k, lid in enumerate(links):
        channels[f"flowrate:{lid}"] = flows[:, k]
    pipes = [p.id for p in network.pipes]
    velocity = _frame(results, "link", "velocity", pipes, "velocity")
    for k, pid in enumerate(pipes):
        channels[f"velocity:{pid}"] = velocity[:, k]
    energy: dict[str, float] = {}
    if network.pumps:
        nodes = sorted({n for pump in network.pumps for n in (pump.start, pump.end)})
        heads = _frame(results, "node", "head", nodes, "pump head")
        column = {n: k for k, n in enumerate(nodes)}
        for pump in network.pumps:
            q = channels[f"flowrate:{pump.id}"]
            if (q < -PUMP_FLOW_NOISE).any():
                tick = int(np.argmax(q < -PUMP_FLOW_NOISE))
                raise HydraulicsError(
                    f"reverse flow {q[tick]} m3/s through {pump.id} at tick {tick}"
                )
            q = np.where(q > PUMP_FLOW_NOISE, q, 0.0)
            gain = heads[:, column[pump.end]] - heads[:, column[pump.start]]
            power_kw = (
                (options.water_density_kg_m3 * options.gravity_m_s2 * q * gain)
                / pump.efficiency
                / 1000.0
            )
            channels[f"power:{pump.id}"] = power_kw
            energy[pump.id] = math.fsum(power_kw[:-1] * step / 3600.0)
    truth = TruthSeries(
        timebase, {name: v.tolist() for name, v in sorted(channels.items())}
    )
    return HydraulicResult(
        truth=truth,
        energy_kwh=MappingProxyType(dict(sorted(energy.items()))),
        engine=options.engine,
        options_hash=options.config_hash,
    )
