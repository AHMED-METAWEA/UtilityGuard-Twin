# ADR-005: Parquet plus DuckDB for time series

Status: stub. The position below is copied from the Master Spec. Context, alternatives, consequences and evidence are written by the card that builds the decision.

Spec references: Master Spec 4.7, 11.2, principle P7.

## Position taken in the Master Spec
- Time series are stored as Parquet files and queried with DuckDB: columnar, fast replay and analytics, no server.
- Relational data uses SQLite in development and PostgreSQL in the compose setup. InfluxDB and Timescale are kept as an upgrade path, not used at the start.
- Runs are immutable and append-only; derived views are rebuildable from the run log plus manifests (P7).

## Where it is built
Spec milestone M1 (run store).

## To settle when this ADR is completed
- File layout and partitioning, and the schema version carried in every file.
- Whether DuckDB and a Parquet writer need approval as dependencies (they are not on the A1 approved list).
