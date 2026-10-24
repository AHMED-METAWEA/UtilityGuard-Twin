import pytest

from app.analysis import analyze_bundle
from app.detect.baseline import ExpectedModel
from app.quality.checks import evaluate_quality


@pytest.fixture(scope="module")
def normal_quality(normal_bundle):
    expected = ExpectedModel(normal_bundle.baseline)
    return evaluate_quality(normal_bundle.readings, normal_bundle.truth, expected)


@pytest.fixture(scope="module")
def stuck_quality():
    from app.scenarios.library import get_preset
    from app.scenarios.runner import run_scenario

    bundle = run_scenario(get_preset("sensor_stuck"))
    expected = ExpectedModel(bundle.baseline)
    return bundle, evaluate_quality(bundle.readings, bundle.truth, expected)


def test_quality_statuses_are_valid(normal_quality):
    for result in normal_quality.values():
        assert set(result.status) <= {"ok", "suspect", "bad"}
        assert len(result.status) == len(result.score) == len(result.flags)
        assert all(0.0 <= score <= 1.0 for score in result.score)


def test_fault_free_run_has_no_bad_readings(normal_quality):
    bad = sum(1 for result in normal_quality.values() for status in result.status if status == "bad")
    suspect = sum(1 for result in normal_quality.values() for status in result.status if status == "suspect")
    total = sum(len(result.status) for result in normal_quality.values())
    assert bad == 0
    # The quality layer may flag individual samples; it must stay a small
    # fraction of all readings on a fault-free run (< 2% of samples).
    assert suspect / total < 0.02


def test_stuck_sensor_is_flagged_bad(stuck_quality):
    bundle, quality = stuck_quality
    result = quality["P02"]
    # P02 is frozen from hour 20 to 26 (ticks 240-312).
    window = range(250, 310)
    flagged = [tick for tick in window if "stuck" in result.flags[tick]]
    assert len(flagged) > 40
    assert any(result.status[tick] == "bad" for tick in window)
    assert len({bundle.readings["P02"][tick] for tick in window}) == 1
    # Neighbouring pressure sensors are not blamed for the frozen sensor.
    others_bad = sum(
        1 for sid, item in quality.items() if sid != "P02"
        for tick in window if item.status[tick] == "bad"
    )
    assert others_bad == 0


def test_drift_is_flagged_relative_to_neighbours(drift_bundle):
    expected = ExpectedModel(drift_bundle.baseline)
    quality = evaluate_quality(drift_bundle.readings, drift_bundle.truth, expected)
    late = range(500, 560)
    p05 = quality["P05"]
    flagged = [tick for tick in late if "drift_vs_neighbors" in p05.flags[tick]]
    assert len(flagged) > 20
    # Other pressure sensors are not flagged in the same window.
    p06 = quality["P06"]
    assert sum(1 for tick in late if "drift_vs_neighbors" in p06.flags[tick]) < 5


def test_analysis_payload_quality_matches_quality_layer(leak_bundle):
    analysis = analyze_bundle(leak_bundle, "quality-check")
    quality = analysis["quality"]
    assert set(quality) == {sensor.id for sensor in __import__(
        "app.network.builder", fromlist=["DEFAULT_PROVIDER"]
    ).DEFAULT_PROVIDER.describe().sensors}
    for series in quality.values():
        assert len(series["status"]) == leak_bundle.truth.ticks + 1
