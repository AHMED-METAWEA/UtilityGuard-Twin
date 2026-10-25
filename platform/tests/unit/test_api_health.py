"""Exercise ASGI directly, without an HTTP client dependency."""

import ast
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import unquote
from urllib.request import urlopen

import pytest
import ug_api
from starlette.types import ASGIApp, Message
from ug_api.app import DISCLAIMER, create_app

ROOT = Path(__file__).resolve().parents[3]


def request(
    app: ASGIApp, path: str, method: str = "GET"
) -> tuple[int, dict[str, str], bytes]:
    async def run() -> tuple[int, dict[str, str], bytes]:
        messages: list[Message] = []
        received = False
        finished = asyncio.Event()

        async def receive() -> Message:
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await finished.wait()
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            messages.append(message)
            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                finished.set()

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.4"},
                "http_version": "1.1",
                "method": method,
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
        return (
            start["status"],
            {k.decode(): v.decode() for k, v in start["headers"]},
            b"".join(m.get("body", b"") for m in messages[1:]),
        )

    return asyncio.run(run())


def test_health() -> None:
    status, headers, body = request(create_app(), "/api/health")
    assert status == 200
    assert headers["content-type"] == "application/json"
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert json.loads(body) == {
        "schema_version": "1",
        "status": "ok",
        "service": "ug-api",
        "version": ug_api.__version__,
        "disclaimer": DISCLAIMER,
    }
    source = (ROOT / "frontend/src/app/strings.ts").read_text()
    match = re.search(r'statement:\s*("(?:[^"\\]|\\.)*")', source)
    assert match is not None, "Cannot parse honesty.statement in shell strings.ts"
    assert DISCLAIMER == json.loads(match[1])


@pytest.mark.parametrize(
    ("path", "method", "code", "title"),
    [
        ("/api/nope", "GET", 404, "Not Found"),
        ("/api", "GET", 404, "Not Found"),
        ("/api/health", "POST", 405, "Method Not Allowed"),
        ("/", "GET", 404, "Not Found"),
        ("/docs", "GET", 404, "Not Found"),
        ("/redoc", "GET", 404, "Not Found"),
        ("/openapi.json", "GET", 404, "Not Found"),
        ("/api/docs", "GET", 404, "Not Found"),
        ("/api/openapi.json", "GET", 404, "Not Found"),
    ],
)
def test_problems(path: str, method: str, code: int, title: str) -> None:
    status, headers, body = request(create_app(), path, method)
    assert status == code
    assert headers["content-type"] == "application/problem+json"
    assert json.loads(body) == {"type": "about:blank", "title": title, "status": code}
    if path.startswith("/api"):
        assert headers["cache-control"] == "no-store"
        assert headers["x-content-type-options"] == "nosniff"
    if code == 405:
        assert "GET" in headers["allow"]


def test_head() -> None:
    status, headers, body = request(create_app(), "/api/health", "HEAD")
    assert status == 200
    assert body == b""
    assert headers["content-type"] == "application/json"
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("value", ["nope", "0", "65536", "-1", "1.5", " 8080", ""])
def test_bad_port(value: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ug_api"],
        env={**os.environ, "UG_API_PORT": value},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "UG_API_PORT must be an integer from 1 to 65535" in result.stderr


def test_defaults_bind_loopback_port_8080(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented defaults: loopback only, the port of the compose file, no reload."""
    from ug_api import __main__ as launcher

    for name in ("UG_API_HOST", "UG_API_PORT", "UG_STATIC_DIR"):
        monkeypatch.delenv(name, raising=False)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        launcher.uvicorn, "run", lambda app, **options: calls.append(options)
    )
    launcher.main()
    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 8080,
            "reload": False,
            "access_log": True,
            "server_header": False,
        }
    ]


def test_environment_overrides_host_and_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from ug_api import __main__ as launcher

    monkeypatch.setenv("UG_API_HOST", "0.0.0.0")
    monkeypatch.setenv("UG_API_PORT", "9001")
    monkeypatch.setenv("UG_STATIC_DIR", str(tmp_path))
    (tmp_path / "index.html").write_text("<title>x</title>")
    seen: list[tuple[object, dict[str, object]]] = []
    monkeypatch.setattr(
        launcher.uvicorn, "run", lambda app, **options: seen.append((app, options))
    )
    launcher.main()
    app, options = seen[0]
    assert (options["host"], options["port"]) == ("0.0.0.0", 9001)
    status, _, body = request(app, "/")  # type: ignore[arg-type]
    assert status == 200 and b"<title>x</title>" in body


def test_subprocess_health() -> None:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except PermissionError:
            pytest.skip("Sandbox denies loopback bind; run subprocess test on host")
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "ug_api"],
        env={
            **os.environ,
            "UG_API_HOST": "127.0.0.1",
            "UG_API_PORT": str(port),
            "UG_STATIC_DIR": "",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            assert process.poll() is None, process.stderr.read().decode()
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.3) as r:
                    assert r.status == 200
                    assert r.headers.get("Server") is None
                    assert json.load(r)["disclaimer"] == DISCLAIMER
                break
            except URLError:
                time.sleep(0.05)
        else:
            pytest.fail("API did not become ready within 10 seconds")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stderr:
            process.stderr.close()


def test_no_domain_imports() -> None:
    for path in (ROOT / "platform/ug_api/src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not any(
                    part == "domains" or part.startswith("ug_water")
                    for part in name.split(".")
                ), f"Domain import at {path}:{node.lineno}"
