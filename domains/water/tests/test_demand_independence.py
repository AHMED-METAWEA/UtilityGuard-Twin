"""P-08 regressions: forecasts cannot read or reproduce truth realizations."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from test_demand_helpers import (
    GOLDEN_CALENDAR,
    GOLDEN_TIMEBASE,
    expectation,
    model,
    network,
)
from ug_core.rng import SeedStreams
from ug_core.timebase import Timebase
from ug_water.demand import DemandCalendar, DemandModel
from ug_water.network.model import Zone


@pytest.mark.parametrize(
    "parameter,path,other",
    [
        ("noise_sigma", "truth", "forecast"),
        ("forecast_sigma", "forecast", "truth"),
        ("noise_phi", "truth", "forecast"),
        ("forecast_phi", "forecast", "truth"),
    ],
)
def test_noise_and_forecast_configuration_are_independent(
    parameter: str, path: str, other: str
) -> None:
    baseline = model()
    changed = model(**{parameter: 0.02 if parameter.endswith("sigma") else 0.3})
    args = (network(), GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    assert not np.array_equal(
        getattr(baseline, path)(*args).values, getattr(changed, path)(*args).values
    )
    np.testing.assert_array_equal(
        getattr(baseline, other)(*args).values, getattr(changed, other)(*args).values
    )
    # Full-set provenance intentionally changes even when output values do not.
    assert baseline.assumptions.content_hash() != changed.assumptions.content_hash()


def test_adding_zone_does_not_change_existing_streams() -> None:
    demand = model()
    net = network()
    extra = replace(
        net,
        zones=(*net.zones, Zone("new_zone", "New area", "residential")),
        junctions=(
            *net.junctions,
            replace(net.junctions[0], id="zz_new", zone="new_zone"),
        ),
    )
    for generate in (demand.truth, demand.forecast):
        base = generate(net, GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
        added = generate(extra, GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
        indices = [added.junction_ids.index(j) for j in base.junction_ids]
        np.testing.assert_array_equal(base.values, added.values[:, indices])


def test_forecast_order_and_truth_noise_access_are_independent() -> None:
    demand = model()
    args = (network(), GOLDEN_TIMEBASE, 7, GOLDEN_CALENDAR)
    first = demand.forecast(*args)
    demand.truth(*args)
    assert demand.forecast(*args).content_hash() == first.content_hash()
    with (
        patch.object(
            DemandModel, "truth", side_effect=AssertionError("truth accessed")
        ),
        patch.object(
            DemandModel,
            "_truth_noise",
            side_effect=AssertionError("truth noise accessed"),
        ),
    ):
        assert demand.forecast(*args).content_hash() == first.content_hash()


def test_forecast_call_graph_does_not_reach_truth_noise_and_imports_are_clean() -> None:
    package = Path(__file__).resolve().parents[1] / "src/ug_water/demand"
    definitions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
                names += [f"{node.module}.{alias.name}" for alias in node.names]
            else:
                names = []
            assert not any(
                name == "freebuff"
                or name.startswith("freebuff.")
                or name == "ug_core.truth"
                or name.startswith("ug_core.truth.")
                for name in names
            ), path
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Conservatively follow every same-named callable, including helpers
                # in other modules, rather than missing an ambiguous call edge.
                definitions.setdefault(node.name, []).append(node)
            if isinstance(node, ast.ClassDef):
                constructors = [
                    n
                    for n in node.body
                    if isinstance(n, ast.FunctionDef) and n.name == "__post_init__"
                ]
                if constructors:
                    definitions.setdefault(node.name, []).extend(constructors)
    assert {"truth", "forecast", "_truth_noise"} <= definitions.keys()
    pending = ["forecast"]
    reached = set()
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        for call in (
            n for definition in definitions[name] for n in ast.walk(definition)
        ):
            if isinstance(call, ast.Call):
                target = (
                    call.func.attr
                    if isinstance(call.func, ast.Attribute)
                    else call.func.id
                    if isinstance(call.func, ast.Name)
                    else ""
                )
                if target in definitions:
                    pending.append(target)
    assert not reached & {"truth", "_truth_noise"}, reached
    assert "_forecast_error" in reached


@pytest.mark.parametrize("seed", [7, 71, 123])
def test_stationary_statistics_for_both_paths_all_zones(seed: int) -> None:
    demand = model()
    tb = Timebase(GOLDEN_TIMEBASE.start, 300, 28 * 288)
    cal = GOLDEN_CALENDAR
    expected = expectation(demand, tb, cal)
    for kind, generate in (("noise", demand.truth), ("forecast", demand.forecast)):
        series = generate(network(), tb, seed, cal)
        for zone in network().zones:
            column = next(
                i for i, j in enumerate(network().junctions) if j.zone == zone.id
            )
            errors = series.values[:, column] / expected[:, column] - 1
            sigma = np.std(errors)
            phi = np.corrcoef(errors[:-1], errors[1:])[0, 1]
            assert sigma == pytest.approx(demand.parameter(f"{kind}_sigma"), rel=0.1), (
                kind,
                zone.id,
                sigma,
            )
            assert phi == pytest.approx(demand.parameter(f"{kind}_phi"), abs=0.05), (
                kind,
                zone.id,
                phi,
            )
        assert not np.array_equal(series.values, expected)


def test_exact_named_stream_first_draw_and_shared_noise_within_zone() -> None:
    demand = model()
    tb = Timebase(GOLDEN_TIMEBASE.start, 300, 4)
    net = network()
    expected = expectation(demand, tb, DemandCalendar())
    for kind, prefix, generate in (
        ("noise", "demand.noise", demand.truth),
        ("forecast", "demand.forecast", demand.forecast),
    ):
        values = generate(net, tb, 7, DemandCalendar()).values
        errors = (
            np.divide(values, expected, out=np.ones_like(values), where=expected > 0)
            - 1
        )
        np.testing.assert_array_equal(values[:, expected[0] == 0], 0)
        for zone in net.zones:
            columns = [
                i
                for i, j in enumerate(net.junctions)
                if j.zone == zone.id and j.base_demand > 0
            ]
            first = (
                demand.parameter(f"{kind}_sigma")
                * SeedStreams(7).stream(f"{prefix}.{zone.id}").standard_normal()
            )
            np.testing.assert_allclose(errors[0, columns], first, atol=1e-15)
            np.testing.assert_allclose(
                errors[:, columns],
                np.repeat(errors[:, columns[:1]], len(columns), axis=1),
                atol=1e-15,
            )
    # Moving the time axis does not consume any prior realization.
    shifted = replace(tb, start=tb.start + timedelta(days=1))
    assert demand.forecast(net, shifted, 7, DemandCalendar()).timebase == shifted
