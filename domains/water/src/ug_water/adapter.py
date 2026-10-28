"""The water domain adapter (Master Spec section 4.6).

The procedural asset model and fault-free solver implement the B1 run path.
Remaining methods declare the milestone that delivers them.

The adapter also offers the optional `health_checks()` hook (ADR-004), so `ug doctor` can ask the
water domain whether its environment is sound without `platform/` importing this package.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from typing import Any, ClassVar

from ug_core.adapter import AdapterBase, HealthCheck
from ug_core.numeric import round_for_hash
from ug_core.runner import RunState
from ug_core.timebase import Timebase
from ug_core.truth import TruthSeries

from ug_water import wntr_api
from ug_water.demand.calendar import DemandCalendar
from ug_water.demand.model import DemandModel
from ug_water.network.model import Junction, Network, Pipe
from ug_water.network.procedural import ProceduralCapitalProvider
from ug_water.scenarios import list_presets, load_preset
from ug_water.solver import load_options, simulate
from ug_water.solver.faults import add_fire_flows, plan_faults


class _WaterSolver:
    def run(
        self, state: RunState, scenario: Mapping[str, Any], horizon: Timebase
    ) -> TruthSeries:
        faults = plan_faults(scenario["faults"], state.asset, horizon)
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
        demand = add_fire_flows(replace(demand, values=demand.values * factors), faults)
        return simulate(state.asset, demand, faults=faults).truth


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
            re.fullmatch(
                r"procedural-capital-v1-seed([0-9]+)(-standard)?", network_version
            )
            if isinstance(network_version, str)
            else None
        )
        if match is None:
            raise ValueError(
                "supported network_version form: procedural-capital-v1-seed<N>"
            )
        if match.group(2):
            config = json.loads(
                files("ug_water.network")
                .joinpath("data/procedural_capital_v1.json")
                .read_text()
            )
            config["targets"] = {"junctions": 800, "pipes": 1050}
            return ProceduralCapitalProvider(config).build(int(match.group(1)))
        return ProceduralCapitalProvider().build(int(match.group(1)))

    def export_view(
        self, store: Any, run_id: str, assumptions_dir: Path
    ) -> dict[str, Any]:
        """Privileged replay bridge: stored channels are used ONLY by measurement.

        Expectations come from independent forecast demand. Hidden tags are never
        read into Python or passed to any consumer. Reconstructed assets must hash
        exactly as the recorded run did.
        """
        import pyarrow as pa  # type: ignore[import-untyped]
        import pyarrow.compute as pc  # type: ignore[import-untyped]
        from ug_core.assumptions import load_assumptions
        from ug_core.rng import SeedStreams
        from ug_core.store.truth_bundle import read_truth

        from ug_water.telemetry.expectation import expected_readings
        from ug_water.telemetry.measurement import WaterMeasurement, _config, rtu_group
        from ug_water.telemetry.readings import to_readings

        manifest = store.verify(run_id)
        config = manifest.to_dict()["config"]
        network = self.asset_model(config)
        if network.content_hash() != manifest.versions["network"]:
            raise ValueError("recorded network version cannot be reconstructed")
        if any(
            manifest.versions.get(name) != value
            for name, value in self.run_versions(network).items()
        ):
            raise ValueError("recorded model versions do not match")
        if any(version(name) != value for name, value in manifest.libraries.items()):
            raise ValueError("recorded library versions do not match")
        assumptions = load_assumptions(
            assumptions_dir / f"{config['assumption_set']}.yaml"
        )
        if assumptions.content_hash() != manifest.versions["assumption_set"]:
            raise ValueError("recorded assumptions do not match")
        step = config["timestep_minutes"] * 60
        horizon = Timebase(
            datetime.fromisoformat(config["start"].replace("Z", "+00:00")),
            step,
            round(config["duration_hours"] * 3600 / step) + 1,
        )
        table = read_truth(store, run_id).select(
            ["tick", "element_id", "quantity", "value"]
        )
        selected = set(network.sensor_sets[config["sensor_set"]])
        mask = None
        for kind, quantity in (
            ("pressure", "pressure"),
            ("flow", "flowrate"),
            ("level", "level"),
        ):
            elements = [
                s.element
                for s in network.sensors
                if s.id in selected and s.kind == kind
            ]
            matches = pc.and_(
                pc.equal(table["quantity"], quantity),
                pc.is_in(
                    table["element_id"], value_set=pa.array(elements, type=pa.string())
                ),
            )
            mask = matches if mask is None else pc.or_(mask, matches)
        rows = table.filter(mask).to_pylist()
        del table, mask
        channels: dict[str, list[float]] = {}
        for row in sorted(rows, key=lambda r: r["tick"]):
            channels.setdefault(f"{row['quantity']}:{row['element_id']}", []).append(
                row["value"]
            )
        telemetry, delays = WaterMeasurement(
            network, config["sensor_set"], config["faults"]
        ).measure_with_delivery(
            TruthSeries(horizon, channels), SeedStreams(manifest.seed)
        )
        del channels, rows
        model = DemandModel(assumptions)
        shift = timedelta(hours=model.parameter("utc_offset_hours", "h"))
        first, last = (
            (horizon.start + shift).date(),
            (horizon.time_at(horizon.n_ticks - 1) + shift).date(),
        )
        days = frozenset(
            first + timedelta(days=i) for i in range((last - first).days + 1)
        )
        calendar = DemandCalendar(
            holidays=days if config["demand"]["holiday"] else frozenset(),
            ramadan=days if config["demand"]["ramadan"] else frozenset(),
        )
        expected = expected_readings(
            network,
            config["sensor_set"],
            model.forecast(network, horizon, manifest.seed, calendar),
        )
        # Match the store's established six-decimal output precision. WNTR's
        # sparse solve can vary at machine epsilon between repeated evaluations.
        # Normalize BEFORE quality, residuals and detection, not only JSON encoding.
        expected = {
            sid: tuple(round_for_hash(v) for v in values)
            for sid, values in expected.items()
        }
        sensors = {s.id: s for s in network.sensors if s.id in telemetry.readings}
        measurement_config = _config(None)
        nodes = [
            dict(
                id=n.id,
                kind=kind,
                x=n.x,
                y=n.y,
                elevation_m=getattr(n, "elevation", 0),
                **({"zone": n.zone} if isinstance(n, Junction) else {}),
            )
            for kind, items in (
                ("junction", network.junctions),
                ("tank", network.tanks),
                ("reservoir", network.reservoirs),
            )
            for n in items
        ]
        links = []
        for kind, items in (
            ("pipe", network.pipes),
            ("pump", network.pumps),
            ("valve", network.valves),
        ):
            for link in items:
                row = dict(id=link.id, kind=kind, start=link.start, end=link.end)
                for source, target in (
                    ("tier", "tier"),
                    ("diameter", "diameter_m"),
                    ("length", "length_m"),
                    ("kind", "valve_kind"),
                ):
                    if hasattr(link, source):
                        row[target] = getattr(link, source)
                if isinstance(link, Pipe) and link.route:
                    row["route"] = [list(point) for point in link.route]
                links.append(row)
        # Procedural zones have no boundary geometry: do not invent polygons.
        view = dict(
            schema_version="1",
            network_hash=network.content_hash(),
            name=network.name,
            fidelity=network.provenance.fidelity,
            coordinates="local_m",
            geometry_label="ASSUMPTION",
            attribute_labels=dict(
                elevation_m="ASSUMPTION", diameter_m="ASSUMPTION", length_m="CALCULATED"
            ),
            nodes=nodes,
            links=links,
            zones=[],
            sensors=[
                dict(
                    id=s.id,
                    kind=s.kind,
                    element=s.element,
                    sets=[
                        name for name, ids in network.sensor_sets.items() if s.id in ids
                    ],
                )
                for s in network.sensors
            ],
        )
        return dict(
            network=view,
            telemetry=telemetry,
            delays=delays,
            expected=expected,
            kinds={sid: s.kind for sid, s in sensors.items()},
            elements={sid: s.element for sid, s in sensors.items()},
            zones={sid: rtu_group(s, network) for sid, s in sensors.items()},
            quanta={
                sid: measurement_config[s.kind]["quantum"] for sid, s in sensors.items()
            },
            ranges={
                sid: ((-100, 1000) if s.kind != "flow" else (-1e6, 1e6))
                for sid, s in sensors.items()
            },
            serialize=to_readings,
            asset=network,
        )

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
