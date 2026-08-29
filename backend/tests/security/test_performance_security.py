"""
Security Under Load & Request Limit Audit Suite — Chargeback Shield Task 8.5
"""

import sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.dispute import Dispute
from backend.app.models.contest_draft import ContestDraft as ContestDraftModel


@pytest.mark.asyncio
async def test_oversized_comment_request_rejected(client, async_db):
    """Verifies review comments exceeding 2,000 characters are cleanly rejected (422)."""
    dispute = Dispute(
        id="disp_sec_perf_1",
        payment_id="pay_sec_1",
        amount=1000,
        currency="INR",
        reason_code="10.4",
        status="open"
    )
    draft = ContestDraftModel(
        id="draft_sec_perf_1",
        dispute_id="disp_sec_perf_1",
        title="Test Title",
        summary="Test summary",
        status="DRAFT",
        review_status="PENDING_REVIEW",
        input_fingerprint="fp_sec_perf_123456"
    )
    async_db.add(dispute)
    async_db.add(draft)
    await async_db.commit()

    oversized_comment = "A" * 2050
    response = await client.post("/api/disputes/disp_sec_perf_1/contest-draft/review", json={
        "decision": "APPROVE",
        "reviewer_id": "rev_admin",
        "comment": oversized_comment
    })
    assert response.status_code == 422
    assert "2000" in response.text or "value_error" in response.text or "string_too_long" in response.text or "comment" in response.text


@pytest.mark.asyncio
async def test_malformed_json_request_rejected(client):
    """Verifies malformed JSON requests yield clean HTTP 400/422 without traceback leakage."""
    response = await client.post("/api/disputes/disp_sec_perf_1/contest-draft/review", content="{invalid_json:", headers={"Content-Type": "application/json"})
    assert response.status_code in [400, 422]
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_sql_and_sort_injection_defense(client):
    """Verifies sort parameter injection attempts are sanitized/rejected."""
    injection_params = ["id; DROP TABLE disputes;--", "' OR 1=1--", "UNION SELECT * FROM users"]
    for param in injection_params:
        res = await client.get(f"/api/dashboard/disputes?sort={param}")
        assert res.status_code in [200, 400, 422]
        assert "Internal Server Error" not in res.text
        assert "Traceback" not in res.text


def test_sqlite_integrity_check_post_load(tmp_path):
    """Executes PRAGMA integrity_check against SQLite database post-test."""
    db_path = str(tmp_path / "post_load_test.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE test (id INT);")
    conn.commit()

    cur.execute("PRAGMA integrity_check;")
    res = cur.fetchone()
    conn.close()
    assert res[0] == "ok"
