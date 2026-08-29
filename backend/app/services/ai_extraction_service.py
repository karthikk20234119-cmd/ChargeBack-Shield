"""
AI Evidence Extraction Service — Phase 4 Task 4.1

Executes visual / OCR evidence extraction on READY_FOR_AI processed page images.
Applies deterministic normalization utilities (amounts, dates, tracking IDs, confidence),
populates EvidenceFactItem provenance records, defends against prompt-injection in untrusted inputs,
and persists structured facts in ExtractedEvidence.

FINANCIAL & SAFETY INVARIANTS:
- NEVER modifies dispute financial fields (payment_id, amount, currency)
- NEVER makes policy or eligibility decisions (ELIGIBLE, HUMAN_REVIEW, NOT_ELIGIBLE)
- NEVER submits contests or mutates Razorpay
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.config import settings
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.processed_artifact import ProcessedArtifact
from backend.app.prompts.extraction_prompts import EXTRACTION_PROMPT_VERSION
from backend.app.schemas.extraction import EvidenceFactItem, ExtractedFactSchema
from backend.app.services.ai_provider import (
    AIProvider,
    MockAIProvider,
    OpenAIProvider,
    ProcessedPageInput,
)
from backend.app.utils.normalization import (
    normalize_amount,
    normalize_confidence,
    normalize_date,
    normalize_email,
    normalize_phone,
    normalize_tracking_id,
)

logger = logging.getLogger(__name__)


async def execute_ai_extraction(
    evidence_id: str,
    db: AsyncSession,
    provider: Optional[AIProvider] = None,
    document_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes evidence fact extraction on processed page images.

    Flow:
    1. Retrieve EvidenceDocument & ProcessedArtifacts
    2. Validate status in (READY_FOR_AI, AI_EXTRACTED, AI_EXTRACTION_FAILED)
    3. Transition status to AI_PROCESSING
    4. Execute Provider extraction
    5. Coerce & validate using ExtractedFactSchema
    6. Apply deterministic normalization & build EvidenceFactItem provenance list
    7. Atomically persist ExtractedEvidence and update status to AI_EXTRACTED
    """
    start_time = time.time()

    # 1. Retrieve Evidence Document
    stmt = select(EvidenceDocument).where(EvidenceDocument.id == evidence_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        logger.warning(f"AUDIT [EXTRACTION_FAILED]: evidence_id={evidence_id}, reason='Document not found'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence document with ID {evidence_id} not found",
        )

    # 2. State Validation
    valid_states = {"READY_FOR_AI", "AI_EXTRACTED", "AI_EXTRACTION_FAILED"}
    if doc.processing_status not in valid_states:
        reason = f"Document status is '{doc.processing_status}', expected READY_FOR_AI"
        logger.warning(f"AUDIT [EXTRACTION_FAILED]: evidence_id={evidence_id}, reason='{reason}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    # Fetch processed artifacts
    stmt_art = (
        select(ProcessedArtifact)
        .where(ProcessedArtifact.evidence_id == evidence_id)
        .order_by(ProcessedArtifact.page_number)
    )
    res_art = await db.execute(stmt_art)
    artifacts = res_art.scalars().all()

    if not artifacts:
        reason = "No processed page artifacts found for evidence document"
        logger.warning(f"AUDIT [EXTRACTION_FAILED]: evidence_id={evidence_id}, reason='{reason}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    # Prepare Input Page List
    page_inputs: List[ProcessedPageInput] = [
        ProcessedPageInput(
            page_number=art.page_number,
            image_path=art.file_path,
            width=art.width,
            height=art.height,
            format=art.format,
        )
        for art in artifacts
    ]

    # 3. Transition State to AI_PROCESSING
    doc.processing_status = "AI_PROCESSING"
    await db.commit()

    logger.info(
        f"AUDIT [EXTRACTION_STARTED]: evidence_id={evidence_id}, dispute_id={doc.dispute_id}, "
        f"page_count={len(page_inputs)}"
    )

    # 4. Select Provider
    if provider is None:
        if (
            settings.ENVIRONMENT in ("test", "testing")
            or not settings.OPENAI_API_KEY
            or "sample" in settings.OPENAI_API_KEY
        ):
            provider = MockAIProvider(mock_scenario=document_hint)
        else:
            provider = OpenAIProvider()

    # 5. Execute Provider Extraction
    try:
        raw_json = await provider.extract_evidence(page_inputs, document_hint=document_hint)
    except Exception as exc:
        logger.error(f"AUDIT [EXTRACTION_FAILED]: evidence_id={evidence_id}, reason='Provider error: {exc}'")
        doc.processing_status = "AI_EXTRACTION_FAILED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Provider extraction error: {str(exc)}",
        ) from exc

    # 6. Pydantic Schema Validation & Untrusted Input Coercion
    try:
        fact_schema = ExtractedFactSchema(**raw_json)
    except Exception as val_err:
        logger.error(f"AUDIT [EXTRACTION_FAILED]: evidence_id={evidence_id}, reason='Validation error: {val_err}'")
        doc.processing_status = "AI_EXTRACTION_FAILED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extracted payload failed schema validation: {str(val_err)}",
        ) from val_err

    # 7. Apply Deterministic Normalization & Build Fact Items
    facts: List[EvidenceFactItem] = []
    first_art_id = artifacts[0].id if artifacts else "art_unknown"

    # Payment / Transaction Facts
    if fact_schema.payment_id:
        facts.append(
            EvidenceFactItem(
                category="TRANSACTION",
                field_name="payment_id",
                field_value=fact_schema.payment_id,
                normalized_value=fact_schema.payment_id.strip(),
                confidence=normalize_confidence(fact_schema.confidence_by_field.get("payment_id", 0.9)),
                extraction_method="vision",
                source_page=1,
                extractor_version=provider.prompt_version,
            )
        )

    if fact_schema.amount_minor is not None:
        norm_amt = normalize_amount(fact_schema.amount_minor)
        facts.append(
            EvidenceFactItem(
                category="TRANSACTION",
                field_name="amount_minor",
                field_value=str(fact_schema.amount_minor),
                normalized_value=norm_amt,
                confidence=normalize_confidence(fact_schema.confidence_by_field.get("amount_minor", 0.9)),
                extraction_method="vision",
                source_page=1,
                extractor_version=provider.prompt_version,
            )
        )

    # Customer Facts
    if fact_schema.customer_name:
        facts.append(
            EvidenceFactItem(
                category="CUSTOMER",
                field_name="customer_name",
                field_value=fact_schema.customer_name,
                normalized_value=fact_schema.customer_name.strip(),
                confidence=normalize_confidence(fact_schema.confidence_by_field.get("customer_name", 0.85)),
                extraction_method="vision",
                source_page=1,
                extractor_version=provider.prompt_version,
            )
        )

    # Shipping Facts
    if fact_schema.awb_number:
        norm_awb = normalize_tracking_id(fact_schema.awb_number)
        facts.append(
            EvidenceFactItem(
                category="SHIPPING",
                field_name="awb_number",
                field_value=fact_schema.awb_number,
                normalized_value=norm_awb,
                confidence=normalize_confidence(fact_schema.confidence_by_field.get("awb_number", 0.9)),
                extraction_method="vision",
                source_page=1,
                extractor_version=provider.prompt_version,
            )
        )

    if fact_schema.delivery_date:
        norm_deliv_date = normalize_date(fact_schema.delivery_date)
        facts.append(
            EvidenceFactItem(
                category="SHIPPING",
                field_name="delivery_date",
                field_value=fact_schema.delivery_date,
                normalized_value=norm_deliv_date,
                confidence=normalize_confidence(fact_schema.confidence_by_field.get("delivery_date", 0.85)),
                extraction_method="vision",
                source_page=1,
                extractor_version=provider.prompt_version,
            )
        )

    # Attach facts list to fact_schema
    fact_schema.facts = facts

    # Calculate average confidence score
    conf_scores = list(fact_schema.confidence_by_field.values()) if fact_schema.confidence_by_field else []
    avg_confidence = sum(conf_scores) / len(conf_scores) if conf_scores else 0.85

    # 8. Retry Handling: Delete existing ExtractedEvidence record if present
    stmt_old = select(ExtractedEvidence).where(ExtractedEvidence.document_id == doc.id)
    res_old = await db.execute(stmt_old)
    old_ext = res_old.scalar_one_or_none()
    if old_ext:
        await db.delete(old_ext)
        await db.commit()

    # 9. Persist ExtractedEvidence Record
    extraction_record = ExtractedEvidence(
        document_id=doc.id,
        document_type=fact_schema.document_type,
        payment_id=fact_schema.payment_id,
        order_id=fact_schema.order_id,
        amount_minor=fact_schema.amount_minor,
        currency=fact_schema.currency,
        customer_name=fact_schema.customer_name,
        awb_number=fact_schema.awb_number,
        delivery_date=fact_schema.delivery_date,
        signature_present=fact_schema.signature_present,
        confidence_score=avg_confidence,
        confidence_by_field=fact_schema.confidence_by_field,
        bounding_boxes=fact_schema.bounding_boxes,
        extraction_warnings={"warnings": fact_schema.extraction_warnings},
        extracted_data=fact_schema.model_dump(),
        raw_response=raw_json,
        model_name=provider.model_name,
        prompt_version=provider.prompt_version,
        schema_version=fact_schema.schema_version,
    )

    db.add(extraction_record)
    doc.processing_status = "AI_EXTRACTED"
    await db.commit()

    elapsed_time = round(time.time() - start_time, 3)
    logger.info(
        f"AUDIT [EXTRACTION_COMPLETED]: evidence_id={evidence_id}, dispute_id={doc.dispute_id}, "
        f"provider={provider.model_name}, schema_version={fact_schema.schema_version}, "
        f"fact_count={len(facts)}, duration_sec={elapsed_time}"
    )

    return {
        "evidence_id": doc.id,
        "dispute_id": doc.dispute_id,
        "status": doc.processing_status,
        "document_type": extraction_record.document_type,
        "extraction_id": extraction_record.id,
        "extracted_data": fact_schema.model_dump(),
    }
