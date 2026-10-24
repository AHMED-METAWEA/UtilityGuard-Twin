import math

import pytest

from app.scenarios.library import get_preset
from app.scenarios.runner import run_scenario
from app.scenarios.schema import (
    ScenarioConfig,
    SensorDropoutFault,
    SensorDriftFault,
    SensorStuckFault,
)


@pytest.fixture(scope="module")
def normal():
    return run_scenario(get_preset("normal"))


def test_normal_48h_runs_without_errors(normal):
    truth = normal.truth
    assert truth.ticks == 576
    assert len(truth.time_iso) == 577
    assert truth.time_iso[0] == "2026-01-01T00:00:00"
    assert truth.time_iso[-1] == "2026-01-03T00:00:00"
    for series in list(truth.pressure.values()) + list(truth.demand.values()):
        assert len(series) == 577
        assert all(math.isfinite(v) for v in series)
    assert all(0 <= v <= 8 for v in truth.tank_level)
    assert normal.runtime_seconds > 0
    assert len(normal.output_hash) == 64


def test_two_runs_same_seed_are_identical(normal):
    again = run_scenario(get_preset("normal"))
    assert again.output_hash == normal.output_hash
    assert again.truth.canon() == normal.truth.canon()
    assert again.readings == normal.readings


def test_leak_lowers_pressure_near_leak(normal):
    leak = run_scenario(get_preset("leak_gradual"))
    # At 11:00 on day 2 the gradual leak is well developed.
    tick = 420
    assert leak.truth.leak_flow_lps[tick] > 5.0
    assert leak.truth.leak_area_cm2[tick] > 3.0
    near = leak.truth.pressure["J20"][tick]
    near_base = leak.baseline.pressure["J20"][tick]
    assert near_base - near > 0.5
    # The simulated leak must not appear in the fault-free baseline.
    assert max(leak.baseline.leak_flow_lps) == 0.0
    assert leak.truth.leak_node == "LEAK_PIPE_17"


def test_sensor_faults_affect_readings_not_ground_truth(normal):
    stuck_cfg = get_preset("sensor_stuck")
    stuck = run_scenario(stuck_cfg)
    # P02 is frozen for hours 20-26 while the true pressure moves.
    start, end = 240, 312
    readings = [stuck.readings["P02"][t] for t in range(start, end)]
    assert len(set(round(v, 6) for v in readings)) == 1
    assert stuck.truth.pressure["J05"][start] != stuck.truth.pressure["J05"][end - 1]
    # Physics is unchanged by sensor faults: same topology/demand/seed-independent.
    assert stuck.truth.pressure["J05"] == normal.truth.pressure["J05"]

    drift = run_scenario(get_preset("sensor_drift"))
    # Drift grows monotonically relative to the fault-free expectation.
    early = drift.readings["P05"][130] - drift.baseline.pressure["J18"][130]
    late = drift.readings["P05"][500] - drift.baseline.pressure["J18"][500]
    assert late - early > 5.0
    assert drift.truth.pressure["J18"] == drift.baseline.pressure["J18"]

    dropout_cfg = ScenarioConfig(
        scenario_id="dropout_test", seed=7,
        duration_hours=4,
        faults=[SensorDropoutFault(
            sensor_id="F02", start_hour=1, duration_hours=2, probability=0.7,
        )],
    )
    dropout = run_scenario(dropout_cfg)
    missing = [t for t in range(12, 37) if dropout.readings["F02"][t] is None]
    assert missing, "dropout should produce missing readings"
    assert len(missing) < 25, "dropout probability should not remove every reading"
    assert dropout.truth.flow["V_PR"][20] != 0.0


def test_sensor_drift_is_deterministic_per_seed():
    cfg = get_preset("sensor_drift")
    a = run_scenario(cfg)
    b = run_scenario(cfg)
    assert a.readings == b.readings
    other = run_scenario(cfg.model_copy(update={"seed": cfg.seed + 1}))
    assert other.readings != a.readings
    assert other.truth.pressure == a.truth.pressure
