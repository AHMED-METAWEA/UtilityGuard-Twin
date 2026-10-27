"""Offline advisory checks of network data and synthetic normal-week hydraulics.

Values are CALCULATED from network data or SIMULATION, thresholds ASSUMPTION.
No network is changed or re-seeded. Demand assumptions are read relative to the
caller's working directory, like the explicitly supplied repository assumptions path.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from typing import Any

import numpy as np
from ug_core.assumptions import load_assumptions
from ug_core.numeric import round_for_hash
from ug_core.timebase import Timebase

from ug_water.demand.calendar import DemandCalendar
from ug_water.demand.model import DemandModel
from ug_water.network.model import Junction, Network, Pipe, Pump, Reservoir, Tank, Valve
from ug_water.solver import HydraulicsError, simulate


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool | None  # None means skipped, or informational
    value: float | bool | None
    threshold: float | bool | None
    unit: str
    label: str
    detail: str

    @property
    def threshold_label(self) -> str | None:
        return "ASSUMPTION" if self.threshold is not None else None


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    checks: tuple[CheckResult, ...]


class NetworkInvalid(ValueError):
    """The network failed one or more named validation checks."""


def load_config(data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Load versioned placeholder thresholds; accept a full mapping override."""
    default = json.loads(
        files("ug_water.network").joinpath("data/validation_v1.json").read_text()
    )
    config = dict(default if data is None else data)
    if set(config) != set(default):
        raise ValueError("validation config must have exactly the version 1 keys")
    if config["version"] != "1" or config["label"] != "ASSUMPTION":
        raise ValueError("validation config requires version 1 and label ASSUMPTION")
    if config["verified"] is not False or not config["note"]:
        raise ValueError("validation thresholds must be unverified with a note")
    for key in default.keys() - {"version", "label", "verified", "note", "solves"}:
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{key} must be a number")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be finite and non-negative")
    # Structural rules and solving are mandatory; callers cannot disable them.
    if config["solves"] is not True or any(
        config[key] != 0
        for key in config
        if key.startswith("max_") and key != "max_velocity_m_s"
    ):
        raise ValueError("structural limits must be zero and solves must be true")
    if not 0 < config["pinned_full_share"] <= 1:
        raise ValueError("pinned_full_share must be in (0, 1]")
    return config


def validate_network(
    network: Network,
    *,
    seed: int,
    config: Mapping[str, Any] | None = None,
    horizon_days: float = 7.0,
) -> ValidationReport:
    """Validate, with a shorter exact multiple of 5 minutes allowed for fixtures.

    Report values use the canonical six-decimal output precision; comparisons
    use unrounded results. Includes both endpoints of the horizon. Ties select the first tick and sorted
    element ID. Skips have no value or pass verdict; an absent element class is
    vacuously passing. No positive demand makes pressures/delivered share N/A.
    """
    cfg = load_config(config)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    steps = horizon_days * 86400 / 300
    if (
        isinstance(horizon_days, bool)
        or not math.isfinite(steps)
        or steps < 1
        or not math.isclose(steps, round(steps), rel_tol=0, abs_tol=1e-9)
    ):
        raise ValueError(
            "horizon_days must be a positive whole number of 5-minute steps"
        )
    checks: list[CheckResult] = []

    def add(
        name: str,
        passed: bool | None,
        value: float | bool | None,
        threshold: float | bool | None,
        unit: str,
        detail: str,
    ) -> None:
        # WNTR can differ at machine precision between equal runs. Use the
        # repository's canonical output precision; verdicts use unrounded values.
        if isinstance(value, float):
            value = round_for_hash(value)
        checks.append(
            CheckResult(name, passed, value, threshold, unit, "CALCULATED", detail)
        )

    links: tuple[Pipe | Pump | Valve, ...] = (
        *network.pipes,
        *network.pumps,
        *network.valves,
    )
    nodes: tuple[Junction | Reservoir | Tank, ...] = (
        *network.junctions,
        *network.reservoirs,
        *network.tanks,
    )
    adjacent: dict[str, list[tuple[str, str]]] = {n.id: [] for n in nodes}
    for link in links:
        adjacent[link.start].append((link.end, link.id))
        adjacent[link.end].append((link.start, link.id))

    def reachable(exclude: str | None = None) -> set[str]:
        seen = {r.id for r in network.reservoirs}
        pending = sorted(seen)
        while pending:
            for neighbor, lid in adjacent[pending.pop()]:
                if lid != exclude and neighbor not in seen:
                    seen.add(neighbor)
                    pending.append(neighbor)
        return seen

    reached = reachable()
    structural = (
        (
            "junction_reachability",
            "max_unreachable_junctions",
            [j.id for j in network.junctions if j.id not in reached],
        ),
        (
            "junction_degree",
            "max_isolated_junctions",
            [j.id for j in network.junctions if not adjacent[j.id]],
        ),
        (
            "tank_connectivity",
            "max_disconnected_tanks",
            [t.id for t in network.tanks if t.id not in reached],
        ),
        (
            "prv_pressure_zone",
            "max_bypassed_prvs",
            [
                v.id
                for v in network.valves
                if v.kind == "prv" and v.end in reachable(v.id)
            ],
        ),
    )
    for name, key, bad in structural:
        add(
            name,
            len(bad) <= cfg[key],
            len(bad),
            cfg[key],
            "count",
            f"From network; failing elements: {', '.join(bad) or 'none'}; tick N/A",
        )
    specs = (
        ("solves", cfg["solves"], "boolean"),
        ("min_pressure_at_peak", cfg["min_pressure_m"], "m"),
        ("min_pressure_any_time", cfg["min_pressure_any_m"], "m"),
        ("max_velocity", cfg["max_velocity_m_s"], "m/s"),
        ("tank_starvation", cfg["tank_margin_m"], "m"),
        ("tank_pinned_full", cfg["pinned_full_share"], "ratio"),
        ("delivered_share", None, "ratio"),
    )

    def finish() -> ValidationReport:
        return ValidationReport(
            # Fail closed: every check except the informational delivered share must pass;
            # a check that could not be evaluated (None) is not a pass (lead review).
            all(c.passed is True for c in checks if c.name != "delivered_share"),
            tuple(checks),
        )

    def skip(reason: str, start: int = 0) -> ValidationReport:
        for name, threshold, unit in specs[start:]:
            add(
                name,
                None,
                None,
                threshold,
                unit,
                f"Skipped: {reason}; element/tick unavailable",
            )
        return finish()

    if not all(c.passed for c in checks):
        return skip("structural failure")
    preset = json.loads(
        files("ug_water.scenarios").joinpath("presets/normal_week.json").read_text()
    )
    axis = Timebase(datetime.fromisoformat(preset["start"]), 300, round(steps) + 1)
    demand = DemandModel(load_assumptions("assumptions/demand_v1.yaml")).truth(
        network, axis, seed, DemandCalendar()
    )
    try:
        result = simulate(network, demand)
    except HydraulicsError as exc:
        add(
            "solves",
            False,
            False,
            cfg["solves"],
            "boolean",
            f"SIMULATION failed: {exc}",
        )
        return skip("HydraulicsError; solves failed", 1)
    add(
        "solves",
        True,
        True,
        cfg["solves"],
        "boolean",
        "SIMULATION solved; all elements and ticks",
    )
    channels = result.truth.channels

    def location(element: str, tick: int) -> str:
        return f"From SIMULATION; worst element {element}, tick {tick} ({axis.iso_at(tick)})"

    positive = [j.id for j in network.junctions if j.base_demand > 0]
    peak = int(np.argmax(demand.total_m3s()))
    for name, threshold, only_peak in (
        ("min_pressure_at_peak", cfg["min_pressure_m"], True),
        ("min_pressure_any_time", cfg["min_pressure_any_m"], False),
    ):
        candidates = [
            (channels[f"pressure:{j}"][t], t, j)
            for t in ([peak] if only_peak else axis.ticks())
            for j in positive
        ]
        if candidates:
            value, tick, element = min(candidates)
            add(
                name, value >= threshold, value, threshold, "m", location(element, tick)
            )
        else:
            add(
                name,
                None,
                None,
                threshold,
                "m",
                "N/A: no positive base demand; element/tick N/A",
            )
    velocities = [
        (abs(v), tick, p.id)
        for p in network.pipes
        for tick, v in enumerate(channels[f"velocity:{p.id}"])
    ]
    if velocities:
        value, tick, element = min(velocities, key=lambda x: (-x[0], x[1], x[2]))
        add(
            "max_velocity",
            value <= cfg["max_velocity_m_s"],
            value,
            cfg["max_velocity_m_s"],
            "m/s",
            location(element, tick),
        )
    else:
        add(
            "max_velocity",
            True,
            None,
            cfg["max_velocity_m_s"],
            "m/s",
            "N/A: no pipes; element/tick N/A",
        )
    margins = [
        (level - tank.min_level, tick, tank.id)
        for tank in network.tanks
        for tick, level in enumerate(channels[f"level:{tank.id}"])
    ]
    full = []
    for tank in network.tanks:
        ticks = [
            t
            for t, level in enumerate(channels[f"level:{tank.id}"])
            if tank.max_level - level <= cfg["tank_margin_m"]
        ]
        full.append((len(ticks) / axis.n_ticks, ticks[0] if ticks else 0, tank.id))
    if margins:
        value, tick, element = min(margins)
        add(
            "tank_starvation",
            value > cfg["tank_margin_m"],
            value,
            cfg["tank_margin_m"],
            "m",
            location(element, tick),
        )
        value, tick, element = min(full, key=lambda x: (-x[0], x[1], x[2]))
        add(
            "tank_pinned_full",
            value < cfg["pinned_full_share"],
            value,
            cfg["pinned_full_share"],
            "ratio",
            location(element, tick)
            + f"; margin {cfg['tank_margin_m']} m ASSUMPTION; tick is first near-full tick (0 if none)",
        )
    else:
        for name, key, unit in (
            ("tank_starvation", "tank_margin_m", "m"),
            ("tank_pinned_full", "pinned_full_share", "ratio"),
        ):
            add(name, True, None, cfg[key], unit, "N/A: no tanks; element/tick N/A")
    requested = float(demand.values[:-1].sum()) * axis.step_seconds
    delivered = (
        math.fsum(v for j in network.junctions for v in channels[f"demand:{j.id}"][:-1])
        * axis.step_seconds
    )
    add(
        "delivered_share",
        None,
        delivered / requested if requested else None,
        None,
        "ratio",
        "From SIMULATION; informational volume ratio, step-held excluding final endpoint; all junctions and intervals; no single worst element/tick",
    )
    return finish()


def require_valid(
    network: Network,
    *,
    seed: int,
    config: Mapping[str, Any] | None = None,
    horizon_days: float = 7.0,
) -> ValidationReport:
    """Return the report or raise naming every failed check (never skipped checks)."""
    report = validate_network(
        network, seed=seed, config=config, horizon_days=horizon_days
    )
    if not report.passed:
        raise NetworkInvalid(
            "Network validation failed: "
            + "; ".join(
                f"{c.name}: {c.value} (threshold {c.threshold}); {c.detail}"
                for c in report.checks
                if c.passed is False
            )
        )
    return report
