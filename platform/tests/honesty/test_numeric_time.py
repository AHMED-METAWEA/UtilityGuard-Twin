"""Behavioural finite-value and exact onset guards."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from honesty_support import rejects
from ug_core import (
    Evidenced,
    EvidenceLabel,
    Manifest,
    NonFiniteError,
    TelemetrySeries,
    Timebase,
    finite,
)
from ug_core.assumptions import AssumptionError, parse_assumptions
from ug_core.truth import TruthSeries


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), -float("inf"), np.float64("nan"), np.float32("inf")],
)
def test_finite_rejects_nonfinite(value):
    """P-17: finite must raise NonFiniteError rather than replace non-finite inputs."""
    with rejects(NonFiniteError, f"P-17: ug_core.finite({value!r})", "finite"):
        finite(value, "P-17: ug_core.finite")


@pytest.mark.parametrize("value", [None, True, "1.0"])
def test_finite_rejects_invalid_types(value):
    """P-17: invalid numeric types must be rejected, never coerced into readings.

    A wrong type is a `TypeError` (the module's documented behaviour); `NonFiniteError` is for
    real numbers that are NaN or infinite. Either way the value is refused, never converted.
    """
    with rejects(
        (TypeError, NonFiniteError), f"P-17: ug_core.finite({value!r}) invalid type"
    ):
        finite(value, "P-17: ug_core.finite invalid numeric type")


@pytest.mark.parametrize(
    "value", [0, -4, 3.125, np.float64(1.5), np.float32(2), np.int64(3)]
)
def test_finite_preserves_numbers(value):
    """P-17: ordinary finite numbers pass through without substitution."""
    assert finite(value) == value, f"P-17: ug_core.finite changed valid {value!r}"


def timebase():
    return Timebase(datetime(2026, 1, 1, tzinfo=UTC), 300, 8)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize(
    "consumer", ["telemetry", "truth", "evidenced", "manifest", "assumption"]
)
def test_entities_reject_nonfinite(consumer, value):
    """P-17: all value containers reject non-finite input at construction/loading."""
    tb = timebase()
    assumptions = {
        "set_id": "honesty_test",
        "parent": None,
        "note": "Synthetic test input",
        "assumptions": {
            "price": {
                "unit": "EGP",
                "source_note": "Placeholder for finite rejection test",
                "verified": False,
                "distribution": {"type": "triangular", "min": 0, "mode": 1, "max": 2},
            }
        },
    }
    raw = deepcopy(assumptions)
    entry = next(iter(raw["assumptions"].values()))
    entry["distribution"]["mode"] = value
    constructors = {
        "telemetry": lambda: TelemetrySeries(tb, {"P01": [value] * tb.n_ticks}),
        "truth": lambda: TruthSeries(tb, {"pressure": [value] * tb.n_ticks}),
        "evidenced": lambda: Evidenced(value, EvidenceLabel.MODEL, "ev_finite"),
        "manifest": lambda: Manifest(config={"x": value}, seed=42, versions={}),
        "assumption": lambda: parse_assumptions(raw),
    }
    # The valid baseline must load so an unrelated fixture error cannot mask NaN acceptance.
    parse_assumptions(assumptions)
    with rejects(
        (NonFiniteError, AssumptionError),
        f"P-17: {consumer} accepted non-finite {value!r}",
        "finite",
    ):
        constructors[consumer]()


def test_missing_telemetry_stays_missing():
    """P-17: a missing telemetry sample stays None, never a healthy-looking zero."""
    tb = timebase()
    series = TelemetrySeries(tb, {"P01": [12.0, None, 0.0, 4.0, 5.0, 6.0, 7.0, 8.0]})
    assert series.readings["P01"][1] is None, "P-17: TelemetrySeries gap became a value"
    assert series.readings["P01"][2] == 0.0, "P-17: genuine zero was lost"
    assert series.missing_count("P01") == 1, "P-17: TelemetrySeries missing count wrong"


@pytest.mark.parametrize("tick", range(8))
def test_exact_onset_ticks(tick):
    """P-05: exact fault onsets map to their tick, including zero and the last tick."""
    tb = timebase()
    offset = tick * tb.step_seconds
    assert tb.tick_at_offset(offset) == tick, (
        f"P-05: offset {offset} landed off tick {tick}"
    )
    assert tb.tick_at(tb.start + timedelta(seconds=offset)) == tick, (
        f"P-05: absolute time for tick {tick} landed late or early"
    )


@pytest.mark.parametrize(
    "offset", [0.000001, 149, 150, 151, 299, 300.000001, 599, 600.5]
)
def test_nonexact_onsets_raise(offset):
    """P-05: fractional-step onsets must fail rather than round/floor/ceil."""
    tb = timebase()
    with rejects(
        ValueError, f"P-05: Timebase.tick_at_offset({offset})", "whole number"
    ):
        tb.tick_at_offset(offset)
    with rejects(
        ValueError, f"P-05: Timebase.tick_at(start + {offset})", "whole number"
    ):
        tb.tick_at(tb.start + timedelta(seconds=offset))
