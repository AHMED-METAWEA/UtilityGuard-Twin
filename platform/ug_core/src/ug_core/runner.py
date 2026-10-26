"""Privileged simulation orchestration; never imported by operator consumers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from importlib.metadata import version
from typing import Any, Protocol

from ug_core.adapter.protocols import PhysicalSolver
from ug_core.assumptions import AssumptionSet
from ug_core.manifest import Manifest
from ug_core.store import truth_bundle
from ug_core.store.run import RunStore
from ug_core.timebase import Timebase


class RunAdapter(Protocol):
    """Optional run capabilities, independent of any domain package."""

    def asset_model(self, params: Any) -> Any: ...
    def solver(self) -> PhysicalSolver: ...
    def run_versions(self, asset: Any) -> Mapping[str, str]: ...
    def run_libraries(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class RunState:
    asset: Any
    assumptions: Mapping[str, AssumptionSet]


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    input_hash: str


def run_scenario(
    adapter: RunAdapter,
    scenario: Mapping[str, Any],
    store: RunStore,
    assumptions: Mapping[str, AssumptionSet],
    *,
    git_commit: str | None,
) -> RunRecord:
    """Run a validated recipe and publish its restricted simulation bundle."""
    asset = adapter.asset_model(scenario)
    steps = (
        Fraction(str(scenario["duration_hours"])) * 60 / scenario["timestep_minutes"]
    )
    if steps <= 0 or steps.denominator != 1:
        raise ValueError("duration_hours must be a positive whole number of steps")
    horizon = Timebase(
        datetime.fromisoformat(scenario["start"].replace("Z", "+00:00")),
        scenario["timestep_minutes"] * 60,
        int(steps) + 1,
    )
    truth = adapter.solver().run(RunState(asset, assumptions), scenario, horizon)
    manifest = Manifest(
        config=scenario,
        seed=scenario["seed"],
        unordered=("faults",),
        versions={
            "contracts": "v1",
            "assumption_set": assumptions[scenario["assumption_set"]].content_hash(),
            **adapter.run_versions(asset),
        },
        libraries={
            name: version(name)
            for name in (
                "numpy",
                "pyarrow",
                "duckdb",
                "jsonschema",
                *adapter.run_libraries(),
            )
        },
        git_commit=git_commit,
    )
    draft = store.new(manifest)
    truth_bundle.write_truth(draft, truth)
    return RunRecord(store.write(draft), manifest.input_hash())
