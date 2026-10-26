"""The Python dependency audit (T-B1-002), tested offline: PyPI is replaced by a fake.

The script must never report a package as clean without an answer about it: an unknown package,
an unreachable PyPI, a changed answer format or a lock line that is not an exact pin all end the
audit with exit code 2.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "audit_python", ROOT / "scripts" / "audit_python.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_python"] = module
    spec.loader.exec_module(module)
    return module


A = load()
CVE = {
    "id": "PYSEC-2099-1",
    "aliases": ["CVE-2099-0001", "GHSA-aaaa-bbbb-cccc"],
    "fixed_in": ["2.0"],
    "withdrawn": None,
}
SAME_CVE_OTHER_ID = {
    "id": "GHSA-aaaa-bbbb-cccc",
    "aliases": ["CVE-2099-0001", "PYSEC-2099-1"],
    "fixed_in": ["2.0.0"],
    "withdrawn": None,
}


def answer(*vulnerabilities: dict[str, Any]) -> dict[str, Any]:
    return {"info": {}, "vulnerabilities": list(vulnerabilities)}


def fake(responses: dict[str, Any]) -> Any:
    def fetch(url: str) -> dict[str, Any]:
        value = responses[url]
        if isinstance(value, Exception):
            raise value
        return value  # type: ignore[no-any-return]

    return fetch


def url(name: str, version: str) -> str:
    return A.PYPI.format(name=name, version=version)


def lock(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "requirements.lock"
    path.write_text(text)
    return path


# ------------------------------------------------------------------ reading the lock


def test_a_hash_pinned_lock_is_read_with_normalized_names(tmp_path: Path) -> None:
    path = lock(
        tmp_path,
        "# comment\n\nFastAPI==0.143.0 \\\n    --hash=sha256:aa \\\n    --hash=sha256:bb\n"
        'Typing_Extensions[extra]==4.15.0 ; python_version >= "3.11"\nzope.interface==7.0\n',
    )
    assert [(p.name, p.version) for p in A.read_lock(path)] == [
        ("fastapi", "0.143.0"),
        ("typing-extensions", "4.15.0"),
        ("zope-interface", "7.0"),
    ]


@pytest.mark.parametrize(
    "line", ["fastapi>=0.143", "fastapi", "-r other.txt", "-e .", "fastapi~=0.143.0"]
)
def test_a_line_that_is_not_an_exact_pin_is_an_error(tmp_path: Path, line: str) -> None:
    with pytest.raises(A.AuditError, match="not an exact pin"):
        A.read_lock(lock(tmp_path, f"uvicorn==0.54.0\n{line}\n"))


def test_an_empty_or_missing_lock_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(A.AuditError, match="no pinned package"):
        A.read_lock(lock(tmp_path, "# nothing\n"))
    with pytest.raises(A.AuditError, match="cannot read"):
        A.read_lock(tmp_path / "missing.lock")


def test_the_real_lock_is_read() -> None:
    packages = A.read_lock(ROOT / "deploy" / "requirements-api.lock")
    names = {p.name for p in packages}
    assert {"fastapi", "uvicorn", "starlette", "pydantic"} <= names


# ------------------------------------------------------------------ installed packages


class Dist:
    def __init__(self, name: str, version: str, direct_url: str | None = None) -> None:
        self.metadata = {"Name": name}
        self.version = version
        self._direct_url = direct_url

    def read_text(self, filename: str) -> str | None:
        return self._direct_url if filename == "direct_url.json" else None


def test_local_installs_are_skipped_even_with_a_second_record() -> None:
    editable = json.dumps(
        {"url": "file:///repo/platform/ug_core", "dir_info": {"editable": True}}
    )
    packages, local = A.installed_packages(
        [
            Dist("ug-core", "0.0.0", editable),
            Dist("ug_core", "0.0.0"),  # an old .egg-info record without direct_url.json
            Dist("NumPy", "2.4.6"),
            Dist(
                "wntr", "1.5.0", json.dumps({"url": "https://example.invalid/wntr.whl"})
            ),
        ]
    )
    assert [(p.name, p.version) for p in packages] == [
        ("numpy", "2.4.6"),
        ("wntr", "1.5.0"),
    ]
    assert local == ["ug-core"]


# ------------------------------------------------------------------ PyPI answers


def test_a_known_vulnerability_is_reported_once_per_alias_group() -> None:
    packages = [A.Package("pip", "23.2.1", "installed")]
    report = A.audit(
        packages, {}, fake({url("pip", "23.2.1"): answer(CVE, SAME_CVE_OTHER_ID)})
    )
    [found] = report.vulnerable[packages[0]]
    assert found.id == "CVE-2099-0001"
    assert set(found.aliases) == {"PYSEC-2099-1", "GHSA-aaaa-bbbb-cccc"}
    assert found.fixed_in == ("2.0", "2.0.0")


def test_a_withdrawn_advisory_does_not_count() -> None:
    withdrawn = {**CVE, "withdrawn": "2099-02-01T00:00:00Z"}
    packages = [A.Package("pip", "23.2.1", "installed")]
    report = A.audit(packages, {}, fake({url("pip", "23.2.1"): answer(withdrawn)}))
    assert report.vulnerable == {} and report.checked == packages


@pytest.mark.parametrize(
    "bad",
    [
        {
            "info": {}
        },  # no vulnerabilities field: the format changed, do not assume clean
        {"vulnerabilities": "none"},
        {"vulnerabilities": [{"aliases": []}]},  # an advisory without an id
    ],
)
def test_an_answer_in_an_unexpected_shape_is_an_error(bad: dict[str, Any]) -> None:
    packages = [A.Package("pip", "23.2.1", "installed")]
    report = A.audit(packages, {}, fake({url("pip", "23.2.1"): bad}))
    assert report.errors and not report.checked


def test_a_package_that_is_not_on_pypi_is_an_error_not_clean() -> None:
    packages = [A.Package("ug-core", "0.0.0", "installed")]
    report = A.audit(
        packages, {}, fake({url("ug-core", "0.0.0"): A.NotOnPyPI("HTTP 404")})
    )
    assert report.errors and report.checked == []


class Response(io.BytesIO):
    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://pypi.org/x", code, "x", {}, None)  # type: ignore[arg-type]


def test_fetch_retries_transient_failures_then_gives_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(A.time, "sleep", lambda seconds: None)
    calls: list[str] = []

    def failing(request: Any, timeout: float) -> Response:
        calls.append(request.full_url)
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(A.urllib.request, "urlopen", failing)
    with pytest.raises(A.AuditError, match="no answer after 3 attempts"):
        A.fetch_json("https://pypi.org/pypi/pip/23.2.1/json")
    assert len(calls) == 3


@pytest.mark.parametrize("code", [500, 502, 503, 429])
def test_fetch_retries_server_errors_and_rate_limits(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    monkeypatch.setattr(A.time, "sleep", lambda seconds: None)
    answers: list[Any] = [http_error(code), Response(json.dumps(answer()).encode())]

    def flaky(request: Any, timeout: float) -> Response:
        value = answers.pop(0)
        if isinstance(value, Exception):
            raise value
        return value  # type: ignore[no-any-return]

    monkeypatch.setattr(A.urllib.request, "urlopen", flaky)
    assert A.fetch_json("https://pypi.org/pypi/pip/26.2.1/json") == answer()


@pytest.mark.parametrize(("code", "error"), [(404, "not on PyPI"), (403, "HTTP 403")])
def test_fetch_does_not_retry_a_definite_answer(
    monkeypatch: pytest.MonkeyPatch, code: int, error: str
) -> None:
    calls: list[int] = []

    def refused(request: Any, timeout: float) -> Response:
        calls.append(code)
        raise http_error(code)

    monkeypatch.setattr(A.urllib.request, "urlopen", refused)
    with pytest.raises(A.AuditError, match=error):
        A.fetch_json("https://pypi.org/pypi/x/1/json")
    assert calls == [code]


def test_fetch_refuses_a_json_answer_that_is_not_an_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(A.urllib.request, "urlopen", lambda r, timeout: Response(b"[]"))
    with pytest.raises(A.AuditError, match="not return a JSON object"):
        A.fetch_json("https://pypi.org/pypi/x/1/json")


# ------------------------------------------------------------------ ignore list and exit codes


def ignore(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "ignore.txt"
    path.write_text(text)
    return path


def run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    responses: dict[str, Any],
    lock_text: str,
    extra: list[str] | None = None,
) -> int:
    monkeypatch.setattr(A, "fetch_json", fake(responses))
    path = lock(tmp_path, lock_text)
    return int(A.main(["--lock", str(path), *(extra or [])], today=date(2026, 10, 26)))


def test_exit_codes_clean_vulnerable_and_unanswered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = {url("fastapi", "0.143.0"): answer()}
    assert run(tmp_path, monkeypatch, clean, "fastapi==0.143.0\n") == 0
    assert "0 known vulnerabilities, 0 errors" in capsys.readouterr().out
    vulnerable = {url("pip", "23.2.1"): answer(CVE)}
    assert run(tmp_path, monkeypatch, vulnerable, "pip==23.2.1\n") == 1
    out = capsys.readouterr().out
    assert (
        "VULNERABLE pip==23.2.1" in out
        and "CVE-2099-0001" in out
        and "fixed in 2.0" in out
    )
    missing = {url("ug-core", "0.0.0"): A.NotOnPyPI("HTTP 404")}
    assert run(tmp_path, monkeypatch, missing, "ug-core==0.0.0\n") == 2
    # an unanswered package wins over a vulnerable one: the audit is incomplete
    both = {**vulnerable, **missing}
    assert run(tmp_path, monkeypatch, both, "pip==23.2.1\nug-core==0.0.0\n") == 2


def test_a_local_package_named_on_the_command_line_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = {url("fastapi", "0.143.0"): answer()}
    lock_text = "fastapi==0.143.0\nug-api==0.0.0\n"
    assert run(tmp_path, monkeypatch, responses, lock_text, ["--local", "UG_API"]) == 0
    assert "SKIPPED local installs: ug-api" in capsys.readouterr().out


def test_an_active_ignore_entry_hides_the_advisory_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    accepted = ignore(
        tmp_path, "# accepted\nGHSA-aaaa-bbbb-cccc until 2026-11-30 build tool only\n"
    )
    responses = {url("pip", "23.2.1"): answer(CVE)}
    code = run(
        tmp_path, monkeypatch, responses, "pip==23.2.1\n", ["--ignore", str(accepted)]
    )
    assert code == 0
    assert (
        "IGNORED pip==23.2.1: CVE-2099-0001 (accepted: build tool only)"
        in capsys.readouterr().out
    )


def test_an_expired_ignore_entry_no_longer_applies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    expired = ignore(
        tmp_path, "CVE-2099-0001 until 2026-10-25 was accepted for a while\n"
    )
    responses = {url("pip", "23.2.1"): answer(CVE)}
    code = run(
        tmp_path, monkeypatch, responses, "pip==23.2.1\n", ["--ignore", str(expired)]
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "expired on 2026-10-25" in out and "VULNERABLE pip==23.2.1" in out


@pytest.mark.parametrize(
    "text",
    [
        "CVE-2099-0001\n",
        "CVE-2099-0001 until tomorrow fine\n",
        "CVE-1 until 2026-13-01 x\n",
    ],
)
def test_a_malformed_ignore_file_stops_the_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    path = ignore(tmp_path, text)
    responses = {url("pip", "23.2.1"): answer(CVE)}
    assert (
        run(tmp_path, monkeypatch, responses, "pip==23.2.1\n", ["--ignore", str(path)])
        == 2
    )


def test_the_output_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = {
        url("pip", "23.2.1"): answer(CVE),
        url("setuptools", "65.5.0"): answer(
            {**CVE, "id": "PYSEC-2099-9", "aliases": []}
        ),
        url("fastapi", "0.143.0"): answer(),
    }
    text = "setuptools==65.5.0\nfastapi==0.143.0\npip==23.2.1\n"
    outputs = []
    for _ in range(3):
        run(tmp_path, monkeypatch, responses, text)
        outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0].index("pip==") < outputs[0].index("setuptools==")


def test_the_shipped_ignore_file_is_well_formed() -> None:
    path = ROOT / "scripts" / "audit_python_ignore.txt"
    active, notes = A.read_ignores(path, date(2026, 10, 26))
    assert notes == []
    assert all(reason for reason in active.values())
