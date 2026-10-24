import pytest

from app.analysis import analyze_bundle


@pytest.fixture(scope="module")
def normal_analysis(normal_bundle):
    return analyze_bundle(normal_bundle, "run-normal")


@pytest.fixture(scope="module")
def leak_analysis(leak_bundle):
    return analyze_bundle(leak_bundle, "run-leak")


@pytest.fixture(scope="module")
def drift_analysis(drift_bundle):
    return analyze_bundle(drift_bundle, "run-drift")


@pytest.fixture(scope="module")
def pump_analysis(pump_bundle):
    return analyze_bundle(pump_bundle, "run-pump")


def test_fault_free_run_has_no_incidents(normal_analysis):
    assert normal_analysis["incidents"] == []
    assert normal_analysis["summary"]["alert_ticks"] == 0
    # Watch states are allowed; they must never open an incident.
    assert set(normal_analysis["detector"]["state"]) <= {"normal", "watch"}


def test_sudden_leak_is_detected_after_it_starts(leak_analysis):
    incidents = leak_analysis["incidents"]
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["diagnosis"] == "leak"
    # The leak starts at hour 12 = tick 144.
    assert 144 < incident["first_detected_tick"] < 400
    assert incident["severity"] in {"medium", "high"}
    assert incident["candidates"], "a leak incident should expose candidate pipes"
    residuals = incident["evidence_numbers"]["residuals_sigma"]
    assert residuals["P05"] < -4, "pressure near the leak should fall sharply"
    assert residuals["F02"] > 0, "tank outflow should rise during a leak"


def test_sensor_drift_is_diagnosed_as_sensor_fault(drift_analysis):
    incidents = drift_analysis["incidents"]
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["diagnosis"] == "sensor_fault"
    assert incident["suspected_location"] == "P05"
    assert incident["quality_context"]["flags"]["P05"], "P05 should carry a quality flag"
    assert incident["evidence_numbers"]["residuals_sigma"]["P05"] > 4


def test_pump_outage_is_diagnosed_as_pump_issue(pump_analysis):
    incidents = pump_analysis["incidents"]
    assert len(incidents) == 1, "a recovery transient must not open a second incident"
    incident = incidents[0]
    assert incident["diagnosis"] == "pump_issue"
    assert incident["suspected_location"] == "PUMP_1"
    assert incident["first_detected_tick"] >= 216


def test_detector_reports_only_model_labels(leak_analysis):
    assert leak_analysis["labels"]["detector"] == "MODEL"
    assert leak_analysis["labels"]["quality"] == "MODEL"
    sources = {
        reading.get("source")
        for reading in leak_analysis["summary"].get("sensor_sources", []) or []
    }
    assert sources <= {"SENSOR_SIM"} or not sources
