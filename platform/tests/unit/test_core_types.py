"""Tests for the core types (task T-A1-003).

Each group names the pitfall from docs/audit/PITFALLS.md that it guards against.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from ug_core import (
    Evidenced,
    EvidenceLabel,
    Manifest,
    NonFiniteError,
    SeedStreams,
    StreamSource,
    TelemetrySeries,
    Timebase,
    finite,
)
from ug_core.canonical import canonical_json
from ug_core.numeric import round_for_hash
from ug_core.truth import TruthEvent, TruthSeries

REPO_ROOT = Path(__file__).resolve().parents[3]
START = datetime(2026, 1, 1, tzinfo=UTC)


def tb(n: int = 4, step: int = 300) -> Timebase:
    return Timebase(start=START, step_seconds=step, n_ticks=n)


def run_python(code: str, hash_seed: str = "0") -> str:
    """Run `code` in a fresh interpreter and return its stdout."""
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout.strip()


# --------------------------------------------------------------------------- evidence labels


def test_exactly_nine_labels_matching_the_honesty_rules_text() -> None:
    assert len(EvidenceLabel) == 9
    rules = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    match = re.search(r"evidence label: ([A-Z_, ]+)\.", rules)
    assert match, "label list not found in AGENTS.md"
    listed = {name.strip() for name in match.group(1).split(",")}
    assert {label.value for label in EvidenceLabel} == listed


def test_master_spec_labels_are_a_subset_of_the_code_labels() -> None:
    """The Spec section 2 table lists eight labels; the code has nine (adds PUBLIC_GEOMETRY).

    This guards against drift in one direction only: a label the Spec names must exist in code.
    """
    spec = (REPO_ROOT / "docs" / "UtilityGuard_Master_Spec.md").read_text(
        encoding="utf-8"
    )
    table = spec.split("## 2. Honesty rules", 1)[1].split("## 3.", 1)[0]
    in_spec = set(re.findall(r"^\| `([A-Z_]+)` \|", table, flags=re.MULTILINE))
    assert in_spec, "no labels found in the Spec table"
    assert in_spec <= {label.value for label in EvidenceLabel}


def test_unknown_label_is_rejected() -> None:
    with pytest.raises(ValueError):
        EvidenceLabel("MAGIC")
    with pytest.raises(ValueError):
        Evidenced(1.0, "MAGIC", "ev_1")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Evidenced(1.0, None, "ev_1")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- Evidenced


def test_evidenced_cannot_be_built_without_a_label() -> None:
    with pytest.raises(TypeError):
        Evidenced(1.0, evidence_id="ev_1")  # type: ignore[call-arg]


def test_evidenced_accepts_a_known_label_given_as_text() -> None:
    value = Evidenced(12.5, "SIMULATION", "ev_sim_1", unit="m")  # type: ignore[arg-type]
    assert value.label is EvidenceLabel.SIMULATION
    assert value.unit == "m"


def test_insufficient_evidence_if_and_only_if_no_value() -> None:
    declined: Evidenced[float] = Evidenced(
        None, EvidenceLabel.INSUFFICIENT_EVIDENCE, "ev_none"
    )
    assert declined.value is None
    with pytest.raises(ValueError):
        Evidenced(3.0, EvidenceLabel.INSUFFICIENT_EVIDENCE, "ev_x")
    with pytest.raises(ValueError):
        Evidenced(None, EvidenceLabel.SIMULATION, "ev_y")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_evidenced_rejects_non_finite_numbers(bad: float) -> None:
    with pytest.raises(NonFiniteError):
        Evidenced(bad, EvidenceLabel.SIMULATION, "ev_bad")


def test_calculated_needs_a_formula_and_inputs() -> None:
    ok = Evidenced(
        11520.0,
        EvidenceLabel.CALCULATED,
        "ev_cost",
        unit="EGP",
        formula="lost_water_m3 * unit_price",
        inputs=("ev_sim_loss", "as_water_price@v1"),
    )
    assert ok.inputs == ("ev_sim_loss", "as_water_price@v1")
    with pytest.raises(ValueError):
        Evidenced(1.0, EvidenceLabel.CALCULATED, "ev_a", inputs=("x",))
    with pytest.raises(ValueError):
        Evidenced(1.0, EvidenceLabel.CALCULATED, "ev_b", formula="a*b")


def test_evidenced_is_frozen() -> None:
    value = Evidenced(1.0, EvidenceLabel.ASSUMPTION, "as_1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        value.value = 2.0  # type: ignore[misc]


# --------------------------------------------------------------------------- Timebase (P-03, P-05)


def test_timebase_basics_and_utc_normalisation() -> None:
    cairo = timezone(timedelta(hours=2))
    base = Timebase(
        start=datetime(2026, 1, 1, 2, 0, tzinfo=cairo), step_seconds=300, n_ticks=12
    )
    assert base.start == START
    assert len(base) == 12
    assert base.iso_at(3) == "2026-01-01T00:15:00Z"
    assert base.tick_at(START + timedelta(minutes=15)) == 3


def test_timebase_conversion_is_exact_never_rounded() -> None:
    base = tb(n=200)
    assert base.tick_at_offset(43200) == 144  # hour 12 at 5 min steps
    with pytest.raises(ValueError):
        base.tick_at_offset(
            43201
        )  # one second off a tick: error, not silently tick 144
    with pytest.raises(ValueError):
        base.tick_at_offset(float("nan"))
    with pytest.raises(ValueError):
        base.tick_at_offset(-300)
    with pytest.raises(ValueError):
        base.tick_at_offset(300 * 200)  # one past the end


def test_timebase_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        Timebase(
            start=datetime(2026, 1, 1), step_seconds=300, n_ticks=4
        )  # naive datetime
    with pytest.raises(ValueError):
        Timebase(start=START, step_seconds=0, n_ticks=4)
    with pytest.raises(ValueError):
        Timebase(start=START, step_seconds=300, n_ticks=0)


# --------------------------------------------------------------------------- truth vs telemetry


def test_truth_and_telemetry_are_unrelated_types() -> None:
    assert not issubclass(TruthSeries, TelemetrySeries)
    assert not issubclass(TelemetrySeries, TruthSeries)
    assert TruthSeries.__mro__[1:] == (object,)
    assert TelemetrySeries.__mro__[1:] == (object,)
    truth_fields = {f.name for f in dataclasses.fields(TruthSeries)} | {
        f.name for f in dataclasses.fields(TruthEvent)
    }
    telemetry_fields = {f.name for f in dataclasses.fields(TelemetrySeries)}
    assert telemetry_fields.isdisjoint(truth_fields - {"timebase"})


def test_telemetry_module_never_imports_truth() -> None:
    """Import-graph check in a fresh interpreter (pitfalls P-01, P-03)."""
    out = run_python(
        "import sys, ug_core.telemetry, ug_core.timebase, ug_core.evidence, ug_core.manifest, "
        "ug_core.rng; print('ug_core.truth' in sys.modules)"
    )
    assert out == "False"


def test_top_level_package_does_not_export_truth() -> None:
    import ug_core

    assert not hasattr(ug_core, "TruthSeries")
    assert not hasattr(ug_core, "TruthEvent")
    out = run_python("import sys, ug_core; print('ug_core.truth' in sys.modules)")
    assert out == "False"


def test_truth_series_validation() -> None:
    base = tb(n=3)
    series = TruthSeries(base, {"pressure:J01": [30.0, 29.5, 29.0]})
    assert series.channels["pressure:J01"] == (30.0, 29.5, 29.0)
    with pytest.raises(ValueError):
        TruthSeries(base, {"pressure:J01": [30.0, 29.5]})  # wrong length
    with pytest.raises(NonFiniteError):
        TruthSeries(base, {"pressure:J01": [30.0, float("nan"), 29.0]})
    with pytest.raises(ValueError):
        TruthSeries(base, {}, events=(TruthEvent("leak", "PIPE_17", start_tick=5),))


def test_truth_event_order_does_not_matter() -> None:
    base = tb(n=10)
    a = TruthEvent("leak", "PIPE_17", start_tick=2, parameters={"area_cm2": 6.0})
    b = TruthEvent("pump_trip", "PUMP_1", start_tick=5, end_tick=7)
    one = TruthSeries(base, {"x": [0.0] * 10}, events=(a, b))
    two = TruthSeries(base, {"x": [0.0] * 10}, events=(b, a))
    assert one.events == two.events
    assert one.content_hash() == two.content_hash()


def test_telemetry_missing_is_none_and_non_finite_is_rejected() -> None:
    base = tb(n=3)
    series = TelemetrySeries(base, {"P01": [30.0, None, 29.0]})
    assert series.readings["P01"][1] is None
    assert series.missing_count("P01") == 1
    assert series.label is EvidenceLabel.SENSOR_SIM
    with pytest.raises(NonFiniteError):
        TelemetrySeries(base, {"P01": [30.0, float("nan"), 29.0]})
    with pytest.raises(ValueError):
        TelemetrySeries(base, {"P01": [30.0, None]})


def test_telemetry_label_must_be_a_telemetry_label() -> None:
    base = tb(n=2)
    for label in (
        EvidenceLabel.OBSERVED,
        EvidenceLabel.BENCHMARK,
        EvidenceLabel.SENSOR_SIM,
    ):
        assert TelemetrySeries(base, {"P01": [1.0, 2.0]}, label=label).label is label
    with pytest.raises(ValueError):
        TelemetrySeries(base, {"P01": [1.0, 2.0]}, label=EvidenceLabel.SIMULATION)


def test_stream_source_values() -> None:
    assert {s.value for s in StreamSource} == {"REPLAY", "SIMULATED", "LIVE"}


def test_content_hash_ignores_noise_below_the_rounding_precision() -> None:
    base = tb(n=2)
    one = TelemetrySeries(base, {"P01": [30.0000001, 29.0]})
    two = TelemetrySeries(base, {"P01": [30.0000002, 29.0]})
    three = TelemetrySeries(base, {"P01": [30.01, 29.0]})
    assert one.content_hash() == two.content_hash()
    assert one.content_hash() != three.content_hash()


# --------------------------------------------------------------------------- Manifest (P-06)

FAULTS = [
    {"type": "leak", "target": "PIPE_17", "start_s": 43200, "area_cm2": 6.0},
    {"type": "sensor_drift", "target": "P05", "start_s": 36000, "per_hour": 0.3},
    {"type": "pump_outage", "target": "PUMP_1", "start_s": 64800, "duration_s": 14400},
]


def make_manifest(faults: list[dict] | None = None, **changes: object) -> Manifest:
    kwargs: dict = {
        "config": {
            "scenario": "leak_demo",
            "horizon_hours": 48,
            "step_seconds": 300,
            "demand": {"holiday": False, "heatwave": 1.0},
            "faults": list(FAULTS if faults is None else faults),
        },
        "seed": 42,
        "versions": {"network_version": "f1_demo", "contract_version": "1"},
        "libraries": {"numpy": "2.4.6"},
        "git_commit": None,
        "unordered": ("faults",),
    }
    kwargs.update(changes)
    return Manifest(**kwargs)


def test_manifest_known_answer_hash() -> None:
    """Pins the canonical form. A failure means canonicalisation changed: a breaking change."""
    manifest = make_manifest(faults=FAULTS[:2])
    assert manifest.input_hash() == (
        "647285baf03f84197d681a3b66ad5bb062cbe14404dccb551ff6539609ff7584"
    )
    assert manifest.config_hash() == (
        "207f32cfc36a1d49e177be9548e5928ae80445c5a9a5a4754ca2292c107962eb"
    )


def test_manifest_hash_is_independent_of_fault_order() -> None:
    reference = make_manifest()
    for permutation in itertools.permutations(FAULTS):
        other = make_manifest(faults=list(permutation))
        assert other == reference
        assert other.input_hash() == reference.input_hash()
        assert other.config_hash() == reference.config_hash()


def test_manifest_hash_is_independent_of_dictionary_order() -> None:
    forward = make_manifest()
    config = dict(reversed(list(dict(forward.config).items())))
    backward = make_manifest(config={k: _thaw(v) for k, v in config.items()})
    assert forward.input_hash() == backward.input_hash()


def _thaw(value: object) -> object:
    from ug_core.canonical import thaw

    return thaw(value)


def test_manifest_hash_changes_when_anything_that_matters_changes() -> None:
    reference = make_manifest().input_hash()
    changed = {
        "seed": make_manifest(seed=43),
        "version": make_manifest(
            versions={"network_version": "f1_demo2", "contract_version": "1"}
        ),
        "library": make_manifest(libraries={"numpy": "2.4.7"}),
        "git": make_manifest(git_commit="abc123"),
        "fault value": make_manifest(
            faults=[{**FAULTS[0], "area_cm2": 6.5}, *FAULTS[1:]]
        ),
        "extra fault": make_manifest(
            faults=[*FAULTS, {"type": "leak", "target": "PIPE_30"}]
        ),
        "duplicate fault": make_manifest(faults=[*FAULTS, FAULTS[0]]),
    }
    for name, manifest in changed.items():
        assert manifest.input_hash() != reference, name


def test_ordered_lists_keep_their_order() -> None:
    one = make_manifest(config={"steps": [1, 2, 3]}, unordered=())
    two = make_manifest(config={"steps": [3, 2, 1]}, unordered=())
    assert one.input_hash() != two.input_hash()


def test_integral_float_and_int_hash_the_same() -> None:
    one = make_manifest(config={"horizon_hours": 48}, unordered=())
    two = make_manifest(config={"horizon_hours": 48.0}, unordered=())
    assert one.input_hash() == two.input_hash()
    assert canonical_json({"x": -0.0}) == canonical_json({"x": 0})


def test_output_hashes_are_recorded_but_not_part_of_the_input_hash() -> None:
    base = make_manifest()
    done = base.with_output_hashes({"truth": "a" * 64, "telemetry": "b" * 64})
    assert done.input_hash() == base.input_hash()
    assert done != base
    assert done.to_dict()["output_hashes"]["truth"] == "a" * 64
    assert len(base.input_hash()) == 64


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_manifest_rejects_non_finite_config(bad: float) -> None:
    with pytest.raises(NonFiniteError):
        make_manifest(config={"x": bad}, unordered=())


def test_manifest_rejects_non_json_content_and_bad_seeds() -> None:
    with pytest.raises(TypeError):
        make_manifest(config={"x": {1, 2, 3}}, unordered=())
    with pytest.raises(TypeError):
        make_manifest(config={"x": datetime(2026, 1, 1)}, unordered=())
    for bad_seed in (-1, True, 1.5):
        with pytest.raises(ValueError):
            make_manifest(seed=bad_seed)


def test_manifest_is_immutable() -> None:
    manifest = make_manifest()
    with pytest.raises(TypeError):
        manifest.config["scenario"] = "other"  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.seed = 1  # type: ignore[misc]
    assert isinstance(hash(manifest), int)


def test_manifest_hash_is_identical_across_processes_and_hash_seeds() -> None:
    code = (
        f"import sys; sys.path.insert(0, {str(Path(__file__).parent)!r}); "
        "from test_core_types import make_manifest; "
        "print(make_manifest().input_hash())"
    )
    first = run_python(code, hash_seed="1")
    second = run_python(code, hash_seed="2")
    assert first == second == make_manifest().input_hash()
    json.loads(json.dumps(make_manifest().to_dict()))  # to_dict is plain JSON


# --------------------------------------------------------------------------- finite (P-17)


def test_finite_accepts_numbers_and_rejects_the_rest() -> None:
    assert finite(3) == 3.0
    assert finite(2.5) == 2.5
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(NonFiniteError):
            finite(bad)
    for bad_type in (None, "1.0", True):
        with pytest.raises(TypeError):
            finite(bad_type)


def test_round_for_hash_turns_negative_zero_into_zero() -> None:
    assert str(round_for_hash(-0.0000001)) == "0.0"
    assert round_for_hash(1.23456789) == 1.234568


# --------------------------------------------------------------------------- SeedStreams (P-12)


def test_streams_are_deterministic_and_independent_of_each_other() -> None:
    alone = SeedStreams(42).stream("sensor:P01").random(5)
    seeds = SeedStreams(42)
    other = seeds.stream("sensor:P02")
    other.random(1000)  # drawing from another stream must not matter
    together = seeds.stream("sensor:P01").random(5)
    assert list(alone) == list(together)
    assert list(alone) != list(SeedStreams(42).stream("sensor:P02").random(5))
    assert list(alone) != list(SeedStreams(43).stream("sensor:P01").random(5))


def test_stream_known_answer() -> None:
    """Pins the derivation (seed, name) -> stream. A failure after a NumPy upgrade means the
    reference streams moved: record the new NumPy version in manifests and re-pin deliberately."""
    draws = [float(x) for x in SeedStreams(42).stream("sensor:P01").random(3)]
    assert draws == [0.7298091261459085, 0.24040913912583117, 0.8274409243144571]


def test_streams_are_identical_across_processes_and_hash_seeds() -> None:
    code = (
        "from ug_core import SeedStreams; "
        "print(list(SeedStreams(42).stream('sensor:P01').random(3)))"
    )
    first = run_python(code, hash_seed="1")
    second = run_python(code, hash_seed="2")
    assert first == second
    assert "0.7298091261459085" in first


def test_seed_and_name_validation() -> None:
    for bad in (-1, True, 1.5):
        with pytest.raises(ValueError):
            SeedStreams(bad)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        SeedStreams(1).stream("")
