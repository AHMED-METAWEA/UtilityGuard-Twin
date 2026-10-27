"""Offline progress counts, GitHub supplementation, and reproducible Markdown."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/status.py"
SPEC = importlib.util.spec_from_file_location("b1_status", SCRIPT)
assert SPEC and SPEC.loader
status = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = status
SPEC.loader.exec_module(status)


@pytest.fixture
def plan(tmp_path: Path) -> Path:
    path = tmp_path / "plan.md"
    path.write_text(
        "## 4. A1\n### T-B1-999: Outside B1\nStatus: merged\n"
        "## 4b. B1\n### T-B1-001: Delivered\nStatus: delivered (PR #1)\n"
        "Status: blocked\n"
        "### T-B1-002: Merged\nStatus: merged (PR #2)\n"
        "### Wave 1\n### T-B1-003: Review\nStatus: PR #3 open; the owner merges\n"
        "### T-B1-004: Running\nStatus: running\n"
        "### T-B1-005: Missing status\nTier: T2\n"
        "### Other heading\nStatus: merged\n"
        "### Wave 2\n### T-B1-005b: Follow-up\nStatus: waits for review; blocked\n"
        "Tier: T2\n"
        "### T-B1-006: Coding\nStatus: in progress\n"
        "## 5. Later\n### T-B1-998: Outside B1\nStatus: merged\n",
        encoding="utf-8",
    )
    return path


def test_fixture_counts_and_missing_status(plan: Path) -> None:
    cards = status.parse_plan(plan)
    assert [(c.id, c.wave, status.classify(c.status)) for c in cards] == [
        ("T-B1-001", 0, "merged"),
        ("T-B1-002", 0, "merged"),
        ("T-B1-003", 1, "in review"),
        ("T-B1-004", 1, "in progress"),
        ("T-B1-005", 1, "not started"),
        ("T-B1-005b", 2, "not started"),
        ("T-B1-006", 2, "in progress"),
    ]
    output = status.render(cards, [])
    for label, expected in [
        ("Wave 0", "| 2 | 0 | 0 | 0 |"),
        ("Wave 1", "| 0 | 1 | 1 | 1 |"),
        ("Wave 2", "| 0 | 0 | 1 | 1 |"),
        ("Total", "| 2 | 1 | 2 | 2 |"),
    ]:
        assert expected in output.split(f"## {label}\n")[1].split("## ")[0]
    assert "- PR #3 (T-B1-003)" in output
    assert "- T-B1-005b: waits for review; blocked" in output


def test_deterministic_cli_output(plan: Path, tmp_path: Path, capsys) -> None:
    destination = tmp_path / "STATUS.md"
    args = ["--plan", str(plan), "--write", str(destination)]
    status.main(args)
    first = destination.read_bytes()
    assert first.decode() == capsys.readouterr().out
    status.main(args)
    assert destination.read_bytes() == first
    assert first.decode() == capsys.readouterr().out
    assert first.decode().splitlines()[0] == status.GENERATED


def test_gh_cli_matches_exact_ids_and_checks_owner_body_and_tier(
    plan: Path, monkeypatch, capsys
):
    prs = [
        {"number": 15, "title": "feat: T-B1-005 provider"},
        {"number": 16, "title": "feat: T-B1-004 worker"},
        {"number": 17, "title": "Tier 2: maintenance"},
        {"number": 18, "title": "feat: T-B1-005b follow-up"},
        {"number": 19, "title": "feat: T-B1-002 merged but plan stale"},
    ]

    def fake_run(command, **kwargs):
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=15)
        if command[2] == "list":
            assert command == [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,headRefName,statusCheckRollup",
            ]
            data = list(reversed(prs))
        else:
            assert command[:3] == ["gh", "pr", "view"]
            assert command[4:] == ["--json", "body"]
            data = {"body": "the owner merges" if command[3] == "16" else ""}
        return subprocess.CompletedProcess(command, 0, json.dumps(data), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    status.main(["--plan", str(plan), "--gh"])
    output = capsys.readouterr().out
    waiting = output.split("## Waiting for Ahmed\n")[1].split("## Blocked")[0]
    assert "PR #15 (T-B1-005)" in waiting
    assert "PR #18 (T-B1-005b)" in waiting
    assert "PR #16: feat: T-B1-004 worker" in waiting
    assert "PR #17: Tier 2: maintenance" in waiting
    assert "PR #19" not in waiting
    assert "| 1 | 5 | 1 | 0 |" in output.split("## Total\n")[1]
    assert output == status.render(status.parse_plan(plan), status.open_prs()[::-1])


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("gh"),
        subprocess.CalledProcessError(1, "gh"),
        subprocess.TimeoutExpired("gh", 15),
    ],
)
def test_gh_failure_warns_and_uses_plan(plan: Path, monkeypatch, capsys, error) -> None:
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    status.main(["--plan", str(plan), "--gh"])
    captured = capsys.readouterr()
    assert "Warning: gh failed; using plan only" in captured.err
    assert captured.out == status.render(status.parse_plan(plan), [])


def test_the_leading_bold_phrase_decides_the_state() -> None:
    """Lead review: a card in progress whose status also mentions a merged part."""
    assert (
        status.classify("Status: **in progress**: data part merged (PR #51)")
        == "in progress"
    )
    assert status.classify("Status: **merged by the owner (PR #45)**") == "merged"
    assert status.classify("Status: **PR #53, in review** (round 1)") == "in review"
    assert status.classify("Status: not started (lead)") == "not started"
