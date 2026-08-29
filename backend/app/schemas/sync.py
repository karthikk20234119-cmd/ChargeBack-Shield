"""
Synchronization Result Schemas — Task 3.2

Typed Pydantic schemas for dispute synchronization results.
Used by the sync service and API endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SyncConflict(BaseModel):
    """
    A single field-level synchronization conflict.

    Records both the local and Razorpay values for auditing.
    """

    field: str = Field(..., description="Name of the conflicting field")
    local_value: Any = Field(..., description="Current local database value")
    razorpay_value: Any = Field(..., description="Value from Razorpay API")
    reason: str = Field(..., description="Human-readable conflict explanation")


class DisputeSyncResult(BaseModel):
    """
    Result of a dispute synchronization attempt.

    Documents exactly what happened: what changed, what didn't,
    and what conflicted.
    """

    dispute_id: str = Field(..., description="Razorpay dispute ID")
    action: Literal["CREATED", "UPDATED", "UNCHANGED", "CONFLICT", "NOT_FOUND"] = Field(
        ..., description="Synchronization action taken"
    )
    changed_fields: list[str] = Field(
        default_factory=list,
        description="Fields that were updated during synchronization",
    )
    unchanged_fields: list[str] = Field(
        default_factory=list,
        description="Fields that matched and required no update",
    )
    conflicts: list[SyncConflict] = Field(
        default_factory=list,
        description="Financial identity fields that differ (not auto-updated)",
    )
    synchronized_at: datetime = Field(
        ..., description="Timestamp of the synchronization attempt"
    )
