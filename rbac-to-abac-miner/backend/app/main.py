"""FastAPI application entry point.

Startup configuration:
  - CORS from FRONTEND_ORIGIN environment variable (default http://localhost:5173)
  - Custom exception handlers returning ErrorResponse for 404, 422, and 500
  - Router includes for datasets, training, and policies

Stub mode: if BACKEND_STUBS=true, all endpoints return matching files from
shared/sample_responses/ so Naeem and Shweta can integrate on day 1.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.datasets import router as datasets_router
from backend.api.policies import router as policies_router
from backend.api.training import router as training_router
from shared.schemas.contracts import ErrorResponse

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# App instance
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="RBAC-to-ABAC Miner API",
    description=(
        "Supervised learning based approach for mining ABAC rules from RBAC systems. "
        "CONTRACT VERSION 1.0.0."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------- #
# Exception handlers (never expose stack traces or file paths)
# --------------------------------------------------------------------------- #

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convert Pydantic validation errors to ErrorResponse."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            code="VALIDATION_ERROR",
            message="Request body failed schema validation.",
            details={"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Convert 404 to ErrorResponse."""
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            code="NOT_FOUND",
            message=f"Path '{request.url.path}' not found.",
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all handler: log the error and return a safe 500 response.

    NEVER returns a permit decision or exposes internal paths.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. The default decision is deny.",
        ).model_dump(),
    )


# --------------------------------------------------------------------------- #
# Stub mode
# --------------------------------------------------------------------------- #

BACKEND_STUBS = os.environ.get("BACKEND_STUBS", "false").lower() == "true"
_SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "shared" / "sample_responses"

STUB_MAP = {
    ("POST", "/api/v1/datasets/upload"): "dataset_validation_ok.json",
    ("GET", "/api/v1/datasets/"): "rbac_authorisation.json",
    ("POST", "/api/v1/training/run"): "training_response.json",
    ("GET", "/api/v1/training/"): "model_comparison.json",
    ("POST", "/api/v1/policies/optimise/"): "optimised_policy.json",
    ("GET", "/api/v1/policies/"): "policy_validation.json",
    ("POST", "/api/v1/policies/"): "approval_response.json",
}


@app.middleware("http")
async def stub_middleware(request: Request, call_next):
    """If BACKEND_STUBS=true, serve sample responses for matching paths."""
    if BACKEND_STUBS:
        for (method, prefix), filename in STUB_MAP.items():
            if request.method == method and request.url.path.startswith(prefix):
                sample_path = _SAMPLE_DIR / filename
                if sample_path.exists():
                    content = json.loads(sample_path.read_text(encoding="utf-8"))
                    return JSONResponse(content=content)
    return await call_next(request)


# --------------------------------------------------------------------------- #
# Routers
# --------------------------------------------------------------------------- #

app.include_router(datasets_router)
app.include_router(training_router)
app.include_router(policies_router)


# --------------------------------------------------------------------------- #
# Operational endpoints (Decision D-009)
# --------------------------------------------------------------------------- #

@app.get("/health", tags=["ops"], summary="Health check")
async def health():
    """Returns OK to indicate the server is running.

    Outside the /api/v1 contract (Decision D-009).
    """
    return {"status": "ok"}


@app.get("/", tags=["ops"], include_in_schema=False)
async def root():
    """Root redirect information."""
    return {
        "status": "ok",
        "message": "RBAC-to-ABAC Miner API. See /docs for the OpenAPI spec.",
        "contract_version": "1.0.0",
    }
