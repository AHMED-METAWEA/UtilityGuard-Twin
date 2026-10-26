"""Fetch public street geometry from the OpenStreetMap Overpass API into a local cache.

What is fetched is described by a versioned area file (`areas/<area>_v<n>.json`) and versioned
query templates (`queries/*.overpassql`). The area file holds nothing taken from OpenStreetMap
(owner decision G2): an anchor point from Wikidata (CC0), a search half-width, a margin and the
names of the landmarks. The study box is placed at fetch time: the landmarks are searched near
the anchor, and the box is their bounding box plus the margin. It is an `ASSUMPTION` and is
stored, with how it was made, only in the cache.

Usage policy of the public server (read on the OSM wiki, 2026-10-26): fewer than 10,000 queries
and less than 1 GB per day, and a User-Agent that identifies the application. Every request here
carries one, waits at least `min_interval_s` after the previous one, and backs off exponentially
on 429 and 5xx answers. An answer that cannot be trusted is an error, never a result: a `remark`
(Overpass reports a timeout that way, with HTTP 200 and partial data), no data timestamp, no
roads, or missing statistics.

Licence (G2): OpenStreetMap data is © OpenStreetMap contributors under the ODbL 1.0. Extracts and
everything derived from them stay in a git-ignored cache (or outside any repository); a cache
location inside a repository that git does not ignore is refused before anything is written.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
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
LANDMARKS, ROADS, STATS = "landmarks_v1", "roads_v1", "stats_v1"
QUERY_ORDER = (LANDMARKS, ROADS, STATS)
# Statistics that `stats_v1` always outputs (a `make` statement prints even a zero count): an
# answer without them is not a complete run of the query.
REQUIRED_STATS = frozenset(
    {
        ("buildings", "all"),
        ("buildings", "with_levels"),
        ("names", "named_highways"),
        ("freshness", "highways_edited_last_year"),
        ("freshness", "highways_edited_last_two_years"),
        ("amenity", "office_government"),
    }
)
KM_PER_DEG_LAT = 111.32

Box = tuple[float, float, float, float]  # south, west, north, east (degrees)


class FetchError(Exception):
    """The geometry could not be fetched, or an answer or an extract cannot be trusted."""


@dataclass(frozen=True)
class Area:
    name: str
    version: str
    title: str
    label: str
    note: str
    anchor: tuple[float, float]
    anchor_source: str
    search_half_width_deg: float
    study_margin_km: float
    min_landmarks: int
    landmarks: tuple[str, ...]
    landmark_radius_m: float
    grid_cell_m: float
    endpoint: str
    sha256: str

    def search_box(self) -> Box:
        lat, lon = self.anchor
        h = self.search_half_width_deg
        return (lat - h, lon - h, lat + h, lon + h)


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
    if data.get("label") != "ASSUMPTION":
        raise FetchError("a study area is chosen by hand: its label must be ASSUMPTION")
    anchor = data.get("anchor") or {}
    try:
        lat, lon = float(anchor["lat"]), float(anchor["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FetchError("an area needs an anchor with lat and lon") from exc
    source = str(anchor.get("source", ""))
    if "openstreetmap" in source.lower() or not source.strip():
        raise FetchError(
            "the anchor must name a source that is not OpenStreetMap (decision G2)"
        )
    if not (-90 < lat < 90 and -180 < lon < 180):
        raise FetchError("the anchor is not a position on the globe")
    half = float(data.get("search_half_width_deg", 0))
    margin = float(data.get("study_margin_km", -1))
    if not 0 < half <= 1 or not 0 <= margin <= 20:
        raise FetchError(
            "search_half_width_deg must be in (0, 1] and study_margin_km in [0, 20]"
        )
    landmarks = tuple(str(name) for name in data.get("landmarks", []))
    if not landmarks or any(not name.strip() or "|" in name for name in landmarks):
        raise FetchError("landmark names must be non-blank and must not contain '|'")
    minimum = int(data.get("min_landmarks", 0))
    if not 2 <= minimum <= len(landmarks):
        raise FetchError(
            "min_landmarks must be at least 2 and at most the number of landmarks"
        )
    endpoint = str(data.get("endpoint", ""))
    if not endpoint.startswith("https://"):
        raise FetchError("the endpoint must be an https:// URL")
    return Area(
        name=str(data["area"]),
        version=str(data["version"]),
        title=str(data.get("name", "")),
        label="ASSUMPTION",
        note=str(data.get("note", "")),
        anchor=(lat, lon),
        anchor_source=source,
        search_half_width_deg=half,
        study_margin_km=margin,
        min_landmarks=minimum,
        landmarks=landmarks,
        landmark_radius_m=float(data.get("landmark_radius_m", 1500)),
        grid_cell_m=float(data.get("grid_cell_m", 1000)),
        endpoint=endpoint,
        sha256=sha256_hex(canonical_json(data)),
    )


def box_text(box: Box) -> str:
    return ",".join(f"{value:.6f}" for value in box)


def render_query(name: str, box: Box, area: Area, retrieved: datetime) -> str:
    """Fill a query template. Box and dates are recorded in the provenance, so a saved query can
    be rendered again and compared."""
    template = (
        resources.files("ug_core.geometry")
        .joinpath(f"queries/{name}.overpassql")
        .read_text(encoding="utf-8")
    )
    values = {
        "bbox": box_text(box),
        "landmarks": "|".join(re.escape(landmark) for landmark in area.landmarks),
        "one_year_ago": iso(retrieved - timedelta(days=365)),
        "two_years_ago": iso(retrieved - timedelta(days=730)),
    }
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    leftover = re.findall(r"\{\{[^}]*\}\}", text)
    if leftover:
        raise FetchError(f"query {name} has unknown placeholders {leftover}")
    return text


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def landmark_positions(
    data: dict[str, Any], area: Area
) -> dict[str, tuple[float, float]]:
    """One position per landmark name found: the feature of that name nearest the anchor (ties
    broken by type and id), so a namesake far from the capital cannot stretch the study box."""
    best: dict[str, tuple[float, str, int, tuple[float, float]]] = {}
    cos_lat = math.cos(math.radians(area.anchor[0]))
    for element in data["elements"]:
        name = (element.get("tags") or {}).get("name:en")
        position = element_position(element)
        if name not in area.landmarks or position is None:
            continue
        d_lat = position[0] - area.anchor[0]
        d_lon = (position[1] - area.anchor[1]) * cos_lat
        key = (
            d_lat * d_lat + d_lon * d_lon,
            str(element.get("type")),
            int(element.get("id", 0)),
            position,
        )
        if name not in best or key < best[name]:
            best[name] = key
    return {name: best[name][3] for name in sorted(best)}


def element_position(element: dict[str, Any]) -> tuple[float, float] | None:
    center = element.get("center")
    if center is None and "lat" in element and "lon" in element:
        center = {"lat": element["lat"], "lon": element["lon"]}
    if not center:
        return None
    return float(center["lat"]), float(center["lon"])


def study_box(positions: list[tuple[float, float]], margin_km: float) -> Box:
    """Bounding box of the landmark positions plus the margin, rounded outward to 0.01 degree."""
    lats = [p[0] for p in positions]
    lons = [p[1] for p in positions]
    d_lat = margin_km / KM_PER_DEG_LAT
    mid = math.radians((min(lats) + max(lats)) / 2)
    d_lon = margin_km / (KM_PER_DEG_LAT * math.cos(mid))
    return (
        math.floor((min(lats) - d_lat) * 100) / 100,
        math.floor((min(lons) - d_lon) * 100) / 100,
        math.ceil((max(lats) + d_lat) * 100) / 100,
        math.ceil((max(lons) + d_lon) * 100) / 100,
    )


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
                return raw, parse_answer(raw)
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


def parse_answer(raw: bytes) -> dict[str, Any]:
    """The checks every answer must pass, whatever the query."""
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
    if not isinstance(base, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", base
    ):
        raise FetchError("the Overpass answer carries no valid OSM data timestamp")
    return data


def check_answer(name: str, data: dict[str, Any], area: Area) -> None:
    """The checks of one query: an empty or partial answer is not coverage, it is a failure."""
    elements = data["elements"]
    if name == ROADS:
        ways = [e for e in elements if e.get("type") == "way"]
        if not ways:
            raise FetchError(
                "the roads answer holds no road: the query failed or the box is wrong"
            )
        for way in ways:
            nodes, geometry = way.get("nodes") or [], way.get("geometry") or []
            if len(nodes) < 2 or len(nodes) != len(geometry):
                raise FetchError(f"road way {way.get('id')} has no usable geometry")
            if not (way.get("tags") or {}).get("highway"):
                raise FetchError(f"road way {way.get('id')} has no highway tag")
    elif name == STATS:
        present = {
            (
                str((e.get("tags") or {}).get("group")),
                str((e.get("tags") or {}).get("value")),
            )
            for e in elements
            if e.get("type") == "stat"
        }
        missing = sorted(REQUIRED_STATS - present)
        if missing:
            raise FetchError(f"the statistics answer is incomplete; missing {missing}")
    elif name == LANDMARKS:
        # Finding few landmarks is judged where the box is placed (`min_landmarks`); a feature
        # that was not asked for means the answer is not the one of this query.
        for element in elements:
            if (element.get("tags") or {}).get("name:en") not in area.landmarks:
                raise FetchError(
                    "the landmarks answer holds a feature that was not asked for"
                )


def _git_toplevel(directory: Path) -> Path | None:
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None  # no git: nothing can commit there
    return Path(top.stdout.strip()).resolve() if top.returncode == 0 else None


def _git_marker(directory: Path) -> Path | None:
    """The nearest folder at or above `directory` that holds a `.git` entry."""
    return next(
        (p for p in (directory, *directory.parents) if (p / ".git").exists()), None
    )


def default_cache(cwd: Path | None = None) -> Path:
    """`data/geometry` at the top of the repository holding `cwd`, so the default does not move
    with the directory the command is run from; `data/geometry` in `cwd` outside a repository."""
    here = (cwd or Path.cwd()).resolve()
    return (_git_toplevel(here) or _git_marker(here) or here) / "data" / "geometry"


def ensure_cache_location(cache_root: Path) -> Path:
    """Refuse a cache that git could commit (decision G2). Returns the resolved location.

    Allowed: a location outside any git repository, or one inside a repository that git ignores
    and under which nothing is tracked. Symbolic links are resolved first.
    """
    resolved = cache_root.expanduser().resolve()
    probe = resolved
    while not probe.is_dir():
        probe = probe.parent
    root = _git_toplevel(probe)
    if root is None:
        marker = _git_marker(probe)
        if marker is not None:  # fail closed: a repository git cannot be asked about
            raise FetchError(
                f"the cache {cache_root} is inside {marker}, which holds a .git entry, but git "
                "cannot say whether it is ignored; use a cache outside the repository"
            )
        return resolved  # not inside a repository
    relative = resolved.relative_to(root).as_posix() if resolved != root else "."
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--", relative],
        cwd=root,
        capture_output=True,
        check=False,
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--", relative],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if ignored.returncode != 0 or tracked.returncode != 0 or tracked.stdout.strip():
        raise FetchError(
            f"the cache {cache_root} is inside the repository {root} but git does not ignore it; "
            "OpenStreetMap data must stay out of git (decision G2). Use data/geometry/."
        )
    return resolved


def fetch_area(area: Area, cache_root: Path, overpass: Overpass, now: datetime) -> Path:
    """Place the study box, fetch the area and store everything, atomically, in the cache."""
    cache = ensure_cache_location(cache_root)
    retrieved = iso(now)
    search = area.search_box()
    answers: dict[str, tuple[str, bytes, dict[str, Any], Box]] = {}

    text = render_query(LANDMARKS, search, area, now)
    raw, data = overpass.query(text)
    check_answer(LANDMARKS, data, area)
    answers[LANDMARKS] = (text, raw, data, search)
    positions = landmark_positions(data, area)
    if len(positions) < area.min_landmarks:
        raise FetchError(
            f"only {len(positions)} of the landmarks were found; at least {area.min_landmarks} "
            "are needed to place the study box"
        )
    box = study_box(list(positions.values()), area.study_margin_km)
    for name in (ROADS, STATS):
        text = render_query(name, box, area, now)
        raw, data = overpass.query(text)
        check_answer(name, data, area)
        answers[name] = (text, raw, data, box)

    bases = {
        name: entry[2]["osm3s"]["timestamp_osm_base"] for name, entry in answers.items()
    }
    snapshot = max(bases.values())
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
        "study_box": {
            "bbox": list(box),
            "label": "ASSUMPTION",
            "method": "bounding box of the landmarks found plus the margin, rounded outward to 0.01 degree",
            "landmarks_found": sorted(positions),
        },
        "queries": {
            name: {
                "bbox": list(entry[3]),
                "osm_base": bases[name],
                "query_sha256": sha256_hex(entry[0]),
                "answer_sha256": _sha(entry[1]),
            }
            for name, entry in sorted(answers.items())
        },
        "extract_sha256": _sha(answers[ROADS][1]),
        "coverage_report": "report.json",
    }
    final = cache / area.name / snapshot.replace(":", "-")
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".fetch-", dir=final.parent))
    try:
        (staging / "queries").mkdir()
        for name, (text, raw, _, _) in answers.items():
            (staging / f"{name}.json").write_bytes(raw)
            (staging / "queries" / f"{name}.overpassql").write_text(
                text, encoding="utf-8"
            )
        (staging / PROVENANCE_FILE).write_text(
            json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        # The new extract must pass the same checks as a cached one.
        verify_extract(staging, area)
        _install(staging, final, area)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final


def _install(staging: Path, final: Path, area: Area) -> None:
    """Move the new extract into place. An existing folder for the same OSM snapshot is kept only
    if it is intact and holds the same answers; otherwise the new extract replaces it."""
    if final.exists():
        try:
            same = (
                verify_extract(final, area)["queries"]
                == verify_extract(staging, area)["queries"]
            )
        except FetchError:
            same = False
        if same:
            shutil.rmtree(staging)
            return
        old = final.with_name(f".old-{final.name}-{os.getpid()}")
        os.replace(final, old)
        try:
            os.replace(staging, final)
        except BaseException:
            os.replace(old, final)
            raise
        shutil.rmtree(old, ignore_errors=True)
        return
    os.replace(staging, final)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def latest_extract(area: Area, cache_root: Path) -> Path | None:
    """The newest cached extract of the area that passes `verify_extract`, or None."""
    folder = ensure_cache_location(cache_root) / area.name
    if not folder.is_dir():
        return None
    candidates = sorted(
        (p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")),
        reverse=True,
    )
    for candidate in candidates:
        try:
            verify_extract(candidate, area)
        except FetchError:
            continue
        return candidate
    return None


def verify_extract(extract: Path, area: Area) -> dict[str, Any]:
    """Check an extract completely against its provenance and the current definitions.

    Every saved query must hash as recorded and equal the current template rendered with the
    recorded box and retrieval time; every answer must hash as recorded, parse, pass its checks
    and carry the recorded timestamp; the study box must follow from the landmarks found; the
    snapshot timestamp, endpoint and extract hash must agree. Returns the provenance.
    """
    try:
        record = json.loads((extract / PROVENANCE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FetchError(f"{extract}: no readable provenance") from exc
    if not isinstance(record, dict):
        raise FetchError(f"{extract}: no readable provenance")
    expected = {
        "label": "PUBLIC_GEOMETRY",
        "source": SOURCE,
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise FetchError(f"{extract}: provenance {key} must be {value!r}")
    if record.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        raise FetchError(f"{extract}: unknown provenance version")
    if record.get("area") != {
        "name": area.name,
        "version": area.version,
        "sha256": area.sha256,
        "label": area.label,
    }:
        raise FetchError(f"{extract}: made for another version of the area definition")
    if record.get("endpoint") != area.endpoint:
        raise FetchError(f"{extract}: fetched from another endpoint")
    try:
        retrieved = parse_iso(str(record.get("retrieved")))
    except ValueError as exc:
        raise FetchError(f"{extract}: retrieval time is not a UTC timestamp") from exc
    queries = record.get("queries")
    if not isinstance(queries, dict) or set(queries) != set(QUERY_ORDER):
        raise FetchError(
            f"{extract}: provenance must list exactly the queries {list(QUERY_ORDER)}"
        )
    parsed: dict[str, dict[str, Any]] = {}
    for name in QUERY_ORDER:
        entry = queries[name]
        try:
            south, west, north, east = (float(v) for v in entry["bbox"])
        except (KeyError, TypeError, ValueError) as exc:
            raise FetchError(f"{extract}: query {name} has no box") from exc
        box = (south, west, north, east)
        query_path = extract / "queries" / f"{name}.overpassql"
        answer_path = extract / f"{name}.json"
        if not query_path.is_file() or not answer_path.is_file():
            raise FetchError(f"{extract}: query or answer {name} is missing")
        saved = query_path.read_text(encoding="utf-8")
        if sha256_hex(saved) != entry.get("query_sha256"):
            raise FetchError(f"{extract}: saved query {name} does not match its hash")
        if saved != render_query(name, box, area, retrieved):
            raise FetchError(
                f"{extract}: query {name} was made from another template or box"
            )
        raw = answer_path.read_bytes()
        if _sha(raw) != entry.get("answer_sha256"):
            raise FetchError(f"{extract}: answer {name} does not match its hash")
        data = parse_answer(raw)
        check_answer(name, data, area)
        if data["osm3s"]["timestamp_osm_base"] != entry.get("osm_base"):
            raise FetchError(f"{extract}: answer {name} carries another OSM timestamp")
        parsed[name] = data
    if tuple(queries[LANDMARKS]["bbox"]) != area.search_box():
        raise FetchError(
            f"{extract}: the landmarks were not searched in the area's search box"
        )
    positions = landmark_positions(parsed[LANDMARKS], area)
    if len(positions) < area.min_landmarks:
        raise FetchError(f"{extract}: too few landmarks to place the study box")
    placed = list(study_box(list(positions.values()), area.study_margin_km))
    study = record.get("study_box")
    if (
        not isinstance(study, dict)
        or study.get("bbox") != placed
        or study.get("label") != "ASSUMPTION"
        or study.get("landmarks_found") != sorted(positions)
    ):
        raise FetchError(
            f"{extract}: the study box does not follow from the landmarks found"
        )
    for name in (ROADS, STATS):
        if queries[name]["bbox"] != placed:
            raise FetchError(f"{extract}: query {name} did not use the study box")
    if record.get("osm_base") != max(str(q.get("osm_base")) for q in queries.values()):
        raise FetchError(
            f"{extract}: the snapshot timestamp does not match the answers"
        )
    if record.get("extract_sha256") != queries[ROADS]["answer_sha256"]:
        raise FetchError(
            f"{extract}: extract_sha256 is not the hash of the roads answer"
        )
    return dict(record)
