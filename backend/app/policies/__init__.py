"""
Policy Rule Package Initialization — Chargeback Shield Task 4.3
"""

from backend.app.policies.registry import PolicyRegistry, BasePolicyRule
from backend.app.policies.dispute_rules import (
    CriticalIdentityMatchingRule,
    MonetaryCurrencyVerificationRule,
    CrossDocumentConsistencyRule,
    DeliveryTimelinePlausibilityRule,
    EvidenceCompletenessRule,
    DocumentPresenceCeilingRule,
    PromptInjectionSafeguardRule,
)

__all__ = [
    "PolicyRegistry",
    "BasePolicyRule",
    "CriticalIdentityMatchingRule",
    "MonetaryCurrencyVerificationRule",
    "CrossDocumentConsistencyRule",
    "DeliveryTimelinePlausibilityRule",
    "EvidenceCompletenessRule",
    "DocumentPresenceCeilingRule",
    "PromptInjectionSafeguardRule",
]
