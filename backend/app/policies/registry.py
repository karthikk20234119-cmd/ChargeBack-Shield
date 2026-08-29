"""
Policy Rule Registry — Chargeback Shield Task 4.3

Makes all active, versioned policy rules discoverable in deterministic priority order.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from backend.app.models.dispute import Dispute
from backend.app.models.matching import MatchResult
from backend.app.schemas.policy import (
    PolicyDecision,
    PolicyRuleResult,
    RuleSeverity,
    RuleStatus,
)


class BasePolicyRule(ABC):
    """Abstract base class for all deterministic policy rules."""

    rule_id: str
    rule_version: str = "1.0"
    rule_name: str
    description: str
    priority: int  # Priority rank (1 = highest priority, evaluated first)
    required_facts: List[str] = []

    @abstractmethod
    def evaluate(
        self,
        dispute: Dispute,
        matches: List[MatchResult],
        documents: List[Any],
        reference_date: str = "2026-08-26",
    ) -> PolicyRuleResult:
        """Evaluates rule against trusted dispute data, match results, and documents."""
        pass


class PolicyRegistry:
    """Registry container for discoverable, versioned policy rules."""

    def __init__(self) -> None:
        self._rules: Dict[str, BasePolicyRule] = {}

    def register(self, rule: BasePolicyRule) -> None:
        """Registers a policy rule by its unique rule_id."""
        self._rules[rule.rule_id] = rule

    def get_all_rules(self) -> List[BasePolicyRule]:
        """Returns all registered rules sorted deterministically by priority."""
        return sorted(self._rules.values(), key=lambda r: (r.priority, r.rule_id))

    def get_rule(self, rule_id: str) -> Optional[BasePolicyRule]:
        """Retrieves a rule by rule_id."""
        return self._rules.get(rule_id)


# Global default registry instance
default_registry = PolicyRegistry()
