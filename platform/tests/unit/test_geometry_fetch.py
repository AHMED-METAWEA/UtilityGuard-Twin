"""T-B1-010: the Overpass client, the area file, the cache and its provenance (offline)."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from geometry_fixtures import (
    BASE,
    LANDMARKS,
    STUDY_BOX,
    FakeOverpass,
    Response,
    landmark,
    landmarks_answer,
    roads_answer,
    stat,
    stats_answer,
)
from ug_core.geometry import fetch as F

NOW = datetime(2026, 10, 26, 10, 25, 33, tzinfo=UTC)
AREA_FILE = Path(F.__file__).parent / "areas" / "capital_v1.json"


def area_data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(AREA_FILE.read_text())
    return data


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


def fetch(cache: Path, area: F.Area | None = None, **overrides: Any) -> Path:
    return F.fetch_area(
        area or F.load_area("capital"),
        cache,
        FakeOverpass(overrides),
        NOW,  # type: ignore[arg-type]
    )


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
        ({"osm3s": {"timestamp_osm_base": "yesterday"}, "elements": []}, "timestamp"),
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


# The area file -------------------------------------------------------------------------------


def test_the_packaged_area_holds_no_osm_geometry() -> None:
    """G2: only a Wikidata anchor, widths, a margin and names; no box, no position from OSM."""
    data = area_data()
    assert set(data) == {
        "area", "version", "name", "label", "note", "anchor", "search_half_width_deg",
        "study_margin_km", "min_landmarks", "landmarks", "landmark_radius_m", "grid_cell_m",
        "endpoint",
    }  # fmt: skip
    area = F.load_area("capital")
    assert area.label == "ASSUMPTION" and area.anchor == (30.033694, 31.755056)
    assert (
        area.anchor_source.startswith("Wikidata Q19588497")
        and "CC0" in area.anchor_source
    )
    assert area.search_box() == pytest.approx(
        (29.833694, 31.555056, 30.233694, 31.955056)
    )
    assert area.endpoint.startswith("https://") and area.min_landmarks == 6


@pytest.mark.parametrize(
    "change",
    [
        {"label": "PUBLIC_GEOMETRY"},
        {"anchor": {"lat": 30.0, "lon": 31.7, "source": "OpenStreetMap node 1"}},
        {"anchor": {"lat": 30.0, "lon": 31.7, "source": " "}},
        {"anchor": {"lat": 95.0, "lon": 31.7, "source": "Wikidata"}},
        {"anchor": {"lon": 31.7, "source": "Wikidata"}},
        {"search_half_width_deg": 0},
        {"search_half_width_deg": 1.5},
        {"study_margin_km": -1},
        {"landmarks": ["Green River|x", "Central Business District"]},
        {"landmarks": ["", "Central Business District"]},
        {"min_landmarks": 1},
        {"min_landmarks": 10},
        {"endpoint": "http://overpass.invalid"},
    ],
)
def test_a_broken_area_definition_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(F.FetchError):
        F.area_from_dict({**area_data(), **change})


def test_queries_are_rendered_with_the_box_and_dates_of_the_retrieval() -> None:
    area = F.load_area("capital")
    stats = F.render_query("stats_v1", STUDY_BOX, area, NOW)
    assert "29.920000,31.660000,30.030000,31.800000" in stats and "{{" not in stats
    assert (
        'newer:"2025-10-26T10:25:33Z"' in stats
        and 'newer:"2024-10-26T10:25:33Z"' in stats
    )
    marks = F.render_query("landmarks_v1", area.search_box(), area, NOW)
    assert "Central\\ Business\\ District|" in marks


# The study box -------------------------------------------------------------------------------


def test_the_study_box_is_the_landmarks_plus_the_margin_rounded_outward() -> None:
    assert F.study_box(list(LANDMARKS.values()), 3) == STUDY_BOX
    assert F.study_box([(30.0, 31.7)], 0) == (30.0, 31.7, 30.0, 31.7)
    assert F.study_box([(30.006, 31.706)], 0) == (30.0, 31.7, 30.01, 31.71)


def test_the_landmark_nearest_the_anchor_places_the_box(tmp_path: Path) -> None:
    far = landmark(
        99, "Central Business District", 30.2, 31.9
    )  # a namesake, inside the search box
    answer = landmarks_answer()
    answer["elements"].insert(0, far)
    extract = fetch(tmp_path, landmarks_v1=answer)
    record = json.loads((extract / "provenance.json").read_text())
    assert record["study_box"]["bbox"] == list(STUDY_BOX)


def test_too_few_landmarks_place_no_box_and_fetch_nothing_else(tmp_path: Path) -> None:
    answer = landmarks_answer()
    answer["elements"] = answer["elements"][:5]
    overpass = FakeOverpass({"landmarks_v1": answer})
    with pytest.raises(F.FetchError, match="only 5 of the landmarks"):
        F.fetch_area(F.load_area("capital"), tmp_path, overpass, NOW)  # type: ignore[arg-type]
    assert len(overpass.queries) == 1 and not (tmp_path / "capital").exists()


# Fetching and the provenance -----------------------------------------------------------------


def test_an_extract_is_cached_with_its_provenance(tmp_path: Path) -> None:
    area = F.load_area("capital")
    overpass = FakeOverpass()
    extract = F.fetch_area(area, tmp_path, overpass, NOW)  # type: ignore[arg-type]
    assert extract == tmp_path.resolve() / "capital" / BASE.replace(":", "-")
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
    assert record["area"] == {
        "name": "capital", "version": "1", "sha256": area.sha256, "label": "ASSUMPTION"
    }  # fmt: skip
    assert record["study_box"] | {"method": None} == {
        "bbox": list(STUDY_BOX),
        "label": "ASSUMPTION",
        "method": None,
        "landmarks_found": sorted(LANDMARKS),
    }
    assert record["queries"]["landmarks_v1"]["bbox"] == list(area.search_box())
    assert record["queries"]["roads_v1"]["bbox"] == list(STUDY_BOX)
    assert record["queries"]["stats_v1"]["bbox"] == list(STUDY_BOX)
    assert F.box_text(area.search_box()) in overpass.queries[0]
    assert all(F.box_text(STUDY_BOX) in q for q in overpass.queries[1:])
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


def test_the_snapshot_is_the_newest_answer(tmp_path: Path) -> None:
    stats = stats_answer()
    stats["osm3s"]["timestamp_osm_base"] = "2026-10-26T10:30:00Z"
    extract = fetch(tmp_path, stats_v1=stats)
    record = F.verify_extract(extract, F.load_area("capital"))
    assert record["osm_base"] == "2026-10-26T10:30:00Z"
    assert record["queries"]["roads_v1"]["osm_base"] == BASE
    assert extract.name == "2026-10-26T10-30-00Z"


def without_geometry() -> dict[str, Any]:
    answer = roads_answer()
    answer["elements"][0]["geometry"] = []
    return answer


def with_a_one_node_way() -> dict[str, Any]:
    answer = roads_answer()
    answer["elements"][0]["nodes"] = answer["elements"][0]["nodes"][:1]
    answer["elements"][0]["geometry"] = answer["elements"][0]["geometry"][:1]
    return answer


def without_highway_tag() -> dict[str, Any]:
    answer = roads_answer()
    answer["elements"][0]["tags"] = {}
    return answer


def without_a_required_stat() -> dict[str, Any]:
    answer = stats_answer()
    answer["elements"] = [
        e for e in answer["elements"] if e["tags"]["value"] != "named_highways"
    ]
    return answer


def with_a_foreign_landmark() -> dict[str, Any]:
    answer = landmarks_answer()
    answer["elements"].append(landmark(98, "Somewhere Else", 30.0, 31.7))
    return answer


@pytest.mark.parametrize(
    ("query", "answer", "message"),
    [
        ("roads_v1", lambda: {**GOOD}, "holds no road"),
        ("roads_v1", without_geometry, "no usable geometry"),
        ("roads_v1", with_a_one_node_way, "no usable geometry"),
        ("roads_v1", without_highway_tag, "no highway tag"),
        ("stats_v1", lambda: {**GOOD}, "statistics answer is incomplete"),
        ("stats_v1", without_a_required_stat, "named_highways"),
        ("landmarks_v1", lambda: {**GOOD}, "only 0 of the landmarks"),
        ("landmarks_v1", with_a_foreign_landmark, "not asked for"),
    ],
)
def test_an_empty_or_partial_answer_is_a_failure_not_coverage(
    tmp_path: Path, query: str, answer: Callable[[], dict[str, Any]], message: str
) -> None:
    with pytest.raises(F.FetchError, match=message):
        fetch(tmp_path, **{query: answer()})
    assert not (tmp_path / "capital").exists()


def test_an_extract_the_cache_would_refuse_is_never_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The new extract is verified like a cached one before it is moved into place."""
    monkeypatch.setattr(F, "iso", lambda moment: "not a time")
    with pytest.raises(F.FetchError, match="retrieval time"):
        fetch(tmp_path)
    assert list((tmp_path / "capital").iterdir()) == []


def test_a_failed_fetch_leaves_nothing_behind(tmp_path: Path) -> None:
    with pytest.raises(F.FetchError):
        fetch(tmp_path, stats_v1=F.FetchError("busy"))
    assert not (tmp_path / "capital").exists()
    assert [p.name for p in tmp_path.iterdir()] == []


# Verification of a cached extract ------------------------------------------------------------


def edit_provenance(extract: Path, change: Callable[[dict[str, Any]], None]) -> None:
    path = extract / "provenance.json"
    record = json.loads(path.read_text())
    change(record)
    path.write_text(json.dumps(record))


def rewrite_answer(extract: Path, name: str, data: dict[str, Any]) -> None:
    """Replace an answer and its recorded hash, so only the deeper checks can catch it."""
    raw = json.dumps(data).encode()
    (extract / f"{name}.json").write_bytes(raw)

    def change(record: dict[str, Any]) -> None:
        record["queries"][name]["answer_sha256"] = F._sha(raw)
        if name == "roads_v1":
            record["extract_sha256"] = F._sha(raw)

    edit_provenance(extract, change)


def set_key(*path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def change(record: dict[str, Any]) -> None:
        target = record
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def drop_key(*path: str) -> Callable[[dict[str, Any]], None]:
    def change(record: dict[str, Any]) -> None:
        target = record
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return change


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (set_key("queries", "stats_v1", "query_sha256", value="wrong"), "saved query"),
        (set_key("extract_sha256", value="wrong"), "extract_sha256"),
        (set_key("endpoint", value="https://elsewhere.invalid"), "another endpoint"),
        (set_key("osm_base", value="2099-01-01T00:00:00Z"), "snapshot timestamp"),
        (set_key("retrieved", value="now"), "retrieval time"),
        (set_key("schema_version", value="0"), "provenance version"),
        (set_key("licence", value="CC-BY-4.0"), "licence"),
        (
            set_key("queries", "roads_v1", "osm_base", value="2026-01-01T00:00:00Z"),
            "another OSM timestamp",
        ),
        (
            set_key("study_box", "bbox", value=[29.0, 31.0, 31.0, 32.0]),
            "does not follow",
        ),
        (set_key("study_box", "label", value="PUBLIC_GEOMETRY"), "does not follow"),
        (set_key("study_box", value=[]), "does not follow"),
        (
            set_key("queries", "landmarks_v1", "bbox", value=list(STUDY_BOX)),
            "another template or box",
        ),
        (drop_key("queries", "stats_v1"), "exactly the queries"),
        (drop_key("queries", "roads_v1", "bbox"), "has no box"),
    ],
)
def test_inconsistent_provenance_is_refused(
    tmp_path: Path, change: Callable[[dict[str, Any]], None], message: str
) -> None:
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    edit_provenance(extract, change)
    with pytest.raises(F.FetchError, match=message):
        F.verify_extract(extract, area)
    assert F.latest_extract(area, tmp_path) is None


def test_the_box_of_the_roads_query_must_be_the_study_box(tmp_path: Path) -> None:
    """A saved query re-rendered with a changed box, hash updated: the box check catches it."""
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    other = (29.0, 31.0, 31.0, 32.0)
    text = F.render_query("roads_v1", other, area, NOW)
    (extract / "queries" / "roads_v1.overpassql").write_text(text)

    def change(record: dict[str, Any]) -> None:
        record["queries"]["roads_v1"]["bbox"] = list(other)
        record["queries"]["roads_v1"]["query_sha256"] = F.sha256_hex(text)

    edit_provenance(extract, change)
    with pytest.raises(F.FetchError, match="did not use the study box"):
        F.verify_extract(extract, area)


def test_the_landmarks_must_be_searched_in_the_search_box(tmp_path: Path) -> None:
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    text = F.render_query("landmarks_v1", STUDY_BOX, area, NOW)
    (extract / "queries" / "landmarks_v1.overpassql").write_text(text)

    def change(record: dict[str, Any]) -> None:
        record["queries"]["landmarks_v1"]["bbox"] = list(STUDY_BOX)
        record["queries"]["landmarks_v1"]["query_sha256"] = F.sha256_hex(text)

    edit_provenance(extract, change)
    with pytest.raises(F.FetchError, match="not searched in the area's search box"):
        F.verify_extract(extract, area)


def test_a_changed_or_missing_saved_query_is_refused(tmp_path: Path) -> None:
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    saved = extract / "queries" / "stats_v1.overpassql"
    saved.write_text(saved.read_text() + "\n")
    with pytest.raises(F.FetchError, match="does not match its hash"):
        F.verify_extract(extract, area)
    saved.unlink()
    with pytest.raises(F.FetchError, match="missing"):
        F.verify_extract(extract, area)


def test_an_extract_made_by_an_older_template_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    render = F.render_query
    monkeypatch.setattr(
        F, "render_query", lambda *a: render(*a).replace("out geom qt", "out geom")
    )
    with pytest.raises(F.FetchError, match="another template"):
        F.verify_extract(extract, area)


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("roads_v1", {**GOOD}, "holds no road"),
        ("stats_v1", {**GOOD}, "incomplete"),
        ("roads_v1", {**roads_answer(), "remark": "timed out"}, "incomplete"),
        (
            "roads_v1",
            {**roads_answer(), "osm3s": {"timestamp_osm_base": "2026-10-01T00:00:00Z"}},
            "another OSM timestamp",
        ),
    ],
)
def test_answers_are_checked_again_not_only_hashed(
    tmp_path: Path, name: str, data: dict[str, Any], message: str
) -> None:
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    rewrite_answer(extract, name, data)
    with pytest.raises(F.FetchError, match=message):
        F.verify_extract(extract, area)


def test_a_tampered_or_foreign_extract_is_not_used(tmp_path: Path) -> None:
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    (extract / "roads_v1.json").write_bytes(b'{"elements": []}')
    assert F.latest_extract(area, tmp_path) is None
    with pytest.raises(F.FetchError, match="does not match its hash"):
        F.verify_extract(extract, area)
    other = F.area_from_dict({**area_data(), "grid_cell_m": 500})
    with pytest.raises(F.FetchError, match="another version"):
        F.verify_extract(fetch(tmp_path / "b"), other)


def test_the_newest_intact_extract_is_used(tmp_path: Path) -> None:
    area = F.load_area("capital")
    old = fetch(tmp_path)
    stats = stats_answer()
    stats["osm3s"]["timestamp_osm_base"] = "2026-10-27T00:00:00Z"
    later = datetime(2026, 10, 27, 0, 30, tzinfo=UTC)
    new = F.fetch_area(area, tmp_path, FakeOverpass({"stats_v1": stats}), later)  # type: ignore[arg-type]
    (tmp_path / "capital" / ".fetch-leftover").mkdir()
    assert F.latest_extract(area, tmp_path) == new
    (new / "stats_v1.json").write_bytes(b"{}")
    assert F.latest_extract(area, tmp_path) == old


# The same OSM snapshot fetched again ----------------------------------------------------------


def test_an_intact_extract_of_the_same_snapshot_is_kept(tmp_path: Path) -> None:
    extract = fetch(tmp_path)
    (extract / "report.json").write_text("{}")
    assert fetch(tmp_path) == extract
    assert (extract / "report.json").is_file()
    assert sorted(p.name for p in extract.parent.iterdir()) == [extract.name]


def test_a_corrupt_extract_of_the_same_snapshot_is_repaired(tmp_path: Path) -> None:
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    (extract / "roads_v1.json").write_bytes(b"{}")
    (extract / "report.json").write_text("{}")
    assert fetch(tmp_path) == extract
    assert F.verify_extract(extract, area)["osm_base"] == BASE
    assert not (extract / "report.json").exists()
    assert sorted(p.name for p in extract.parent.iterdir()) == [extract.name]


def test_an_extract_of_another_area_version_is_replaced(tmp_path: Path) -> None:
    other = F.area_from_dict({**area_data(), "grid_cell_m": 500})
    extract = fetch(tmp_path, area=other)
    assert fetch(tmp_path) == extract
    F.verify_extract(extract, F.load_area("capital"))


def test_a_failed_repair_puts_the_old_extract_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extract = fetch(tmp_path)
    (extract / "roads_v1.json").write_bytes(b"{}")
    replace = os.replace
    calls: list[str] = []

    def second_replace_fails(src: Any, dst: Any) -> None:
        calls.append(Path(dst).name)
        if len(calls) == 2:
            raise OSError("disk full")
        replace(src, dst)

    monkeypatch.setattr(F.os, "replace", second_replace_fails)
    with pytest.raises(OSError, match="disk full"):
        fetch(tmp_path)
    assert (extract / "roads_v1.json").read_bytes() == b"{}"
    assert sorted(p.name for p in extract.parent.iterdir()) == [extract.name]


def test_a_failure_while_writing_removes_the_staging_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_replace(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(F.os, "replace", broken_replace)
    with pytest.raises(OSError, match="disk full"):
        fetch(tmp_path)
    assert not list(tmp_path.rglob(".fetch-*"))


# The cache boundary (G2) ---------------------------------------------------------------------


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / ".gitignore").write_text("/data/\n")
    (root / "platform").mkdir()
    return root


def test_a_cache_that_git_could_commit_is_refused_before_anything_is_written(
    repo: Path,
) -> None:
    with pytest.raises(F.FetchError, match="does not ignore"):
        fetch(repo / "platform" / "geometry-cache")
    assert not (repo / "platform" / "geometry-cache").exists()
    with pytest.raises(F.FetchError, match="does not ignore"):
        F.latest_extract(F.load_area("capital"), repo / "platform")
    with pytest.raises(F.FetchError, match="does not ignore"):
        F.ensure_cache_location(repo)


def test_an_ignored_cache_inside_a_repository_is_allowed(repo: Path) -> None:
    extract = fetch(repo / "data" / "geometry")
    assert extract.is_relative_to(repo.resolve() / "data" / "geometry")


def test_an_ignored_folder_holding_a_tracked_file_is_refused(repo: Path) -> None:
    tracked = repo / "data" / "geometry" / "capital" / "note.txt"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("x")
    git(repo, "add", "-f", "data/geometry/capital/note.txt")
    with pytest.raises(F.FetchError, match="does not ignore"):
        F.ensure_cache_location(repo / "data" / "geometry")


def test_a_symbolic_link_into_a_tracked_folder_is_refused(
    repo: Path, tmp_path: Path
) -> None:
    link = tmp_path / "looks-outside"
    link.symlink_to(repo / "platform", target_is_directory=True)
    with pytest.raises(F.FetchError, match="does not ignore"):
        fetch(link)
    assert list((repo / "platform").iterdir()) == []


def test_a_repository_git_cannot_answer_for_is_refused(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed: git missing, or refusing (for example over the owner of the folder)."""
    monkeypatch.setattr(F, "_git_toplevel", lambda directory: None)
    with pytest.raises(F.FetchError, match="cannot say whether it is ignored"):
        F.ensure_cache_location(repo / "data" / "geometry")
    assert F.default_cache(repo / "platform") == repo.resolve() / "data" / "geometry"


def test_a_cache_outside_any_repository_is_allowed(tmp_path: Path) -> None:
    assert F.ensure_cache_location(tmp_path / "cache") == (tmp_path / "cache").resolve()


def test_the_default_cache_is_at_the_top_of_the_repository(
    repo: Path, tmp_path: Path
) -> None:
    assert F.default_cache(repo / "platform") == repo.resolve() / "data" / "geometry"
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert F.default_cache(outside) == outside.resolve() / "data" / "geometry"


def test_the_default_cache_of_this_repository_is_git_ignored() -> None:
    here = Path(__file__).resolve().parent
    cache = F.default_cache(here)
    assert cache == Path(__file__).resolve().parents[3] / "data" / "geometry"
    assert F.ensure_cache_location(cache) == cache


# Round 2 of the review ------------------------------------------------------------------------


def test_the_road_classes_match_the_query_template() -> None:
    template = (Path(F.__file__).parent / "queries" / "roads_v1.overpassql").read_text()
    classes = template.split('way["highway"~"^(')[1].split(')$"]')[0].split("|")
    assert set(classes) == F.ROAD_CLASSES and len(classes) == len(F.ROAD_CLASSES)


def translated(answer: dict[str, Any], d_lat: float, d_lon: float) -> dict[str, Any]:
    for element in answer["elements"]:
        for point in [
            element,
            element.get("center") or {},
            *element.get("geometry", []),
        ]:
            if "lat" in point:
                point["lat"] -= d_lat
                point["lon"] -= d_lon
    return answer


def with_a_class(highway: str) -> dict[str, Any]:
    answer = roads_answer()
    answer["elements"][0]["tags"]["highway"] = highway
    return answer


def with_a_point(lat: float) -> dict[str, Any]:
    answer = roads_answer()
    answer["elements"][0]["geometry"][0]["lat"] = lat
    return answer


def with_an_element(kind: str) -> dict[str, Any]:
    answer = roads_answer()
    answer["elements"].append({"type": kind, "id": 5})
    return answer


@pytest.mark.parametrize(
    ("query", "answer", "message"),
    [
        (
            "roads_v1",
            lambda: translated(roads_answer(), 30, 31),
            "outside the queried box",
        ),
        # One edge at a time: the box's south, north, west and east side.
        *(
            (
                "roads_v1",
                lambda d=d: translated(roads_answer(), *d),
                "outside the queried",
            )
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1))
        ),
        ("landmarks_v1", lambda: translated(landmarks_answer(), 30, 31), "only 0 of"),
        ("roads_v1", lambda: with_a_class("footway"), "was not asked for"),
        ("roads_v1", lambda: with_a_point(float("nan")), "off the globe"),
        ("roads_v1", lambda: with_a_point(95.0), "off the globe"),
        ("roads_v1", lambda: with_an_element("node"), "another kind"),
    ],
)
def test_foreign_geometry_is_refused(
    tmp_path: Path, query: str, answer: Callable[[], dict[str, Any]], message: str
) -> None:
    with pytest.raises(F.FetchError, match=message):
        fetch(tmp_path, **{query: answer()})


def stats_with(change: Callable[[list[dict[str, Any]]], None]) -> dict[str, Any]:
    answer = stats_answer()
    change(answer["elements"])
    return answer


def strip_numbers(elements: list[dict[str, Any]]) -> None:
    for e in elements:
        e["tags"] = {"group": e["tags"]["group"], "value": e["tags"]["value"]}


def set_field(
    group: str, key: str, value: str
) -> Callable[[list[dict[str, Any]]], None]:
    def change(elements: list[dict[str, Any]]) -> None:
        next(e for e in elements if e["tags"]["group"] == group)["tags"][key] = value

    return change


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (strip_numbers, "has the fields"),
        (set_field("buildings", "ways", "12.5"), "ways='12.5'"),
        (set_field("buildings", "ways", "-1"), "ways='-1'"),
        (set_field("highway", "km", "nan"), "km='nan'"),
        (lambda e: e.append(dict(e[0])), "appears twice"),
        (lambda e: e.append(stat("parking", "lots", n=3)), "was not asked for"),
    ],
)
def test_statistics_need_their_numbers(
    tmp_path: Path, change: Callable[[list[dict[str, Any]]], None], message: str
) -> None:
    with pytest.raises(F.FetchError, match=message):
        fetch(tmp_path, stats_v1=stats_with(change))


def test_an_answer_from_the_future_is_refused(tmp_path: Path) -> None:
    roads = roads_answer()
    roads["osm3s"]["timestamp_osm_base"] = "2099-01-01T00:00:00Z"
    with pytest.raises(F.FetchError, match="lies after its retrieval"):
        fetch(tmp_path, roads_v1=roads)
    # Within the tolerance (the live run saw the timestamp pass the retrieval by 104 s).
    roads["osm3s"]["timestamp_osm_base"] = "2026-10-26T11:20:00Z"
    F.verify_extract(fetch(tmp_path, roads_v1=roads), F.load_area("capital"))
    # And on a cached extract, with the hashes made to agree.
    extract = fetch(tmp_path / "b")
    late = roads_answer()
    late["osm3s"]["timestamp_osm_base"] = "2099-01-01T00:00:00Z"
    rewrite_answer(extract, "roads_v1", late)
    edit_provenance(
        extract,
        set_key("queries", "roads_v1", "osm_base", value="2099-01-01T00:00:00Z"),
    )
    with pytest.raises(F.FetchError, match="lies after its retrieval"):
        F.verify_extract(extract, F.load_area("capital"))


def test_a_link_inside_the_cache_is_refused(repo: Path) -> None:
    cache = repo / "data" / "geometry"
    cache.mkdir(parents=True)
    (cache / "capital").symlink_to(repo / "platform", target_is_directory=True)
    with pytest.raises(F.FetchError, match="symbolic link"):
        fetch(cache)
    with pytest.raises(F.FetchError, match="symbolic link"):
        F.latest_extract(F.load_area("capital"), cache)
    assert list((repo / "platform").iterdir()) == []


def test_a_link_inside_an_extract_is_refused(tmp_path: Path) -> None:
    extract = fetch(tmp_path)
    outside = tmp_path / "elsewhere.json"
    (extract / "roads_v1.json").rename(outside)
    (extract / "roads_v1.json").symlink_to(outside)
    with pytest.raises(F.FetchError, match="symbolic link"):
        F.verify_extract(extract, F.load_area("capital"))


def test_an_interrupted_replacement_is_recovered(tmp_path: Path) -> None:
    area = F.load_area("capital")
    extract = fetch(tmp_path)
    hidden = extract.with_name(f".old-{extract.name}-999")
    extract.rename(hidden)  # killed after the first rename, before the second
    assert F.latest_extract(area, tmp_path) == extract
    assert not hidden.exists()
    # Killed after the second rename, before the old folder was removed.
    (extract.parent / f".old-{extract.name}-998").mkdir()
    assert F.latest_extract(area, tmp_path) == extract
    assert sorted(p.name for p in extract.parent.iterdir()) == [extract.name]
