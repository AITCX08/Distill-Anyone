"""Explicit response schemas for the versioned Dashboard API."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    api_version: str
    static_compatible: bool


class PreviewInput(BaseModel):
    target: str = Field(min_length=1, max_length=4096)
    platform: str = "auto"
    outputs: tuple[Literal["episodes", "skill"], ...] = ("episodes", "skill")
    rag_chunks: bool = False


class CreateJobInput(PreviewInput):
    preview_fingerprint: str = Field(min_length=1, max_length=256)


class RevisionInput(BaseModel):
    expected_revision: int = Field(ge=0)


class PreviewResponse(BaseModel):
    fingerprint: str
    platform: str
    creator_id: str
    creator_name: str
    total_items: int
    processable_items: int
    skipped_items: int
    unsupported_items: int
    auth_status: str


class JobResponse(BaseModel):
    job_id: str
    status: str
    revision: int
    platform: str
    creator_id: str
    creator_name: str
    outputs: tuple[str, ...]
    total_items: int
    completed_items: int
    failed_items: int
    unsupported_items: int
    updated_at: str


class ItemResponse(BaseModel):
    source_id: str
    processing_status: str
    stage_progress: float
    overall_progress: float
    last_error: str | None
    updated_at: str
