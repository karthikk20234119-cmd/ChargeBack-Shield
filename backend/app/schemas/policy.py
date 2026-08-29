from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class PolicyDecision(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    HUMAN_REVIEW = "HUMAN_REVIEW"


# Alias for backward compatibility across evaluation harness and tests
PolicyOutcome = PolicyDecision


class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


class RuleSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class PolicyRuleResult(BaseModel):
    rule_id: str
    rule_name: str = ""
    rule_version: str = "1.0"
    decision: PolicyDecision = PolicyDecision.HUMAN_REVIEW
    status: RuleStatus
    severity: RuleSeverity = RuleSeverity.INFO
    explanation: str = ""
    reason: str = ""
    required_facts: List[str] = Field(default_factory=list)
    matched_facts: List[str] = Field(default_factory=list)
    conflicting_facts: List[str] = Field(default_factory=list)
    source_match_result_ids: List[str] = Field(default_factory=list)
    evidence_reference: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "explanation" not in data and "reason" in data:
                data["explanation"] = data["reason"]
            elif "reason" not in data and "explanation" in data:
                data["reason"] = data["explanation"]

            if "decision" not in data:
                status = data.get("status")
                severity = data.get("severity")
                if status == RuleStatus.FAIL or status == "FAIL":
                    if severity == RuleSeverity.CRITICAL or severity == "CRITICAL":
                        data["decision"] = PolicyDecision.NOT_ELIGIBLE
                    else:
                        data["decision"] = PolicyDecision.HUMAN_REVIEW
                elif status == RuleStatus.WARN or status == "WARN":
                    data["decision"] = PolicyDecision.HUMAN_REVIEW
                elif status == RuleStatus.PASS or status == "PASS":
                    data["decision"] = PolicyDecision.ELIGIBLE
                else:
                    data["decision"] = PolicyDecision.HUMAN_REVIEW
        return data


# Backward compatibility alias
RuleEvaluationResult = PolicyRuleResult


class EvidenceCoverage(BaseModel):
    required_fact_count: int = 0
    satisfied_fact_count: int = 0
    missing_fact_count: int = 0
    ambiguous_fact_count: int = 0
    conflicting_fact_count: int = 0
    coverage_percentage: float = 0.0


class PolicyResultSchema(BaseModel):
    id: Optional[str] = None
    dispute_id: str
    decision: PolicyDecision
    outcome: PolicyDecision
    policy_version: str = "cb13.1-v1.0"
    evaluated_at: Optional[datetime] = None
    requires_human_review: bool
    summary: str
    explanation: str
    critical_findings: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    rule_results: List[PolicyRuleResult] = Field(default_factory=list)
    evidence_coverage: Optional[EvidenceCoverage] = None
    financial_safety_verified: bool = True

    @model_validator(mode="before")
    @classmethod
    def sync_outcome_and_decision(cls, data: Any) -> Any:
        if isinstance(data, dict):
            dec = data.get("decision") or data.get("outcome")
            if dec:
                data["decision"] = dec
                data["outcome"] = dec

            exp = data.get("explanation") or data.get("summary")
            if exp:
                data["explanation"] = exp
                data["summary"] = exp
        return data


# Backward compatibility aliases for evaluation harness & API contracts
PolicyEvaluationSummary = PolicyResultSchema
PolicyEvaluationResponse = PolicyResultSchema
