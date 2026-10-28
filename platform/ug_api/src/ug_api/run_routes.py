"""Recorded-run routes mounted inside the existing API application."""

from typing import Any

from fastapi import FastAPI, Request

from ug_api.runs import RunError, RunStore, WhatIfHook, identifier, parse_json


def mount_runs(api: FastAPI, store: RunStore, whatif: WhatIfHook | None) -> None:
    @api.get("/runs")
    def runs() -> Any:
        return store.list()

    @api.get("/runs/{run_id}/network")
    def network(run_id: str) -> Any:
        return store.load(run_id).network

    @api.get("/runs/{run_id}/series")
    def series(run_id: str) -> Any:
        return [
            {key: item[key] for key in ("series_id", "kind", "element", "label")}
            for item in store.load(run_id).series.values()
        ]

    @api.get("/runs/{run_id}/series/{series_id}")
    def one_series(run_id: str, series_id: str) -> Any:
        identifier(series_id)
        result = store.load(run_id).series.get(series_id)
        if result is None:
            raise RunError(404, "Unknown series")
        return result

    @api.get("/runs/{run_id}/incidents")
    def incidents(run_id: str) -> Any:
        return store.load(run_id).incidents

    @api.get("/runs/{run_id}/decision")
    def decision(run_id: str) -> Any:
        result = store.load(run_id).decision
        if result is None:
            raise RunError(404, "No decision recorded")
        return result

    @api.get("/runs/{run_id}/evidence/{evidence_id}")
    def evidence(run_id: str, evidence_id: str) -> Any:
        identifier(evidence_id)
        result = store.load(run_id).evidence.get(evidence_id)
        if result is None:
            raise RunError(404, "Unknown evidence")
        return result

    @api.post("/runs/{run_id}/whatif")
    async def run_whatif(run_id: str, request: Request) -> Any:
        bundle = store.load(run_id)
        try:
            body = parse_json(await request.body())
        except (ValueError, UnicodeError):
            raise RunError(422, "Invalid payload: whatif-request") from None
        store.contracts.validate("whatif-request", body, "whatif-request", 422)
        sensors = {item["id"] for item in bundle.network["sensors"]}
        if body["run_id"] != run_id or any(
            change["sensor_id"] not in sensors for change in body["changes"]
        ):
            raise RunError(422, "Run or sensor does not match bundle")
        if whatif is None:
            raise RunError(501, "what-if engine not wired")
        try:
            result = whatif(bundle, body)
        except Exception:
            raise RunError(500, "what-if engine failed") from None
        store.validate_whatif(result, run_id)
        return result
