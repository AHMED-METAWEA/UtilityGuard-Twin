"""T-B1-010: the Overpass client, the area file, the cache and its provenance (offline)."""

from __future__ import annotations

import json
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from geometry_fixtures import BASE, FakeOverpass, Response
from ug_core.geometry import fetch as F

NOW = datetime(2026, 10, 26, 10, 25, 33, tzinfo=UTC)


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://overpass.invalid", code, "x", {}, None)  # type: ignore[arg-type]


def client(
    answers: list[Any], **kwargs: Any
) -> tuple[F.Overpass, list[Any], list[float]]:
    requests: list[Any] = []
    sleeps: list[float] = []

    def urlopen(request: Any, timeout: float) -> Response:
        requests.append(request)
        value = answers.pop(0)
        if isinstance(value, Exception):
            raise value
        return Response(
            json.dumps(value).encode() if not isinstance(value, bytes) else value
        )

    ticks = iter(range(0, 10_000, 100))
    overpass = F.Overpass(
        "https://overpass.invalid/api/interpreter",
        sleep=sleeps.append,
        clock=lambda: float(next(ticks)),
        urlopen=urlopen,
        **kwargs,
    )
    return overpass, requests, sleeps


GOOD = {"osm3s": {"timestamp_osm_base": BASE}, "elements": []}


def test_a_query_identifies_the_application_and_posts_the_query() -> None:
    overpass, requests, _ = client([GOOD])
    raw, data = overpass.query("[out:json];node(1);out;")
    assert data["osm3s"]["timestamp_osm_base"] == BASE and raw
    request = requests[0]
    assert request.get_method() == "POST"
    assert request.get_header("User-agent") == F.USER_AGENT
    assert b"data=%5Bout%3Ajson%5D" in request.data


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_busy_servers_are_retried_with_exponential_backoff(code: int) -> None:
    overpass, requests, sleeps = client([http_error(code), http_error(code), GOOD])
    overpass.query("q")
    assert len(requests) == 3
    assert [s for s in sleeps if s >= 30] == [30.0, 60.0]


def test_a_refused_query_is_not_retried() -> None:
    overpass, requests, _ = client([http_error(400)])
    with pytest.raises(F.FetchError, match="HTTP 400"):
        overpass.query("q")
    assert len(requests) == 1


def test_it_gives_up_after_the_last_attempt() -> None:
    overpass, requests, _ = client([urllib.error.URLError("down")] * 3, attempts=3)
    with pytest.raises(F.FetchError, match="after 3 attempts"):
        overpass.query("q")
    assert len(requests) == 3


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        ({**GOOD, "remark": 'runtime error: Query timed out in "query"'}, "incomplete"),
        ({"elements": []}, "timestamp"),
        ({"osm3s": {"timestamp_osm_base": BASE}}, "element list"),
        (b"<html>busy</html>", "JSON"),
    ],
)
def test_an_answer_that_cannot_be_trusted_is_an_error(
    answer: Any, message: str
) -> None:
    overpass, _, _ = client([answer])
    with pytest.raises(F.FetchError, match=message):
        overpass.query("q")


def test_queries_are_spaced_out() -> None:
    sleeps: list[float] = []
    clock = iter([0.0, 0.0, 0.5, 0.5])
    overpass = F.Overpass(
        "https://x.invalid",
        sleep=sleeps.append,
        clock=lambda: next(clock),
        urlopen=lambda r, timeout: Response(json.dumps(GOOD).encode()),
        min_interval_s=2.0,
    )
    overpass.query("a")
    overpass.query("b")
    assert sleeps == [pytest.approx(1.5)]


def test_the_packaged_area_is_an_assumption_with_a_valid_box() -> None:
    area = F.load_area("capital")
    assert area.label == "ASSUMPTION" and area.bbox == (29.87, 31.61, 30.07, 31.8)
    assert set(area.queries) == {"roads_v1", "stats_v1", "landmarks_v1"}
    assert area.endpoint.startswith("https://")


@pytest.mark.parametrize(
    "change",
    [
        {"label": "PUBLIC_GEOMETRY"},
        {"bbox": {"south": 30.1, "west": 31.6, "north": 30.0, "east": 31.8}},
        {"landmarks": ["Green River|x"]},
        {"endpoint": "http://overpass.invalid"},
        {"queries": ["../etc"]},
    ],
)
def test_a_broken_area_definition_is_refused(change: dict[str, Any]) -> None:
    data = json.loads(
        (Path(F.__file__).parent / "areas" / "capital_v1.json").read_text()
    )
    with pytest.raises(F.FetchError):
        F.area_from_dict({**data, **change})


def test_queries_are_rendered_with_the_box_and_dates_of_the_retrieval() -> None:
    area = F.load_area("capital")
    stats = F.render_query("stats_v1", area, NOW)
    assert "29.87,31.61,30.07,31.8" in stats and "{{" not in stats
    assert (
        'newer:"2025-10-26T10:25:33Z"' in stats
        and 'newer:"2024-10-26T10:25:33Z"' in stats
    )
    marks = F.render_query("landmarks_v1", area, NOW)
    assert "Central\\ Business\\ District|" in marks


def test_an_extract_is_cached_with_its_provenance(tmp_path: Path) -> None:
    area = F.load_area("capital")
    extract = F.fetch_area(area, tmp_path, FakeOverpass(), NOW)  # type: ignore[arg-type]
    assert extract == tmp_path / "capital" / BASE.replace(":", "-")
    record = json.loads((extract / "provenance.json").read_text())
    assert {
        k: record[k]
        for k in ("label", "source", "licence", "attribution", "retrieved", "osm_base")
    } == {
        "label": "PUBLIC_GEOMETRY",
        "source": "OpenStreetMap",
        "licence": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors",
        "retrieved": "2026-10-26T10:25:33Z",
        "osm_base": BASE,
    }
    assert (
        record["area"]["sha256"] == area.sha256
        and record["area"]["label"] == "ASSUMPTION"
    )
    assert record["extract_sha256"] == record["queries"]["roads_v1"]["answer_sha256"]
    assert sorted(p.name for p in extract.iterdir()) == [
        "landmarks_v1.json",
        "provenance.json",
        "queries",
        "roads_v1.json",
        "stats_v1.json",
    ]
    assert F.verify_extract(extract, area)["osm_base"] == BASE
    assert F.latest_extract(area, tmp_path) == extract


def test_a_failed_fetch_leaves_nothing_behind(tmp_path: Path) -> None:
    area = F.load_area("capital")
    with pytest.raises(F.FetchError):
        F.fetch_area(
            area, tmp_path, FakeOverpass({"stats_v1": F.FetchError("busy")}), NOW
        )  # type: ignore[arg-type]
    assert not (tmp_path / "capital").exists()
    assert [p.name for p in tmp_path.iterdir()] == []


def test_a_tampered_or_foreign_extract_is_not_used(tmp_path: Path) -> None:
    area = F.load_area("capital")
    extract = F.fetch_area(area, tmp_path, FakeOverpass(), NOW)  # type: ignore[arg-type]
    (extract / "roads_v1.json").write_bytes(b'{"elements": []}')
    assert F.latest_extract(area, tmp_path) is None
    with pytest.raises(F.FetchError, match="does not match its hash"):
        F.verify_extract(extract, area)
    other = F.area_from_dict(
        {
            **json.loads(
                (Path(F.__file__).parent / "areas" / "capital_v1.json").read_text()
            ),
            "grid_cell_m": 500,
        }
    )
    with pytest.raises(F.FetchError, match="another version"):
        F.verify_extract(extract, other)


def test_the_cache_is_never_tracked_by_git() -> None:
    root = Path(__file__).resolve().parents[3]
    assert "\n/data/\n" in (root / ".gitignore").read_text()


def test_a_failure_while_writing_removes_the_staging_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_replace(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(F.os, "replace", broken_replace)
    with pytest.raises(OSError, match="disk full"):
        F.fetch_area(F.load_area("capital"), tmp_path, FakeOverpass(), NOW)  # type: ignore[arg-type]
    assert [p.name for p in tmp_path.iterdir()] == ["capital"] or not list(
        tmp_path.iterdir()
    )
    assert not [p for p in tmp_path.rglob(".fetch-*")]
