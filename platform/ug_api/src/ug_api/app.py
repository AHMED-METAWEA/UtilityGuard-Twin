"""Same-origin shell hosting and the minimal, advisory-only health API."""

from collections.abc import Mapping
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles

import ug_api

DISCLAIMER = (
    "Virtual twin. Not ACUD data and not a survey of any real network. "
    "Advisory only: a human approves every action. "
    "Not certified for operation of critical infrastructure."
)


def problem(status: int, headers: Mapping[str, str] | None = None) -> JSONResponse:
    """Return the minimal RFC 7807 representation, preserving protocol headers."""
    return JSONResponse(
        {"type": "about:blank", "title": HTTPStatus(status).phrase, "status": status},
        status_code=status,
        headers=headers,
        media_type="application/problem+json",
    )


async def http_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, HTTPException)
    return problem(exc.status_code, exc.headers)


def create_app(static_dir: Path | None = None) -> FastAPI:
    """Create isolated applications; importing this module starts no server."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_exception_handler(HTTPException, http_error)
    api.add_exception_handler(HTTPException, http_error)

    @app.middleware("http")
    async def api_headers(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        response = problem(404) if path == "/api" else await call_next(request)
        if path == "/api" or path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {
            "schema_version": "1",
            "status": "ok",
            "service": "ug-api",
            "version": ug_api.__version__,
            "disclaimer": DISCLAIMER,
        }

    @api.head("/health")
    async def health_head() -> Response:
        return Response(media_type="application/json")

    app.mount("/api", api)
    if static_dir is not None and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True))
    return app
