"""Structural honesty guards, including positive and negative scanner controls."""

import inspect

import pytest
import ug_core
from honesty_support import (
    OPERATOR_SIDE,
    ROOT,
    advisory_violations,
    finite_violations,
    rejects,
    truth_violations,
)
from ug_core import TelemetrySeries
from ug_core.truth import TruthEvent, TruthSeries


@pytest.mark.parametrize("root", OPERATOR_SIDE)
def test_operator_truth_boundary(root):
    """P-01/P-03: detector and operator modules cannot import or accept truth."""
    paths = sorted(root.rglob("*.py"))
    assert paths, f"P-01/P-03: no operator modules scanned at {root}"
    for path in paths:
        errors = truth_violations(path.read_text())
        assert not errors, f"P-01/P-03: {path}: {errors}"


@pytest.mark.parametrize("name", ["telemetry", "timebase", "evidence", "manifest"])
def test_shared_types_never_import_truth(name):
    """P-01/P-03: shared telemetry-side types cannot depend on truth."""
    path = ROOT / f"platform/ug_core/src/ug_core/{name}.py"
    errors = truth_violations(path.read_text(), any_truth_import=True)
    assert not errors, f"P-01/P-03: {path}: {errors}"


@pytest.mark.parametrize(
    "source",
    [
        "import ug_core.truth",
        "import ug_core.ports as p",
        "from ug_core.truth import TruthSeries as TS",
        "from ug_core import truth as t",
        "from ug_core import ports",
        "from other import TruthEvent as Event",
        "import TruthSeries as S",
        "import importlib; importlib.import_module('ug_core.truth')",
        "from importlib import import_module as load; load('ug_core.ports')",
        "__import__('ug_core.truth')",
        "from builtins import __import__ as load; load('ug_core.truth')",
        "def check(truth): pass",
        "async def check(*, truth=None): pass",
        "def check(x: TruthSeries): pass",
        "def check(x: 'TruthEvent | None'): pass",
        "def check(*x: 'list[ug_core.truth.TruthSeries]'): pass",
        "def check(**x: TruthEvent): pass",
    ],
)
def test_truth_scanner_rejects(source):
    """P-01/P-03: synthetic leaks must exercise the AST scanner."""
    assert truth_violations(source), f"P-01/P-03: scanner missed {source!r}"


@pytest.mark.parametrize(
    "source",
    [
        "from ug_core import TelemetrySeries, Timebase",
        "def check(x: 'TelemetrySeries', timebase: 'Timebase'): pass",
        "# import ug_core.truth\ntext = 'TruthSeries'",
        "def truth_summary(): return 'truth'",
        "import importlib as il; il.import_module('ug_core.telemetry')",
    ],
)
def test_truth_scanner_allows(source):
    """P-01/P-03: names in comments/strings and ordinary telemetry are legitimate."""
    assert not truth_violations(source), f"P-01/P-03: false positive for {source!r}"


def test_truth_is_not_telemetry():
    """P-01: no common series base, re-export, or public truth conversion."""
    shared = set(TruthSeries.__mro__) & set(TelemetrySeries.__mro__)
    assert shared == {object}, f"P-01: shared truth/telemetry bases: {shared}"
    assert not issubclass(TruthSeries, TelemetrySeries), "P-01: truth is telemetry"
    assert not issubclass(TelemetrySeries, TruthSeries), "P-01: telemetry is truth"
    assert not hasattr(ug_core, "TruthSeries"), "P-01: ug_core exports TruthSeries"
    for name, value in vars(ug_core).items():
        if name.startswith("_") or not callable(value):
            continue
        if name == "MeasurementPort" and value.__module__ == "ug_core.ports":
            continue
        try:
            annotations = str(inspect.signature(value))
        except (TypeError, ValueError):
            continue
        assert not (
            any(t.__name__ in annotations for t in (TruthSeries, TruthEvent))
            and "TelemetrySeries" in annotations
        ), f"P-01: ug_core.{name}{annotations} converts truth outside MeasurementPort"
    from datetime import UTC, datetime

    timebase = ug_core.Timebase(datetime(2026, 1, 1, tzinfo=UTC), 300, 1)
    truth = TruthSeries(timebase, {"pressure": [30.0]})
    with rejects((TypeError, AttributeError), "P-01: TelemetrySeries(timebase, truth)"):
        TelemetrySeries(timebase, truth)


def test_no_silent_nonfinite_conversion():
    """P-17: core modules must reject non-finite values rather than invent zeros."""
    paths = sorted((ROOT / "platform/ug_core/src/ug_core").glob("*.py"))
    assert paths, "P-17: core scan has no files"
    for path in paths:
        errors = finite_violations(path.read_text())
        assert not errors, f"P-17: {path}: {errors}"


@pytest.mark.parametrize(
    "source",
    [
        "np.nan_to_num(x)",
        "frame.fillna(0)",
        "from numpy import nan_to_num as clean; clean(x)",
        "if x != x:\n    return 0.0",
        "if math.isnan(x):\n    x = 0",
        "if isinf(x):\n    x: float = 0.0",
        "if not math.isfinite(x):\n    return 0",
        "from math import isnan as bad\nif bad(x):\n    return 0",
        "if math.isfinite(x):\n    return x\nelse:\n    return 0",
    ],
)
def test_finite_scanner_rejects(source):
    """P-17: replacement calls and direct zero substitution must be caught."""
    assert finite_violations(source), f"P-17: scanner missed {source!r}"


@pytest.mark.parametrize(
    "source",
    [
        "if not math.isfinite(x):\n    raise NonFiniteError('bad')",
        "if isnan(x):\n    raise ValueError('bad')",
        "if x != y:\n    return 0",
        "if x is None:\n    return None",
        "text = 'nan_to_num(x)' # not executed",
    ],
)
def test_finite_scanner_allows(source):
    """P-17: legitimate rejection and unrelated zero returns must pass."""
    assert not finite_violations(source), f"P-17: false positive {source!r}"


def test_advisory_only():
    """P-04: advisory-only Honesty Rule excludes equipment control paths."""
    paths = [
        path
        for root in (ROOT / "platform", ROOT / "domains")
        for src in root.glob("*/src")
        for path in src.rglob("*.py")
    ]
    assert paths, "P-04: advisory scan has no source files"
    for path in sorted(paths):
        errors = advisory_violations(path.read_text())
        assert not errors, f"P-04: {path}: {errors}"


@pytest.mark.parametrize(
    "source",
    [
        "import pymodbus as m",
        "from opcua import Client",
        "import asyncua",
        "import paho.mqtt.client",
        "import serial",
        "import snap7",
        "import bacpypes",
        "import pycomm3",
        "import minimalmodbus",
        "__import__('serial')",
        "def write_to_pump(): pass",
        "async def actuate_valve(): pass",
        "def set_setpoint(x): pass",
    ],
)
def test_advisory_scanner_rejects(source):
    """P-04: advisory-only scanner must catch control imports and entry points."""
    assert advisory_violations(source), f"P-04: scanner missed {source!r}"


@pytest.mark.parametrize(
    "source", ["import json", "def read_pressure(): pass", "text = 'import serial'"]
)
def test_advisory_scanner_allows(source):
    """P-04: advisory scanner allows ordinary readers and string literals."""
    assert not advisory_violations(source), f"P-04: false positive {source!r}"
