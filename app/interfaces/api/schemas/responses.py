"""Response schemas for API."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Error response schema."""

    status: str = Field(default="error", description="Response status")
    error: ErrorDetail = Field(..., description="Error information")


class SuccessResponse(BaseModel):
    """Success response schema."""

    status: str = Field(default="success", description="Response status")
    data: dict[str, Any] | None = Field(None, description="Response data")
    message: str | None = Field(None, description="Success message")
