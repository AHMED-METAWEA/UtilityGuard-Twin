"""Infer a pipe skeleton from a street graph: pipes follow streets (decision G1).

The rules, in order (every number is an `ASSUMPTION` of the tier table below or the provider's
config; the inferred topology is an `ASSUMPTION` too, only the street geometry is public):

1. Keep the street segments of the tier's road classes, then the largest connected component
   (by node count; ties by the smallest node id). What is dropped is counted.
2. Contract chains of degree-2 nodes: a pipe runs between two nodes of degree other than 2 and
   carries the length of the street path between them (its segments' sum) and those segments.
   A chain that returns to its own start (a loop street) is dropped and counted.
3. Join junctions that are closer than a radius `r` along a pipe (dual carriageways, ramps and
   short connectors make clusters of nodes): the junction with the most neighbours (then the
   smallest OSM id) stands for the group, pipes inside a group disappear, and the chains are
   contracted again. A pipe whose end moves to the representative gains the shortest street
   route between them over the joined streets, in length and in segments, so every pipe is a
   complete street route between its two junctions.
4. The tier's junction target picks `r`: the smallest radius (bisection, 0.1 m resolution) whose
   skeleton has at most the target; it must then hold at least 90% of it, otherwise the tier
   cannot be built from this graph and that is an error, never a silent shortfall. In a tier
   that joins junctions, parallel pipes between the same two junctions (the two carriageways of
   a divided road) become one pipe, the shortest: a main follows the road corridor once.
5. A pipe's tier (transmission, submain, distribution) is the tier of the road classes that
   cover the largest part of its length (ties: the higher tier).
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ug_water.network.model import PipeTier
from ug_water.network.osm import Street, StreetGraph

LINKS = (
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
)
CLASS_TIER: dict[str, PipeTier] = {
    "motorway": "transmission", "trunk": "transmission", "primary": "transmission",
    "motorway_link": "transmission", "trunk_link": "transmission",
    "primary_link": "transmission", "secondary": "submain", "tertiary": "submain",
    "secondary_link": "submain", "tertiary_link": "submain",
}  # fmt: skip
TIER_RANK = {"transmission": 0, "submain": 1, "distribution": 2}
MAIN = frozenset(
    {"motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link",
     "primary_link", "secondary_link"}
)  # fmt: skip
STREETS = MAIN | {
    "tertiary",
    "tertiary_link",
    "residential",
    "unclassified",
    "living_street",
}


@dataclass(frozen=True)
class TierRule:
    classes: frozenset[str]
    target: (
        int | None
    )  # junctions; None keeps every junction of the class set (no joining)
    minimum: int = 0


TIERS: dict[str, TierRule] = {
    "lite": TierRule(MAIN, 250),
    "standard": TierRule(MAIN, 800),
    "full": TierRule(STREETS, None, minimum=2000),
}


@dataclass(frozen=True)
class SkeletonPipe:
    a: int
    b: int
    length_m: float
    tier: PipeTier
    streets: tuple[
        tuple[int, int], ...
    ]  # the street segments it follows (OSM node pairs)


@dataclass(frozen=True)
class Skeleton:
    nodes: Mapping[
        int, tuple[float, float]
    ]  # OSM node id -> local (x, y), the junctions
    pipes: tuple[SkeletonPipe, ...]
    radius_m: float
    dropped: Mapping[str, float]  # what rules 1 and 2 left out, counted


@dataclass(frozen=True)
class _Chain:
    a: int
    b: int
    length: float
    streets: tuple[tuple[int, int], ...]
    by_tier: tuple[tuple[str, float], ...]  # tier -> street length, sorted


def _tier_lengths(streets: Iterable[Street]) -> dict[str, float]:
    lengths: dict[str, float] = defaultdict(float)
    for s in streets:
        lengths[CLASS_TIER.get(s.highway, "distribution")] += s.length_m
    return lengths


def _largest_component(streets: list[Street]) -> tuple[list[Street], int]:
    neighbours: dict[int, set[int]] = defaultdict(set)
    for s in streets:
        neighbours[s.a].add(s.b)
        neighbours[s.b].add(s.a)
    seen: set[int] = set()
    best: tuple[int, int, set[int]] | None = None
    for start in sorted(neighbours):
        if start in seen:
            continue
        group, stack = {start}, [start]
        while stack:
            for n in neighbours[stack.pop()]:
                if n not in group:
                    group.add(n)
                    stack.append(n)
        seen |= group
        key = (-len(group), start)
        if best is None or key < (best[0], best[1]):
            best = (key[0], key[1], group)
    keep = best[2] if best else set()
    kept = [s for s in streets if s.a in keep]
    return kept, len(neighbours) - len(keep)


def _contract(edges: list[_Chain]) -> tuple[list[_Chain], int]:
    """Merge chains through degree-2 nodes; returns the chains and the loops dropped."""
    incident: dict[int, list[int]] = defaultdict(list)
    for k, e in enumerate(edges):
        incident[e.a].append(k)
        incident[e.b].append(k)
    # Multigraph degree (edge ends), so parallel streets keep their junctions.
    kept = {n for n, ks in incident.items() if len(ks) != 2}
    if not kept and incident:
        kept = {min(incident)}
    out: list[_Chain] = []
    used: set[int] = set()
    loops = 0
    for start in sorted(kept):
        for first in incident[start]:
            if first in used:
                continue
            node, length = start, 0.0
            segments: list[tuple[int, int]] = []
            tiers: dict[str, float] = defaultdict(float)
            k = first
            while True:
                used.add(k)
                e = edges[k]
                forward = e.a == node
                segments.extend(e.streets)
                length += e.length
                for tier, value in e.by_tier:
                    tiers[tier] += value
                node = e.b if forward else e.a
                if node in kept:
                    break
                k = next(j for j in incident[node] if j not in used)
            if node == start:
                loops += 1
                continue
            out.append(
                _Chain(
                    start, node, length, tuple(segments), tuple(sorted(tiers.items()))
                )
            )
    return out, loops


def _find(parent: dict[int, int], n: int) -> int:
    while parent[n] != n:
        parent[n] = parent[parent[n]]
        n = parent[n]
    return n


Route = tuple[float, tuple[tuple[int, int], ...], tuple[tuple[str, float], ...]]


def _merge_tiers(
    *parts: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    total: dict[str, float] = defaultdict(float)
    for part in parts:
        for tier, length in part:
            total[tier] += length
    return tuple(sorted(total.items()))


def _routes(short: list[_Chain], parent: dict[int, int]) -> dict[int, Route]:
    """For every joined node, the shortest street route to its group's representative over the
    joined streets: (length, street segments, length per tier). Representatives: (0, (), ())."""
    graph: dict[int, list[tuple[int, _Chain]]] = defaultdict(list)
    for e in short:
        graph[e.a].append((e.b, e))
        graph[e.b].append((e.a, e))
    routes: dict[int, Route] = {}
    for rep in sorted({_find(parent, n) for n in graph}):
        best: dict[int, Route] = {rep: (0.0, (), ())}
        queue = [(0.0, rep)]
        while queue:
            dist, n = heapq.heappop(queue)
            if dist > best[n][0]:
                continue
            for m, e in sorted(graph[n], key=lambda item: (item[1].length, item[0])):
                if _find(parent, m) != rep:
                    continue
                candidate = (
                    dist + e.length,
                    best[n][1] + e.streets,
                    _merge_tiers(best[n][2], e.by_tier),
                )
                if m not in best or candidate[0] < best[m][0]:
                    best[m] = candidate
                    heapq.heappush(queue, (candidate[0], m))
        routes.update(best)
    return routes


def _join(edges: list[_Chain], radius: float) -> list[_Chain]:
    """Join the ends of chains shorter than `radius`, contracting again until nothing changes.
    A chain whose end moves to its group's representative gains the street route between them
    (length and segments), so every pipe stays a complete street route."""
    while True:
        degree: dict[int, set[int]] = defaultdict(set)
        for e in edges:
            degree[e.a].add(e.b)
            degree[e.b].add(e.a)
        parent = {n: n for n in degree}
        joined = False
        short: list[_Chain] = []
        for e in sorted(edges, key=lambda c: (c.length, c.a, c.b)):
            if e.length >= radius:
                break
            short.append(e)
            ra, rb = _find(parent, e.a), _find(parent, e.b)
            if ra != rb:
                rank_a, rank_b = (-len(degree[ra]), ra), (-len(degree[rb]), rb)
                keep, lose = (ra, rb) if rank_a < rank_b else (rb, ra)
                parent[lose] = keep
                joined = True
        if not joined:
            return edges
        routes = _routes(short, parent)
        moved: list[_Chain] = []
        for e in edges:
            ra, rb = _find(parent, e.a), _find(parent, e.b)
            if ra == rb:
                continue  # inside a group: its street is part of the group's routes
            (la, sa, ta), (lb, sb, tb) = (
                routes.get(e.a, (0.0, (), ())),
                routes.get(e.b, (0.0, (), ())),
            )
            moved.append(
                _Chain(
                    ra,
                    rb,
                    e.length + la + lb,
                    sa + e.streets + sb,
                    _merge_tiers(ta, e.by_tier, tb),
                )  # fmt: skip
            )
        edges, _ = _contract(moved)


def ordered_route(
    streets: tuple[tuple[int, int], ...], start: int, end: int
) -> tuple[int, ...]:
    """The OSM nodes of a pipe's street route in order from `start` to `end` (an Euler trail
    over its segments, which form one route; a repeated street is walked twice)."""
    remaining: dict[int, list[int]] = defaultdict(list)
    for k, (a, b) in enumerate(streets):
        remaining[a].append(k)
        remaining[b].append(k)
    used: set[int] = set()
    stack, trail = [start], []
    while stack:
        n = stack[-1]
        while remaining[n] and remaining[n][-1] in used:
            remaining[n].pop()
        if remaining[n]:
            k = remaining[n].pop()
            used.add(k)
            a, b = streets[k]
            stack.append(b if a == n else a)
        else:
            trail.append(stack.pop())
    route = tuple(reversed(trail))
    if len(used) != len(streets) or route[0] != start or route[-1] != end:
        raise ValueError(f"the streets of the pipe {start}-{end} do not form one route")
    return route


def _one_per_corridor(edges: list[_Chain]) -> list[_Chain]:
    best: dict[tuple[int, int], _Chain] = {}
    for e in edges:
        key = (min(e.a, e.b), max(e.a, e.b))
        if key not in best or (e.length, e.streets) < (
            best[key].length,
            best[key].streets,
        ):
            best[key] = e
    return [best[key] for key in sorted(best)]


def _tier(by_tier: tuple[tuple[str, float], ...]) -> PipeTier:
    tier = min(by_tier, key=lambda item: (-item[1], TIER_RANK[item[0]]))[0]
    return tier  # type: ignore[return-value]


def _junctions(edges: list[_Chain]) -> set[int]:
    return {n for e in edges for n in (e.a, e.b)}


def skeleton(graph: StreetGraph, tier: str, rule: TierRule | None = None) -> Skeleton:
    """The pipe skeleton of the street graph for a tier (`lite`, `standard`, `full`); `rule`
    replaces the tier's rule (tests use small targets on small graphs)."""
    if rule is None:
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier!r}; known: {sorted(TIERS)}")
        rule = TIERS[tier]
    chosen = [s for s in graph.streets if s.highway in rule.classes]
    if not chosen:
        raise ValueError(
            f"tier {tier}: the street graph holds none of its road classes"
        )
    kept, dropped_nodes = _largest_component(chosen)
    base = [
        _Chain(
            s.a,
            s.b,
            s.length_m,
            ((min(s.a, s.b), max(s.a, s.b)),),
            tuple(sorted(_tier_lengths([s]).items())),
        )
        for s in kept
    ]
    contracted, loops = _contract(base)
    radius = 0.0
    edges = contracted
    if rule.target is not None:
        high = rule.target
        if len(_junctions(contracted)) > high:
            lo, hi = 0.0, 5000.0
            if len(_junctions(_join(contracted, hi))) > high:
                raise ValueError(f"tier {tier}: cannot reach {rule.target} junctions")
            while hi - lo > 0.1:
                mid = (lo + hi) / 2
                if len(_junctions(_join(contracted, mid))) > high:
                    lo = mid
                else:
                    hi = mid
            radius = math.ceil(hi * 10) / 10
            edges = _join(contracted, radius)
        edges = _one_per_corridor(edges)
        count = len(_junctions(edges))
        if count < 0.9 * rule.target:
            raise ValueError(
                f"tier {tier}: {count} junctions, below 90% of the target {rule.target}"
            )
    elif len(_junctions(edges)) < rule.minimum:
        raise ValueError(f"tier {tier}: fewer than {rule.minimum} junctions")
    pipes = sorted(
        (
            SkeletonPipe(min(e.a, e.b), max(e.a, e.b), e.length,
                         _tier(e.by_tier), tuple(sorted(e.streets)))
            for e in edges
        ),
        key=lambda p: (p.a, p.b, p.length_m, p.streets),
    )  # fmt: skip
    nodes = {n: graph.nodes[n] for n in sorted(_junctions(edges))}
    return Skeleton(
        nodes=nodes,
        pipes=tuple(pipes),
        radius_m=radius,
        dropped={
            "nodes_outside_the_largest_component": float(dropped_nodes),
            "loop_streets": float(loops),
        },
    )
