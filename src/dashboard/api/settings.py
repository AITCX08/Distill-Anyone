"""Private local settings endpoints for the Dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.dashboard.schemas import (
    DirectorySelectionResponse,
    DirectoryValidationResponse,
    OutputDirectoryInput,
    OutputDirectoryResponse,
)
from src.dashboard.security import require_local_session, require_mutation_security

router = APIRouter(tags=["settings"])


def _directory_error(error: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail="保存位置不可用")


@router.get("/api/v1/settings/output-directory", response_model=OutputDirectoryResponse)
def get_output_directory(
    request: Request,
    _: object = Depends(require_local_session),
) -> OutputDirectoryResponse:
    return OutputDirectoryResponse(directory=str(request.app.state.output_directories.get_default()))


@router.put(
    "/api/v1/settings/output-directory",
    response_model=OutputDirectoryResponse,
    dependencies=[Depends(require_mutation_security)],
)
def set_output_directory(payload: OutputDirectoryInput, request: Request) -> OutputDirectoryResponse:
    try:
        directory = request.app.state.output_directories.set_default(payload.directory)
    except ValueError as error:
        raise _directory_error(error) from error
    return OutputDirectoryResponse(directory=str(directory))


@router.post(
    "/api/v1/directories/validate",
    response_model=DirectoryValidationResponse,
    dependencies=[Depends(require_mutation_security)],
)
def validate_output_directory(
    payload: OutputDirectoryInput,
    request: Request,
) -> DirectoryValidationResponse:
    try:
        result = request.app.state.output_directories.validate(payload.directory)
    except ValueError as error:
        raise _directory_error(error) from error
    return DirectoryValidationResponse(**result.__dict__)


@router.post(
    "/api/v1/directories/choose",
    response_model=DirectorySelectionResponse,
    dependencies=[Depends(require_mutation_security)],
)
def choose_directory(request: Request) -> DirectorySelectionResponse:
    try:
        selection = request.app.state.output_directories.choose(request.app.state.choose_output_directory)
    except ValueError as error:
        raise _directory_error(error) from error
    return DirectorySelectionResponse(**selection.__dict__)
