"""The packaged procedural network passes the network validation (lead network tuning card).

Two days per seed keep CI short; the seven-day runs for seeds 1 to 3 are recorded in
`docs/progress/claude-code/T-B1-tuning.md`. SIMULATION on a synthetic network, not field data.
"""

import pytest
from ug_water.network.procedural import ProceduralCapitalProvider
from ug_water.network.validation import validate_network


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_packaged_procedural_network_passes_validation(seed: int) -> None:
    report = validate_network(
        ProceduralCapitalProvider().build(seed), seed=seed, horizon_days=2
    )
    failed = [(c.name, c.value, c.detail) for c in report.checks if c.passed is False]
    assert report.passed, failed
    pinned = next(c for c in report.checks if c.name == "tank_pinned_full")
    # The tanks cycle under the level controls; they are not floating storage held full.
    assert pinned.value < 0.5
