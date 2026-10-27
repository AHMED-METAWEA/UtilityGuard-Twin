"""Offline recipe loading, contract validation and run command output."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from ug_core.adapter import AdapterBase
from ug_core.assumptions import load_assumptions
from ug_core.registry import discover
from ug_core.runner import run_scenario
from ug_core.store.run import RunStore

from ug_cli.doctor import _finite_float, _no_constant, _unique_keys


def _read_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_no_constant,
        parse_float=_finite_float,
        object_pairs_hook=_unique_keys,
    )


def _root() -> Path:
    cwd = Path.cwd()
    for path in (cwd, *cwd.parents):
        if (path / "contracts/v1").is_dir():
            return path
    raise ValueError("Contracts folder contracts/v1 not found; run from the repository")


def _validate(scenario: Any, root: Path) -> None:
    registry: Registry[Any] = Registry()
    for path in sorted((root / "contracts/v1").glob("*.schema.json")):
        resource = Resource.from_contents(
            _read_json(path), default_specification=DRAFT202012
        )
        registry = registry.with_resource(
            resource.id() or path.resolve().as_uri(), resource
        )
    schema = _read_json(root / "contracts/v1/scenario-config.schema.json")
    Draft202012Validator(schema, registry=registry).validate(scenario)


def _git_commit(root: Path) -> str | None:
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        if not status.stdout:
            return subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    print(
        "Warning: run is not tied to a commit (working tree dirty or git unavailable)",
        file=sys.stderr,
    )
    return None


def run_command(args: argparse.Namespace) -> int:
    try:
        if args.network == "osm" or args.tier != "lite":
            raise ValueError("not available before T-B1-013")
        root = _root()
        adapter = discover().get("water")
        if not isinstance(adapter, AdapterBase):
            raise ValueError("water domain with run capabilities is not installed")
        path = Path(args.scenario)
        if path.is_file() or path.suffix == ".json":
            scenario = _read_json(path)
        else:
            presets = adapter.presets()
            if args.scenario not in presets:
                raise ValueError(
                    f"Unknown preset {args.scenario!r}; known ids: {', '.join(sorted(presets))}"
                )
            scenario = deepcopy(presets[args.scenario])
        if isinstance(scenario, dict) and args.seed is not None:
            scenario["seed"] = args.seed
            network = scenario.get("network_version", "")
            if isinstance(network, str) and network.startswith(
                "procedural-capital-v1-seed"
            ):
                scenario["network_version"] = f"procedural-capital-v1-seed{args.seed}"
        _validate(scenario, root)
        assumption_id = scenario["assumption_set"]
        assumption = load_assumptions(
            (args.assumptions or root / "assumptions") / f"{assumption_id}.yaml"
        )
        if assumption.set_id != assumption_id:
            raise ValueError(
                f"assumption set_id {assumption.set_id!r} does not match {assumption_id!r}"
            )
        record = run_scenario(
            adapter,
            scenario,
            RunStore(args.store or root / "data/runs"),
            {assumption_id: assumption},
            git_commit=_git_commit(root),
        )
        print(f"run_id: {record.run_id}\ninput_hash: {record.input_hash}")
        return 0
    except Exception as exc:
        print(f"ug run: {exc}", file=sys.stderr)
        return 1
