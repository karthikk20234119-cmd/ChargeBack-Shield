"""
Deterministic Evidence Matching Schemas — Phase 4 Task 4.2

Defines Pydantic schemas for MatchStatus, MatchResult, and MatchingRunResult.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    CROSS_DOCUMENT_CONFLICT = "CROSS_DOCUMENT_CONFLICT"
    UNVERIFIABLE = "UNVERIFIABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MatchResultSchema(BaseModel):
    id: Optional[str] = Field(default=None, description="Match result primary key UUID")
    dispute_id: str = Field(..., description="Target dispute ID")
    evidence_id: Optional[str] = Field(default=None, description="Source evidence document ID")
    processed_artifact_id: Optional[str] = Field(default=None, description="Source processed page artifact ID")
    fact_name: str = Field(..., description="Evaluated fact field name e.g. amount_minor, payment_id")
    expected_value: Optional[str] = Field(default=None, description="Raw expected trusted value")
    observed_value: Optional[str] = Field(default=None, description="Raw observed extracted value")
    normalized_expected_value: Optional[str] = Field(
        default=None, description="Normalized expected value snapshot"
    )
    normalized_observed_value: Optional[str] = Field(
        default=None, description="Normalized observed value snapshot"
    )
    status: MatchStatus = Field(..., description="Comparison match status")
    confidence: str = Field(default="MEDIUM", description="Confidence level: HIGH, MEDIUM, LOW")
    source_page: int = Field(default=1, ge=1, description="1-indexed source page number")
    source_region: Optional[Dict[str, Any]] = Field(
        default=None, description="Visual bounding box / region"
    )
    extraction_method: str = Field(default="ocr", description="Extraction technique: vision, ocr, text")
    matcher_version: str = Field(default="1.0", description="Matching algorithm version")
    explanation: str = Field(..., description="Deterministic human-readable comparison explanation")
    created_at: Optional[str] = Field(default=None, description="Timestamp ISO string")

    # Backwards compatibility properties
    @property
    def field(self) -> str:
        return self.fact_name

    @property
    def extracted_value(self) -> Optional[str]:
        return self.observed_value

    @property
    def reason(self) -> str:
        return self.explanation


class FieldMatchDetail(BaseModel):
    """Backwards compatible detail model for Phase 2 evaluation harness."""

    field: str
    expected_value: Optional[Any] = None
    extracted_value: Optional[Any] = None
    normalized_expected: Optional[str] = None
    normalized_extracted: Optional[str] = None
    status: MatchStatus
    is_critical: bool = False
    reason: str
    source_doc_type: str = "general"
    evidence_id: Optional[str] = None


class MatchingRunResult(BaseModel):
    dispute_id: str
    status: str  # DETERMINISTIC_MATCH, CRITICAL_MISMATCH, INCOMPLETE_EVIDENCE, CONFLICT_DETECTED
    total_facts: int
    match_count: int
    mismatches_count: int
    missing_count: int
    ambiguous_count: int
    results: List[MatchResultSchema]


class DisputeMatchSummary(BaseModel):
    """Backwards compatible summary model for Phase 2 evaluation harness."""

    dispute_id: str
    overall_status: str
    has_critical_mismatch: bool
    total_fields_evaluated: int
    matches_count: int
    mismatches_count: int
    missing_count: int
    unverifiable_count: int
    conflicts_count: int
    field_results: List[FieldMatchDetail]
