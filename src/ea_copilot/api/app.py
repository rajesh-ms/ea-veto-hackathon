"""FastAPI application factory for FR-101, FR-601..FR-710, and NFR-01."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ea_copilot.api import (
    routes_demo,
    routes_live,
    routes_metrics,
    routes_preferences,
    routes_requests,
    routes_review,
)
from ea_copilot.bootstrap import ApplicationRuntime, build_runtime
from ea_copilot.config import project_root
from ea_copilot.domain.errors import (
    ApprovalRequiredError,
    CalendarWritesDisabledError,
    DecisionValidationError,
    ResourceNotFoundError,
)


def create_app(runtime: ApplicationRuntime | None = None) -> FastAPI:
    root = project_root()
    application = FastAPI(
        title="Executive Time Management Copilot",
        version="0.1.0",
        description="Governed, offline-first scheduling recommendations for Executive Assistants.",
    )
    application.state.root = root
    application.state.runtime = runtime or build_runtime(root)
    application.include_router(routes_requests.router)
    application.include_router(routes_review.router)
    application.include_router(routes_preferences.router)
    application.include_router(routes_metrics.router)
    application.include_router(routes_demo.router)
    application.include_router(routes_live.router)
    static = Path(__file__).parent / "static"
    application.mount("/static", StaticFiles(directory=static), name="static")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "adapters": "fake"}

    @application.get("/demo", include_in_schema=False)
    def demo() -> FileResponse:
        return FileResponse(static / "demo.html")

    @application.exception_handler(ApprovalRequiredError)
    async def approval_required(
        request: Request,
        error: ApprovalRequiredError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=409,
            content={"error": type(error).__name__, "detail": str(error)},
        )

    @application.exception_handler(CalendarWritesDisabledError)
    async def writes_disabled(
        request: Request,
        error: CalendarWritesDisabledError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=403,
            content={"error": type(error).__name__, "detail": str(error)},
        )

    @application.exception_handler(DecisionValidationError)
    async def bad_decision(
        request: Request,
        error: DecisionValidationError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=422,
            content={"error": type(error).__name__, "detail": str(error)},
        )

    @application.exception_handler(ResourceNotFoundError)
    async def not_found(
        request: Request,
        error: ResourceNotFoundError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=404,
            content={"error": type(error).__name__, "detail": str(error)},
        )

    return application


app = create_app()
