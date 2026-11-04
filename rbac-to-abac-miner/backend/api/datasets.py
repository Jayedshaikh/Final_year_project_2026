"""Dataset upload and authorisation endpoints.

POST /api/v1/datasets/upload
GET  /api/v1/datasets/{dataset_id}/authorisation
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from backend.services import pipeline_service
from shared.schemas.contracts import (
    DatasetUploadRequest,
    DatasetValidationResponse,
    ErrorResponse,
    RBACAuthorisationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["datasets"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".csv", ".json"}


async def _read_upload(upload: UploadFile) -> bytes:
    """Read and size-check an uploaded file.

    Args:
        upload: FastAPI UploadFile.

    Returns:
        Raw bytes content.

    Raises:
        HTTPException 400: If the file exceeds the size limit.
    """
    content = await upload.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                code="FILE_TOO_LARGE",
                message=f"File '{upload.filename}' exceeds 10 MB limit.",
            ).model_dump(),
        )
    return content


@router.post(
    "/datasets/upload",
    response_model=DatasetValidationResponse,
    summary="Upload and validate an RBAC dataset",
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def upload_dataset(
    dataset_name: str = Form(..., min_length=1, max_length=100),
    file_format: str = Form("csv"),
    users: UploadFile = File(...),
    roles: UploadFile = File(...),
    permissions: UploadFile = File(...),
    user_roles: UploadFile = File(...),
    role_permissions: UploadFile = File(...),
    resources: UploadFile = File(...),
    user_attribute_columns: Optional[str] = Form(None),
    resource_attribute_columns: Optional[str] = Form(None),
) -> DatasetValidationResponse:
    """Upload six RBAC files (CSV or JSON) and validate the dataset.

    Returns a DatasetValidationResponse with status, dataset_id, summary and issues.
    HTTP 400 with status 'invalid' if structural errors are found.
    """
    if file_format not in ("csv", "json"):
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                code="INVALID_CONFIG",
                message=f"Unsupported file_format '{file_format}'. Use 'csv' or 'json'.",
            ).model_dump(),
        )

    files_bytes = {
        "users": await _read_upload(users),
        "roles": await _read_upload(roles),
        "permissions": await _read_upload(permissions),
        "user_roles": await _read_upload(user_roles),
        "role_permissions": await _read_upload(role_permissions),
        "resources": await _read_upload(resources),
    }

    user_attr_cols = (
        [c.strip() for c in user_attribute_columns.split(",") if c.strip()]
        if user_attribute_columns else None
    )
    resource_attr_cols = (
        [c.strip() for c in resource_attribute_columns.split(",") if c.strip()]
        if resource_attribute_columns else None
    )

    request = DatasetUploadRequest(
        dataset_name=dataset_name,
        file_format=file_format,
        user_attribute_columns=user_attr_cols,
        resource_attribute_columns=resource_attr_cols,
    )

    result = pipeline_service.upload_dataset(request, files_bytes)

    if result.status == "invalid":
        return JSONResponse(status_code=400, content=result.model_dump())
    return result


@router.get(
    "/datasets/{dataset_id}/authorisation",
    response_model=RBACAuthorisationResponse,
    summary="Get RBAC authorisation matrix summary",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_authorisation(dataset_id: str) -> RBACAuthorisationResponse:
    """Return the authorisation summary and up to 50 sample tuples.

    HTTP 404 if the dataset_id is unknown.
    """
    try:
        return pipeline_service.get_authorisation_response(dataset_id)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="DATASET_NOT_FOUND",
                message=f"No dataset with id '{dataset_id}'.",
            ).model_dump(),
        )
