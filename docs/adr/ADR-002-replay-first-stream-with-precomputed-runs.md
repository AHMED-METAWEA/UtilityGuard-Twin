# ADR-002: Replay-first stream with precomputed runs

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 4.5; Honesty Rules (stream source).

## Position taken in the Master Spec
- The full scenario is simulated once, up front. The analytics pipeline processes a deterministic replay.
- This keeps the stream cheap, the demo smooth and the results reproducible, and lets evaluation sweeps run without a UI.
- The same analytics code path serves replay today and a live source at fidelity F3. The stream source (REPLAY, SIMULATED, LIVE) is always visible.

## Where it is built
T-A1-002 (the stream envelope requires `stream_source`); the replay player in Spec milestone M2.

## To settle when this ADR is completed
- The replay clock, seek and speed protocol (M2).
- What a live source must provide to plug in at F3 without changing the analytics path.
