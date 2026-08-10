"""Safe, read-only text artifacts addressed by server-generated identifiers."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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
    display_title: str
    kind: str
    size_bytes: int
    created_at: str


class ArtifactSummary(BaseModel):
    artifact_id: str
    source_id: str
    name: str
    display_name: str
    display_title: str
    kind: str
    size_bytes: int
    created_at: str


class ArtifactContent(ArtifactSummary):
    content: str


def _artifacts(request: Request, job_id: str) -> dict[str, _Artifact]:
    state = request.app.state.service.queries.get(job_id)
    root = request.app.state.service.repository.root.resolve()
    roots = [root]
    raw_destination = state.request.get("output_directory")
    if isinstance(raw_destination, str) and raw_destination.strip():
        destination = Path(raw_destination).expanduser().resolve(strict=False)
        if destination != destination.parent:
            roots.append(destination)
    values: dict[str, _Artifact] = {}

    def add_artifact(
        *,
        source_id: str,
        name: str,
        candidate: str | Path,
        display_title: str,
        kind: str,
    ) -> None:
        path = Path(candidate).resolve()
        if (
            path.suffix.lower() not in _TEXT_SUFFIXES
            or not path.is_file()
            or not any(path.is_relative_to(allowed_root) for allowed_root in roots)
        ):
            return
        opaque = hashlib.sha256(f"{job_id}\0{source_id}\0{name}".encode()).hexdigest()[:24]
        values[opaque] = _Artifact(
            opaque,
            source_id,
            name,
            path,
            display_title,
            kind,
            path.stat().st_size,
            datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        )

    for source_id, item in state.items.items():
        catalog_entry = state.catalog.get(source_id)
        title = catalog_entry.get("title") if isinstance(catalog_entry, dict) else None
        display_title = str(title).strip() if isinstance(title, str) and title.strip() else source_id
        for name, record in item.artifacts.items():
            add_artifact(
                source_id=source_id,
                name=name,
                candidate=record.path,
                display_title=display_title,
                kind=str(record.content_type or name),
            )
        for name, receipt in item.outputs.items():
            if not isinstance(receipt, dict) or receipt.get("status") != "completed":
                continue
            path = receipt.get("path")
            if isinstance(path, str):
                add_artifact(
                    source_id=source_id,
                    name=str(name),
                    candidate=path,
                    display_title=display_title,
                    kind=str(name),
                )

    for name, receipt in state.outputs.items():
        if not isinstance(receipt, dict):
            continue
        path = receipt.get("path")
        if isinstance(path, str):
            add_artifact(
                source_id="job-output",
                name=str(name),
                candidate=path,
                display_title=str(state.creator.get("display_name") or "任务汇总产物"),
                kind=str(name),
            )
    return values


def _summary(value: _Artifact) -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=value.artifact_id,
        source_id=value.source_id,
        name=value.name,
        display_name=value.path.name,
        display_title=value.display_title,
        kind=value.kind,
        size_bytes=value.size_bytes,
        created_at=value.created_at,
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
