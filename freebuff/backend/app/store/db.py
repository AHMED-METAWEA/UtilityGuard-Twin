"""Small SQLite store. Time series are zlib-compressed canonical JSON blobs.

SQLite is used for run metadata, time series, incidents and decisions. This
keeps the demo single-file and offline; no external database is required.
"""
from __future__ import annotations

import json
import sqlite3
import zlib
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    config_json TEXT NOT NULL,
    network_version TEXT NOT NULL,
    seed INTEGER NOT NULL,
    output_hash TEXT,
    runtime_seconds REAL,
    error TEXT,
    truth_blob BLOB,
    baseline_blob BLOB,
    readings_blob BLOB,
    analysis_blob BLOB
);
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    diagnosis TEXT NOT NULL,
    suspected_location TEXT,
    first_detected_tick INTEGER NOT NULL,
    last_tick INTEGER NOT NULL,
    opened_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_run ON incidents(run_id);
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_incident ON decisions(incident_id);
"""

_RUN_COLUMNS = (
    "id, scenario_id, status, created_at, config_json, network_version, seed, "
    "output_hash, runtime_seconds, error"
)


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    with closing(_connect(db_path)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dump(obj: Any) -> bytes:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                         allow_nan=False)
    return zlib.compress(payload.encode("utf-8"), level=6)


def _load(blob: bytes | None) -> Any:
    if blob is None:
        return None
    return json.loads(zlib.decompress(blob).decode("utf-8"))


def delete_run(run_id: str) -> None:
    """Remove a run and its derived rows (used by the evaluation rerun)."""
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM decisions WHERE incident_id IN "
                     "(SELECT id FROM incidents WHERE run_id=?)", (run_id,))
        conn.execute("DELETE FROM incidents WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
        conn.commit()


def create_run(run_id: str, config: dict[str, Any], network_version: str,
               seed: int) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO runs (id, scenario_id, status, created_at, config_json, "
            "network_version, seed) VALUES (?, ?, 'queued', ?, ?, ?, ?)",
            (run_id, config["scenario_id"], _now(),
             json.dumps(config, sort_keys=True), network_version, seed),
        )
        conn.commit()


def set_status(run_id: str, status: str, error: str | None = None) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE runs SET status=?, error=? WHERE id=?",
                     (status, error, run_id))
        conn.commit()


def complete_run(run_id: str, truth: dict, baseline: dict, readings: dict,
                 output_hash: str, runtime_seconds: float,
                 analysis: dict | None = None) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE runs SET status='ready', truth_blob=?, baseline_blob=?, "
            "readings_blob=?, analysis_blob=?, output_hash=?, runtime_seconds=? "
            "WHERE id=?",
            (_dump(truth), _dump(baseline), _dump(readings),
             _dump(analysis) if analysis is not None else None,
             output_hash, runtime_seconds, run_id),
        )
        conn.commit()


def save_analysis(run_id: str, analysis: dict) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE runs SET analysis_blob=? WHERE id=?",
                     (_dump(analysis), run_id))
        conn.commit()


def get_run(run_id: str, include_blobs: bool = False) -> dict[str, Any] | None:
    columns = _RUN_COLUMNS + (", truth_blob, baseline_blob, readings_blob, analysis_blob"
                              if include_blobs else "")
    with closing(_connect()) as conn:
        row = conn.execute(f"SELECT {columns} FROM runs WHERE id=?",
                           (run_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["config"] = json.loads(data["config_json"])
    if include_blobs:
        data["truth"] = _load(data.pop("truth_blob"))
        data["baseline"] = _load(data.pop("baseline_blob"))
        data["readings"] = _load(data.pop("readings_blob"))
        data["analysis"] = _load(data.pop("analysis_blob"))
    return data


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["config"] = json.loads(item["config_json"])
        out.append(item)
    return out


def save_incidents(run_id: str, incidents: list[dict[str, Any]]) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM incidents WHERE run_id=?", (run_id,))
        for inc in incidents:
            conn.execute(
                "INSERT INTO incidents (id, run_id, status, severity, diagnosis, "
                "suspected_location, first_detected_tick, last_tick, opened_at, "
                "payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (inc["id"], run_id, inc["status"], inc["severity"],
                 inc["diagnosis"], inc.get("suspected_location"),
                 inc["first_detected_tick"], inc["last_tick"], _now(),
                 json.dumps(inc, sort_keys=True)),
            )
        conn.commit()


def get_incidents(run_id: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT payload_json FROM incidents"
    args: tuple = ()
    if run_id:
        query += " WHERE run_id=?"
        args = (run_id,)
    query += " ORDER BY first_detected_tick"
    with closing(_connect()) as conn:
        rows = conn.execute(query, args).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def get_incident(incident_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT payload_json FROM incidents WHERE id=?", (incident_id,)
        ).fetchone()
    return json.loads(row["payload_json"]) if row else None


def save_decision(incident_id: str, decision_id: str, payload: dict[str, Any]) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO decisions (id, incident_id, created_at, "
            "payload_json) VALUES (?, ?, ?, ?)",
            (decision_id, incident_id, _now(),
             json.dumps(payload, sort_keys=True)),
        )
        conn.commit()


def get_decision(incident_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT payload_json FROM decisions WHERE incident_id=? "
            "ORDER BY created_at DESC LIMIT 1", (incident_id,)
        ).fetchone()
    return json.loads(row["payload_json"]) if row else None
