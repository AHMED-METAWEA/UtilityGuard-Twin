"""Static hosting cannot expose files outside the build or swallow API errors."""

import json
from pathlib import Path

import pytest
from test_api_health import request
from ug_api.app import create_app


@pytest.fixture
def web(tmp_path: Path) -> Path:
    directory = tmp_path / "web"
    directory.mkdir()
    (directory / "index.html").write_text("<title>UtilityGuard Twin</title>")
    (directory / "app.css").write_text("body { color: black; }")
    (tmp_path / "secret").write_text("private")
    (directory / "escape").symlink_to(tmp_path / "secret")
    (directory / "api").mkdir()
    (directory / "api/nope").write_text("must not serve")
    return directory


def test_static(web: Path) -> None:
    app = create_app(web)
    status, headers, body = request(app, "/")
    assert status == 200
    assert headers["content-type"].startswith("text/html")
    assert body == b"<title>UtilityGuard Twin</title>"
    status, headers, body = request(app, "/app.css")
    assert status == 200
    assert headers["content-type"].startswith("text/css")
    assert body == b"body { color: black; }"
    assert request(app, "/api/health")[0] == 200
    status, headers, body = request(app, "/api/nope")
    assert status == 404
    assert headers["content-type"] == "application/problem+json"
    assert json.loads(body)["status"] == 404
    assert request(app, "/api/health", "POST")[0] == 405


@pytest.mark.parametrize(
    "path", ["/missing", "/../secret", "/%2e%2e/secret", "/escape"]
)
def test_static_boundary(web: Path, path: str) -> None:
    status, _, body = request(create_app(web), path)
    assert status == 404
    assert b"private" not in body


def test_absent_directory(tmp_path: Path) -> None:
    assert request(create_app(tmp_path / "missing"), "/")[0] == 404
