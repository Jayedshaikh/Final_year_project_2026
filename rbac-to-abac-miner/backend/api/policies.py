"""Policy optimisation, validation, review, and export endpoints.

POST /api/v1/policies/optimise/{run_id}
GET  /api/v1/policies/{policy_id}/validation
POST /api/v1/policies/{policy_id}/review
POST /api/v1/policies/{policy_id}/export
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.services import pipeline_service
from shared.schemas.contracts import (
    ApprovalRequest,
    ApprovalResponse,
    ErrorResponse,
    ExportRequest,
    ExportResponse,
    OptimisedPolicyResponse,
    PolicyValidationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["policies"])


@router.post(
    "/policies/optimise/{run_id}",
    response_model=OptimisedPolicyResponse,
    summary="Optimise extracted rules via the policy engine",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def optimise_policy(run_id: str) -> OptimisedPolicyResponse:
    """Call policy_engine.optimise_policy on the candidate rules from a training run.

    Then immediately validates the optimised rules on the full access matrix.
    Creates and returns a new policy_id.

    HTTP 404 if run_id is not found.
    HTTP 409 if training has not completed or no rules exist.
    """
    try:
        return pipeline_service.optimise_policy(run_id)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="RUN_NOT_FOUND",
                message=f"No training run with id '{run_id}'.",
            ).model_dump(),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                code="INVALID_STATE",
                message=str(exc),
            ).model_dump(),
        )


@router.get(
    "/policies/{policy_id}/validation",
    response_model=PolicyValidationResponse,
    summary="Validate a policy against the full access matrix",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def validate_policy(policy_id: str) -> PolicyValidationResponse:
    """Re-validate the current rule set (including any admin edits) on the full matrix.

    HTTP 404 if policy_id is not found.
    """
    try:
        return pipeline_service.validate_policy(policy_id)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="POLICY_NOT_FOUND",
                message=f"No policy with id '{policy_id}'.",
            ).model_dump(),
        )


@router.post(
    "/policies/{policy_id}/review",
    response_model=ApprovalResponse,
    summary="Apply administrator approve/reject/edit decisions to rules",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def review_policy(policy_id: str, request: ApprovalRequest) -> ApprovalResponse:
    """Apply a set of approve / reject / edit decisions.

    Nothing is ever auto-approved. Only explicit API calls change rule status.

    HTTP 404 if policy_id or a rule_id is not found.
    HTTP 400 if an edit decision is missing edited_conditions.
    """
    if request.policy_id != policy_id:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                code="INVALID_CONFIG",
                message="policy_id in path and request body must match.",
            ).model_dump(),
        )
    try:
        return pipeline_service.review_policy(policy_id, request)
    except KeyError as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="POLICY_NOT_FOUND",
                message=str(exc),
            ).model_dump(),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                code="INVALID_CONFIG",
                message=str(exc),
            ).model_dump(),
        )


@router.post(
    "/policies/{policy_id}/export",
    response_model=ExportResponse,
    summary="Export approved rules as JSON or XACML-style policy",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def export_policy(policy_id: str, request: ExportRequest) -> ExportResponse:
    """Export only the approved rules as a JSON or XACML-style policy document.

    Default decision is always 'deny' (fail safe).

    HTTP 404 if policy_id is not found.
    HTTP 409 if no rules have been approved yet.
    """
    if request.policy_id != policy_id:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                code="INVALID_CONFIG",
                message="policy_id in path and request body must match.",
            ).model_dump(),
        )
    try:
        return pipeline_service.export_policy(policy_id, request)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="POLICY_NOT_FOUND",
                message=f"No policy with id '{policy_id}'.",
            ).model_dump(),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                code="NO_APPROVED_RULES",
                message=str(exc),
            ).model_dump(),
        )
