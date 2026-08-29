"""
Shared Contest Draft Input Fingerprinting Helper — Chargeback Shield Task 5.2

Provides canonical JSON serialization and SHA-256 fingerprinting for ContestDrafts.
Reused deterministically by Task 5.1 draft generation and Task 5.2 review validation.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional


def compute_contest_draft_input_fingerprint(
    dispute_id: str,
    payment_id: str,
    amount: int,
    currency: str,
    policy_result_id: Optional[str],
    policy_version: Optional[str],
    policy_outcome: Optional[Any],
    match_results: List[Any],
    documents: List[Any],
    generator_version: str = "contest-draft-v1.0.0",
    draft_version: str = "1.0",
) -> str:
    """
    Computes a canonical SHA-256 input fingerprint across trusted dispute data,
    policy result, match results, and document hashes. Zero non-deterministic timestamps.
    """
    formatted_matches = []
    for m in match_results:
        m_id = getattr(m, "id", None) if not isinstance(m, dict) else m.get("id")
        if m_id is None:
            m_id = str(m)

        m_fact = getattr(m, "fact_name", None) if not isinstance(m, dict) else m.get("fact_name")
        raw_status = getattr(m, "status", None) if not isinstance(m, dict) else m.get("status")
        m_status = getattr(raw_status, "value", str(raw_status or ""))

        m_exp = getattr(m, "expected_value", None) if not isinstance(m, dict) else m.get("expected_value")
        m_obs = getattr(m, "observed_value", None) if not isinstance(m, dict) else m.get("observed_value")

        formatted_matches.append({
            "id": str(m_id),
            "fact": str(m_fact or ""),
            "status": str(m_status),
            "expected": str(m_exp) if m_exp is not None else None,
            "observed": str(m_obs) if m_obs is not None else None,
        })

    # Sort matches numerically by int id if possible, otherwise string sort
    def match_sort_key(item: dict) -> tuple:
        iid = item["id"]
        return (0, int(iid)) if iid.isdigit() else (1, iid)

    formatted_matches.sort(key=match_sort_key)

    formatted_docs = []
    for d in documents:
        d_id = getattr(d, "id", None) if not isinstance(d, dict) else d.get("id")
        if d_id is None:
            d_id = str(d)
        d_hash = getattr(d, "file_hash", None) if not isinstance(d, dict) else d.get("file_hash")

        formatted_docs.append({
            "id": str(d_id),
            "hash": str(d_hash or ""),
        })

    formatted_docs.sort(key=lambda x: str(x["id"]))

    outcome_str = getattr(policy_outcome, "value", str(policy_outcome or ""))

    canonical_payload: Dict[str, Any] = {
        "dispute_id": str(dispute_id),
        "payment_id": str(payment_id),
        "amount": int(amount),
        "currency": str(currency),
        "policy_result_id": str(policy_result_id) if policy_result_id else None,
        "policy_version": str(policy_version) if policy_version else None,
        "policy_outcome": outcome_str if policy_outcome else None,
        "match_results": formatted_matches,
        "documents": formatted_docs,
        "generator_version": str(generator_version),
        "draft_version": str(draft_version),
    }

    canonical_json = json.dumps(canonical_payload, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
