"""Fetch public street geometry from the OpenStreetMap Overpass API into a local cache.

What is fetched is described by a versioned area file (`areas/<area>_v<n>.json`: the study box,
an `ASSUMPTION`, and landmark names) and versioned query templates (`queries/*.overpassql`). The
answers are stored byte for byte, with a provenance record, in
`data/geometry/<area>/<osm timestamp>/`.

Usage policy of the public server (read on the OSM wiki, 2026-10-26): fewer than 10,000 queries
and less than 1 GB per day, and a User-Agent that identifies the application. Every request here
carries one, waits at least `min_interval_s` after the previous one, and backs off exponentially
on 429 and 5xx answers (the feasibility test met `502 server at capacity`). An answer with a
`remark` (Overpass reports a timeout or an out-of-memory that way, with HTTP 200 and partial data)
is an error, never a result.

Licence (owner decision G2): OpenStreetMap data is © OpenStreetMap contributors under the ODbL
1.0. Extracts and everything derived from them stay in the git-ignored cache; nothing here writes
into the repository.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any

from ug_core.canonical import canonical_json, sha256_hex

SOURCE = "OpenStreetMap"
LICENCE = "ODbL-1.0"
ATTRIBUTION = "© OpenStreetMap contributors"
USER_AGENT = "UtilityGuard-Twin/1 (+https://github.com/AHMED-METAWEA/UtilityGuard-Twin)"
RETRY_CODES = frozenset({429, 500, 502, 503, 504})
PROVENANCE_FILE = "provenance.json"
PROVENANCE_SCHEMA_VERSION = "1"


class FetchError(Exception):
    """The geometry could not be fetched or the answer cannot be trusted."""


@dataclass(frozen=True)
class Area:
    name: str
    version: str
    title: str
    label: str
    note: str
    bbox: tuple[float, float, float, float]  # south, west, north, east (degrees)
    landmarks: tuple[str, ...]
    landmark_radius_m: float
    grid_cell_m: float
    queries: tuple[str, ...]
    endpoint: str
    sha256: str

    def bbox_text(self) -> str:
        return ",".join(f"{value:g}" for value in self.bbox)


def load_area(name: str, version: str = "1") -> Area:
    """Read a packaged area file (`areas/<name>_v<version>.json`) and check it."""
    resource = resources.files("ug_core.geometry").joinpath(
        f"areas/{name}_v{version}.json"
    )
    try:
        data = json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FetchError(f"no area file for {name!r} version {version}") from exc
    return area_from_dict(data)


def area_from_dict(data: dict[str, Any]) -> Area:
    box = data.get("bbox") or {}
    try:
        bbox = (
            float(box["south"]),
            float(box["west"]),
            float(box["north"]),
            float(box["east"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FetchError(
            "an area needs a bbox with south, west, north and east"
        ) from exc
    south, west, north, east = bbox
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise FetchError(f"the bbox is not a valid box: {bbox}")
    if data.get("label") != "ASSUMPTION":
        raise FetchError("a study area is drawn by hand: its label must be ASSUMPTION")
    landmarks = tuple(str(name) for name in data.get("landmarks", []))
    if any(not name.strip() or "|" in name for name in landmarks):
        raise FetchError("landmark names must be non-blank and must not contain '|'")
    queries = tuple(str(q) for q in data.get("queries", []))
    if not queries or any(not re.fullmatch(r"[a-z0-9_]+", q) for q in queries):
        raise FetchError("an area names its queries as lower-case tokens")
    endpoint = str(data.get("endpoint", ""))
    if not endpoint.startswith("https://"):
        raise FetchError("the endpoint must be an https:// URL")
    return Area(
        name=str(data["area"]),
        version=str(data["version"]),
        title=str(data.get("name", "")),
        label="ASSUMPTION",
        note=str(data.get("note", "")),
        bbox=bbox,
        landmarks=landmarks,
        landmark_radius_m=float(data.get("landmark_radius_m", 1500)),
        grid_cell_m=float(data.get("grid_cell_m", 1000)),
        queries=queries,
        endpoint=endpoint,
        sha256=sha256_hex(canonical_json(data)),
    )


def render_query(name: str, area: Area, retrieved: datetime) -> str:
    """Fill a query template; the dates are fixed by the retrieval time, so they are recorded."""
    template = (
        resources.files("ug_core.geometry")
        .joinpath(f"queries/{name}.overpassql")
        .read_text(encoding="utf-8")
    )
    values = {
        "bbox": area.bbox_text(),
        "landmarks": "|".join(re.escape(landmark) for landmark in area.landmarks),
        "one_year_ago": _iso(retrieved - timedelta(days=365)),
        "two_years_ago": _iso(retrieved - timedelta(days=730)),
    }
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    leftover = re.findall(r"\{\{[^}]*\}\}", text)
    if leftover:
        raise FetchError(f"query {name} has unknown placeholders {leftover}")
    return text


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


Opener = Callable[..., Any]


class Overpass:
    """A polite Overpass client: identifying User-Agent, spacing, retries with backoff."""

    def __init__(
        self,
        endpoint: str,
        *,
        user_agent: str = USER_AGENT,
        attempts: int = 5,
        first_backoff_s: float = 30.0,
        timeout_s: float = 300.0,
        min_interval_s: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        urlopen: Opener = urllib.request.urlopen,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self.endpoint = endpoint
        self.user_agent = user_agent
        self.attempts = attempts
        self.first_backoff_s = first_backoff_s
        self.timeout_s = timeout_s
        self.min_interval_s = min_interval_s
        self._sleep = sleep
        self._clock = clock
        self._urlopen = urlopen
        self._last: float | None = None

    def query(self, text: str) -> tuple[bytes, dict[str, Any]]:
        """Run one query; return the raw answer and its parsed form. Raises `FetchError`."""
        wait = self.first_backoff_s
        last_error = "no attempt made"
        for attempt in range(1, self.attempts + 1):
            self._space_out()
            try:
                raw = self._post(text)
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRY_CODES:
                    raise FetchError(
                        f"Overpass refused the query: HTTP {exc.code}"
                    ) from exc
                last_error = f"HTTP {exc.code}"
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                return raw, _parse(raw)
            if attempt < self.attempts:
                self._sleep(wait)
                wait *= 2
        raise FetchError(
            f"no usable answer after {self.attempts} attempts ({last_error})"
        )

    def _space_out(self) -> None:
        now = self._clock()
        if self._last is not None and now - self._last < self.min_interval_s:
            self._sleep(self.min_interval_s - (now - self._last))
        self._last = self._clock()

    def _post(self, text: str) -> bytes:
        body = urllib.parse.urlencode({"data": text}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"User-Agent": self.user_agent},
            method="POST",
        )
        with self._urlopen(request, timeout=self.timeout_s) as response:
            data: bytes = response.read()
            return data


def _parse(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise FetchError("Overpass did not answer with JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        raise FetchError("the Overpass answer has no element list")
    if data.get("remark"):
        # A timeout or an out-of-memory comes back as HTTP 200 with partial data and a remark.
        raise FetchError(
            f"Overpass reported a problem, the answer is incomplete: {data['remark']}"
        )
    base = (data.get("osm3s") or {}).get("timestamp_osm_base")
    if not isinstance(base, str) or not base:
        raise FetchError("the Overpass answer carries no OSM data timestamp")
    return data


def fetch_area(area: Area, cache_root: Path, overpass: Overpass, now: datetime) -> Path:
    """Fetch every query of the area and store the answers, atomically, in a new extract folder."""
    retrieved = _iso(now)
    answers: dict[str, tuple[str, bytes, dict[str, Any]]] = {}
    for name in area.queries:
        text = render_query(name, area, now)
        raw, parsed = overpass.query(text)
        answers[name] = (text, raw, parsed)
    bases = {
        name: parsed["osm3s"]["timestamp_osm_base"]
        for name, (_, _, parsed) in answers.items()
    }
    snapshot = max(bases.values())
    final = cache_root / area.name / snapshot.replace(":", "-")
    record = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "label": "PUBLIC_GEOMETRY",
        "source": SOURCE,
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "retrieved": retrieved,
        "osm_base": snapshot,
        "endpoint": area.endpoint,
        "user_agent": overpass.user_agent,
        "area": {
            "name": area.name,
            "version": area.version,
            "sha256": area.sha256,
            "label": area.label,
        },
        "queries": {
            name: {
                "osm_base": bases[name],
                "query_sha256": sha256_hex(text),
                "answer_sha256": _sha(raw),
            }
            for name, (text, raw, _) in sorted(answers.items())
        },
        "extract_sha256": _sha(answers["roads_v1"][1])
        if "roads_v1" in answers
        else None,
        "coverage_report": "report.json",
    }
    cache_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".fetch-", dir=cache_root))
    try:
        (staging / "queries").mkdir()
        for name, (text, raw, _) in answers.items():
            (staging / f"{name}.json").write_bytes(raw)
            (staging / "queries" / f"{name}.overpassql").write_text(
                text, encoding="utf-8"
            )
        (staging / PROVENANCE_FILE).write_text(
            json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            shutil.rmtree(staging)
            return final  # the same OSM snapshot is already cached
        os.replace(staging, final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final


def _sha(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def latest_extract(area: Area, cache_root: Path) -> Path | None:
    """The newest cached extract of the area that is complete and unaltered, or None."""
    folder = cache_root / area.name
    if not folder.is_dir():
        return None
    for candidate in sorted(
        (p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")),
        reverse=True,
    ):
        try:
            verify_extract(candidate, area)
        except FetchError:
            continue
        return candidate
    return None


def verify_extract(extract: Path, area: Area) -> dict[str, Any]:
    """Check an extract against its provenance (every answer's hash); return the provenance."""
    try:
        record = json.loads((extract / PROVENANCE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FetchError(f"{extract}: no readable provenance") from exc
    if record.get("source") != SOURCE or record.get("licence") != LICENCE:
        raise FetchError(f"{extract}: provenance is not OpenStreetMap under {LICENCE}")
    if record.get("area", {}).get("sha256") != area.sha256:
        raise FetchError(f"{extract}: made for another version of the area definition")
    for name in area.queries:
        expected = (record.get("queries") or {}).get(name, {}).get("answer_sha256")
        path = extract / f"{name}.json"
        if not expected or not path.is_file() or _sha(path.read_bytes()) != expected:
            raise FetchError(
                f"{extract}: answer {name} is missing or does not match its hash"
            )
    return dict(record)
