"""UtilityGuard Twin API.

All values exposed here are either simulated, model output, assumptions, or
insufficient evidence. "Real-time" in this project means a replayed simulation
stream, never live field data.
"""
from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import (
    DEFAULT_SPEED,
    FRONTEND_DIR,
    MAX_SPEED,
    MIN_SPEED,
    NETWORK_VERSION,
    SETTINGS,
    DETECTOR_VERSION,
)
from app.network.builder import DEFAULT_PROVIDER
from app.scenarios.library import PRESETS, get_preset, list_presets
from app.scenarios.runner import RunBundle, run_scenario
from app.scenarios.schema import ScenarioConfig
from app.store import db

# Optional analysis pipeline is provided by the quality/detector milestone.
try:  # pragma: no cover - exercised once the pipeline exists
    from app.analysis import analyze_bundle
except ImportError:  # pragma: no cover
    analyze_bundle = None  # type: ignore[assignment]


class RunRequest(BaseModel):
    scenario_id: str | None = None
    config: ScenarioConfig | None = None
    speed: float | None = Field(default=None, ge=MIN_SPEED, le=MAX_SPEED)


class AssumptionUpdate(BaseModel):
    values: dict[str, float]


class AnalyzeRequest(BaseModel):
    budget: float | None = Field(default=None, ge=0)
    max_unserved_m3: float | None = Field(default=None, ge=0)


def _sensor_metadata() -> list[dict[str, Any]]:
    return [s.model_dump() for s in DEFAULT_PROVIDER.describe().sensors]


def _execute_run(run_id: str, config: ScenarioConfig) -> None:
    db.set_status(run_id, "simulating")
    try:
        bundle = run_scenario(config)
        analysis = None
        if analyze_bundle is not None:
            analysis = analyze_bundle(bundle, run_id)
            db.save_incidents(run_id, analysis.get("incidents", []))
        db.complete_run(
            run_id,
            truth=bundle.truth.canon(),
            baseline=bundle.baseline.canon(),
            readings=bundle.readings,
            output_hash=bundle.output_hash,
            runtime_seconds=bundle.runtime_seconds,
            analysis=analysis,
        )
    except Exception as exc:  # surface a useful error to the UI
        db.set_status(run_id, "error", f"{type(exc).__name__}: {exc}")


def _run_or_404(run_id: str, include_blobs: bool = False) -> dict[str, Any]:
    run = db.get_run(run_id, include_blobs=include_blobs)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


def _summary(run: dict[str, Any]) -> dict[str, Any]:
    config = run["config"]
    ticks = int(round(config["duration_hours"] * 60 / config["timestep_minutes"]))
    return {
        "run_id": run["id"],
        "scenario_id": run["scenario_id"],
        "status": run["status"],
        "error": run.get("error"),
        "network_version": run["network_version"],
        "seed": run["seed"],
        "created_at": run["created_at"],
        "simulated_hours": config["duration_hours"],
        "ticks": ticks,
        "output_hash": run.get("output_hash"),
        "runtime_seconds": run.get("runtime_seconds"),
        "config": config,
        "labels": {
            "scenario": "ASSUMPTION",
            "physics": "SIMULATION",
            "sensor_stream": "SENSOR_SIM",
        },
    }


def _empty_quality() -> dict[str, Any]:
    return {"status": "ok", "score": 1.0, "flags": []}


def _frame(run: dict[str, Any], tick: int) -> dict[str, Any]:
    config = run["config"]
    readings = run.get("readings") or {}
    analysis = run.get("analysis") or {}
    sensor_quality = analysis.get("quality") or {}
    detector_series = analysis.get("detector") or {}
    events = analysis.get("alert_events") or {}
    seconds = tick * config["timestep_minutes"] * 60
    total_seconds = config["duration_hours"] * 3600
    from datetime import datetime, timedelta
    sim_time = datetime.fromisoformat("2026-01-01T00:00:00") + timedelta(
        seconds=seconds)
    sensor_rows = []
    for sensor in _sensor_metadata():
        sid = sensor["id"]
        value = (readings.get(sid) or [None] * (tick + 1))[tick]
        q = _empty_quality()
        q_series = sensor_quality.get(sid)
        if q_series:
            q = {
                "status": q_series["status"][tick],
                "score": q_series["score"][tick],
                "flags": q_series["flags"][tick],
            }
        sensor_rows.append({
            "sensor_id": sid,
            "value": value,
            "unit": sensor["unit"],
            "source": "SENSOR_SIM",
            "quality": q,
        })
    detector = {
        "state": (detector_series.get("state") or ["normal"] * (tick + 1))[tick],
        "residuals": (detector_series.get("residuals") or [{}] * (tick + 1))[tick],
    }
    tank_value = (readings.get("T01") or [None] * (tick + 1))[tick]
    frame = {
        "run_id": run["id"],
        "tick": tick,
        "sim_time": sim_time.isoformat(timespec="seconds"),
        "readings": sensor_rows,
        "tank": {"sensor_id": "T01", "level_m": tank_value},
        "detector": detector,
        "alerts_changed": events.get(str(tick), []),
        "labels": {
            "readings": "SENSOR_SIM",
            "detector": "MODEL",
            "physics": "SIMULATION",
        },
    }
    _ = total_seconds
    return frame


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(SETTINGS.db_path).parent.mkdir(parents=True, exist_ok=True)
    db.init_db()
    yield


app = FastAPI(title="UtilityGuard Twin", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "network_version": NETWORK_VERSION,
        "detector_version": DETECTOR_VERSION,
        "disclaimer": "Virtual utility twin. Hypothetical network, simulated data.",
    }


@app.get("/api/network")
def network() -> dict[str, Any]:
    desc = DEFAULT_PROVIDER.describe().model_dump()
    desc["sensor_metadata"] = _sensor_metadata()
    desc["labels"] = {"geometry": "ASSUMPTION", "hydraulics": "SIMULATION"}
    desc["disclaimer"] = "Virtual utility twin. Hypothetical network, simulated data."
    return desc


@app.get("/api/scenarios")
def scenarios() -> dict[str, Any]:
    return {
        "presets": list_presets(),
        "network_version": NETWORK_VERSION,
        "labels": {"demand": "ASSUMPTION", "faults": "ASSUMPTION"},
    }


@app.post("/api/runs", status_code=202)
def create_run(
    body: RunRequest,
    background_tasks: BackgroundTasks,
    wait: bool = Query(default=False),
) -> dict[str, Any]:
    if body.config is not None:
        config = body.config
    elif body.scenario_id:
        try:
            config = get_preset(body.scenario_id)
        except KeyError:
            raise HTTPException(status_code=404,
                                detail=f"unknown scenario {body.scenario_id}")
    else:
        raise HTTPException(status_code=422,
                            detail="provide scenario_id or config")
    run_id = uuid.uuid4().hex
    db.create_run(run_id, config.canonical(), config.network_version, config.seed)
    if wait:
        _execute_run(run_id, config)
    else:
        background_tasks.add_task(_execute_run, run_id, config)
    run = _run_or_404(run_id)
    payload = _summary(run)
    payload["speed"] = body.speed or DEFAULT_SPEED
    return payload


@app.get("/api/runs")
def runs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    return {"runs": [_summary(r) for r in db.list_runs(limit)]}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = _run_or_404(run_id)
    payload = _summary(run)
    analysis = db.get_run(run_id, include_blobs=True) or {}
    payload["incident_count"] = len(db.get_incidents(run_id))
    payload["has_analysis"] = bool(analysis.get("analysis"))
    return payload


@app.get("/api/runs/{run_id}/truth")
def truth(run_id: str) -> dict[str, Any]:
    run = _run_or_404(run_id, include_blobs=True)
    if run["status"] != "ready":
        raise HTTPException(status_code=409, detail=f"run is {run['status']}")
    truth_data = run["truth"]
    baseline = run["baseline"]
    flow_lps = {
        link: [round(v * 1000.0, 4) for v in values]
        for link, values in truth_data["flow"].items()
    }
    return {
        "run_id": run_id,
        "network_version": run["network_version"],
        "labels": {
            "pressure": "SIMULATION",
            "flow": "SIMULATION",
            "tank_level": "SIMULATION",
            "leak": "SIMULATION",
        },
        "disclaimer": "Twin-internal ground truth. Not measured field data.",
        "truth": {
            "time_iso": truth_data["time_iso"],
            "pressure": truth_data["pressure"],
            "flow_lps": flow_lps,
            "tank_level": truth_data["tank_level"],
            "leak_flow_lps": truth_data["leak_flow_lps"],
            "leak_area_cm2": truth_data["leak_area_cm2"],
            "leak_node": truth_data["leak_node"],
            "leak_pipe": truth_data["leak_pipe"],
            "pump_status": truth_data["pump_status"],
            "delivered_lps": truth_data["delivered_lps"],
        },
        "baseline": {
            "pressure": baseline["pressure"],
            "tank_level": baseline["tank_level"],
            "leak_flow_lps": baseline["leak_flow_lps"],
        },
    }


@app.get("/api/runs/{run_id}/readings")
def readings(run_id: str) -> dict[str, Any]:
    run = _run_or_404(run_id, include_blobs=True)
    if run["status"] != "ready":
        raise HTTPException(status_code=409, detail=f"run is {run['status']}")
    return {
        "run_id": run_id,
        "sensors": _sensor_metadata(),
        "readings": run["readings"],
        "quality": (run["analysis"] or {}).get("quality"),
        "time_iso": run["truth"]["time_iso"],
        "labels": {"readings": "SENSOR_SIM", "quality": "MODEL"},
    }


@app.get("/api/runs/{run_id}/alerts")
def alerts(run_id: str) -> dict[str, Any]:
    _run_or_404(run_id)
    return {"run_id": run_id, "incidents": db.get_incidents(run_id)}


@app.get("/api/incidents/{incident_id}")
def incident(incident_id: str) -> dict[str, Any]:
    inc = db.get_incident(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return inc


@app.get("/api/incidents/{incident_id}/evidence")
def incident_evidence(incident_id: str) -> dict[str, Any]:
    inc = db.get_incident(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="incident not found")
    from app.evidence.builder import build_incident_evidence
    return build_incident_evidence(inc)


@app.post("/api/incidents/{incident_id}/analyze")
def analyze_incident(
    incident_id: str,
    body: AnalyzeRequest | None = None,
) -> dict[str, Any]:
    inc = db.get_incident(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="incident not found")
    try:
        from app.decision.engine import analyze_incident as run_analysis
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=501,
                            detail=f"decision engine unavailable: {exc}")
    try:
        return run_analysis(
            inc,
            budget=body.budget if body else None,
            max_unserved_m3=body.max_unserved_m3 if body else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@app.get("/api/assumptions")
def assumptions() -> dict[str, Any]:
    from app.finance.engine import load_assumptions
    return load_assumptions()


@app.put("/api/assumptions")
def update_assumptions(body: AssumptionUpdate) -> dict[str, Any]:
    from app.finance.engine import update_assumptions
    try:
        return update_assumptions(body.values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.websocket("/ws/runs/{run_id}")
async def stream(websocket: WebSocket, run_id: str,
                 speed: float = Query(default=DEFAULT_SPEED)) -> None:
    await websocket.accept()
    deadline = time.monotonic() + 180
    run = db.get_run(run_id, include_blobs=True)
    while run is None or run["status"] in ("queued", "simulating"):
        if time.monotonic() > deadline:
            await websocket.send_json({"type": "error", "message": "run timed out"})
            await websocket.close(code=1011)
            return
        await asyncio.sleep(0.1)
        run = db.get_run(run_id, include_blobs=True)
    if run is None:
        await websocket.send_json({"type": "error", "message": "run not found"})
        await websocket.close(code=4404)
        return
    if run["status"] != "ready":
        await websocket.send_json({"type": "error", "message": run.get("error")})
        await websocket.close(code=4400)
        return

    ticks = len(run["truth"]["time_iso"]) - 1
    current = 0
    paused = False
    rate = max(MIN_SPEED, min(MAX_SPEED, float(speed or DEFAULT_SPEED)))
    await websocket.send_text(json.dumps(_frame(run, current)))
    try:
        while True:
            timestep_seconds = run["config"]["timestep_minutes"] * 60
            if paused:
                message = await websocket.receive_text()
            else:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=max(0.01, timestep_seconds / rate),
                    )
                except asyncio.TimeoutError:
                    message = None
            if message is not None:
                try:
                    control = json.loads(message)
                except json.JSONDecodeError:
                    continue
                action = control.get("action")
                if action == "pause":
                    paused = True
                    continue
                if action == "resume":
                    paused = False
                    continue
                if action == "speed":
                    try:
                        rate = max(MIN_SPEED, min(MAX_SPEED, float(control["value"])))
                    except (KeyError, TypeError, ValueError):
                        pass
                    continue
                if action == "jump":
                    try:
                        current = max(0, min(ticks, int(control["value"])))
                    except (KeyError, TypeError, ValueError):
                        continue
                    await websocket.send_text(json.dumps(_frame(run, current)))
                    continue
                if action == "frame":
                    await websocket.send_text(json.dumps(_frame(run, current)))
                    continue
            if paused:
                continue
            if current >= ticks:
                paused = True
                continue
            current += 1
            await websocket.send_text(json.dumps(_frame(run, current)))
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
        return


DIST = FRONTEND_DIR / "dist"
if DIST.exists():  # single-process production convenience
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="frontend")
