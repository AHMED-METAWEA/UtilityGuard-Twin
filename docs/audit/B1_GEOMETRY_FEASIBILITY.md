# B1 geometry feasibility test: is public map data of the New Administrative Capital usable?

Task T-B1-003, 2026-10-26, lead agent. Adoption Plan Phase B1 and Master Spec 1.4 require this test before any network provider is built: "Whether a source is usable is decided by a geometry feasibility test." This is a measurement of OpenStreetMap (OSM) as of the timestamps below, not a survey of the city. Every number here is `OBSERVED` from OSM (what contributors have mapped), not from the ground.

## Verdict in one paragraph

**The street layout is strong; districts, land use and buildings are weak; the water network is absent (as expected).** OSM holds a dense, connected street graph of the capital. In the study box there are 2,888 km of drivable roads with 12,451 junctions, 97.7% of the length in one connected component, and 1,103 km more tagged as under construction. That is enough to infer pipe routes for all three scale tiers (`lite` about 250 junctions, `standard` about 800, `full` 2,000 or more). OSM does not hold the masterplan districts as areas: it has no boundary for the capital, a handful of named district polygons, 53 residential and 8 commercial land-use areas, 3,517 buildings and names on 0.9% of the roads. Demand zones cannot be derived from OSM alone. **Proposal: a hybrid.** Streets come from OSM (`OsmCapitalProvider`). District polygons come from a small hand-made overlay, drawn over the OSM street graph around the OSM-named landmarks, labelled `ASSUMPTION` because the boundaries are ours (the manual-overlay fallback). The procedural F0 network stays as the fallback and the test fixture. Nothing is built until the owner decides (section 6).

## 1. Method

**APIs, verified before use** (rule: verify every external API):
- Overpass API, `https://overpass-api.de/api/interpreter`, Overpass API 0.7.62.11. Usage policy read on the OSM wiki: fewer than 10,000 queries and less than 1 GB per day, a User-Agent that identifies the application. This test sent 4 successful queries; 3 more were refused with `502 server at capacity` and retried with exponential backoff. It downloaded about 12 MB.
- Nominatim, `https://nominatim.openstreetmap.org/search`. Usage policy read (`operations.osmfoundation.org/policies/nominatim/`): at most 1 request per second, an identifying User-Agent, results cached, attribution, ODbL. One request.
- User-Agent of every request: `UtilityGuard-Twin-feasibility/1 (+https://github.com/AHMED-METAWEA/UtilityGuard-Twin)`.

**Where the capital is.** Nominatim knows the New Administrative Capital only as a point (`node 7152775457`, `place=city`, `proposed=yes`, `construction=yes`, "The city is still under construction", 30.024 N, 31.755 E). OSM has **no boundary polygon** for the city. The study area is therefore a box drawn around the OSM features that name the capital or its masterplan districts: **latitude 29.87 to 30.07, longitude 31.61 to 31.80** (about 22 km by 18 km, 437 cells of 1 km). This box is an `ASSUMPTION` of this test. It contains the Central Business District and the Iconic Tower, the Governmental District (Wizarat District), the Arts and Culture City, the Green River park, the R1 and R2 stations, the Presidential Palace, Egypt International Olympic City, the New Capital power plant and the high-speed rail station. It probably also takes in some ground next to the capital (for example the Octagon), and it leaves out the far east of the masterplan.

**Data timestamps** (`timestamp_osm_base` of each Overpass answer): 2026-10-26T10:17:16Z to 10:24:21Z. SHA-256 of the two extracts used for the numbers: statistics `1921a368d3d0e628…c324c4`, roads `3d2a58848d8d95c1…f3c656`. The extracts themselves are **not** in the repository (licence, section 5).

**Queries** (exact text; `B` is the study box):
```
way["highway"](B)->.roads; for.roads(t["highway"]) { make stat ways=count(ways), km=sum(length())/1000; out; }
way["landuse"](B)->.lu; for.lu(t["landuse"]) { make stat ways=count(ways); out; }
(way["building"](B); relation["building"](B);) out count;
nwr["amenity"~"^(school|university|college|hospital|clinic|place_of_worship|police|fire_station|townhall)$"](B) ...
nwr["man_made"~"^(water_tower|reservoir_covered|water_works|pumping_station|storage_tank|wastewater_plant|pipeline|water_well)$"](B) ...
way["highway"](newer:"2025-10-26T00:00:00Z")(B) out count;   (and 2024-10-26)
way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|living_street|*_link|construction)$"](B); out geom;
```
The street-graph numbers come from the last query, computed locally: a node is a junction if it has three or more distinct neighbours; components are found by union-find over road segments; lengths are great-circle distances.

## 2. Results

### Streets (strong)

| Road set | Ways | Length | Junctions (3+ neighbours) | Dead ends | Components | Length in the largest component |
|---|---|---|---|---|---|---|
| Drivable roads, built | 8,546 | 2,888 km | 12,451 | 1,654 | 11 | 97.7% |
| Drivable roads plus roads under construction | 11,217 | 3,992 km | 16,831 | 2,016 | 19 | 98.1% |
| Main streets only (no service roads, no construction), the candidate routes for mains | 3,987 | 2,320 km | 6,072 | 392 | 11 | 97.3% |

By class (all ways, including footways): construction 1,103 km, service 567 km, tertiary 549 km, footway 529 km, residential 522 km, unclassified 367 km, secondary 240 km, trunk 211 km, motorway 185 km, primary 147 km; 4,563 km in all. **27.7% of the drivable length is tagged as under construction**, which fits a city that is still being built.

Spread: 365 of the 437 one-kilometre cells hold a road, 257 hold at least 5 km and 168 at least 10 km. Road length within 1.5 km of each named district: Presidential Palace 142 km, Arts and Culture City 137 km, Central Business District 126 km, R2 126 km, Green River 121 km, R1 120 km, Governmental District 110 km, Olympic City 106 km; the power plant (29 km) and the high-speed rail station (14 km) lie at the edge of the built area.

### Districts, land use, buildings, names (weak)

| Layer | What OSM holds in the study box |
|---|---|
| City boundary | none (the capital is a point, `place=city`, `proposed=yes`) |
| Masterplan districts as areas | a few: Green River (`leisure=park` relation), Central Business District (`landuse=commercial`), Al Masa hotel area, "The City New Capital" (`landuse=residential`); R1 and R2 exist only as stations and stop areas, the Governmental District as stations and a stop area |
| Land use (ways) | grass 1,704 (mostly small patches), construction 146, residential 53, military 18, greenfield 13, commercial 8, religious 6, industrial 5, institutional 5, government 1 |
| Buildings | 3,517 (50 with a height), far fewer than the built districts contain |
| Points of interest | places of worship 48, universities 5, schools 3, hospital 1, government offices 12 |
| Street names | 162 of 18,306 road ways (0.9%) |
| Freshness | 9% of road ways were edited in the last year, 19% in the last two years |

### Water infrastructure (absent, as expected)

1 water tower, 8 pipeline segments, 17 storage tanks, 13 basins, 1 wastewater plant, a few small water bodies. There is no public water network, so pipe routes are inferred from the streets, as Master Spec 1.4 already says for F1.

## 3. What this means for the F1 network

- **Pipe inference is feasible.** The main-street graph alone has 6,072 junctions in one component that holds 97% of the length, so all three tiers can be cut from it by keeping the trunk, primary and secondary classes for transmission and sampling the rest. The rule must be seeded and documented, and its output labelled `ASSUMPTION`.
- **Demand zones need the overlay.** Zones (8 to 10 per Spec 5.1, named after the districts) cannot come from OSM land use: it covers a small part of the area. They come from the overlay (section 4), demands per zone stay synthetic (`ASSUMPTION`), and the district names are the OSM names where they exist.
- **Roads under construction** should be kept as a separate, selectable layer: they are future streets, and a twin that shows them as built would overstate the city.
- **Freshness is a risk.** The city changes faster than its OSM map; every network carries the `timestamp_osm_base` it was built from.

## 4. The manual-overlay fallback (proposal)

A small GeoJSON file, `domains/water/data/overlays/capital_districts_v1.geojson`, holds 8 to 10 polygons drawn by hand over the OSM street graph around the OSM-named landmarks (Governmental District, Central Business District, Arts and Culture City, Green River, R1, R2, R3, Olympic City, Presidential area). It records, for every polygon, `source: "manual overlay"`, `basis` (which OSM features placed it), `drawn_by`, `date`, `label: "ASSUMPTION"`, `confidence: "approximate"`. Rules: it is **not** traced from a copyrighted masterplan image; names are checked against the official ACUD masterplan before any demo (Spec 1.4); when OSM gains a district polygon, the provider prefers OSM and records it as `PUBLIC_GEOMETRY`.

## 5. Licence and reproducibility

- OSM data is © OpenStreetMap contributors under the **ODbL 1.0**. A network derived from it and published is a derivative database. This repository is public. Proposal: OSM extracts and everything derived from them stay in a local, git-ignored cache (`data/geometry/`), filled by `ug fetch-geometry`; tests use synthetic fixtures; the UI and every report show "© OpenStreetMap contributors"; only aggregate numbers such as these are committed. Committing a derived network would require publishing it under the ODbL (owner's decision).
- Reproducibility: the provider records `timestamp_osm_base`, the query text and the SHA-256 of the extract in the run manifest. The same extract gives the same network (seeded inference). A new fetch gives a new network version.
- Availability: the public Overpass server refused 3 of 8 requests with `502 at capacity` during this test. `ug fetch-geometry` must cache, back off, and allow a regional extract file (for example a Geofabrik `.osm.pbf`) as an offline source; reading PBF files needs a new dependency, so that is a later, separate decision.

## 6. Decisions for the owner

1. Accept the hybrid (OSM streets plus the hand-made district overlay), or pure OSM (zones from OSM only, which today gives too few areas), or procedural only (F0, no public layout).
2. Accept the licence rule of section 5 (no OSM-derived data in the public repository), or decide to publish derived networks under the ODbL.
3. Accept the overlay label `ASSUMPTION` for hand-drawn boundaries, with `PUBLIC_GEOMETRY` only for geometry that comes from OSM.

## 7. Addendum (2026-10-26): the study box of `ug fetch-geometry` compared with the box of this test

**Why the box changed.** The box of section 1 was drawn around OSM features, so it is OSM-derived even with the label `ASSUMPTION`; the first review round of T-B1-010 found that committing it breaks decision G2 (`docs/reviews/T-B1-010.md`). `ug fetch-geometry` therefore commits no box: its area file holds an anchor point from Wikidata (Q19588497, CC0), a search half-width, a 3 km margin and the nine landmark names of section 1. At fetch time it searches the landmarks near the anchor and places the study box around those found, plus the margin, rounded outward to 0.01 degree. That box is an `ASSUMPTION` and is stored only in the git-ignored cache. Its coordinates are derived from OSM positions, so they are not given here; its size is.

**The two boxes.** All nine landmarks were found (OSM timestamp 2026-10-26T12:39:20Z).

| | This test (section 1) | Study box of `ug fetch-geometry` | Both boxes |
|---|---|---|---|
| Size | 22.2 km north-south x 18.3 km east-west | 23.4 km x 16.4 km | 21.1 km x 16.4 km |
| Area | 407 km2 | 382 km2 | 346 km2 (85% of the test box, 90% of the new box) |

The new box reaches further south (the 3 km margin around the high-speed rail station and the power plant) and is shorter on the north and narrower east-west (its east and west edges follow the outermost landmarks).

**Road length, built drivable roads** (CALCULATED from the two cached extracts, 30 minutes apart; a segment counts where its midpoint lies):

| | Test box | New box |
|---|---|---|
| In the part both boxes share | 2,353.8 km | 2,353.8 km |
| In the part only this box holds | 219.4 km | 20.1 km |
| Inside the box | 2,573.2 km | 2,373.8 km |
| Outside the box, on ways that cross its edge | 314.6 km (10.9% of the total) | 362.3 km (13.2%) |
| Total of the ways that touch the box (the number section 2 reports) | 2,887.7 km | 2,736.1 km |
| Junctions (whole ways) | 12,451 | 11,727 |
| Share of the length in the largest component | 0.977 | 0.996 |

**Reading.** The shared part holds exactly the same length in both extracts, so OpenStreetMap did not change there between the two snapshots and the whole difference comes from the box: the new box holds 199.4 km (7.7%) less road inside it and 5.8% fewer junctions, more than the 2% of the T-B1-010 acceptance, explained by the box and not by the data or the code. The street graph is more connected in the new box (0.996; 5 components instead of 11): 6 of the 10 pieces separate from the main graph in the test box (26.6 km together) lie wholly in the strips the new box leaves out, and the two largest (16.7 and 16.6 km) are part of the main graph in the new extract, which holds ways that the test box did not. Section 2's lengths, and the coverage report's until T-B1-010 changes it, count every way that touches the box over its whole length, so about a tenth of the reported length lies outside the box; the coverage report gains the length inside the box so that the two cannot be confused. The conclusions of sections 2 to 4 stand: the new box holds all nine landmarks and enough streets for the three scale tiers.
