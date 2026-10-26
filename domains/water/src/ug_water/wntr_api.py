"""The WNTR API surface the water domain may use, checked against the installed WNTR.

Why: generated code often calls library functions that do not exist or have changed. Here the
allowed surface is a short, explicit list. `generate()` records what the installed WNTR really
offers (signatures come from introspection, never from memory); `verify()` re-checks a recorded
manifest against the installed library and names every symbol that no longer matches. The same
code runs from `scripts/gen_wntr_manifest.py` and, through the water domain adapter, `ug doctor`.

A symbol enters the lists below only when new code needs it. Adding one is a reviewed change:
extend the list, run `python scripts/gen_wntr_manifest.py --write`, commit both files.
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import re
from importlib import resources
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = "1"
MANIFEST_RESOURCE = "wntr_api_manifest.json"

# Callables whose signature is recorded and compared. Dotted import paths.
CALLABLES: tuple[str, ...] = (
    "wntr.network.WaterNetworkModel.add_junction",
    "wntr.network.WaterNetworkModel.add_reservoir",
    "wntr.network.WaterNetworkModel.add_tank",
    "wntr.network.WaterNetworkModel.add_pipe",
    "wntr.network.WaterNetworkModel.add_pump",
    "wntr.network.WaterNetworkModel.add_valve",
    "wntr.network.WaterNetworkModel.add_pattern",
    "wntr.network.WaterNetworkModel.add_curve",
    "wntr.network.WaterNetworkModel.remove_link",
    "wntr.network.WaterNetworkModel.get_node",
    "wntr.network.WaterNetworkModel.get_link",
    "wntr.network.WaterNetworkModel.get_pattern",
    "wntr.network.elements.Junction.add_leak",
    "wntr.sim.WNTRSimulator.run_sim",
)

# Attributes that must exist on objects of a small probe network: (root, path). Paths use `.name`
# and `[index]` only; they are resolved by `_resolve`, never evaluated.
MEMBERS: tuple[tuple[str, str], ...] = (
    ("wn", "link_name_list"),
    ("wn", "options.time.duration"),
    ("wn", "options.time.hydraulic_timestep"),
    ("wn", "options.time.report_timestep"),
    ("wn", "options.time.pattern_timestep"),
    ("wn", "options.hydraulic.demand_model"),
    ("wn", "options.hydraulic.minimum_pressure"),
    ("wn", "options.hydraulic.required_pressure"),
    ("wn", "options.hydraulic.pressure_exponent"),
    ("wn", "options.quality.parameter"),
    ("junction", "demand_timeseries_list[0].base_value"),
    ("junction", "coordinates"),
    ("junction", "elevation"),
    ("tank", "init_level"),
    ("tank", "min_level"),
    ("tank", "max_level"),
    ("tank", "diameter"),
    ("pump", "initial_status"),
    ("pipe", "start_node_name"),
    ("pipe", "end_node_name"),
    ("pipe", "length"),
    ("pipe", "diameter"),
    ("pipe", "roughness"),
    ("pipe", "minor_loss"),
    ("pipe", "initial_status"),
    ("pipe", "link_type"),
    ("pattern", "multipliers"),
    ("link_status", "Open"),
    ("link_status", "Closed"),
)

# Columns that must exist in the simulation result tables: (table, key).
RESULT_KEYS: tuple[tuple[str, str], ...] = (
    ("node", "pressure"),
    ("node", "demand"),
    ("node", "leak_demand"),
    ("node", "head"),
    ("link", "flowrate"),
    ("link", "status"),
)

_PATH_TOKEN = re.compile(r"\.?([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]")


def _wntr() -> Any:
    return importlib.import_module("wntr")


def installed_version() -> str:
    return str(_wntr().__version__)


def _resolve_callable(path: str) -> Any:
    """Import the longest module prefix of `path` (inside `wntr` only), then follow attributes."""
    parts = path.split(".")
    if parts[0] != "wntr" or len(parts) < 2:
        raise ValueError(f"only symbols inside wntr can be resolved, got {path!r}")
    for split in range(len(parts) - 1, 0, -1):
        try:
            obj: Any = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        for name in parts[split:]:
            obj = getattr(obj, name)
        return obj
    raise ImportError(f"cannot import any module prefix of {path!r}")


def _signature(path: str) -> str:
    return str(inspect.signature(_resolve_callable(path)))


def _resolve(root: Any, path: str) -> Any:
    """Follow `.name` and `[index]` steps from `root`. No evaluation of code."""
    obj = root
    position = 0
    while position < len(path):
        match = _PATH_TOKEN.match(path, position)
        if match is None:
            raise ValueError(f"unsupported path syntax at {path[position:]!r}")
        name, index = match.groups()
        obj = getattr(obj, name) if name is not None else obj[int(index)]
        position = match.end()
    return obj


def _probe_elements() -> dict[str, Any]:
    """A tiny network with one element of every kind the member checks need (no simulation)."""
    wntr = _wntr()
    wn = wntr.network.WaterNetworkModel()
    wn.add_reservoir("R1", base_head=50.0, coordinates=(0.0, 0.0))
    wn.add_junction("J1", base_demand=0.001, elevation=1.0, coordinates=(100.0, 0.0))
    wn.add_junction("J2", base_demand=0.0, elevation=1.0, coordinates=(200.0, 0.0))
    wn.add_tank(
        "T1",
        elevation=30.0,
        init_level=2.0,
        min_level=0.5,
        max_level=5.0,
        diameter=10.0,
    )
    wn.add_pipe("P1", "R1", "J1", length=100.0, diameter=0.3, roughness=100.0)
    wn.add_curve("C1", "HEAD", [(0.0, 60.0), (0.02, 40.0), (0.04, 10.0)])
    wn.add_pump("PU1", "J1", "J2", pump_type="HEAD", pump_parameter="C1")
    wn.add_pattern("PAT1", [1.0, 1.2])
    return {
        "wn": wn,
        "junction": wn.get_node("J1"),
        "tank": wn.get_node("T1"),
        "pump": wn.get_link("PU1"),
        "pipe": wn.get_link("P1"),
        "pattern": wn.get_pattern("PAT1"),
        "link_status": wntr.network.base.LinkStatus,
    }


def _probe_result_tables() -> dict[str, Any]:
    """Run a one-step simulation on a small leaking network and return its result tables."""
    wntr = _wntr()
    wn = wntr.network.WaterNetworkModel()
    wn.add_reservoir("R1", base_head=50.0, coordinates=(0.0, 0.0))
    wn.add_junction("J1", base_demand=0.001, elevation=1.0, coordinates=(100.0, 0.0))
    wn.add_junction("J2", base_demand=0.001, elevation=1.0, coordinates=(200.0, 0.0))
    wn.add_pipe("P1", "R1", "J1", length=100.0, diameter=0.3, roughness=100.0)
    wn.add_pipe("P2", "J1", "J2", length=100.0, diameter=0.3, roughness=100.0)
    wn.get_node("J2").add_leak(wn, area=1e-5, discharge_coeff=0.75, start_time=0)
    wn.options.time.duration = 0
    wn.options.hydraulic.demand_model = "PDD"
    results = wntr.sim.WNTRSimulator(wn).run_sim()
    return {"node": results.node, "link": results.link}


def generate() -> dict[str, Any]:
    """Describe the installed WNTR: version plus the signature of every declared callable."""
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "wntr_version": installed_version(),
        "callables": {path: _signature(path) for path in CALLABLES},
        "members": [{"root": root, "path": path} for root, path in MEMBERS],
        "result_keys": [{"table": table, "key": key} for table, key in RESULT_KEYS],
    }


def symbol_count(manifest: dict[str, Any]) -> int:
    return (
        len(manifest.get("callables", {}))
        + len(manifest.get("members", []))
        + len(manifest.get("result_keys", []))
    )


MANIFEST_ENV = "UG_WNTR_MANIFEST"


def manifest_location() -> str:
    """Where the manifest is read from: the packaged file, or the file named by UG_WNTR_MANIFEST.

    The variable is a test and diagnosis hook (`ug doctor` against an edited copy). It cannot make
    a wrong environment look right: whatever file is named is verified against the installed WNTR
    and against the symbols declared in this module, exactly like the packaged one.
    """
    override = os.environ.get(MANIFEST_ENV)
    return override if override else f"ug_water/{MANIFEST_RESOURCE}"


def load_manifest() -> dict[str, Any]:
    override = os.environ.get(MANIFEST_ENV)
    if override:
        text = Path(override).read_text(encoding="utf-8")
    else:
        text = (
            resources.files("ug_water")
            .joinpath(MANIFEST_RESOURCE)
            .read_text(encoding="utf-8")
        )
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("WNTR API manifest must be a JSON object")
    return loaded


def manifest_problems(manifest: object) -> list[str]:
    """Structure and completeness: the manifest must hold exactly the symbols declared above.

    Nothing from the manifest is resolved or imported here; this runs before any check against
    the installed library, so a manifest cannot make the verifier import anything.
    """
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    problems: list[str] = []
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        problems.append(
            f"manifest schema_version {manifest.get('schema_version')!r} not supported"
        )
    if not isinstance(manifest.get("wntr_version"), str):
        problems.append("manifest has no wntr_version")

    callables = manifest.get("callables")
    if not isinstance(callables, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in callables.items()
    ):
        problems.append(
            "manifest 'callables' must map each symbol path to a signature text"
        )
    else:
        for path in sorted(set(callables) - set(CALLABLES)):
            problems.append(
                f"callable {path}: in the manifest but not declared in wntr_api.py"
            )
        for path in sorted(set(CALLABLES) - set(callables)):
            problems.append(
                f"callable {path}: declared in wntr_api.py but missing from the manifest"
            )

    for section, keys, declared in (
        ("members", ("root", "path"), MEMBERS),
        ("result_keys", ("table", "key"), RESULT_KEYS),
    ):
        entries = manifest.get(section)
        if not isinstance(entries, list) or not all(
            isinstance(e, dict) and all(isinstance(e.get(k), str) for k in keys)
            for e in entries
        ):
            problems.append(
                f"manifest '{section}' must be a list of objects with {keys}"
            )
            continue
        recorded = [tuple(e[k] for k in keys) for e in entries]
        for item in sorted({r for r in recorded if recorded.count(r) > 1}):
            problems.append(
                f"{section[:-1]} {'.'.join(item)}: listed twice in the manifest"
            )
        for item in sorted(set(recorded) - set(declared)):
            problems.append(
                f"{section[:-1]} {'.'.join(item)}: in the manifest but not declared in wntr_api.py"
            )
        for item in sorted(set(declared) - set(recorded)):
            problems.append(
                f"{section[:-1]} {'.'.join(item)}: declared in wntr_api.py but missing from the manifest"
            )
    return problems


def verify(manifest: object) -> list[str]:
    """Problems found when checking `manifest` against the installed WNTR. Empty means OK.

    A manifest that is malformed, incomplete or lists symbols that are not declared in this
    module is reported and nothing is resolved. Only then is the installed library inspected.
    """
    problems = manifest_problems(manifest)
    if problems or not isinstance(manifest, dict):
        return problems
    recorded_version = manifest["wntr_version"]
    if recorded_version != installed_version():
        problems.append(
            f"WNTR version: manifest was generated for {recorded_version!r}, "
            f"installed is {installed_version()!r}"
        )

    for path, recorded in manifest.get("callables", {}).items():
        try:
            actual = _signature(path)
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            problems.append(f"callable {path}: not found or has no signature ({exc})")
            continue
        if actual != recorded:
            problems.append(
                f"callable {path}: signature changed\n  recorded {recorded}\n  actual   {actual}"
            )

    probes: dict[str, Any] | None = None
    for entry in manifest.get("members", []):
        probes = probes if probes is not None else _probe_elements()
        root, path = entry["root"], entry["path"]
        try:
            if root not in probes:
                raise KeyError(f"unknown probe root {root!r}")
            _resolve(probes[root], path)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            problems.append(f"member {root}.{path}: missing ({exc})")

    tables: dict[str, Any] | None = None
    for entry in manifest.get("result_keys", []):
        tables = tables if tables is not None else _probe_result_tables()
        table, key = entry["table"], entry["key"]
        if table not in tables or key not in tables[table]:
            problems.append(
                f"result key {table}[{key!r}]: missing from simulation results"
            )
    return problems
