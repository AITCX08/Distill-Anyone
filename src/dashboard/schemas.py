"""Explicit response schemas for the versioned Dashboard API."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    api_version: str
    static_compatible: bool
