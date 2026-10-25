# ADR-007: Map engine and offline basemap

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 4.7, 13; principle P10.

## Position taken in the Master Spec
- The map uses deck.gl on a local Cartesian coordinate system, plus an SVG schematic view. Online map services are rejected: they need the internet and have licensing limits.
- The whole demo runs offline: no map tiles, no CDN fonts, no external APIs. A 3D city view (three.js) is an optional visual layer.

## Where it is built
Spec milestones M2 (map engine v1) and M6 (3D view).

## To settle when this ADR is completed
- What the offline basemap is drawn from (the public geometry of the capital, with provenance and licence) and the geometry feasibility test of Phase B1.
- Performance on the reference scene (target 60 fps, Spec 4.8).
