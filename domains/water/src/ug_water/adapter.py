"""The water domain adapter (Master Spec section 4.6).

The procedural asset model and fault-free solver implement the B1 run path.
Remaining methods declare the milestone that delivers them.

The adapter also offers the optional `health_checks()` hook (ADR-004), so `ug doctor` can ask the
water domain whether its environment is sound without `platform/` importing this package.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import timedelta
from importlib.metadata import version
from typing import Any, ClassVar

from ug_core.adapter import AdapterBase, HealthCheck
from ug_core.runner import RunState
from ug_core.timebase import Timebase
from ug_core.truth import TruthSeries

from ug_water import wntr_api
from ug_water.demand.calendar import DemandCalendar
from ug_water.demand.model import DemandModel
from ug_water.network.model import Network
from ug_water.network.procedural import ProceduralCapitalProvider
from ug_water.scenarios import list_presets, load_preset
from ug_water.solver import load_options, simulate


class _WaterSolver:
    def run(
        self, state: RunState, scenario: Mapping[str, Any], horizon: Timebase
    ) -> TruthSeries:
        if scenario["faults"]:
            raise ValueError("faults arrive with T-B1-017")
        model = DemandModel(state.assumptions[scenario["assumption_set"]])
        settings = scenario["demand"]
        shift = timedelta(hours=model.parameter("utc_offset_hours", "h"))
        first = (horizon.start + shift).date()
        last = (horizon.time_at(horizon.n_ticks - 1) + shift).date()
        days = frozenset(
            first + timedelta(days=i) for i in range((last - first).days + 1)
        )
        calendar = DemandCalendar(
            holidays=days if settings["holiday"] else frozenset(),
            ramadan=days if settings["ramadan"] else frozenset(),
        )
        demand = model.truth(state.asset, horizon, scenario["seed"], calendar)
        zones = {j.id: j.zone for j in state.asset.junctions}
        unknown = set(settings["zone_multipliers"]) - set(zones.values())
        if unknown:
            raise ValueError(f"unknown demand zones: {sorted(unknown)}")
        # Stage 1 applies the scenario multiplier directly, without heatwave dates.
        # forecast_error remains in the recipe; forecasts arrive with M3.
        factors = [
            settings["zone_multipliers"].get(zones[jid], 1.0)
            * settings["heatwave_multiplier"]
            for jid in demand.junction_ids
        ]
        demand = replace(demand, values=demand.values * factors)
        return simulate(state.asset, demand).truth


class WaterAdapter(AdapterBase):
    domain_id: ClassVar[str] = "water"
    unimplemented_reasons: ClassVar[dict[str, str]] = {
        "asset_model": "arrives with Spec milestone M1 (twin core)",
        "solver": "arrives with Spec milestone M1 (twin core)",
        "fault_library": "arrives with Spec milestone M1 (twin core)",
        "measurement_model": "arrives with Spec milestone M2 (telemetry)",
        "ui_manifest": "arrives with Spec milestone M2 (map and shell)",
        "expectation_model": "arrives with Spec milestone M3 (detection)",
        "detectors": "arrives with Spec milestone M3 (detection)",
        "localizer": "arrives with Spec milestone M3 (detection)",
        "impact_model": "arrives with Spec milestone M4 (impact and decision)",
        "action_catalog": "arrives with Spec milestone M4 (impact and decision)",
        "cost_model": "arrives with Spec milestone M4 (impact and decision)",
        "validate_dataset": "arrives with Spec milestones M1 and M5 (network and benchmark import)",
    }

    def presets(self) -> Mapping[str, Mapping[str, Any]]:
        return {name: load_preset(name) for name in list_presets()}

    def asset_model(self, params: Any) -> Network:
        network_version = (
            params.get("network_version") if isinstance(params, Mapping) else None
        )
        match = (
            re.fullmatch(r"procedural-capital-v1-seed([0-9]+)", network_version)
            if isinstance(network_version, str)
            else None
        )
        if match is None:
            raise ValueError(
                "supported network_version form: procedural-capital-v1-seed<N>"
            )
        return ProceduralCapitalProvider().build(int(match.group(1)))

    def solver(self) -> _WaterSolver:
        return _WaterSolver()

    def run_versions(self, asset: Any) -> Mapping[str, str]:
        return {
            "network": asset.content_hash(),
            "hydraulics": load_options().config_hash,
            "ug-water": version("ug-water"),
        }

    def run_libraries(self) -> tuple[str, ...]:
        return ("wntr",)

    def health_checks(self) -> Sequence[HealthCheck]:
        """Is the installed WNTR the one the code was written against? Never raises."""
        location = wntr_api.manifest_location()
        try:
            manifest = wntr_api.load_manifest()
        except (OSError, ValueError) as exc:
            reason = f"cannot read the WNTR API manifest ({location}): {type(exc).__name__}: {exc}"
            return [
                HealthCheck("wntr_version", False, reason),
                HealthCheck("wntr_api_manifest", False, reason),
            ]
        try:
            installed = wntr_api.installed_version()
        except (
            Exception
        ) as exc:  # WNTR missing or broken: report it, do not crash the doctor
            reason = f"WNTR cannot be imported: {type(exc).__name__}: {exc}"
            return [
                HealthCheck("wntr_version", False, reason),
                HealthCheck("wntr_api_manifest", False, reason),
            ]
        recorded = manifest.get("wntr_version")
        version_ok = recorded == installed
        version = HealthCheck(
            "wntr_version",
            version_ok,
            f"WNTR {installed} installed; the manifest ({location}) was generated for {recorded}",
        )
        try:
            problems = wntr_api.verify(manifest)
        except (
            Exception
        ) as exc:  # the probe network or simulation failed: that is a finding
            problems = [f"verification failed: {type(exc).__name__}: {exc}"]
        if problems:
            shown = "; ".join(p.splitlines()[0] for p in problems[:5])
            more = f" (and {len(problems) - 5} more)" if len(problems) > 5 else ""
            detail = (
                f"{len(problems)} problem(s) against WNTR {installed}: {shown}{more}"
            )
        else:
            detail = (
                f"{wntr_api.symbol_count(manifest)} symbols verified against WNTR {installed} "
                f"({location})"
            )
        return [version, HealthCheck("wntr_api_manifest", not problems, detail)]
