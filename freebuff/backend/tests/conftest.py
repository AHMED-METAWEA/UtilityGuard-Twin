import pytest

from app.scenarios.library import get_preset
from app.scenarios.runner import run_scenario


@pytest.fixture(scope="session")
def normal_bundle():
    return run_scenario(get_preset("normal"))


@pytest.fixture(scope="session")
def leak_bundle():
    return run_scenario(get_preset("leak_sudden"))


@pytest.fixture(scope="session")
def drift_bundle():
    return run_scenario(get_preset("sensor_drift"))


@pytest.fixture(scope="session")
def pump_bundle():
    return run_scenario(get_preset("pump_outage"))
