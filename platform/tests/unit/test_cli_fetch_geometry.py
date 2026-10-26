"""T-B1-010: `ug fetch-geometry` uses the cache, never fetches offline, and reports."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from geometry_fixtures import BASE, FakeOverpass
from ug_cli.main import main
from ug_core.geometry import fetch as F


def test_offline_without_a_cache_fails_with_a_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["fetch-geometry", "--offline", "--cache", str(tmp_path)]) == 1
    assert "--offline" in capsys.readouterr().err


def test_a_cached_extract_is_used_and_reported_without_any_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    extract = F.fetch_area(
        F.load_area("capital"),
        tmp_path,
        FakeOverpass(),
        datetime(2026, 10, 26, tzinfo=UTC),
    )  # type: ignore[arg-type]

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("fetched although a complete extract was cached")

    monkeypatch.setattr(F.Overpass, "query", no_network)
    assert main(["fetch-geometry", "--report", "--cache", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert str(extract) in out and BASE in out and "© OpenStreetMap contributors" in out
    assert (extract / "report.json").is_file() and (extract / "report.md").is_file()


def test_refresh_and_offline_exclude_each_other(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["fetch-geometry", "--refresh", "--offline", "--cache", str(tmp_path)])
    assert exit_info.value.code == 2


def test_a_failed_fetch_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def busy(self: object, text: str) -> None:
        raise F.FetchError("no usable answer after 5 attempts (HTTP 502)")

    monkeypatch.setattr(F.Overpass, "query", busy)
    assert main(["fetch-geometry", "--refresh", "--cache", str(tmp_path)]) == 1
    assert "HTTP 502" in capsys.readouterr().err
    assert not (tmp_path / "capital").exists()


def test_the_default_cache_is_at_the_top_of_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    (repo / "platform").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("/data/\n")
    monkeypatch.chdir(repo / "platform")
    assert main(["fetch-geometry", "--offline"]) == 1
    assert f"in {repo.resolve() / 'data' / 'geometry'};" in capsys.readouterr().err


def test_a_cache_git_could_commit_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    monkeypatch.setattr(F.Overpass, "query", FakeOverpass().query)
    assert main(["fetch-geometry", "--refresh", "--cache", str(repo / "cache")]) == 1
    assert "does not ignore it" in capsys.readouterr().err
    assert not (repo / "cache").exists()
