"""D-04 quality rules consume telemetry and optional model expectations only."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ug_core.telemetry import TelemetrySeries
from ug_core.timebase import Timebase
from ug_intel.quality import assess


def series(values: list[float | None], step: int = 300) -> TelemetrySeries:
    return TelemetrySeries(
        Timebase(datetime(2027, 1, 1, tzinfo=UTC), step, len(values)), {"s": values}
    )


def test_missing_stale_range_and_worst_score() -> None:
    result = assess(
        series([None, 5.0, 11.0, -1.0, 5.0]),
        {"s": "pressure"},
        {"s": 0.01},
        {"s": (0.0, 10.0)},
        {"s": [700.0, 601.0, 601.0, 0.0, 600.0]},
    )["s"]
    assert [q["flags"] for q in result] == [
        ["Q01"],
        ["Q01"],
        ["Q01", "Q02"],
        ["Q02"],
        [],
    ]
    assert [q["status"] for q in result] == ["bad", "suspect", "bad", "bad", "ok"]
    assert [q["score"] for q in result] == [0.0, 0.5, 0.0, 0.0, 1.0]
    assert all(
        q["label"] == "CALCULATED" and q["formula_ref"] == "quality.score.v1"
        for q in result
    )


@pytest.mark.parametrize("step, window", [(300, 12), (600, 6), (240, 15)])
def test_flatline_full_non_null_window(step: int, window: int) -> None:
    values = [5.0] * (window - 1) + [None, 5.0, 5.0]
    flags = assess(
        series(values, step), {"s": "any_kind"}, {"s": 0.01}, {"s": (0.0, 10.0)}
    )["s"]
    assert all("Q04" not in q["flags"] for q in flags[:window])
    assert flags[window]["flags"] == ["Q04"] and flags[window]["score"] == 0.5


def test_flatline_includes_one_quantum_but_not_more() -> None:
    for difference, flag in ((0.01, True), (0.02, False)):
        for baseline in (0.0, 20.0):
            result = assess(
                series([baseline] * 11 + [baseline + difference]),
                {"s": "x"},
                {"s": 0.01},
                {"s": (-100.0, 100.0)},
            )
            assert ("Q04" in result["s"][-1]["flags"]) == flag


def test_q08_mad_floor_ewma_and_optional_expectations() -> None:
    values = [float(k % 2) for k in range(288)] + [10.0] * 20
    expected = [float(k % 2) for k in range(288)] + [0.0] * 20
    result = assess(
        series(values),
        {"s": "pressure"},
        {"s": 0.1},
        {"s": (-100.0, 100.0)},
        expected={"s": expected},
    )["s"]
    # sigma = max(0, 2 * .1) = .2; z = 50; EWMA is 1, 1.98, 2.9404, 3.881592.
    assert all("Q08" not in q["flags"] for q in result[:291])
    assert "Q08" in result[291]["flags"]
    absent = assess(
        series(values), {"s": "pressure"}, {"s": 0.1}, {"s": (-100.0, 100.0)}
    )
    assert all("Q08" not in q["flags"] for q in absent["s"])


def test_q08_uses_median_absolute_deviation_not_standard_deviation() -> None:
    # Baseline residual median 10, MAD 1; large isolated calibration outlier must not inflate sigma.
    residuals = [9.0, 10.0, 11.0] * 95 + [9.0, 11.0, 10000.0] + [100.0] * 10
    result = assess(
        series(residuals),
        {"s": "x"},
        {"s": 0.01},
        {"s": (-20000.0, 20000.0)},
        expected={"s": [0.0] * len(residuals)},
    )["s"]
    sigma = 1.4826
    ewma = 0.0
    for residual, quality in zip(residuals, result, strict=True):
        ewma = 0.02 * residual / sigma + 0.98 * ewma
        assert ("Q08" in quality["flags"]) == (abs(ewma) > 3)


def test_q08_missing_does_not_update_ewma_and_negative_residuals_trigger() -> None:
    values: list[float | None] = [0.0] * 288 + [None, -10.0, None, -10.0, -10.0, -10.0]
    result = assess(
        series(values),
        {"s": "x"},
        {"s": 0.1},
        {"s": (-100.0, 100.0)},
        expected={"s": [0.0] * len(values)},
    )["s"]
    assert "Q08" not in result[-2]["flags"]
    assert "Q08" in result[-1]["flags"]


def test_all_intelligence_modules_have_no_truth_ports_or_domain_imports() -> None:
    root = Path(__file__).resolve().parents[3]
    domains = {f"ug_{p.name}" for p in (root / "domains").iterdir() if p.is_dir()}
    forbidden = {"ug_core.truth", "ug_core.ports", "domains", *domains}
    intel = root / "platform/ug_intel/src/ug_intel"
    paths = set(intel.rglob("*.py"))
    # Explicit coverage guard: new D-05a modules must exist and be scanned.
    assert {
        intel / name for name in ("detect/cusum.py", "detect/incident.py", "trend.py")
    } <= paths
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [
                    node.module or "",
                    *[f"{node.module}.{a.name}" for a in node.names],
                ]
            elif (
                isinstance(node, ast.Call)
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "__import__"
                    or isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                ):
                    names = [node.args[0].value]
            assert not any(
                name == blocked or name.startswith(blocked + ".")
                for name in names
                for blocked in forbidden
            ), f"{path}:{node.lineno}: {names}"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"delivered_delay_s": {"s": [0.0]}},
        {"expected": {"s": [0.0]}},
        {"delivered_delay_s": {"s": [0.0, float("nan")]}},
        {"expected": {"s": [0.0, float("inf")]}},
    ],
)
def test_invalid_side_series_fail_clearly(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        assess(
            series([1.0, 2.0]), {"s": "x"}, {"s": 0.01}, {"s": (0.0, 10.0)}, **kwargs
        )
