"""Real run -> exporter -> API, using the D-07 recursive truth walker."""

import json

from test_runs import request, truth_violations
from ug_api.app import create_app
from ug_cli.export import export_run
from ug_cli.main import main


def test_recorded_export_served_and_truth_walk(tmp_path, capsys):
    store, views = tmp_path / "store", tmp_path / "views"
    assert (
        main(
            [
                "run",
                "normal_week",
                "--seed",
                "1",
                "--duration-hours",
                "0.25",
                "--store",
                str(store),
            ]
        )
        == 0
    )
    run_id = capsys.readouterr().out.split("run_id: ")[1].splitlines()[0]
    assert main(["export", run_id, "--store", str(store), "--out", str(views)]) == 0
    directory = views / run_id
    contracts = {
        "manifest.json": "run-manifest",
        "network.json": "network-view",
        "readings.json": "telemetry-reading",
        "incidents.json": "incident",
    }
    for path in directory.rglob("*.json"):
        payload = json.loads(path.read_text())
        assert not truth_violations(payload, contracts.get(path.name, "time-series")), (
            path
        )
        assert '"SIMULATION"' not in path.read_text()
    app = create_app(runs_root=views)
    for path, contract in (
        ("/api/runs", None),
        (f"/api/runs/{run_id}/network", "network-view"),
        (f"/api/runs/{run_id}/incidents", "incident"),
    ):
        status, body = request(app, path)
        assert status == 200
        assert not truth_violations(body, contract)
    assert request(app, f"/api/runs/{run_id}/decision")[0] == 404
    assert export_run(run_id, store, views) == directory
