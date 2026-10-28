"""D-07 endpoint, contract, traversal and recursive truth-boundary regressions."""

import asyncio
import json
import shutil
from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from urllib.parse import unquote

import pytest
from ug_api.app import DISCLAIMER, create_app
from ug_api.runs import Contracts, RunStore
from ug_core.truth import TruthEvent, TruthSeries

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "fixtures/run_demo"
SERIES = "s_p_0001.reading"
EVIDENCE = "ev_read_P05_144"
REQUEST = {"schema_version": "1", "run_id": "run_demo", "changes": []}
ENDPOINTS = [
    ("/api/runs", None),
    ("/api/runs/run_demo/network", "network-view"),
    ("/api/runs/run_demo/series", "time-series"),
    (f"/api/runs/run_demo/series/{SERIES}", "time-series"),
    ("/api/runs/run_demo/incidents", "incident"),
    ("/api/runs/run_demo/decision", "decision-comparison"),
    (f"/api/runs/run_demo/evidence/{EVIDENCE}", "evidence-record"),
]


def request(app, path, body=None, method=None):
    """Direct ASGI transport preserves traversal paths and needs no HTTP dependency."""

    async def run():
        messages = []
        received = False
        finished = asyncio.Event()

        async def receive():
            nonlocal received
            if not received:
                received = True
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                return {"type": "http.request", "body": raw, "more_body": False}
            await finished.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                finished.set()

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.4"},
                "http_version": "1.1",
                "method": method or ("POST" if body is not None else "GET"),
                "scheme": "http",
                "path": unquote(path),
                "raw_path": path.encode(),
                "query_string": b"",
                "root_path": "",
                "headers": [],
                "client": ("127.0.0.1", 1234),
                "server": ("test", 80),
            },
            receive,
            send,
        )
        start = messages[0]
        headers = {k.decode(): v.decode() for k, v in start["headers"]}
        assert headers["x-ug-disclaimer"] == DISCLAIMER
        assert headers["x-ug-stream-source"] == "REPLAY"
        assert headers["cache-control"] == "no-store"
        data = json.loads(b"".join(m.get("body", b"") for m in messages[1:]))
        if start["status"] >= 400:
            assert headers["content-type"] == "application/problem+json"
            assert data["status"] == start["status"]
        return start["status"], data

    return asyncio.run(run())


@pytest.fixture
def runs_root(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "run_demo")
    return tmp_path


def hook(bundle, request):
    assert request["run_id"] == bundle.run_id
    return {
        "run_id": bundle.run_id,
        "whatif_hash": "a" * 64,
        "series": list(bundle.series.values()),
        "incidents": bundle.incidents,
        "decision": bundle.decision,
    }


def declared_names(contract):
    """Names explicitly declared by this payload's schema and its local refs."""
    if contract is None:
        return set()
    names, seen = set(), set()

    def visit(value, current):
        if isinstance(value, dict):
            names.update(value.get("properties", {}))
            ref = value.get("$ref")
            if ref:
                document, _, fragment = ref.partition("#")
                target = (
                    current.parent / document.rsplit("/", 1)[-1]
                    if document
                    else current
                )
                identity = (target, fragment)
                if identity not in seen:
                    seen.add(identity)
                    schema = json.loads(target.read_text())
                    for part in fragment.strip("/").split("/") if fragment else []:
                        schema = schema[part.replace("~1", "/").replace("~0", "~")]
                    visit(schema, target)
            for child in value.values():
                visit(child, current)
        elif isinstance(value, list):
            for child in value:
                visit(child, current)

    path = ROOT / f"contracts/v1/{contract}.schema.json"
    visit(json.loads(path.read_text()), path)
    return names


def truth_violations(value, contract=None):
    """Stems are always forbidden; schema-declared names exempt truth field names."""
    allowed = declared_names(contract)
    truth_fields = {
        f.name.casefold() for cls in (TruthSeries, TruthEvent) for f in fields(cls)
    }
    stems = ("truth", "fault_tag", "faulttag", "hidden", "injected", "ground_truth")
    errors = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, child in node.items():
                if any(stem in key.casefold() for stem in stems) or (
                    key.casefold() in truth_fields and key not in allowed
                ):
                    errors.append(f"{path}.{key}")
                walk(child, f"{path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")

    walk(value, "$")
    return errors


@pytest.mark.parametrize(("path", "contract"), ENDPOINTS)
def test_endpoints(runs_root, path, contract):
    status, body = request(create_app(runs_root=runs_root), path)
    assert status == 200
    assert not truth_violations(body, contract)
    contracts = Contracts()
    if path == "/api/runs":
        assert body == [
            {
                "run_id": "run_demo",
                "scenario_id": "leak_gradual_medium",
                "seed": 42,
                "simulation_start": "2026-01-01T00:00:00Z",
            }
        ]
    elif path.endswith("/series"):
        assert body == [
            {
                "series_id": SERIES,
                "kind": "sensor",
                "element": "s_p_0001",
                "label": "SENSOR_SIM",
            }
        ]
    elif isinstance(body, list):
        for item in body:
            contracts.validate(contract, item, "response")
    else:
        contracts.validate(contract, body, "response")


def test_fixture_all_payloads_and_determinism(runs_root):
    store = RunStore(runs_root)
    first = store.load("run_demo")
    assert first == store.load("run_demo")
    assert first.readings and first.evidence and first.decision
    for path in ENDPOINTS:
        app = create_app(runs_root=runs_root)
        assert request(app, path[0]) == request(app, path[0])


def test_whatif(runs_root):
    app = create_app(runs_root=runs_root, whatif=hook)
    body = deepcopy(REQUEST)
    body["changes"] = [{"sensor_id": "s_p_0001", "mode": "disable", "from_tick": 1}]
    status, result = request(app, "/api/runs/run_demo/whatif", body)
    assert status == 200
    assert set(result) == {"run_id", "whatif_hash", "series", "incidents", "decision"}
    assert result["whatif_hash"] == "a" * 64
    assert not truth_violations(
        {
            k: v
            for k, v in result.items()
            if k not in {"series", "incidents", "decision"}
        }
    )
    for key, contract in [
        ("series", "time-series"),
        ("incidents", "incident"),
        ("decision", "decision-comparison"),
    ]:
        values = result[key] if isinstance(result[key], list) else [result[key]]
        for value in values:
            Contracts().validate(contract, value, key)
            assert not truth_violations(value, contract)
    assert request(app, "/api/runs/run_demo/whatif", body)[1] == result


def test_default_hook_and_empty_store(runs_root):
    assert request(create_app(), "/api/runs") == (200, [])
    status, body = request(
        create_app(runs_root=runs_root), "/api/runs/run_demo/whatif", REQUEST
    )
    assert status == 501 and body["detail"] == "what-if engine not wired"
    assert not truth_violations(body)


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {**REQUEST, "run_id": "other"},
        {**REQUEST, "extra": 1},
        {
            **REQUEST,
            "changes": [{"sensor_id": "missing", "mode": "disable", "from_tick": 0}],
        },
        {
            **REQUEST,
            "changes": [{"sensor_id": "s_p_0001", "mode": "drift", "from_tick": 0}],
        },
        {
            **REQUEST,
            "changes": [{"sensor_id": "s_p_0001", "mode": "disable", "from_tick": -1}],
        },
        b'{"run_id": NaN}',
        b'{"run_id":1e999}',
        b'{"run_id":1,"run_id":2}',
        b"not json",
        b"\xff",
    ],
)
def test_bad_whatif(runs_root, body):
    def never_called(*args):
        pytest.fail("Invalid input reached hook")

    status, result = request(
        create_app(runs_root=runs_root, whatif=never_called),
        "/api/runs/run_demo/whatif",
        body,
    )
    assert status == 422
    assert not truth_violations(result)


@pytest.mark.parametrize(
    "path",
    [
        "/api/runs/missing/network",
        "/api/runs/missing/series",
        "/api/runs/missing/incidents",
        "/api/runs/missing/decision",
        "/api/runs/missing/evidence/x",
        "/api/runs/run_demo/series/missing",
        "/api/runs/run_demo/evidence/missing",
    ],
)
def test_unknown(runs_root, path):
    status, body = request(create_app(runs_root=runs_root), path)
    assert status == 404 and not truth_violations(body)


@pytest.mark.parametrize(
    "bad",
    [
        "..",
        "%2e%2e",
        "%252e%252e",
        "%2e%2e%2foutside",
        "a%2fb",
        "%5c..",
        "_bad",
        "a" * 129,
    ],
)
@pytest.mark.parametrize(
    "template",
    [
        "/api/runs/{}/network",
        "/api/runs/run_demo/series/{}",
        "/api/runs/run_demo/evidence/{}",
    ],
)
def test_traversal(runs_root, bad, template):
    status, body = request(create_app(runs_root=runs_root), template.format(bad))
    assert status == 404 and not truth_violations(body)


@pytest.mark.parametrize(
    ("file", "content"),
    [
        ("truth.json", "{}"),
        ("series/truth.json", "{}"),
        ("other/extra.json", "{}"),
        (f"series/{SERIES}.json", '{"label":"SIMULATION"}'),
        ("network.json", '{"extra":1}'),
        ("incidents.json", "{}"),
        ("readings.json", '[{"value":NaN}]'),
        ("decision.json", "null"),
        (f"evidence/{EVIDENCE}.json", "{"),
        ("manifest.json", "{}"),
    ],
)
def test_invalid_bundle_no_partial_response(runs_root, file, content):
    path = runs_root / "run_demo" / file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    app = create_app(runs_root=runs_root, whatif=hook)
    for endpoint, _ in ENDPOINTS:
        status, body = request(app, endpoint)
        assert (
            status == 500
            and (file if not file.startswith("other/") else "other") in body["detail"]
        )
        assert not truth_violations(body)
    status, body = request(app, "/api/runs/run_demo/whatif", REQUEST)
    assert (
        status == 500
        and (file if not file.startswith("other/") else "other") in body["detail"]
    )


def test_simulation_series_contract_rejected_via_api(runs_root):
    path = runs_root / "run_demo/series" / f"{SERIES}.json"
    value = json.loads(path.read_text())
    value["label"] = "SIMULATION"
    path.write_text(json.dumps(value))
    assert (
        request(create_app(runs_root=runs_root), f"/api/runs/run_demo/series/{SERIES}")[
            0
        ]
        == 500
    )


@pytest.mark.parametrize(
    "key",
    [
        "fault_tag",
        "injected",
        "channels",
        "target",
        "start_tick",
        "end_tick",
        "events",
        "parameters",
        "hidden_state",
        "ground_truth",
    ],
)
def test_truth_walker_negative_and_closed_schema(key):
    value = json.loads((FIXTURE / "decision.json").read_text())
    value["evidence"][0]["inputs"][0][key] = "LEAK_SENTINEL"
    assert truth_violations(value, "decision-comparison")
    validator = Contracts().validators["decision-comparison"]
    assert any(
        e.validator == "additionalProperties" for e in validator.iter_errors(value)
    )


@pytest.mark.parametrize("key", ["fault_tag", "injected"])
def test_hook_nested_leaks_refused(runs_root, key):
    def leaking(bundle, body):
        result = hook(bundle, body)
        result["decision"]["evidence"][0]["inputs"][0][key] = "LEAK_SENTINEL"
        return result

    status, body = request(
        create_app(runs_root=runs_root, whatif=leaking),
        "/api/runs/run_demo/whatif",
        REQUEST,
    )
    assert status == 500 and "LEAK_SENTINEL" not in json.dumps(body)
    assert not truth_violations(body)


def test_optional_files_and_null_hook_decision(runs_root):
    (runs_root / "run_demo/decision.json").unlink()
    (runs_root / "run_demo/readings.json").unlink()
    app = create_app(runs_root=runs_root, whatif=hook)
    assert request(app, "/api/runs/run_demo/decision")[0] == 404
    status, body = request(app, "/api/runs/run_demo/whatif", REQUEST)
    assert status == 200 and body["decision"] is None


@pytest.mark.parametrize("target", ["network.json", "series", "run"])
def test_symlinks_refused(runs_root, target, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    if target == "run":
        (runs_root / "linked").symlink_to(outside, target_is_directory=True)
        endpoint = "/api/runs/linked/network"
    else:
        destination = runs_root / "run_demo" / target
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
        destination.symlink_to(outside, target_is_directory=True)
        endpoint = "/api/runs/run_demo/network"
    assert request(create_app(runs_root=runs_root), endpoint)[0] == 500


@pytest.mark.parametrize("file", ["manifest.json", "network.json", "incidents.json"])
def test_required_file_missing(runs_root, file):
    (runs_root / "run_demo" / file).unlink()
    status, body = request(create_app(runs_root=runs_root), "/api/runs")
    assert (
        status == 500
        and (file if not file.startswith("other/") else "other") in body["detail"]
    )


def test_health_and_errors_truth_walk(runs_root):
    app = create_app(runs_root=runs_root)
    for path, method in [
        ("/api/health", "GET"),
        ("/api", "GET"),
        ("/api/missing", "GET"),
        ("/api/runs", "DELETE"),
    ]:
        _, body = request(app, path, method=method)
        assert not truth_violations(body)


@pytest.mark.parametrize("key", ["fault_tag", "injected"])
def test_truth_walk_two_levels(key):
    assert truth_violations({"outer": {"inner": {key: "LEAK_SENTINEL"}}})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("extra", "LEAK_SENTINEL"),
        ("run_id", "other"),
        ("whatif_hash", "bad"),
        ("series", {}),
        ("incidents", {}),
        ("decision", {}),
        ("series", [{"fault_tag": "LEAK_SENTINEL"}]),
        ("incidents", [{"injected": "LEAK_SENTINEL"}]),
    ],
)
def test_invalid_hook_output(runs_root, field, value):
    def invalid(bundle, body):
        result = hook(bundle, body)
        result[field] = value
        return result

    status, body = request(
        create_app(runs_root=runs_root, whatif=invalid),
        "/api/runs/run_demo/whatif",
        REQUEST,
    )
    assert status == 500 and "LEAK_SENTINEL" not in json.dumps(body)
    assert not truth_violations(body)


def test_hook_exception_sanitised(runs_root):
    def broken(bundle, body):
        raise RuntimeError("LEAK_SENTINEL")

    status, body = request(
        create_app(runs_root=runs_root, whatif=broken),
        "/api/runs/run_demo/whatif",
        REQUEST,
    )
    assert status == 500 and "LEAK_SENTINEL" not in json.dumps(body)


@pytest.mark.parametrize(
    "file", [f"series/{SERIES}.json", "incidents.json", "decision.json"]
)
def test_cross_run_payload_refused(runs_root, file):
    path = runs_root / "run_demo" / file
    value = json.loads(path.read_text())
    (value[0] if isinstance(value, list) else value)["run_id"] = "other"
    path.write_text(json.dumps(value))
    status, body = request(create_app(runs_root=runs_root), "/api/runs")
    assert status == 500 and file in body["detail"]


def test_unknown_whatif_run(runs_root):
    assert (
        request(create_app(runs_root=runs_root), "/api/runs/missing/whatif", REQUEST)[0]
        == 404
    )


def test_unreadable_series_never_returns_partial_bundle(runs_root, monkeypatch):
    original = Path.iterdir

    def unreadable(path):
        if path == runs_root / "run_demo/series":
            raise PermissionError("LEAK_SENTINEL")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", unreadable)
    status, body = request(
        create_app(runs_root=runs_root), "/api/runs/run_demo/network"
    )
    assert status == 500 and "LEAK_SENTINEL" not in json.dumps(body)


def test_the_app_starts_without_jsonschema_and_refuses_bundles_loudly(runs_root):
    # The API container installs neither jsonschema nor contracts/ (deploy/requirements-api.lock).
    import subprocess
    import sys

    code = (
        "import sys; sys.modules['jsonschema'] = None; sys.modules['referencing'] = None\n"
        f"sys.path.insert(0, {str(Path(__file__).parent)!r})\n"
        "from pathlib import Path\n"
        "from test_runs import request\n"
        "from ug_api.app import create_app\n"
        "status, body = request(create_app(), '/api/runs')\n"
        "assert status == 200 and body == [], body\n"
        f"status, body = request(create_app(runs_root=Path({str(runs_root)!r})), '/api/runs')\n"
        "assert status == 500 and 'not installed' in body['detail'], body\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr[-2000:]
