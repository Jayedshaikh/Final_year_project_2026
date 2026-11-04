"""Training and rule extraction endpoints.

POST /api/v1/training/run
GET  /api/v1/training/{run_id}/comparison
GET  /api/v1/training/{run_id}/rules
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.services import pipeline_service
from shared.schemas.contracts import (
    ErrorResponse,
    ExtractedRulesResponse,
    ModelComparisonResponse,
    TrainingConfigRequest,
    TrainingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["training"])


@router.post(
    "/training/run",
    response_model=TrainingResponse,
    summary="Train ML models on an RBAC dataset",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def run_training(config: TrainingConfigRequest) -> TrainingResponse:
    """Train Decision Tree, Random Forest and Gradient Boosting on the dataset.

    Builds samples, encodes features, runs stratified k-fold CV, evaluates on the
    held-out test split, and extracts candidate ABAC rules from the Decision Tree.

    HTTP 404 if dataset_id is not found.
    HTTP 400 if the configuration is semantically invalid.
    """
    try:
        return pipeline_service.run_training(config)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="DATASET_NOT_FOUND",
                message=f"No dataset with id '{config.dataset_id}'.",
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


@router.get(
    "/training/{run_id}/comparison",
    response_model=ModelComparisonResponse,
    summary="Get model comparison for a training run",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_model_comparison(run_id: str) -> ModelComparisonResponse:
    """Return precision, recall, F1 and interpretability flag for all trained models.

    HTTP 404 if run_id is not found.
    """
    try:
        return pipeline_service.get_model_comparison(run_id)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="RUN_NOT_FOUND",
                message=f"No training run with id '{run_id}'.",
            ).model_dump(),
        )


@router.get(
    "/training/{run_id}/rules",
    response_model=ExtractedRulesResponse,
    summary="Get extracted ABAC rules for a training run",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_rules(run_id: str) -> ExtractedRulesResponse:
    """Return the candidate ABAC rules extracted from the Decision Tree.

    HTTP 404 if run_id is not found.
    """
    try:
        return pipeline_service.get_extracted_rules(run_id)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="RUN_NOT_FOUND",
                message=f"No training run with id '{run_id}'.",
            ).model_dump(),
        )
