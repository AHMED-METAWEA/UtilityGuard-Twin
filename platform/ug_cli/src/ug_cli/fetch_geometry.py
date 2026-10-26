"""`ug fetch-geometry`: fetch, cache and report the public street geometry of a study area.

OpenStreetMap data is © OpenStreetMap contributors under the ODbL 1.0. It is stored only in the
local cache (default `data/geometry/` at the top of the repository, git-ignored; owner decision
G2) and never in the repository: a cache that git does not ignore is refused before anything is
written. Without `--refresh`, a complete cached extract is used and nothing is fetched.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from ug_core.geometry.fetch import (
    ATTRIBUTION,
    FetchError,
    Overpass,
    default_cache,
    fetch_area,
    latest_extract,
    load_area,
    verify_extract,
)
from ug_core.geometry.report import coverage_report, write_report


def add_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser(
        "fetch-geometry",
        help="fetch and report the public street geometry of a study area",
    )
    parser.add_argument(
        "--area", default="capital", help="area name (default: capital)"
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="cache folder, git-ignored or outside any repository "
        "(default: data/geometry at the top of the repository)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--refresh", action="store_true", help="fetch a new extract")
    group.add_argument(
        "--offline", action="store_true", help="never fetch; use the cache"
    )
    parser.add_argument(
        "--report", action="store_true", help="write report.json and report.md"
    )


def run(args: argparse.Namespace) -> int:
    try:
        area = load_area(args.area)
        cache = args.cache if args.cache is not None else default_cache()
        extract = None if args.refresh else latest_extract(area, cache)
        if extract is None:
            if args.offline:
                print(
                    f"ug fetch-geometry: no complete cached extract of {area.name} in {cache}; "
                    "run without --offline to fetch one",
                    file=sys.stderr,
                )
                return 1
            extract = fetch_area(
                area, cache, Overpass(area.endpoint), datetime.now(UTC)
            )
        record = verify_extract(extract, area)
    except FetchError as exc:
        print(f"ug fetch-geometry: {exc}", file=sys.stderr)
        return 1
    print(f"extract: {extract}")
    print(f"OSM data timestamp: {record['osm_base']} (retrieved {record['retrieved']})")
    print(f"licence: {record['licence']}; {ATTRIBUTION}")
    if args.report:
        json_path, md_path = write_report(extract, area)
        streets = coverage_report(extract, area)["streets"]["drivable_built"]
        print(f"report: {json_path} and {md_path}")
        print(
            f"drivable, built: {streets['length_km']} km, {streets['junctions']} junctions, "
            f"{streets['largest_component_length_share']} of the length in the largest component"
        )
    return 0
