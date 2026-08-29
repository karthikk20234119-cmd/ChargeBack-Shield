"""
Deterministic Policy Engine & Eligibility Evaluation — Chargeback Shield Task 4.3

Evaluates deterministic policy rules against trusted dispute data, MatchResult records,
and evidence extractions. Produces typed PolicyResult records with zero LLM/embedding calls.

SAFETY & FINANCIAL INVARIANTS:
- MUST NOT modify dispute payment_id, amount, or currency
- MUST NOT call an LLM or generate embeddings
- MUST NOT call Razorpay mutation APIs or create contests
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.policy import PolicyResult
from backend.app.policies.registry import PolicyRegistry, default_registry
from backend.app.schemas.matching import MatchStatus
from backend.app.schemas.policy import (
    EvidenceCoverage,
    PolicyDecision,
    PolicyOutcome,
    PolicyResultSchema,
    PolicyRuleResult,
    RuleSeverity,
    RuleStatus,
)
from backend.app.services.matching_service import run_dispute_matching

logger = logging.getLogger(__name__)

POLICY_VERSION = "cb13.1-v1.0"


def calculate_evidence_coverage(matches: List[MatchResult]) -> EvidenceCoverage:
    """Calculates deterministic evidence coverage metrics from MatchResults."""
    required_fact_names = {"payment_id", "amount_minor", "currency", "order_id", "awb_number"}
    eval_matches = [m for m in matches if m.fact_name in required_fact_names]

    satisfied_cnt = sum(1 for m in eval_matches if m.status == MatchStatus.MATCH.value)
    missing_cnt = sum(1 for m in eval_matches if m.status == MatchStatus.MISSING.value)
    ambiguous_cnt = sum(
        1 for m in eval_matches if m.status in (MatchStatus.AMBIGUOUS.value, MatchStatus.UNVERIFIABLE.value)
    )
    conflicting_cnt = sum(1 for m in eval_matches if m.status == MatchStatus.CROSS_DOCUMENT_CONFLICT.value)

    req_total = len(required_fact_names)
    cov_pct = round((satisfied_cnt / req_total) * 100.0, 2) if req_total > 0 else 0.0

    return EvidenceCoverage(
        required_fact_count=req_total,
        satisfied_fact_count=satisfied_cnt,
        missing_fact_count=missing_cnt,
        ambiguous_fact_count=ambiguous_cnt,
        conflicting_fact_count=conflicting_cnt,
        coverage_percentage=cov_pct,
    )


async def evaluate_dispute_policy(
    dispute_id: str,
    db: AsyncSession,
    reference_date: str = "2026-08-26",
    registry: Optional[PolicyRegistry] = None,
) -> PolicyResultSchema:
    """
    Executes deterministic policy evaluation for Visa Reason Code 13.1 (Product Not Delivered).
    Consumes ONLY deterministic MatchResult outputs and trusted dispute data.
    ZERO LLM calls. ZERO embeddings. ZERO external financial actions.
    """
    if registry is None:
        registry = default_registry

    db.expire_all()

    # 1. Fetch Dispute with MatchResults and Documents
    stmt = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.match_results),
            selectinload(Dispute.documents).selectinload(EvidenceDocument.extraction),
        )
        .where(Dispute.id == dispute_id)
    )

    res = await db.execute(stmt)
    dispute = res.scalar_one_or_none()

    if not dispute:
        raise ValueError(f"Dispute with ID '{dispute_id}' not found.")

    # Financial Safety Check: Capture trusted identity before evaluation
    payment_id_before = dispute.payment_id
    amount_before = dispute.amount
    currency_before = dispute.currency

    stmt_matches = select(MatchResult).where(MatchResult.dispute_id == dispute_id)
    res_m = await db.execute(stmt_matches)
    matches = res_m.scalars().all()

    # Run/refresh matching if no matching results exist
    if not matches:
        await run_dispute_matching(dispute_id, db, reference_date=reference_date)
        res = await db.execute(stmt)
        dispute = res.scalar_one_or_none()
        res_m = await db.execute(stmt_matches)
        matches = res_m.scalars().all()

    documents = list(dispute.documents) if dispute.documents else []

    # 2. Evaluate Registered Policy Rules in Deterministic Priority Order
    active_rules = registry.get_all_rules()
    rule_results: List[PolicyRuleResult] = []
    critical_findings: List[str] = []
    reason_codes: List[str] = []

    for rule in active_rules:
        rule_res = rule.evaluate(dispute, matches, documents, reference_date=reference_date)
        rule_results.append(rule_res)
        if rule_res.status == RuleStatus.FAIL or rule_res.status == RuleStatus.WARN:
            if rule_res.explanation:
                critical_findings.append(rule_res.explanation)
            reason_codes.append(rule.rule_id)

    # 3. Calculate Deterministic Evidence Coverage
    evidence_cov = calculate_evidence_coverage(matches)

    # 4. Three-Way Decision Precedence Evaluation
    has_critical_fail = any(
        (r.status == RuleStatus.FAIL or r.status == RuleStatus.FAIL.value or r.status == "FAIL")
        and (
            r.severity == RuleSeverity.CRITICAL
            or r.severity == RuleSeverity.CRITICAL.value
            or r.severity == "CRITICAL"
        )
        for r in rule_results
    )
    has_high_fail_or_warn = any(
        (
            r.status in (RuleStatus.FAIL, RuleStatus.FAIL.value, "FAIL")
            and r.severity in (RuleSeverity.HIGH, RuleSeverity.HIGH.value, "HIGH")
        )
        or (r.status in (RuleStatus.WARN, RuleStatus.WARN.value, "WARN"))
        for r in rule_results
    )
    has_valid_extraction = any(
        getattr(d, "processing_status", None) == "AI_EXTRACTED" and getattr(d, "extraction", None)
        for d in documents
    )

    if has_critical_fail:
        decision = PolicyDecision.NOT_ELIGIBLE
        requires_human_review = False
        summary = (
            "Dispute evidence is NOT ELIGIBLE for representment due to critical field contradictions or invalid timeline."
        )
    elif has_high_fail_or_warn or not has_valid_extraction:
        decision = PolicyDecision.HUMAN_REVIEW
        requires_human_review = True
        summary = (
            "Dispute evidence requires HUMAN REVIEW due to incomplete evidence, cross-document conflicts, or unverifiable fields."
        )
    else:
        decision = PolicyDecision.ELIGIBLE
        requires_human_review = False
        summary = (
            "Dispute evidence is DETERMINISTICALLY ELIGIBLE for representment. All critical identity and financial fields match cleanly."
        )

    # 5. Financial Immutability Verification Assertion
    await db.refresh(dispute)
    assert dispute.payment_id == payment_id_before, "Financial safety invariant violated: payment_id mutated"
    assert dispute.amount == amount_before, "Financial safety invariant violated: amount mutated"
    assert dispute.currency == currency_before, "Financial safety invariant violated: currency mutated"

    eval_timestamp = datetime.utcnow()

    # 6. Delete Old Policy Results & Persist New PolicyResult Record
    del_stmt = select(PolicyResult).where(PolicyResult.dispute_id == dispute_id)
    old_res = await db.execute(del_stmt)
    for old_r in old_res.scalars().all():
        await db.delete(old_r)
    await db.commit()

    rule_dicts = [r.model_dump() for r in rule_results]

    policy_db_record = PolicyResult(
        dispute_id=dispute_id,
        policy_version=POLICY_VERSION,
        outcome=decision.value,
        decision=decision.value,
        requires_human_review=requires_human_review,
        summary=summary,
        explanation=summary,
        critical_findings={"findings": critical_findings},
        reason_codes={"codes": reason_codes},
        rule_results={"rules": rule_dicts},
        evidence_coverage=evidence_cov.model_dump(),
        financial_safety_verified=True,
        evaluated_at=eval_timestamp,
    )
    db.add(policy_db_record)
    await db.commit()
    await db.refresh(policy_db_record)

    logger.info(
        f"AUDIT [Policy Engine Complete]: dispute_id={dispute_id}, policy_version={POLICY_VERSION}, "
        f"decision={decision.value}, requires_human_review={requires_human_review}, findings_count={len(critical_findings)}"
    )

    return PolicyResultSchema(
        id=policy_db_record.id,
        dispute_id=dispute_id,
        decision=decision,
        outcome=decision,
        policy_version=POLICY_VERSION,
        evaluated_at=eval_timestamp,
        requires_human_review=requires_human_review,
        summary=summary,
        explanation=summary,
        critical_findings=critical_findings,
        reason_codes=reason_codes,
        rule_results=rule_results,
        evidence_coverage=evidence_cov,
        financial_safety_verified=True,
    )
