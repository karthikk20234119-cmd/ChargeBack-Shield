"""
Deterministic Dispute Policy Rules — Chargeback Shield Task 4.3

Implements versioned, deterministic rules for Visa Reason Code 13.1 (Product Not Delivered).
"""

from datetime import datetime
from typing import Any, List, Optional
from backend.app.models.dispute import Dispute
from backend.app.models.matching import MatchResult
from backend.app.policies.registry import BasePolicyRule, default_registry
from backend.app.schemas.matching import MatchStatus
from backend.app.schemas.policy import (
    PolicyDecision,
    PolicyRuleResult,
    RuleSeverity,
    RuleStatus,
)


def parse_iso_date(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d")
    except Exception:
        return None


class CriticalIdentityMatchingRule(BasePolicyRule):
    rule_id = "CB13.1-001"
    rule_version = "1.0"
    rule_name = "Critical Identity Matching"
    description = "Verifies Payment ID, Order ID, and AWB match trusted transaction records."
    priority = 10
    required_facts = ["payment_id", "order_id", "awb_number"]

    def evaluate(
        self,
        dispute: Dispute,
        matches: List[MatchResult],
        documents: List[Any],
        reference_date: str = "2026-08-26",
    ) -> PolicyRuleResult:
        pay_matches = [m for m in matches if m.fact_name in ("payment_id", "field")]
        ord_matches = [m for m in matches if m.fact_name == "order_id"]
        awb_matches = [m for m in matches if m.fact_name == "awb_number"]

        pay_mismatch = any(m.status == MatchStatus.MISMATCH.value for m in pay_matches)
        ord_mismatch = any(m.status == MatchStatus.MISMATCH.value for m in ord_matches)
        awb_mismatch = any(m.status == MatchStatus.MISMATCH.value for m in awb_matches)

        match_ids = [m.id for m in pay_matches + ord_matches + awb_matches]
        matched_facts = [m.fact_name for m in matches if m.status == MatchStatus.MATCH.value]

        if pay_mismatch or ord_mismatch or awb_mismatch:
            reasons = []
            conflicting = []
            if pay_mismatch:
                reasons.append("Payment ID does not match transaction record.")
                conflicting.append("payment_id")
            if ord_mismatch:
                reasons.append("Order ID does not match trusted order record.")
                conflicting.append("order_id")
            if awb_mismatch:
                reasons.append("Airway Bill (AWB) number does not match logistics record.")
                conflicting.append("awb_number")

            explanation = "Critical identity mismatch detected: " + " ".join(reasons)
            return PolicyRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                rule_version=self.rule_version,
                decision=PolicyDecision.NOT_ELIGIBLE,
                status=RuleStatus.FAIL,
                severity=RuleSeverity.CRITICAL,
                explanation=explanation,
                reason=explanation,
                required_facts=self.required_facts,
                matched_facts=matched_facts,
                conflicting_facts=conflicting,
                source_match_result_ids=match_ids,
            )

        explanation = "Payment ID and Order ID match trusted transaction records cleanly."
        return PolicyRuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_version=self.rule_version,
            decision=PolicyDecision.ELIGIBLE,
            status=RuleStatus.PASS,
            severity=RuleSeverity.INFO,
            explanation=explanation,
            reason=explanation,
            required_facts=self.required_facts,
            matched_facts=matched_facts,
            conflicting_facts=[],
            source_match_result_ids=match_ids,
        )


class MonetaryCurrencyVerificationRule(BasePolicyRule):
    rule_id = "CB13.1-002"
    rule_version = "1.0"
    rule_name = "Monetary & Currency Verification"
    description = "Verifies invoice amount in minor units and currency code against dispute record."
    priority = 20
    required_facts = ["amount_minor", "currency"]

    def evaluate(
        self,
        dispute: Dispute,
        matches: List[MatchResult],
        documents: List[Any],
        reference_date: str = "2026-08-26",
    ) -> PolicyRuleResult:
        amt_matches = [m for m in matches if m.fact_name == "amount_minor"]
        curr_matches = [m for m in matches if m.fact_name == "currency"]

        amt_mismatch = any(m.status == MatchStatus.MISMATCH.value for m in amt_matches)
        curr_mismatch = any(m.status == MatchStatus.MISMATCH.value for m in curr_matches)

        match_ids = [m.id for m in amt_matches + curr_matches]
        matched_facts = [m.fact_name for m in amt_matches + curr_matches if m.status == MatchStatus.MATCH.value]

        if amt_mismatch or curr_mismatch:
            reasons = []
            conflicting = []
            if amt_mismatch:
                reasons.append("Invoice amount in minor units does not match disputed charge.")
                conflicting.append("amount_minor")
            if curr_mismatch:
                reasons.append("Currency code mismatch against trusted dispute currency.")
                conflicting.append("currency")

            explanation = "Monetary contradiction detected: " + " ".join(reasons)
            return PolicyRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                rule_version=self.rule_version,
                decision=PolicyDecision.NOT_ELIGIBLE,
                status=RuleStatus.FAIL,
                severity=RuleSeverity.CRITICAL,
                explanation=explanation,
                reason=explanation,
                required_facts=self.required_facts,
                matched_facts=matched_facts,
                conflicting_facts=conflicting,
                source_match_result_ids=match_ids,
            )

        explanation = "Invoice amount and currency match trusted dispute values."
        return PolicyRuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_version=self.rule_version,
            decision=PolicyDecision.ELIGIBLE,
            status=RuleStatus.PASS,
            severity=RuleSeverity.INFO,
            explanation=explanation,
            reason=explanation,
            required_facts=self.required_facts,
            matched_facts=matched_facts,
            conflicting_facts=[],
            source_match_result_ids=match_ids,
        )


class CrossDocumentConsistencyRule(BasePolicyRule):
    rule_id = "CB13.1-003"
    rule_version = "1.0"
    rule_name = "Cross-Document Consistency"
    description = "Checks that all evidence documents contain consistent identifiers without conflicts."
    priority = 30
    required_facts = ["order_id", "awb_number"]

    def evaluate(
        self,
        dispute: Dispute,
        matches: List[MatchResult],
        documents: List[Any],
        reference_date: str = "2026-08-26",
    ) -> PolicyRuleResult:
        conflicts = [m for m in matches if m.status == MatchStatus.CROSS_DOCUMENT_CONFLICT.value]
        match_ids = [m.id for m in conflicts]

        if conflicts:
            reasons = "; ".join(c.explanation or c.reason or "Cross-document conflict" for c in conflicts)
            explanation = f"Cross-document conflict detected: {reasons}"
            return PolicyRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                rule_version=self.rule_version,
                decision=PolicyDecision.HUMAN_REVIEW,
                status=RuleStatus.FAIL,
                severity=RuleSeverity.HIGH,
                explanation=explanation,
                reason=explanation,
                required_facts=self.required_facts,
                matched_facts=[],
                conflicting_facts=[c.fact_name for c in conflicts],
                source_match_result_ids=match_ids,
            )

        explanation = "All evidence documents are internally consistent with zero cross-document conflicts."
        return PolicyRuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_version=self.rule_version,
            decision=PolicyDecision.ELIGIBLE,
            status=RuleStatus.PASS,
            severity=RuleSeverity.INFO,
            explanation=explanation,
            reason=explanation,
            required_facts=self.required_facts,
            matched_facts=self.required_facts,
            conflicting_facts=[],
            source_match_result_ids=[],
        )


class DeliveryTimelinePlausibilityRule(BasePolicyRule):
    rule_id = "CB13.1-004"
    rule_version = "1.0"
    rule_name = "Delivery Timeline & Temporal Plausibility"
    description = "Ensures delivery date is valid, not in the future, and plausible relative to shipment."
    priority = 40
    required_facts = ["delivery_date"]

    def evaluate(
        self,
        dispute: Dispute,
        matches: List[MatchResult],
        documents: List[Any],
        reference_date: str = "2026-08-26",
    ) -> PolicyRuleResult:
        date_matches = [m for m in matches if m.fact_name == "delivery_date"]
        date_mismatch = any(m.status == MatchStatus.MISMATCH.value for m in date_matches)
        match_ids = [m.id for m in date_matches]

        if date_mismatch:
            reasons = "; ".join(m.explanation or m.reason or "Timeline mismatch" for m in date_matches if m.status == MatchStatus.MISMATCH.value)
            explanation = f"Invalid delivery timeline: {reasons}"
            return PolicyRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                rule_version=self.rule_version,
                decision=PolicyDecision.NOT_ELIGIBLE,
                status=RuleStatus.FAIL,
                severity=RuleSeverity.CRITICAL,
                explanation=explanation,
                reason=explanation,
                required_facts=self.required_facts,
                matched_facts=[],
                conflicting_facts=["delivery_date"],
                source_match_result_ids=match_ids,
            )

        explanation = "Delivery date is valid and temporally plausible relative to shipment date."
        return PolicyRuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_version=self.rule_version,
            decision=PolicyDecision.ELIGIBLE,
            status=RuleStatus.PASS,
            severity=RuleSeverity.INFO,
            explanation=explanation,
            reason=explanation,
            required_facts=self.required_facts,
            matched_facts=["delivery_date"],
            conflicting_facts=[],
            source_match_result_ids=match_ids,
        )


class EvidenceCompletenessRule(BasePolicyRule):
    rule_id = "CB13.1-005"
    rule_version = "1.0"
    rule_name = "Evidence Completeness & Unverifiable Fields"
    description = "Checks that all required fields are present and OCR confidence meets threshold."
    priority = 50
    required_facts = ["payment_id", "amount_minor", "currency", "order_id", "awb_number"]

    def evaluate(
        self,
        dispute: Dispute,
        matches: List[MatchResult],
        documents: List[Any],
        reference_date: str = "2026-08-26",
    ) -> PolicyRuleResult:
        missing_critical = [m for m in matches if m.status == MatchStatus.MISSING.value and getattr(m, "is_critical", True)]
        unverifiable = [m for m in matches if m.status == MatchStatus.UNVERIFIABLE.value]
        match_ids = [m.id for m in missing_critical + unverifiable]

        if missing_critical or unverifiable:
            reasons = []
            if missing_critical:
                reasons.append(f"Missing critical fields: {', '.join(m.fact_name for m in missing_critical)}")
            if unverifiable:
                reasons.append(f"Unverifiable fields: {', '.join(m.fact_name for m in unverifiable)}")

            explanation = "; ".join(reasons)
            return PolicyRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                rule_version=self.rule_version,
                decision=PolicyDecision.HUMAN_REVIEW,
                status=RuleStatus.WARN,
                severity=RuleSeverity.MEDIUM,
                explanation=explanation,
                reason=explanation,
                required_facts=self.required_facts,
                matched_facts=[m.fact_name for m in matches if m.status == MatchStatus.MATCH.value],
                conflicting_facts=[],
                source_match_result_ids=match_ids,
            )

        explanation = "All required evidence fields are present and verified."
        return PolicyRuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_version=self.rule_version,
            decision=PolicyDecision.ELIGIBLE,
            status=RuleStatus.PASS,
            severity=RuleSeverity.INFO,
            explanation=explanation,
            reason=explanation,
            required_facts=self.required_facts,
            matched_facts=self.required_facts,
            conflicting_facts=[],
            source_match_result_ids=[],
        )


class DocumentPresenceCeilingRule(BasePolicyRule):
    rule_id = "CB13.1-006"
    rule_version = "1.0"
    rule_name = "Evidence Document Presence Ceiling"
    description = "Ensures AI-extracted evidence documents exist for the dispute."
    priority = 60
    required_facts = ["documents"]

    def evaluate(
        self,
        dispute: Dispute,
        matches: List[MatchResult],
        documents: List[Any],
        reference_date: str = "2026-08-26",
    ) -> PolicyRuleResult:
        has_valid_extraction = any(
            getattr(d, "processing_status", None) == "AI_EXTRACTED" and getattr(d, "extraction", None)
            for d in documents
        )

        if not has_valid_extraction:
            explanation = "No AI-extracted evidence documents exist for this dispute."
            return PolicyRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                rule_version=self.rule_version,
                decision=PolicyDecision.HUMAN_REVIEW,
                status=RuleStatus.FAIL,
                severity=RuleSeverity.HIGH,
                explanation=explanation,
                reason=explanation,
                required_facts=self.required_facts,
                matched_facts=[],
                conflicting_facts=[],
                source_match_result_ids=[],
            )

        explanation = "AI-extracted evidence documents exist and are available for policy evaluation."
        return PolicyRuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_version=self.rule_version,
            decision=PolicyDecision.ELIGIBLE,
            status=RuleStatus.PASS,
            severity=RuleSeverity.INFO,
            explanation=explanation,
            reason=explanation,
            required_facts=self.required_facts,
            matched_facts=["documents"],
            conflicting_facts=[],
            source_match_result_ids=[],
        )


class PromptInjectionSafeguardRule(BasePolicyRule):
    rule_id = "CB13.1-007"
    rule_version = "1.0"
    rule_name = "Prompt Injection & Adversarial Defense Safeguard"
    description = "Detects adversarial text or prompt injection attempts in raw document payload."
    priority = 70
    required_facts = ["raw_payload"]

    def evaluate(
        self,
        dispute: Dispute,
        matches: List[MatchResult],
        documents: List[Any],
        reference_date: str = "2026-08-26",
    ) -> PolicyRuleResult:
        has_injection_warning = False
        for doc in documents:
            ext = getattr(doc, "extraction", None)
            if ext and getattr(ext, "extraction_warnings", None):
                warnings = ext.extraction_warnings.get("warnings", [])
                for w in warnings:
                    w_str = str(w).lower()
                    if any(k in w_str for k in ("injection", "override", "adversarial", "ignore instructions")):
                        has_injection_warning = True
                        break

        if has_injection_warning:
            explanation = "Adversarial text or prompt injection attempt detected in raw document payload."
            return PolicyRuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                rule_version=self.rule_version,
                decision=PolicyDecision.HUMAN_REVIEW,
                status=RuleStatus.WARN,
                severity=RuleSeverity.MEDIUM,
                explanation=explanation,
                reason=explanation,
                required_facts=self.required_facts,
                matched_facts=[],
                conflicting_facts=["raw_payload"],
                source_match_result_ids=[],
            )

        explanation = "No prompt injection attempts detected in evidence document content."
        return PolicyRuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_version=self.rule_version,
            decision=PolicyDecision.ELIGIBLE,
            status=RuleStatus.PASS,
            severity=RuleSeverity.INFO,
            explanation=explanation,
            reason=explanation,
            required_facts=self.required_facts,
            matched_facts=["raw_payload"],
            conflicting_facts=[],
            source_match_result_ids=[],
        )


# Register all rules into the default registry
default_registry.register(CriticalIdentityMatchingRule())
default_registry.register(MonetaryCurrencyVerificationRule())
default_registry.register(CrossDocumentConsistencyRule())
default_registry.register(DeliveryTimelinePlausibilityRule())
default_registry.register(EvidenceCompletenessRule())
default_registry.register(DocumentPresenceCeilingRule())
default_registry.register(PromptInjectionSafeguardRule())
