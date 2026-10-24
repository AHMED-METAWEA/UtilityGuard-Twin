import pytest
from fastapi.testclient import TestClient

from app.config import SETTINGS
from app.evidence.builder import LABELS
from app.finance import engine as finance
from app.main import app
from app.store import db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / "api.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(SETTINGS, "db_path", str(path))
    monkeypatch.setattr(finance, "OVERRIDES_PATH", tmp_path / "assumption_overrides.json")
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_network_metadata(client):
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["disclaimer"] == "Virtual utility twin. Hypothetical network, simulated data."
    network = client.get("/api/network").json()
    assert len(network["sensors"]) == 12
    assert len(network["nodes"]) == 41
    assert network["labels"]["geometry"] == "ASSUMPTION"
    scenarios = client.get("/api/scenarios").json()
    assert len(scenarios["presets"]) >= 8
    assert all("note" in preset for preset in scenarios["presets"])


def test_unknown_scenario_and_bad_config(client):
    missing = client.post("/api/runs", json={"scenario_id": "does_not_exist"})
    assert missing.status_code == 404
    bad = client.post(
        "/api/runs",
        json={"config": {"scenario_id": "x", "duration_hours": 0.1}},
    )
    assert bad.status_code == 422


def test_run_stream_data_and_evidence(client):
    created = client.post("/api/runs?wait=true", json={"scenario_id": "leak_sudden"})
    assert created.status_code == 202, created.text
    payload = created.json()
    assert payload["status"] == "ready"
    assert len(payload["output_hash"]) == 64
    run_id = payload["run_id"]

    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["status"] == "ready"
    assert detail["incident_count"] == 1
    assert detail["has_analysis"] is True

    truth = client.get(f"/api/runs/{run_id}/truth").json()
    assert truth["labels"]["pressure"] == "SIMULATION"
    assert truth["truth"]["leak_pipe"] == "PIPE_17"
    assert len(truth["truth"]["time_iso"]) == 577

    readings = client.get(f"/api/runs/{run_id}/readings").json()
    assert readings["labels"]["readings"] == "SENSOR_SIM"
    assert set(readings["readings"]) == {sensor["id"] for sensor in readings["sensors"]}

    alerts = client.get(f"/api/runs/{run_id}/alerts").json()
    assert len(alerts["incidents"]) == 1
    incident = alerts["incidents"][0]
    assert incident["diagnosis"] == "leak"

    evidence = client.get(f"/api/incidents/{incident['id']}/evidence").json()
    assert evidence["numbers"]
    assert {record["label"] for record in evidence["numbers"]} <= LABELS
    assert evidence["reproducibility"]["run_id"] == run_id


def test_assumptions_are_exposed_and_editable(client):
    payload = client.get("/api/assumptions").json()
    assert payload["labels"]["water_price_per_m3"] == "ASSUMPTION"
    assert payload["assumptions"]["water_price_per_m3"]["value"] > 0
    bad = client.put("/api/assumptions", json={"values": {"water_price_per_m3": 1e9}})
    assert bad.status_code == 422
    good = client.put("/api/assumptions", json={"values": {"water_price_per_m3": 2.5}})
    assert good.status_code == 200
    assert good.json()["assumptions"]["water_price_per_m3"]["value"] == 2.5


def test_websocket_replays_frames(client):
    created = client.post("/api/runs?wait=true", json={"scenario_id": "normal"}).json()
    run_id = created["run_id"]
    with client.websocket_connect(f"/ws/runs/{run_id}?speed=86400") as websocket:
        first = websocket.receive_json()
        assert first["tick"] == 0
        assert first["labels"]["readings"] == "SENSOR_SIM"
        assert len(first["readings"]) == 12
        second = websocket.receive_json()
        assert second["tick"] == 1
        assert second["sim_time"].endswith("00:05:00")
        websocket.send_json({"action": "pause"})
        websocket.send_json({"action": "jump", "value": 300})
        jumped = websocket.receive_json()
        while jumped["tick"] != 300:
            jumped = websocket.receive_json()
        assert jumped["tick"] == 300
        assert jumped["detector"]["state"] in {"normal", "watch", "alert"}
