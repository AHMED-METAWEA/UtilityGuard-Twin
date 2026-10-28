"""D-05a: deterministic D2 over readings and quality only."""

from __future__ import annotations

from random import Random

import pytest
from ug_intel.detect.cusum import detect


def run(values: list[float | None], bad: tuple[int, ...] = (), quantum: float = 0.5):
    quality = [
        {"status": "bad" if t in bad else "ok", "flags": []} for t in range(len(values))
    ]
    return detect(
        {"p": values}, {"p": [0.0] * len(values)}, {"p": quality}, {"p": quantum}
    )


@pytest.mark.parametrize("seed", range(1, 6))
def test_two_days_zero_mean_noise_no_alarm_and_determinism(seed: int) -> None:
    rng = Random(seed)
    values = [rng.gauss(0, 1) for _ in range(576)]
    result = run(values, quantum=0.01)
    assert result == run(values, quantum=0.01)
    assert result.sensors["p"].alarm_tick is None
    assert result.sensors["p"].statistics[:288] == (0.0,) * 288
    assert result.sensors["p"].label == "CALCULATED"
    assert result.sensors["p"].formula_ref == "d2.cusum.v1"
    assert result.version == "d2_v1"


@pytest.mark.parametrize("seed", range(1, 6))
def test_negative_three_sigma_step_alarms_within_six_ticks(seed: int) -> None:
    rng = Random(seed)
    baseline = [rng.gauss(0, 1) for _ in range(400)]
    sigma = run(baseline, quantum=0.01).sensors["p"].sigma
    result = run(baseline + [-3 * sigma] * 176, quantum=0.01).sensors["p"]
    assert result.alarm_tick is not None and 400 <= result.alarm_tick <= 405
    assert result.direction == "low"


@pytest.mark.parametrize("sign, direction", [(-1, "low"), (1, "high")])
def test_strict_threshold_and_third_consecutive_updated_exceedance(
    sign: int, direction: str
) -> None:
    # sigma floor = 1; each update adds 4. A statistic equal to h=8 is not an exceedance.
    values: list[float | None] = [0.0] * 288 + [
        sign * 4.5,
        sign * 4.5,
        sign * 4.5,
        None,
        999.0,
        sign * 4.5,
        sign * 4.5,
    ]
    result = run(values, bad=(292,)).sensors["p"]
    assert result.statistics[288:] == (4.0, 8.0, 12.0, 12.0, 12.0, 16.0, 20.0)
    assert result.alarm_tick == 294
    assert result.direction == direction


def test_non_exceedance_resets_persistence() -> None:
    result = run([0.0] * 288 + [-10.0, 1.5, 0.0, -10.0, -10.0, -10.0]).sensors["p"]
    assert result.alarm_tick == 293


def test_calibration_mad_uses_first_288_ticks_non_missing_and_floor() -> None:
    values: list[float | None] = (
        [None, 10000.0] + [9.0, 10.0, 11.0] * 95 + [10.0] + [999.0] * 10
    )
    result = run(values, quantum=0.01).sensors["p"]
    assert result.sigma == 1.4826
    assert run([None] * 300).sensors["p"].statistics == (0.0,) * 300
    assert run([None] * 300).sensors["p"].sigma == 1.0


@pytest.mark.parametrize("quantum", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_quantum_rejected(quantum: float) -> None:
    with pytest.raises(ValueError):
        run([0.0] * 300, quantum=quantum)


def test_misaligned_or_nonfinite_inputs_rejected() -> None:
    for expected, quality in (
        ([0.0], [{"status": "ok"}] * 2),
        ([0.0, float("nan")], [{"status": "ok"}] * 2),
        ([0.0] * 2, []),
    ):
        with pytest.raises(ValueError):
            detect({"p": [0.0] * 2}, {"p": expected}, {"p": quality}, {"p": 0.01})
    with pytest.raises(ValueError):
        run([float("inf")])
