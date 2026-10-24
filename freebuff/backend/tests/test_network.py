from app.config import NETWORK_VERSION, SENSOR_IDS
from app.network.builder import DEFAULT_PROVIDER, GRID_PIPE_MAX
from app.scenarios.schema import ScenarioConfig


def test_network_shape_and_sensors():
    desc = DEFAULT_PROVIDER.describe()
    assert desc.network_version == NETWORK_VERSION
    junctions = [n for n in desc.nodes if n.kind == "junction"]
    assert 30 <= len(junctions) <= 40
    pipes = [l for l in desc.links if l.kind == "pipe"]
    assert 45 <= len(pipes) <= 60
    assert sum(1 for l in desc.links if l.kind == "valve") >= 3
    assert len(desc.sensors) == 12
    assert tuple(s.id for s in desc.sensors) == SENSOR_IDS
    assert {s.kind for s in desc.sensors} == {"pressure", "flow", "level"}
    assert {z.id for z in desc.zones} == {"gov", "res", "com"}
    assert len({n.id for n in desc.nodes}) == len(desc.nodes)


def test_network_builds_and_is_connected():
    wn = DEFAULT_PROVIDER.build()
    assert wn.num_nodes == 41
    assert wn.num_links == 66
    assert "PUMP_1" in wn.link_name_list
    assert wn.get_link("PUMP_2").initial_status.name == "Closed"
    assert wn.get_node("TANK1").node_type == "Tank"


def test_scenario_contract_defaults():
    cfg = ScenarioConfig(scenario_id="x")
    assert cfg.network_version == NETWORK_VERSION
    assert cfg.duration_hours == 48
    assert cfg.timestep_minutes == 5
    assert cfg.ticks == 576
    assert cfg.demand.heatwave_multiplier == 1.0
    assert cfg.demand.zone_multipliers == {"gov": 1.0, "res": 1.0, "com": 1.0}
    assert GRID_PIPE_MAX == 60
