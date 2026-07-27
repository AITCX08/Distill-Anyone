"""Safe, read-only text artifacts addressed by server-generated identifiers."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from src.dashboard.security import require_mutation_security

router = APIRouter(prefix="/api/v1/jobs/{job_id}/artifacts", tags=["artifacts"])
_TEXT_SUFFIXES = {".md", ".txt", ".json"}
_MAX_TEXT_BYTES = 1_000_000


@dataclass(frozen=True)
class _Artifact:
    artifact_id: str
    source_id: str
    name: str
    path: Path


class ArtifactSummary(BaseModel):
    artifact_id: str
    source_id: str
    name: str
    display_name: str


class ArtifactContent(ArtifactSummary):
    content: str


def _artifacts(request: Request, job_id: str) -> dict[str, _Artifact]:
    state = request.app.state.service.queries.get(job_id)
    root = request.app.state.service.repository.root.resolve()
    values: dict[str, _Artifact] = {}
    for source_id, item in state.items.items():
        for name, record in item.artifacts.items():
            path = Path(record.path).resolve()
            if (
                path.suffix.lower() not in _TEXT_SUFFIXES
                or not path.is_file()
                or not path.is_relative_to(root)
            ):
                continue
            opaque = hashlib.sha256(f"{job_id}\0{source_id}\0{name}".encode()).hexdigest()[:24]
            values[opaque] = _Artifact(opaque, source_id, name, path)
    return values


def _summary(value: _Artifact) -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=value.artifact_id,
        source_id=value.source_id,
        name=value.name,
        display_name=value.path.name,
    )


def _allowlisted_artifact(request: Request, job_id: str, artifact_id: str) -> _Artifact:
    if artifact_id in {".", ".."} or "/" in artifact_id or "\\" in artifact_id:
        raise HTTPException(status_code=403, detail="artifact path rejected")
    artifact = _artifacts(request, job_id).get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=403, detail="artifact is not allowlisted")
    return artifact


def reveal_directory(directory: Path) -> None:
    """Ask the local desktop to show a previously allowlisted output folder."""

    if sys.platform == "win32":
        os.startfile(str(directory))
        return
    command = ["open", str(directory)] if sys.platform == "darwin" else ["xdg-open", str(directory)]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@router.get("", response_model=tuple[ArtifactSummary, ...])
def list_artifacts(job_id: str, request: Request):
    return tuple(_summary(value) for value in _artifacts(request, job_id).values())


@router.get("/{artifact_id}", response_model=ArtifactContent)
def read_artifact(job_id: str, artifact_id: str, request: Request):
    artifact = _allowlisted_artifact(request, job_id, artifact_id)
    if artifact.path.stat().st_size > _MAX_TEXT_BYTES:
        raise HTTPException(status_code=413, detail="artifact is too large to preview")
    try:
        content = artifact.path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=415, detail="artifact is not UTF-8 text") from error
    return ArtifactContent(**_summary(artifact).model_dump(), content=content)


@router.post("/{artifact_id}/reveal", status_code=204, dependencies=[Depends(require_mutation_security)])
def reveal_artifact(job_id: str, artifact_id: str, request: Request) -> Response:
    artifact = _allowlisted_artifact(request, job_id, artifact_id)
    root = request.app.state.service.repository.root.resolve()
    directory = artifact.path.parent.resolve()
    if not directory.is_relative_to(root):
        raise HTTPException(status_code=403, detail="artifact path rejected")
    try:
        request.app.state.reveal_directory(directory)
    except OSError as error:
        raise HTTPException(status_code=409, detail="artifact reveal unavailable") from error
    return Response(status_code=204)
